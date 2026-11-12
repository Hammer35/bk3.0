"""Offline tests for the saved-image evaluation runner."""

import csv
import hashlib
import io
import json
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace

from django.conf import settings
from django.test import SimpleTestCase
from PIL import Image

from apps.strategist.test_image_analysis import trouser_check


class ImageEvaluationRunnerTests(SimpleTestCase):
    def setUp(self):
        self.runner = runpy.run_path(str(settings.BASE_DIR / "scripts/evaluate_image_analysis.py"))
        self.review = {
            "description": "Товар показан полностью.",
            "product_match": "MATCH",
            "content_type": "PRODUCT",
            "visibility": "MAIN",
            "technical_quality": "GOOD",
            "composition": "STRONG",
            "category_fit": "STRONG",
            "flags": [],
        }

    def case(self, path, *, case_id="1221114868:01", expected="recommended"):
        article, image = case_id.split(":")
        prompt = self.runner["_image_prompt"]("Рубашка", "clothing")
        return {
            "case_id": case_id,
            "article": article,
            "image_number": int(image),
            "filename": f"{image}.webp",
            "path": path,
            "sha256": "a" * 64,
            "expected": expected,
            "rating_status": "editorial_unconfirmed",
            "owner_confirmed": False,
            "rating_reason": "",
            "product_name": "Рубашка",
            "category": "clothing",
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        }

    def write_dataset(self, root, *, actual_data=b"image", declared_hash=None):
        directory = root / "media/image-analysis-test/1221114868"
        directory.mkdir(parents=True)
        (directory / "01.webp").write_bytes(actual_data)
        dataset = root / "cases.csv"
        row = {
            "article": "1221114868",
            "image_number": "1",
            "filename": "01.webp",
            "sha256": declared_hash or hashlib.sha256(actual_data).hexdigest(),
            "group": "cosmetics",
            "image_rating": "recommended",
            "rating_status": "editorial_unconfirmed",
            "owner_confirmed": "false",
            "rating_reason": "",
        }
        with dataset.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        return dataset, root / "media"

    def test_dataset_loading_verifies_hash_and_builds_current_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset, media = self.write_dataset(Path(directory))
            cases = self.runner["load_cases"](dataset, media_root=media)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["case_id"], "1221114868:01")
        self.assertFalse(cases[0]["owner_confirmed"])
        self.assertEqual(len(cases[0]["prompt_sha256"]), 64)
        self.assertIn("Оцени изображение", cases[0]["prompt"])

    def test_dataset_loading_rejects_changed_or_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset, media = self.write_dataset(Path(directory), declared_hash="0" * 64)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                self.runner["load_cases"](dataset, media_root=media)
        with tempfile.TemporaryDirectory() as directory:
            dataset, media = self.write_dataset(Path(directory))
            (media / "image-analysis-test/1221114868/01.webp").unlink()
            with self.assertRaisesRegex(ValueError, "missing"):
                self.runner["load_cases"](dataset, media_root=media)

    def test_selection_is_deterministic_and_validated(self):
        cases = [{"case_id": value} for value in ("1:01", "1:02", "2:01")]
        self.assertEqual(
            [case["case_id"] for case in self.runner["select_cases"](cases, limit=2)],
            ["1:01", "1:02"],
        )
        self.assertEqual(
            [case["case_id"] for case in self.runner["select_cases"](cases, case_ids=["2:01"])],
            ["2:01"],
        )
        for kwargs in ({"limit": 0}, {"limit": True}, {"case_ids": []}, {"case_ids": ["unknown"]}, {"case_ids": ["1:01", "1:01"]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.runner["select_cases"](cases, **kwargs)

    def test_dry_run_writes_report_without_constructing_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            report = self.runner["evaluate"](
                [self.case(Path(directory) / "unused.webp")],
                output_path=output,
                provider_factory=lambda: self.fail("Dry-run must not construct GigaChatProvider"),
            )
            saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(report["summary"]["selected"], 1)
        self.assertEqual(report["summary"]["evaluated"], 0)
        self.assertIsNone(report["summary"]["agreement"]["ratio"])
        self.assertEqual(saved["rows"], [])

    def fake_client(self, raw, *, usage=None):
        review = self.review if raw is None else raw
        content = review if isinstance(review, str) else json.dumps(review, ensure_ascii=False)

        class FakeClient:
            def __init__(self):
                self.uploads = []
                self.chats = []
                self.deleted = []
                self.completion = SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                    usage=usage if usage is not None else SimpleNamespace(prompt_tokens=8, completion_tokens=4, total_tokens=12),
                    model="GigaChat-2-Pro",
                )

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def upload_file(self, file, purpose):
                self.uploads.append((file, purpose))
                return SimpleNamespace(id_="file-1")

            def chat(self, chat):
                self.chats.append(chat)
                if "lowest_visible" in chat.messages[0].content:
                    return SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(trouser_check())))],
                        usage=self.completion.usage, model=self.completion.model,
                    )
                if "Проверь только КАДРИРОВАНИЕ" in chat.messages[0].content:
                    return SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                            "description": "Весь товар в кадре.", "framing": "WHOLE", "presentation": "PRODUCT", "frames_count": 1,
                        })))], usage=self.completion.usage, model=self.completion.model,
                    )
                if "Проверь ТОЛЬКО расположение" in chat.messages[0].content:
                    return SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                            "description": "Текст на отдельном фоне.",
                            "lists_background": "PHOTO" if review.get("comparison_layout") == "TEXT_OVER_SUBJECT" or "text_heavy" in review.get("flags", []) else "SOLID_PANEL",
                            "comparison_size": "SMALL" if review.get("comparison_layout") == "SMALL_PANELS" else "LARGE",
                        })))], usage=self.completion.usage, model=self.completion.model,
                    )
                return self.completion

            def delete_file(self, file_id):
                self.deleted.append(file_id)

        return FakeClient()

    def image_path(self, directory):
        path = Path(directory) / "01.webp"
        data = io.BytesIO()
        Image.new("RGB", (900, 1200), "white").save(data, "PNG")
        path.write_bytes(data.getvalue())
        return path

    def test_live_trousers_use_evidence_in_shared_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.fake_client(None)
            case = self.case(self.image_path(directory))
            case["product_name"] = "Джинсы клеш"
            case["prompt"] = self.runner["_image_prompt"](case["product_name"], case["category"])
            case["prompt_sha256"] = hashlib.sha256(case["prompt"].encode()).hexdigest()
            report = self.runner["evaluate"](
                [case], live=True, output_path=Path(directory) / "evidence.json",
                provider_factory=lambda: SimpleNamespace(_client=lambda: client),
            )
        self.assertEqual(report["rows"][0]["actual"], "recommended")
        self.assertEqual(report["rows"][0]["review"]["verification"], trouser_check())
        self.assertEqual(len(client.chats), 2)
        self.assertEqual(client.deleted, ["file-1"])

    def test_live_uses_current_pipeline_and_saves_result_usage_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.fake_client(None)
            output = Path(directory) / "live.json"
            report = self.runner["evaluate"](
                [self.case(self.image_path(directory))],
                live=True,
                output_path=output,
                provider_factory=lambda: SimpleNamespace(_client=lambda: client),
            )
            saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(len(client.chats), 2)
        self.assertEqual(client.chats[0].model, "GigaChat-2-Pro")
        self.assertEqual(client.deleted, ["file-1"])
        self.assertEqual(report["rows"][0]["actual"], "recommended")
        self.assertEqual(report["rows"][0]["score"], 100)
        self.assertEqual(report["summary"]["agreement"], {"matches": 1, "evaluated": 1, "ratio": 1.0})
        self.assertEqual(report["summary"]["usage"]["total_tokens"], 24)
        self.assertTrue(report["summary"]["usage_complete"])
        self.assertEqual(saved["rows"][0]["raw_response"], report["rows"][0]["raw_response"])
        self.assertEqual(saved["rows"][0]["review"]["description"], "Товар показан полностью.")

    def test_invalid_model_answer_is_an_error_without_retry_and_file_is_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.fake_client("not-json")
            report = self.runner["evaluate"](
                [self.case(self.image_path(directory))],
                live=True,
                output_path=Path(directory) / "live.json",
                provider_factory=lambda: SimpleNamespace(_client=lambda: client),
            )
        self.assertEqual(len(client.chats), 1)
        self.assertEqual(client.deleted, ["file-1"])
        self.assertFalse(report["batch_aborted"])
        self.assertIsNone(report["rows"][0]["actual"])
        self.assertEqual(report["rows"][0]["error"]["type"], "ImageReviewError")
        self.assertEqual(report["summary"]["confusion_matrix"]["recommended"]["error"], 1)

    def test_detail_without_whole_product_is_rejected_despite_high_scores(self):
        self.review.update(content_type="DETAIL", description="Крупный план ткани и шва, целого товара нет.")
        with tempfile.TemporaryDirectory() as directory:
            client = self.fake_client(None)
            report = self.runner["evaluate"](
                [self.case(self.image_path(directory), expected="not_recommended")],
                live=True, output_path=Path(directory) / "detail.json",
                provider_factory=lambda: SimpleNamespace(_client=lambda: client),
            )
        self.assertEqual(report["rows"][0]["actual"], "not_recommended")
        self.assertEqual(report["summary"]["agreement"]["matches"], 1)

    def test_provider_failure_stops_batch_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.image_path(directory)
            client = self.fake_client(None)
            client.__class__.chat = lambda self, chat: (_ for _ in ()).throw(RuntimeError("private details must not be reported"))
            report = self.runner["evaluate"](
                [self.case(path), self.case(path, case_id="1221114868:02")],
                live=True,
                output_path=Path(directory) / "live.json",
                provider_factory=lambda: SimpleNamespace(_client=lambda: client),
            )
        self.assertEqual(len(client.uploads), 1)
        self.assertEqual(client.deleted, ["file-1"])
        self.assertTrue(report["batch_aborted"])
        self.assertEqual(report["summary"]["completed"], 1)
        self.assertNotIn("private details", json.dumps(report, ensure_ascii=False))

    def test_owner_rules_override_optimistic_model_scores(self):
        cases = (
            ({"content_type": "SIZE_CHART"}, "not_recommended"),
            ({"content_type": "COLLAGE"}, "not_recommended"),
            ({"flags": ["collage"]}, "not_recommended"),
            ({"content_type": "BEFORE_AFTER", "comparison_layout": "CLEAR"}, "acceptable"),
            ({"content_type": "BEFORE_AFTER", "comparison_layout": "CLEAR", "flags": ["text_heavy"]}, "not_recommended"),
            ({"content_type": "PRODUCT"}, "recommended"),
            ({"flags": ["off_body"]}, "acceptable"),
        )
        original = self.review.copy()
        for overrides, expected in cases:
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as directory:
                self.review = {**original, **overrides}
                client = self.fake_client(None)
                report = self.runner["evaluate"](
                    [self.case(self.image_path(directory), expected=expected)],
                    live=True, output_path=Path(directory) / "rules.json",
                    provider_factory=lambda: SimpleNamespace(_client=lambda: client),
                )
                self.assertEqual(report["rows"][0]["actual"], expected)

    def test_before_after_layout_controls_suitability(self):
        for layout, expected in (("CLEAR", "acceptable"), ("TEXT_OVER_SUBJECT", "not_recommended"), ("SMALL_PANELS", "not_recommended")):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as directory:
                self.review.update(content_type="BEFORE_AFTER", comparison_layout=layout, flags=["collage"])
                client = self.fake_client(None)
                report = self.runner["evaluate"](
                    [self.case(self.image_path(directory), expected=expected)], live=True,
                    output_path=Path(directory) / "layout.json",
                    provider_factory=lambda: SimpleNamespace(_client=lambda: client),
                )
                self.assertEqual(report["rows"][0]["actual"], expected)

    def test_incomplete_or_malformed_risk_fields_never_approve_an_image(self):
        original = self.review.copy()
        for overrides in ({"flags": None}, {"flags": "collage"}, {"flags": ["unknown"]}, {"visibility": []}):
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as directory:
                self.review = {**original, **overrides}
                client = self.fake_client(None)
                report = self.runner["evaluate"](
                    [self.case(self.image_path(directory))], live=True,
                    output_path=Path(directory) / "malformed.json",
                    provider_factory=lambda: SimpleNamespace(_client=lambda: client),
                )
                self.assertIsNone(report["rows"][0]["actual"])
                self.assertEqual(report["rows"][0]["error"]["type"], "ImageReviewError")
                self.assertFalse(report["batch_aborted"])

    def test_live_rejects_unbounded_batches_before_provider_creation(self):
        cases = [self.case(Path("unused"), case_id=f"1221114868:{number:02d}") for number in range(1, 17)]
        with self.assertRaises(ValueError):
            self.runner["evaluate"](
                cases,
                live=True,
                provider_factory=lambda: self.fail("Provider must not be constructed"),
            )

    def test_summary_keeps_missing_usage_and_label_sources_visible(self):
        rows = [
            {"expected": "recommended", "actual": "recommended", "owner_confirmed": True,
             "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12}},
            {"expected": "not_recommended", "actual": None, "owner_confirmed": False, "usage": None},
        ]
        summary = self.runner["summarize"](rows, selected=2)
        self.assertFalse(summary["usage_complete"])
        self.assertEqual(summary["label_groups"]["owner_confirmed"]["evaluated"], 1)
        self.assertEqual(summary["label_groups"]["editorial"]["errors"], 1)
        self.assertEqual(summary["recommendation_precision"], 1.0)

    def test_live_refuses_to_overwrite_an_existing_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            output.write_text("original")
            with self.assertRaises(FileExistsError):
                self.runner["evaluate"](
                    [self.case(Path(directory) / "unused.webp")], live=True, output_path=output,
                    provider_factory=lambda: self.fail("No API call when output already exists"),
                )
            self.assertEqual(output.read_text(), "original")

    def test_framing_disagreement_requires_human_review(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.fake_client(None)
            original_chat = client.chat
            def chat(request):
                completion = original_chat(request)
                if len(client.chats) == 2:
                    completion.choices[0].message.content = json.dumps({
                        "description": "Видны только рукав и манжета.", "framing": "PART", "presentation": "PRODUCT", "frames_count": 1,
                    })
                return completion
            client.chat = chat
            report = self.runner["evaluate"](
                [self.case(self.image_path(directory), expected="acceptable")], live=True,
                output_path=Path(directory) / "verified.json",
                provider_factory=lambda: SimpleNamespace(_client=lambda: client),
            )
        self.assertEqual(report["rows"][0]["actual"], "acceptable")
        self.assertIn("ручная проверка", report["rows"][0]["reasons"][0])
        self.assertEqual(len(report["rows"][0]["stages"]), 2)
        self.assertEqual(report["summary"]["usage"]["total_tokens"], 24)

    def test_manual_review_does_not_override_confirmed_rejection_reasons(self):
        cases = (
            ("PARTIAL", {"framing": "PART", "presentation": "PRODUCT", "frames_count": 1}),
            ("MAIN", {"framing": "PART", "presentation": "PRODUCT", "frames_count": 2}),
            ("MAIN", {"framing": "NONE", "presentation": "PRODUCT", "frames_count": 1}),
            ("MAIN", {"framing": "PART", "presentation": "PACKAGING", "frames_count": 1}),
            ("MAIN", {"framing": "PART", "presentation": "INCOMPLETE_SET", "frames_count": 1}),
        )
        for visibility, verification in cases:
            with self.subTest(visibility=visibility, verification=verification), tempfile.TemporaryDirectory() as directory:
                self.review["visibility"] = visibility
                client = self.fake_client(None)
                original_chat = client.chat
                def chat(request):
                    completion = original_chat(request)
                    if len(client.chats) == 2:
                        completion.choices[0].message.content = json.dumps({"description": "Проверены видимость и компоновка.", **verification})
                    return completion
                client.chat = chat
                report = self.runner["evaluate"](
                    [self.case(self.image_path(directory), expected="not_recommended")], live=True,
                    output_path=Path(directory) / "reject.json",
                    provider_factory=lambda: SimpleNamespace(_client=lambda: client),
                )
                self.assertEqual(report["rows"][0]["actual"], "not_recommended")

    def test_second_stage_timeout_keeps_first_usage_but_never_approves(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.fake_client(None)
            original_chat = client.chat
            def chat(request):
                if client.chats:
                    raise TimeoutError("private provider detail")
                return original_chat(request)
            client.chat = chat
            report = self.runner["evaluate"](
                [self.case(self.image_path(directory))], live=True,
                output_path=Path(directory) / "timeout.json",
                provider_factory=lambda: SimpleNamespace(_client=lambda: client),
            )
        self.assertIsNone(report["rows"][0]["actual"])
        self.assertTrue(report["batch_aborted"])
        self.assertFalse(report["summary"]["usage_complete"])
        self.assertEqual(report["summary"]["usage"]["total_tokens"], 12)
        self.assertEqual(client.deleted, ["file-1"])

    def test_comparison_uses_observed_background_instead_of_model_verdict(self):
        self.review.update(content_type="BEFORE_AFTER", comparison_layout="CLEAR")
        with tempfile.TemporaryDirectory() as directory:
            client = self.fake_client(None)
            original_chat = client.chat
            def chat(request):
                completion = original_chat(request)
                if len(client.chats) == 2:
                    completion.choices[0].message.content = json.dumps({
                        "description": "Списки написаны на фотографии.",
                        "lists_background": "PHOTO", "comparison_size": "LARGE",
                    })
                return completion
            client.chat = chat
            report = self.runner["evaluate"](
                [self.case(self.image_path(directory), expected="not_recommended")], live=True,
                output_path=Path(directory) / "background.json",
                provider_factory=lambda: SimpleNamespace(_client=lambda: client),
            )
        self.assertEqual(report["rows"][0]["actual"], "not_recommended")

    def test_outfit_requires_both_components_and_held_jacket_needs_review(self):
        for jacket, trousers, expected in (
            ("WORN", "WHOLE", "recommended"), ("HELD", "WHOLE", "acceptable"),
            ("ABSENT", "WHOLE", "not_recommended"), ("PART", "ABSENT", "not_recommended"),
        ):
            with self.subTest(jacket=jacket, trousers=trousers), tempfile.TemporaryDirectory() as directory:
                client = self.fake_client(None)
                original_chat = client.chat
                def chat(request):
                    completion = original_chat(request)
                    if len(client.chats) == 2:
                        completion.choices[0].message.content = json.dumps({
                            "description": "Проверены куртка и брюки.", "jacket": jacket, "trousers": trousers,
                        })
                    return completion
                client.chat = chat
                case = self.case(self.image_path(directory), expected=expected)
                case["product_name"] = "Спортивный костюм"
                report = self.runner["evaluate"](
                    [case], live=True, output_path=Path(directory) / "outfit.json",
                    provider_factory=lambda: SimpleNamespace(_client=lambda: client),
                )
                self.assertEqual(report["rows"][0]["actual"], expected)

    def test_provider_startup_failure_is_saved_without_exposing_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "startup.json"
            def fail():
                raise RuntimeError("secret credential")
            report = self.runner["evaluate"](
                [self.case(Path(directory) / "unused.webp")], live=True,
                output_path=output, provider_factory=fail,
            )
            saved = json.loads(output.read_text())
        self.assertTrue(report["batch_aborted"])
        self.assertEqual(saved["provider_error"], "RuntimeError")
        self.assertNotIn("secret credential", json.dumps(saved))

    def test_kit_requires_multiple_visible_products_and_rejects_boxes(self):
        for products, presentation, expected in (
            (["Крем", "Сыворотка"], "PRODUCTS_MAIN", "recommended"),
            (["Шампунь"], "PRODUCTS_MAIN", "not_recommended"),
            (["Крем", "Сыворотка"], "BOX_MAIN", "not_recommended"),
        ):
            with self.subTest(products=products, presentation=presentation), tempfile.TemporaryDirectory() as directory:
                client = self.fake_client(None)
                original_chat = client.chat
                def chat(request):
                    completion = original_chat(request)
                    if len(client.chats) == 2:
                        completion.choices[0].message.content = json.dumps({
                            "description": "Проверены отдельные предметы.", "visible_products": products,
                            "visibility": "ALL_COMPLETE", "presentation": presentation, "frames_count": 1,
                        })
                    return completion
                client.chat = chat
                case = self.case(self.image_path(directory), expected=expected)
                case["product_name"] = "Набор крем и сыворотка"
                report = self.runner["evaluate"](
                    [case], live=True, output_path=Path(directory) / "kit.json",
                    provider_factory=lambda: SimpleNamespace(_client=lambda: client),
                )
                self.assertEqual(report["rows"][0]["actual"], expected)

    def test_incomplete_verification_never_approves_a_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.fake_client(None)
            original_chat = client.chat
            def chat(request):
                completion = original_chat(request)
                if len(client.chats) == 2:
                    completion.choices[0].message.content = '{"framing":"WHOLE"}'
                return completion
            client.chat = chat
            report = self.runner["evaluate"](
                [self.case(self.image_path(directory))], live=True,
                output_path=Path(directory) / "incomplete.json",
                provider_factory=lambda: SimpleNamespace(_client=lambda: client),
            )
        self.assertIsNone(report["rows"][0]["actual"])
        self.assertEqual(report["rows"][0]["error"]["type"], "ImageReviewError")
        self.assertEqual(report["summary"]["usage"]["total_tokens"], 24)
