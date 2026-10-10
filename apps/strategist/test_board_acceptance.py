"""Board pagination at the authenticated chat boundary; external calls mocked."""

from unittest.mock import patch

from django.test import TestCase

from . import test_analytics_acceptance as analytics


class BoardAcceptanceTest(TestCase):
    setUp = analytics.AnalyticsAcceptanceTest.setUp
    ask = analytics.AnalyticsAcceptanceTest.ask

    def test_complete_two_pages_reports_count(self):
        self.read.side_effect = [
            {"items": [{"name": "Керамика"}], "bookmark": "next"},
            {"items": [{"name": "Подарки"}], "bookmark": None},
        ]
        answer = self.ask("Покажи доски @alpha")
        self.assertEqual((answer.provider, answer.model), ("pinterest-api", "direct-read"))
        self.assertIn("2 досок", answer.content)
        self.assertIn("Керамика", answer.content)
        self.assertIn("Подарки", answer.content)
        self.assertNotIn("неполный", answer.content)
        self.assertEqual(self.read.call_count, 2)
        self.assertEqual(self.read.call_args_list[1].kwargs["arguments"]["bookmark"], "next")

    def test_four_page_cap_reports_partial_list(self):
        self.read.return_value = {"items": [{"name": "Керамика"}], "bookmark": "next"}
        answer = self.ask("Покажи доски @alpha")
        self.assertIn("Список неполный", answer.content)
        self.assertEqual(self.read.call_count, 4)

    def test_failed_second_page_is_not_reported_as_complete(self):
        self.read.side_effect = [
            {"items": [{"name": "Керамика"}], "bookmark": "next"},
            {"error": "Pinterest временно недоступен."},
        ]
        answer = self.ask("Покажи доски @alpha")
        self.assertIn("Не удалось прочитать доски", answer.content)
        self.assertNotIn("1 досок", answer.content)

    def test_non_object_response_does_not_crash_chat(self):
        for malformed in ([], None):
            with self.subTest(response=malformed):
                self.read.return_value = malformed
                answer = self.ask("Покажи доски @alpha")
                self.assertIn("Не удалось прочитать доски", answer.content)
                self.assertIn("некорректный формат", answer.content)

    def test_missing_items_is_not_zero_boards(self):
        self.read.return_value = {"bookmark": None}
        answer = self.ask("Покажи доски @alpha")
        self.assertIn("без списка записей", answer.content)
        self.assertNotIn("0 досок", answer.content)
