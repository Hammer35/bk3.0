"""Characterization tests for image response parsing and recommendations."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.strategist.image_analysis_test import ImageReviewError, _parse_response, _recommendation, review_image


def valid_review(**overrides):
    review = {
        "description": "Товар на нейтральном фоне.",
        "product_match": "MATCH",
        "content_type": "PRODUCT",
        "comparison_layout": "CLEAR",
        "visibility": "MAIN",
        "technical_quality": "GOOD",
        "composition": "STRONG",
        "category_fit": "STRONG",
        "flags": [],
    }
    review.update(overrides)
    return review


def trouser_check(**overrides):
    check = {
        "description": "Один кадр, пояс, обе штанины и обувь видны.",
        "layout": "PHOTO", "presentation": "WORN", "lowest_visible": "FEET",
        "waist_visible": True, "complete_trousers": True,
    }
    check.update(overrides)
    return check


class TrouserEvidenceTests(SimpleTestCase):
    def review(self, check, *, first=None, category="", product_name="Джинсы клеш"):
        def completion(payload):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
        client = Mock()
        client.chat.side_effect = [completion(first or valid_review()), completion(check)]
        result = review_image(client, "image", product_name=product_name, category=category, stages=[])
        self.assertEqual(client.chat.call_count, 2)
        return result

    def test_cropped_legs_override_model_claim_that_trousers_are_complete(self):
        for lowest in ("CALVES", "KNEES", "THIGHS", "HIPS"):
            with self.subTest(lowest=lowest):
                result = self.review(trouser_check(lowest_visible=lowest))
                self.assertEqual(result[2], "acceptable")
                self.assertTrue(result[0]["framing_disagreement"])

    def test_collage_is_rejected_even_when_central_trousers_are_complete(self):
        result = self.review(trouser_check(layout="COLLAGE"))
        self.assertEqual(result[2], "not_recommended")
        self.assertEqual(result[0]["content_type"], "COLLAGE")

    def test_collage_rejection_does_not_require_unrelated_trouser_fields(self):
        result = self.review({"layout": "COLLAGE", "description": "Несколько отдельных фото предметов.", "presentation": ""})
        self.assertEqual(result[2], "not_recommended")
        self.assertEqual(result[0]["content_type"], "COLLAGE")

    def test_no_verification_branch_can_return_a_blank_description(self):
        cases = (
            ("Джинсы", valid_review(), trouser_check()),
            ("Джинсы", valid_review(), trouser_check(layout="COLLAGE")),
            ("Рубашка", valid_review(), {"framing": "WHOLE", "presentation": "PRODUCT", "frames_count": 1}),
            ("Костюм", valid_review(), {"jacket": "WORN", "trousers": "WHOLE"}),
            ("Набор", valid_review(), {"visible_products": ["Шампунь", "Бальзам"], "visibility": "ALL_COMPLETE", "presentation": "PRODUCTS_MAIN", "frames_count": 1}),
            ("Сыворотка", valid_review(content_type="BEFORE_AFTER"), {"lists_background": "SOLID_PANEL", "comparison_size": "LARGE"}),
        )
        for name, first, observations in cases:
            with self.subTest(name=name, valid=True):
                self.review({**observations, "description": "Товар и расположение элементов видны."}, first=first, product_name=name)
            for description in ("", " \n\t ", None):
                with self.subTest(name=name, description=description), self.assertRaises(ImageReviewError):
                    self.review({**observations, "description": description}, first=first, product_name=name)

    def test_whole_trousers_remain_recommended_worn_or_flat(self):
        for check in (trouser_check(), trouser_check(presentation="FLAT", lowest_visible="NO_PERSON")):
            with self.subTest(presentation=check["presentation"]):
                self.assertEqual(self.review(check)[2], "recommended")

    def test_incomplete_or_hidden_trousers_need_manual_review(self):
        for check in (trouser_check(complete_trousers=False), trouser_check(waist_visible=False)):
            self.assertEqual(self.review(check)[2], "acceptable")

    def test_packaging_and_agreed_partial_view_are_not_rescued(self):
        self.assertEqual(self.review(trouser_check(presentation="PACKAGING", lowest_visible="NO_PERSON"))[2], "not_recommended")
        result = self.review(trouser_check(lowest_visible="HIPS"), first=valid_review(visibility="PARTIAL"))
        self.assertEqual(result[2], "not_recommended")

    def test_missing_or_malformed_observations_fail_closed(self):
        cases = [trouser_check(**{key: value}) for key, value in (
            ("description", ""), ("description", " \n "),
            ("layout", "UNKNOWN"), ("presentation", "PRODUCT"), ("lowest_visible", "UNKNOWN"),
            ("waist_visible", "true"), ("complete_trousers", 1),
        )]
        for key in trouser_check():
            case = trouser_check()
            del case[key]
            cases.append(case)
        for check in cases:
            with self.subTest(check=check), self.assertRaises(ImageReviewError):
                self.review(check)


class ParseImageResponseTests(SimpleTestCase):
    def test_valid_json_is_returned_with_additional_fields(self):
        payload = {**valid_review(), "additional": "preserved"}

        result = _parse_response(json.dumps(payload, ensure_ascii=False))

        self.assertEqual(result, payload)

    def test_json_code_fence_is_removed(self):
        payload = valid_review()
        raw = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"

        self.assertEqual(_parse_response(raw), payload)

    def test_malformed_json_raises_safe_error(self):
        for raw in ("", "{not json}", '{"description":'):
            with self.subTest(raw=raw), self.assertRaises(ImageReviewError) as context:
                _parse_response(raw)
            self.assertEqual(
                str(context.exception),
                "Модель вернула ответ, который нельзя разобрать. Попробуйте ещё раз.",
            )

    def test_non_dict_json_is_rejected(self):
        for raw in ("[]", '"text"', "1", "null", "true"):
            with self.subTest(raw=raw), self.assertRaises(ImageReviewError) as context:
                _parse_response(raw)
            self.assertEqual(str(context.exception), "Модель вернула неполную оценку. Результат не засчитан.")

    def test_missing_enum_fields_are_rejected(self):
        fields = (
            "product_match",
            "content_type",
            "visibility",
            "technical_quality",
            "composition",
            "category_fit",
        )
        for field in fields:
            payload = valid_review()
            payload.pop(field)
            with self.subTest(field=field), self.assertRaises(ImageReviewError) as context:
                _parse_response(json.dumps(payload))
            self.assertEqual(str(context.exception), "Модель вернула неполную оценку. Результат не засчитан.")

    def test_invalid_enum_values_are_rejected(self):
        fields = (
            "product_match",
            "content_type",
            "visibility",
            "technical_quality",
            "composition",
            "category_fit",
        )
        for field in fields:
            payload = valid_review(**{field: "INVALID"})
            with self.subTest(field=field), self.assertRaises(ImageReviewError) as context:
                _parse_response(json.dumps(payload))
            self.assertEqual(str(context.exception), "Модель вернула неполную оценку. Результат не засчитан.")

    def test_blank_or_non_string_description_is_rejected(self):
        for description in ("", " \n\t ", None, 0, [], {}):
            payload = valid_review(description=description)
            with self.subTest(description=description), self.assertRaises(ImageReviewError) as context:
                _parse_response(json.dumps(payload))
            self.assertEqual(str(context.exception), "Модель не описала изображение. Результат не засчитан.")

    def test_description_is_stripped_and_truncated_to_400_characters(self):
        payload = valid_review(description="  " + "я" * 450 + "  ")

        result = _parse_response(json.dumps(payload, ensure_ascii=False))

        self.assertEqual(result["description"], "я" * 400)
        self.assertEqual(len(result["description"]), 400)

    def test_flags_are_deduplicated_and_sorted(self):
        payload = valid_review(flags=[
            "watermark",
            "text_heavy",
            "watermark",
            "collage",
            "low_quality",
            "text_heavy",
        ])

        result = _parse_response(json.dumps(payload))

        self.assertEqual(result["flags"], ["collage", "low_quality", "text_heavy", "watermark"])

    def test_malformed_flags_are_rejected(self):
        for flags in (None, "watermark", {"watermark": True}, 1, True, ["unknown"], [42], [None]):
            payload = valid_review(flags=flags)
            with self.subTest(flags=flags), self.assertRaises(ImageReviewError):
                _parse_response(json.dumps(payload))

    def test_missing_flags_do_not_hide_unchecked_risks(self):
        payload = valid_review()
        payload.pop("flags")

        with self.assertRaises(ImageReviewError):
            _parse_response(json.dumps(payload))


class ImageRecommendationTests(SimpleTestCase):
    def test_ordinary_score_80_without_warnings_is_recommended(self):
        review = valid_review(
            technical_quality="POOR",
            composition="ACCEPTABLE",
            category_fit="ACCEPTABLE",
        )

        score, status, label, reasons = _recommendation(review)

        self.assertEqual((score, status, label), (80, "recommended", "Рекомендую"))
        self.assertEqual(len(reasons), 5)

    def test_ordinary_score_79_is_acceptable(self):
        review = valid_review(
            visibility="SECONDARY",
            composition="WEAK",
            category_fit="WEAK",
        )

        score, status, label, reasons = _recommendation(review)

        self.assertEqual((score, status, label), (79, "acceptable", "Допустим"))
        self.assertEqual(
            reasons[0],
            "Фото пригодно, но не прошло порог автоматической рекомендации (80 баллов).",
        )

    def test_ordinary_score_60_is_acceptable(self):
        review = valid_review(
            product_match="UNCERTAIN",
            visibility="PARTIAL",
            composition="STRONG",
            category_fit="ACCEPTABLE",
        )

        score, status, label, reasons = _recommendation(review)

        self.assertEqual((score, status, label), (60, "acceptable", "Допустим"))
        self.assertIn("совпадение товара не подтверждено уверенно", reasons[0])

    def test_ordinary_score_below_60_is_not_recommended(self):
        review = valid_review(
            visibility="PARTIAL",
            technical_quality="POOR",
            composition="WEAK",
            category_fit="WEAK",
        )

        score, status, label, reasons = _recommendation(review)

        self.assertEqual((score, status, label), (55, "not_recommended", "Не рекомендую"))
        self.assertEqual(reasons[0], "Ниже порога ручного рассмотрения (60 баллов).")

    def test_warnings_prevent_recommended_despite_high_score(self):
        cases = (
            ({"flags": ["watermark"]}, 100, "обнаружены признаки: watermark"),
            ({"product_match": "UNCERTAIN"}, 80, "совпадение товара не подтверждено уверенно"),
        )
        for overrides, expected_score, warning in cases:
            with self.subTest(overrides=overrides):
                score, status, label, reasons = _recommendation(valid_review(**overrides))
            self.assertEqual((score, status, label), (expected_score, "acceptable", "Допустим"))
            self.assertIn(warning, reasons[0])

    def test_ordinary_hard_rejects_override_score(self):
        cases = (
            ("MISMATCH", {"product_match": "MISMATCH"}, 65, "На фото явно другой товар"),
            ("NONE", {"visibility": "NONE"}, 75, "Товар неразличим"),
            ("UNUSABLE", {"technical_quality": "UNUSABLE"}, 80, "Качество не позволяет рассмотреть товар"),
        )
        for name, overrides, expected_score, reason in cases:
            with self.subTest(name=name):
                score, status, label, reasons = _recommendation(valid_review(**overrides))
            self.assertEqual((score, status, label), (expected_score, "not_recommended", "Не рекомендую"))
            self.assertEqual(reasons[0], reason)

    def test_ideal_before_after_is_only_an_additional_pin(self):
        score, status, label, reasons = _recommendation(valid_review(content_type="BEFORE_AFTER"))

        self.assertEqual((score, status, label), (100, "acceptable", "Допустим"))
        self.assertEqual(len(reasons), 2)
        self.assertEqual(
            reasons[0],
            "Формат «до/после» допустим как дополнительный пин, если сравнение связано с товаром и легко читается.",
        )

    def test_before_after_text_heavy_is_rejected(self):
        review = valid_review(content_type="BEFORE_AFTER", flags=["text_heavy"])

        score, status, label, reasons = _recommendation(review)

        self.assertEqual((score, status, label), (80, "not_recommended", "Не рекомендую"))
        self.assertEqual(reasons[0], "текст перегружает сравнение")

    def test_before_after_mismatch_and_unusable_are_hard_rejects(self):
        cases = (
            ("MISMATCH", {"product_match": "MISMATCH"}, 80),
            ("UNUSABLE", {"technical_quality": "UNUSABLE"}, 75),
        )
        for name, overrides, expected_score in cases:
            review = valid_review(content_type="BEFORE_AFTER", **overrides)
            with self.subTest(name=name):
                score, status, label, reasons = _recommendation(review)
            self.assertEqual((score, status, label), (expected_score, "not_recommended", "Не рекомендую"))
            self.assertEqual(
                reasons[0],
                "Изображение не связано с товаром или качество не позволяет рассмотреть сравнение.",
            )
