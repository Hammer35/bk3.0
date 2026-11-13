"""Pin pictures: validation and re-encoding, rights, locked versions, serving headers."""
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.strategist import pin_images
from apps.strategist.models import Approval, PinImage
from apps.strategist.test_approvals import ApprovalBase


def picture(size=(400, 600), fmt="PNG", mode="RGB", name="pin.png", **save):
    out = io.BytesIO()
    Image.new(mode, size, "red").save(out, format=fmt, **save)
    return SimpleUploadedFile(name, out.getvalue(), content_type="application/octet-stream")


class ProcessUploadTest(ApprovalBase):
    def test_png_without_alpha_becomes_jpeg_with_measured_size(self):
        values = pin_images.process_upload(picture())
        self.assertEqual((values["content_type"], values["width"], values["height"]), ("image/jpeg", 400, 600))
        self.assertEqual(values["size"], len(values["data"]))
        self.assertEqual(Image.open(io.BytesIO(values["data"])).format, "JPEG")

    def test_alpha_is_kept_as_png(self):
        values = pin_images.process_upload(picture(mode="RGBA"))
        self.assertEqual(values["content_type"], "image/png")

    def test_exif_is_stripped(self):
        exif = Image.Exif()
        exif[0x010E] = "secret description"
        values = pin_images.process_upload(picture(fmt="JPEG", exif=exif, name="pin.jpg"))
        self.assertNotIn(b"secret description", values["data"])

    def test_rejects_garbage_disguised_as_image(self):
        for upload in (SimpleUploadedFile("pin.png", b"<script>alert(1)</script>"), SimpleUploadedFile("pin.jpg", b""),
                       SimpleUploadedFile("pin.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50)):
            with self.subTest(upload=upload.name), self.assertRaises(pin_images.ImageError):
                pin_images.process_upload(upload)

    def test_rejects_other_formats_and_tiny_pictures(self):
        with self.assertRaises(pin_images.ImageError):
            pin_images.process_upload(picture(fmt="GIF", name="pin.gif"))
        with self.assertRaises(pin_images.ImageError):
            pin_images.process_upload(picture(size=(100, 100)))

    def test_rejects_oversized_file(self):
        big = SimpleUploadedFile("pin.png", b"0" * (pin_images.MAX_BYTES + 1))
        with self.assertRaises(pin_images.ImageError):
            pin_images.process_upload(big)

    def test_ratio_note_only_for_odd_ratios(self):
        self.assertEqual(pin_images.ratio_note(1000, 1500), "")
        self.assertTrue(pin_images.ratio_note(1000, 1000))


class PinImageViewsTest(ApprovalBase):
    def setUp(self):
        super().setUp()
        self.pin = self.make_pins(1)[0]
        kwargs = {"workspace_slug": "a", "business_slug": "shop", "pin_id": self.pin.pk}
        self.upload_url = reverse("strategist:pin-image-upload", kwargs=kwargs)
        self.delete_url = reverse("strategist:pin-image-delete", kwargs=kwargs)
        self.image_url = reverse("strategist:pin-image", kwargs={**kwargs, "number": self.pin.current_version.number})

    def upload(self, file=None):
        return self.client.post(self.upload_url, {"image": file or picture()}, follow=True)

    def test_owner_uploads_and_page_shows_the_picture(self):
        self.client.force_login(self.owner)
        response = self.upload()
        image = PinImage.objects.get(pin_version=self.pin.current_version)
        self.assertEqual((image.width, image.height, image.uploaded_by), (400, 600, self.owner))
        self.assertContains(response, self.image_url)
        self.assertContains(response, "400×600")

    def test_second_upload_replaces_the_first(self):
        self.client.force_login(self.owner)
        self.upload()
        self.upload(picture(size=(500, 750)))
        self.assertEqual(PinImage.objects.filter(pin_version=self.pin.current_version).count(), 1)
        self.assertEqual(PinImage.objects.get().width, 500)

    def test_bad_file_gives_message_and_stores_nothing(self):
        self.client.force_login(self.owner)
        response = self.upload(SimpleUploadedFile("pin.png", b"not a picture"))
        self.assertEqual(PinImage.objects.count(), 0)
        self.assertContains(response, "Не удалось прочитать изображение")
        self.assertNotContains(response, "Traceback")

    def test_missing_file_is_refused(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.upload_url, {}, follow=True)
        self.assertContains(response, "Выберите файл")

    def test_viewer_and_stranger_cannot_change_but_viewer_can_see(self):
        self.client.force_login(self.owner)
        self.upload()
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(self.upload_url, {"image": picture()}).status_code, 404)
        self.assertEqual(self.client.post(self.delete_url).status_code, 404)
        self.assertEqual(self.client.get(self.image_url).status_code, 200)
        self.assertNotContains(self.client.get(self.page), "Сохранить изображение")
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.image_url).status_code, 404)
        self.assertEqual(self.client.post(self.upload_url, {"image": picture()}).status_code, 404)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.image_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_upload_is_post_only(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.upload_url).status_code, 404)

    def test_picture_is_served_with_safe_headers(self):
        self.client.force_login(self.owner)
        self.upload()
        response = self.client.get(self.image_url)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("sandbox", response["Content-Security-Policy"])
        self.assertEqual(Image.open(io.BytesIO(response.content)).size, (400, 600))

    def test_delete_removes_the_picture(self):
        self.client.force_login(self.owner)
        self.upload()
        self.client.post(self.delete_url)
        self.assertEqual(PinImage.objects.count(), 0)

    def test_decided_version_picture_is_locked(self):
        self.client.force_login(self.owner)
        self.upload()
        self.post(self.pin, action="reject")
        self.assertTrue(Approval.objects.exists())
        response = self.upload(picture(size=(500, 750)))
        self.assertContains(response, "менять нельзя")
        self.assertEqual(PinImage.objects.get().width, 400)
        self.client.post(self.delete_url)
        self.assertEqual(PinImage.objects.count(), 1)
        self.assertNotContains(self.client.get(self.page), "Сохранить изображение")

    def test_other_business_cannot_read_the_picture_by_guessing_ids(self):
        self.client.force_login(self.owner)
        self.upload()
        other = type(self.business).objects.create(workspace=self.workspace, name="Other", slug="other", niche="x", audience="y", goals="z")
        url = reverse("strategist:pin-image", kwargs={"workspace_slug": "a", "business_slug": other.slug, "pin_id": self.pin.pk,
                                                       "number": self.pin.current_version.number})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_english_page(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.page, headers={"accept-language": "en"})
        self.assertContains(response, "Upload image")
        self.assertContains(response, "No image yet")
