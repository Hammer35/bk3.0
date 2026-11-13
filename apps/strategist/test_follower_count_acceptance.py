"""Simple follower counts use the API field, never an LLM-generated total."""

from django.test import TestCase

from . import test_analytics_acceptance as analytics


class FollowerCountAcceptanceTest(TestCase):
    setUp = analytics.AnalyticsAcceptanceTest.setUp
    ask = analytics.AnalyticsAcceptanceTest.ask

    def test_explicit_account_uses_profile_count(self):
        self.read.return_value = {"follower_count": 25}
        answer = self.ask("Сколько подписчиков у @beta? Ответь только количеством и укажи профиль.")
        self.assertEqual(answer.content, "У профиля @beta подписчиков: 25.")
        self.assertEqual((answer.provider, answer.model, answer.total_tokens), ("pinterest-api", "direct-read", 0))
        arguments = self.read.call_args.kwargs["arguments"]
        self.assertEqual(arguments["account_key"], str(self.accounts[1].public_id))
        self.assertEqual(arguments["resource"], "profile")
        self.assertEqual(self.read.call_count, 1)

    def test_missing_or_invalid_count_is_not_zero(self):
        for value in (None, True, -1, "25", 2.5):
            with self.subTest(value=value):
                self.read.return_value = {"follower_count": value}
                answer = self.ask("Сколько подписчиков у @alpha?")
                self.assertIn("точное количество неизвестно", answer.content)
                self.assertNotIn("подписчиков: 0", answer.content)

    def test_actual_zero_is_reported(self):
        self.read.return_value = {"follower_count": 0}
        answer = self.ask("Сколько подписчиков у @alpha?")
        self.assertIn("подписчиков: 0.", answer.content)

    def test_failed_profile_read_is_not_a_count(self):
        self.read.return_value = {"error": "Pinterest временно недоступен."}
        answer = self.ask("Сколько подписчиков у @alpha?")
        self.assertIn("Не удалось прочитать число подписчиков", answer.content)

    def test_multiple_accounts_require_selection(self):
        answer = self.ask("Сколько подписчиков?")
        self.assertIn("Уточни профиль", answer.content)
        self.read.assert_not_called()

    def test_unknown_account_is_not_substituted(self):
        answer = self.ask("Сколько подписчиков у @unknown?")
        self.assertIn("не подключён", answer.content)
        self.read.assert_not_called()

    def test_non_object_profile_response_is_safe(self):
        self.read.return_value = []
        answer = self.ask("Сколько подписчиков у @alpha?")
        self.assertIn("точное количество неизвестно", answer.content)
