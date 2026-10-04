"""User supplied arithmetic at the authenticated chat boundary; no live API."""
from unittest.mock import patch
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.pinterest.models import PinterestAccount
from apps.strategist.models import AIConversation, AIMessage
from apps.strategist.user_metrics import user_metrics_answer
from apps.workspaces.models import Membership, Workspace


CASES = [
    ("Показы за месяц удвоились: со 16000 до 32000, а переходы на товары не изменились — 480. Коротко: это хорошо или плохо и что проверить в первую очередь?", "3% → 1,5%"),
    ("За неделю было 12 переходов на товары и ни одного заказа. Значит, переходы бесполезны? Коротко, и назови один следующий шаг.", "12 переходов и 0 заказов"),
    ("За последние 7 дней было 500 показов, а за 30 дней — 1800. Делаю вывод, что трафик падает. Проверь коротко и дай один шаг.", "Сопоставимость этих периодов не подтверждена"),
    ("У варианта А 3 перехода, у варианта Б 1. Получается, А втрое лучше? Ответь коротко и дай один следующий шаг.", "Статистическая значимость не рассчитана"),
    ("Переходы упали с 90 до 40 за месяц. Вижу причину: стал реже публиковать. Так и есть? Коротко и один следующий шаг.", "Причина изменения не установлена"),
    ("За неделю выложил 10 почти одинаковых публикаций с новым товаром и не понимаю, что сработало. Коротко: что я делаю не так и один следующий шаг.", "результатов по каждой нет"),
]


class UserMetricsParserTest(SimpleTestCase):
    def test_original_failures(self):
        for question, expected in CASES:
            with self.subTest(question=question):
                answer = user_metrics_answer(question)
                self.assertIsNotNone(answer)
                self.assertIn(expected, answer)
                self.assertEqual(answer.count("Одна проверка:"), 1)

    def test_different_counts_and_thousands_spaces(self):
        answer = user_metrics_answer("Показы выросли с 2 000 до 4 000, а переходы остались прежними — 100. Что проверить?")
        self.assertIn("5% → 2,5%", answer)
        self.assertNotIn("3%", answer)

    def test_zero_denominator(self):
        answer = user_metrics_answer("Показы выросли с 0 до 200, а переходы остались прежними — 10. Что проверить?")
        self.assertIn("при нуле показов", answer)
        self.assertNotIn("0%", answer)

    def test_decimal_counter_is_clarified(self):
        answer = user_metrics_answer("Показы выросли с 1,5 до 20, а переходы остались 2. Что проверить?")
        self.assertIn("Уточни", answer)

    def test_percent_is_not_a_counter(self):
        answer = user_metrics_answer("Переходы упали с 10% до 5%. Что проверить?")
        self.assertIn("Уточни", answer)

    def test_mixed_profiles_are_clarified(self):
        answer = user_metrics_answer("У @alpha было 20 переходов, у @beta было 5. Что проверить?")
        self.assertIn("какого одного профиля", answer)

    def test_unnamed_profiles_are_not_combined(self):
        answer = user_metrics_answer("В первом Pinterest-аккаунте 900 показов и 30 кликов, во втором 1800 показов и 45 кликов.")
        self.assertIn("какого одного профиля", answer)
        self.assertNotIn("%", answer)

    def test_creative_policy_and_non_analytics_requests_continue(self):
        for question in (
            "Напиши подпись: 12 переходов к уюту за 1999 рублей",
            "В 2026 году какие правила Pinterest?",
            "Создай 30 одинаковых пинов для спама",
            "Сколько пинов публиковать каждый день?",
            "Почему у товара артикул 123456?",
        ):
            with self.subTest(question=question):
                self.assertIsNone(user_metrics_answer(question))

    def test_neighbour_cases_from_opencode(self):
        cases = [
            ("Переходов было 27, стало 45. Показов 900 те же. Почему так?", "3% → 5%"),
            ("Заказов было 5, стало 8. Больше цифр нет.", "60%"),
            ("Показов было 800, потом 1200. Не помню, за какие периоды это.", "Уточни"),
            ("Показы в 25 000, неделей раньше 12 500. Кликов 300 против 150. Что изменилось?", "Уточни"),
            ("Кликов ноль, заказов тоже ноль, показов 900. Какой у меня конверт?", "Уточни"),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                self.assertIn(expected, user_metrics_answer(question))
        self.assertIsNone(user_metrics_answer("Цена выросла со 199 до 299 рублей, показы не менялись. Это хорошо?"))

    def test_structured_reply_to_clarification(self):
        answer = user_metrics_answer("За прошлую неделю: показы: 1000, переходы: 20; за текущую неделю: показы: 2000, переходы: 20")
        self.assertIn("2% → 1%", answer)
        self.assertIn("Причина изменения неизвестна", answer)

    def test_unambiguous_metric_pairs(self):
        for question in ("Было 1000 показов, 20 переходов. Что проверить?", "Показы: 1000, переходы: 20. Что проверить?"):
            with self.subTest(question=question):
                answer = user_metrics_answer(question)
                self.assertIn("2%", answer)
                self.assertIn("По одному периоду", answer)
        self.assertIn("Уточни", user_metrics_answer("Было 1000 показов, 20% переходов. Что проверить?"))

    def test_reverse_chronology_is_not_silently_swapped(self):
        answer = user_metrics_answer("За текущую неделю: показы: 2000, переходы: 20; за прошлую неделю: показы: 1000, переходы: 20")
        self.assertIn("Уточни", answer)

    def test_orders_require_attribution(self):
        answer = user_metrics_answer("За неделю было 20 переходов и 2 заказа. Значит, всё хорошо?")
        self.assertIn("Если эти заказы относятся именно к этим переходам", answer)
        self.assertIn("10%", answer)

    def test_negative_count_is_not_silently_positive(self):
        answer = user_metrics_answer("Было -10 показов, стало 20. Что проверить?")
        self.assertIn("Уточни", answer)


class UserMetricsChatTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("numeric-owner")
        workspace = Workspace.objects.create(name="Numeric", slug="numeric", created_by=self.user)
        Membership.objects.create(workspace=workspace, user=self.user, role=Membership.Role.OWNER)
        business = Business.objects.create(workspace=workspace, name="Shop", slug="shop")
        for username in ("numeric-alpha", "numeric-beta"):
            PinterestAccount.objects.create(
                business=business, connected_by=self.user, username=username,
                pinterest_user_id=username, access_token_encrypted="synthetic-only",
                access_token_expires_at=timezone.now() + timedelta(days=1),
                granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED,
            )
        self.conversation = AIConversation.objects.create(business=business, created_by=self.user)
        self.client.force_login(self.user)
        self.complete = self.enterContext(patch("apps.strategist.services.GigaChatProvider.complete", side_effect=AssertionError("Unexpected paid call")))
        self.read = self.enterContext(patch("apps.strategist.services.read_pinterest_data", side_effect=AssertionError("Unexpected API read")))

    def test_all_six_questions_in_fresh_sessions_are_rendered(self):
        for question, expected in CASES:
            with self.subTest(question=question):
                conversation = AIConversation.objects.create(business=self.conversation.business, created_by=self.user)
                url = reverse("strategist:session", kwargs={"workspace_slug": "numeric", "business_slug": "shop", "session_slug": conversation.slug})
                response = self.client.post(url, {"message": question}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                self.assertEqual(response.status_code, 200)
                answer = conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")
                self.assertEqual((answer.provider, answer.model), ("calculation", "user-metrics"))
                self.assertEqual(answer.total_tokens, 0)
                self.assertIn(expected, answer.content)
                self.assertTrue(response.json()["messages_html"])
                self.assertIn(answer.content.split(".")[0], response.json()["messages_html"])
        self.complete.assert_not_called()
        self.read.assert_not_called()
