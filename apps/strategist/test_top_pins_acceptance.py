"""Top Pins render API counters and links directly, with availability limits."""
from datetime import UTC, timedelta

from django.test import TestCase
from django.utils import timezone

from . import test_analytics_acceptance as analytics


class TopPinsAcceptanceTest(TestCase):
    setUp = analytics.AnalyticsAcceptanceTest.setUp
    ask = analytics.AnalyticsAcceptanceTest.ask

    def question(self, count=5):
        today = timezone.now().date()
        return f"Покажи {count} лучших пинов @beta по исходящим кликам за {today-timedelta(days=7)} — {today-timedelta(days=1)}"

    def test_links_counts_and_api_date_limitation(self):
        today = timezone.now().date()
        latest = timezone.datetime.combine(today-timedelta(days=3), timezone.datetime.min.time(), tzinfo=UTC)
        self.read.return_value = {"pins": [{"pin_id": "12345", "metrics": {"OUTBOUND_CLICK": 12},
            "data_status": {"OUTBOUND_CLICK": "READY"}}],
            "date_availability": {"latest_available_timestamp": latest.timestamp()*1000}}
        answer = self.ask(self.question())
        self.assertIn("https://www.pinterest.com/pin/12345/", answer.content)
        page = self.client.get(self.url)
        self.assertContains(page, 'href="https://www.pinterest.com/pin/12345/"')
        self.assertIn("исходящие клики: 12", answer.content)
        self.assertIn("предварительный", answer.content)
        self.assertEqual(answer.total_tokens, 0)
        args = self.read.call_args.kwargs["arguments"]
        self.assertEqual(args["resource"], "top_pins")
        self.assertEqual(args["account_key"], str(self.accounts[1].public_id))
        self.assertIn('"num_of_pins": 5', args["options"])

    def test_unready_counter_is_not_zero(self):
        self.read.return_value = {"pins": [{"pin_id": "12345", "metrics": {"OUTBOUND_CLICK": 0},
            "data_status": {"OUTBOUND_CLICK": "PROCESSING"}}]}
        answer = self.ask(self.question())
        self.assertIn("нет готовых данных", answer.content)
        self.assertNotIn("клики: 0", answer.content)

    def test_empty_response_is_not_zero_clicks(self):
        self.read.return_value = {"pins": []}
        answer = self.ask(self.question())
        self.assertIn("не вернул пины", answer.content)

    def test_error_is_not_empty_top(self):
        self.read.return_value = {"error": "Pinterest временно недоступен."}
        answer = self.ask(self.question())
        self.assertIn("Не удалось получить лучшие пины", answer.content)

    def test_malformed_top_response_is_safe(self):
        for value in (None, [], {"pins": None}, {"pins": [{"pin_id": "bad/id"}]}):
            with self.subTest(value=value):
                self.read.return_value = value
                answer = self.ask(self.question())
                self.assertNotIn("pinterest.com/pin/", answer.content)

    def test_invalid_count_does_not_request_api(self):
        answer = self.ask(self.question(51))
        self.assertIn("от 1 до 50", answer.content)
        self.read.assert_not_called()
