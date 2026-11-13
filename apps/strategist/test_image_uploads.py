"""Exercise image selection through uploads, with only the external SDK mocked."""
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from apps.strategist.image_analysis_test import ImageReviewError, analyze_uploads
from apps.strategist import pin_images
from apps.strategist.models import PinImage
from apps.strategist.test_approvals import ApprovalBase
from apps.strategist.test_image_analysis import trouser_check, valid_review


def upload(color="red", size=(900, 1200), name="photo.png"):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return SimpleUploadedFile(name, out.getvalue(), content_type="image/png")


class ImageUploadTests(ApprovalBase):
    def setUp(self):
        super().setUp()
        sdk = patch("apps.strategist.providers.GigaChat")
        self.sdk = sdk.start()
        self.addCleanup(sdk.stop)
        self.remote = self.sdk.return_value.__enter__.return_value
        self.remote.upload_file.return_value = SimpleNamespace(id_="file-1")
        self.remote.chat.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(valid_review())))],
        )
        def respond(chat):
            if "lowest_visible" in chat.messages[0].content:
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(trouser_check())))])
            if "Проверь только КАДРИРОВАНИЕ" in chat.messages[0].content:
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                    "description": "Весь товар виден.", "framing": "WHOLE", "presentation": "PRODUCT", "frames_count": 1,
                })))])
            return self.remote.chat.return_value
        self.remote.chat.side_effect = respond

    def analyze(self, files):
        return analyze_uploads(files, product_name="Брюки", business=self.business)

    def test_connection_failure_stops_remaining_images_without_retry(self):
        self.remote.chat.side_effect = TimeoutError("secret provider detail")
        rows = self.analyze([upload(), upload("blue")])
        self.assertEqual([row["status"] for row in rows], ["error", "error"])
        self.assertEqual(self.remote.chat.call_count, 1)
        self.assertEqual(self.remote.upload_file.call_count, 1)
        self.remote.delete_file.assert_called_once_with("file-1")
        self.assertNotIn("secret provider detail", str(rows))

    def test_duplicates_and_small_images_are_skipped_and_order_is_preserved(self):
        rows = self.analyze([upload(), upload(name="duplicate.png"), upload("blue", (400, 600))])
        self.assertEqual([r["number"] for r in rows], [1, 2, 3])
        self.assertEqual([r["status"] for r in rows], ["recommended", "not_recommended", "not_recommended"])
        self.assertEqual(self.remote.chat.call_count, 2)
        self.remote.delete_file.assert_called_once_with("file-1")

    def test_used_image_is_skipped_only_for_its_business(self):
        pin = self.make_pins(1)[0]
        PinImage.objects.create(pin_version=pin.current_version, **pin_images.process_upload(upload()))
        rows = self.analyze([upload()])
        self.assertEqual(rows[0]["status"], "not_recommended")
        self.sdk.assert_not_called()
        from apps.businesses.models import Business
        other = Business.objects.create(workspace=self.workspace, name="Other", slug="other")
        rows = analyze_uploads([upload()], product_name="Брюки", business=other)
        self.assertEqual(rows[0]["status"], "recommended")
        self.assertEqual(self.remote.chat.call_count, 2)

    def test_invalid_upload_and_batch_limit_do_not_call_provider(self):
        for files in ([SimpleUploadedFile("broken.jpg", b"garbage")], [upload()] * 16):
            with self.subTest(count=len(files)), self.assertRaises(ImageReviewError):
                self.analyze(files)
        self.sdk.assert_not_called()

    def test_size_limit_is_checked_before_any_paid_call(self):
        with patch("apps.strategist.image_analysis_test.MAX_TOTAL_BYTES", 1), self.assertRaises(ImageReviewError):
            self.analyze([upload()])
        self.sdk.assert_not_called()

    def test_invalid_response_is_not_approved_or_retried_and_file_is_deleted(self):
        self.remote.chat.return_value.choices[0].message.content = "not-json"
        rows = self.analyze([upload()])
        self.assertEqual(rows[0]["status"], "error")
        self.assertEqual(self.remote.chat.call_count, 1)
        self.remote.delete_file.assert_called_once_with("file-1")

    def test_provider_initialization_failure_returns_safe_error_for_every_image(self):
        self.sdk.side_effect = RuntimeError("credentials must not be exposed")
        rows = self.analyze([upload(), upload("blue")])
        self.assertEqual([r["status"] for r in rows], ["error", "error"])
        self.assertNotIn("credentials", str(rows))

    def test_cleanup_failure_is_visible_and_does_not_repeat_analysis(self):
        self.remote.delete_file.side_effect = RuntimeError("private response")
        rows = self.analyze([upload()])
        self.assertTrue(rows[0]["file_cleanup_failed"])
        self.assertEqual(self.remote.chat.call_count, 2)
        self.assertNotIn("private response", str(rows))

    def test_review_page_denies_other_users_and_viewers_before_paid_call(self):
        url = reverse("strategist:image-analysis-test", kwargs={"workspace_slug": "a", "business_slug": "shop"})
        for user in (self.viewer, self.stranger):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.post(url, {"product_name": "Брюки", "images": upload()})
                self.assertEqual(response.status_code, 404)
        self.sdk.assert_not_called()

    def test_disabled_vision_does_not_make_paid_calls(self):
        self.client.force_login(self.owner)
        url = reverse("strategist:image-analysis-test", kwargs={"workspace_slug": "a", "business_slug": "shop"})
        with tempfile.TemporaryDirectory() as directory, override_settings(
            STRATEGIST_PRODUCT_VISION_ENABLED=False, MEDIA_ROOT=Path(directory),
        ):
            response = self.client.post(url, {"product_name": "Брюки", "images": upload()})
        self.assertContains(response, "Визуальный анализ отключён")
        self.sdk.assert_not_called()
