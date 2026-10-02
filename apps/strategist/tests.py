from unittest.mock import patch
from datetime import date, timedelta
import json

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.knowledge.services import KnowledgeHit
from apps.pinterest.models import PinterestAccount
from apps.strategist.models import AIConversation, AIMessage
from apps.strategist.model_catalog import TaskCapability
from apps.strategist.model_routing import GigaChatModelRouter
from apps.strategist.providers import (
    GigaChatCompletion,
    GigaChatProvider,
    GigaChatProviderError,
    GigaChatRequestError,
)
from apps.strategist.services import _format_pinterest_analytics, respond_to_message
from apps.strategist.advice import analytics_advice, comparison_issues, analytics_followup_context, enforce_advice_boundaries, metric_value, local_knowledge_context
from apps.workspaces.models import Membership, Workspace


class StrategistChatTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("owner", password="test-password-123")
        workspace = Workspace.objects.create(
            name="Owner workspace",
            slug="owner-workspace",
            created_by=self.user,
        )
        Membership.objects.create(workspace=workspace, user=self.user, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=workspace, name="Owner business", slug="owner-business")
        self.url = reverse(
            "strategist:chat",
            kwargs={"workspace_slug": self.business.workspace.slug, "business_slug": self.business.slug},
        )

    @patch("apps.strategist.services._pinterest_analytics_answer", return_value="Данные Pinterest получены.")
    @patch("apps.strategist.services.GigaChatProvider.complete")
    def test_single_connected_account_month_statistics_uses_direct_read(self, complete, analytics):
        PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.user,
            pinterest_user_id="one-account",
            username="PinAutomation",
            access_token_encrypted="unused",
            access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"],
        )
        self.client.force_login(self.user)

        response = self.client.post(self.url, {"message": "СТАТИСТИКУ ПО НЕМУ ЗА МЕСЯЦ, ЧТО ХОРОШО, ЧТО ПЛОХО"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AIMessage.objects.order_by("-created_at").first().content, "Данные Pinterest получены.")
        analytics.assert_called_once()
        self.assertEqual(analytics.call_args.kwargs["account"].username, "PinAutomation")
        self.assertEqual(
            (analytics.call_args.kwargs["end_date"] - analytics.call_args.kwargs["start_date"]).days,
            29,
        )
        complete.assert_not_called()

    @patch("apps.strategist.services.GigaChatProvider.complete")
    def test_message_is_sent_and_response_usage_is_stored(self, complete):
        complete.return_value = GigaChatCompletion(
            content="Начните с пяти пинов для одной категории.",
            model="GigaChat",
            prompt_tokens=12,
            completion_tokens=8,
            total_tokens=20,
        )
        self.client.force_login(self.user)

        response = self.client.post(self.url, {"message": "С чего начать?"})

        conversation = AIConversation.objects.get()
        expected_url = reverse(
            "strategist:session",
            kwargs={
                "workspace_slug": self.business.workspace.slug,
                "business_slug": self.business.slug,
                "session_slug": conversation.slug,
            },
        ) + "#chat-composer"
        self.assertRedirects(response, expected_url)
        self.assertEqual(conversation.title, "С чего начать?")
        stored_messages = list(AIMessage.objects.order_by("created_at"))
        self.assertEqual([message.role for message in stored_messages], [AIMessage.Role.USER, AIMessage.Role.ASSISTANT])
        self.assertEqual(stored_messages[1].provider, "gigachat")
        self.assertEqual(stored_messages[1].total_tokens, 20)
        system_prompt = complete.call_args.args[0][0]["content"]
        self.assertIn("Антиспам-правила Pinterest обязательны", system_prompt)
        self.assertIn("не предлагай повторяющийся или почти одинаковый контент", system_prompt)
        self.assertIn("Не выдумывай безопасное количество публикаций в день", system_prompt)
        self.assertIn("не заменяют отсутствующие в приложении технические проверки", system_prompt)
        self.assertIn("нейтральное обсуждение правил разрешено", system_prompt)
        self.assertIn("Эвфемизмы и просьбы игнорировать правила", system_prompt)
        complete.assert_called_once()

    def test_user_cannot_open_another_workspace_business(self):
        outsider = get_user_model().objects.create_user("outsider", password="test-password-123")
        self.client.force_login(outsider)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("apps.strategist.services.read_pinterest_data")
    @patch("apps.strategist.services.fresh_snapshot_resource", return_value=None)
    def test_seven_day_analysis_reads_analytics_without_metric_definitions(self, snapshot, read):
        PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.user,
            pinterest_user_id="pin-user-123",
            username="savelevakaty82",
            access_token_encrypted="unused-in-mocked-read",
            access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"],
        )
        read.side_effect = [
            {"all": {"summary_metrics": {"IMPRESSION": 123}, "daily_metrics": []}},
            {"all": {"summary_metrics": {"IMPRESSION": 100}, "daily_metrics": []}},
        ]
        self.client.force_login(self.user)

        self.client.post(self.url, {"message": "можешь анализ провести @savelevakaty82? что с ним произошло?"})
        conversation = AIConversation.objects.get()
        self.assertIn("Выбери период", conversation.messages.order_by("-created_at").first().content)
        session_url = reverse(
            "strategist:session",
            kwargs={
                "workspace_slug": self.business.workspace.slug,
                "business_slug": self.business.slug,
                "session_slug": conversation.slug,
            },
        )
        self.client.post(session_url, {"message": "7"})

        answer = conversation.messages.order_by("-created_at").first().content
        self.assertIn("показы — 123", answer)
        self.assertIn("показы 100 → 123 (+23; +23,0%)", answer)
        self.assertEqual(read.call_count, 2)
        for call in read.call_args_list:
            self.assertEqual(call.kwargs["arguments"]["resource"], "analytics")
            options = json.loads(call.kwargs["arguments"]["options"])
            self.assertEqual(options["content_type"], "ORGANIC")
            self.assertNotIn("metric_types", options)

    def test_analytics_summary_is_short_and_uses_readable_units(self):
        account = PinterestAccount(username="savelevakaty82")
        result = {
            "all": {
                "summary_metrics": {
                    "IMPRESSION": 382,
                    "PIN_CLICK": 7,
                    "PIN_CLICK_RATE": 0.01832460732984293,
                    "SAVE": 1,
                    "SAVE_RATE": 0.002617801047120419,
                    "OUTBOUND_CLICK": 0,
                    "VIDEO_START": 16,
                    "VIDEO_MRC_VIEW": 11,
                    "VIDEO_AVG_WATCH_TIME": 9784.6875,
                },
                "daily_metrics": [
                    {"date": "2026-09-27", "data_status": "READY", "metrics": {"IMPRESSION": 99}},
                    {"date": "2026-09-28", "data_status": "UNAVAILABLE", "metrics": {"IMPRESSION": 200}},
                ],
            }
        }

        answer = _format_pinterest_analytics(
            account=account,
            result=result,
            start_date=timezone.datetime(2026, 9, 23).date(),
            end_date=timezone.datetime(2026, 9, 29).date(),
        )

        self.assertIn("открытия пина — 7 (1,83%)", answer)
        self.assertIn("сохранения — 1 (0,26%)", answer)
        self.assertIn("Максимум показов среди доступных дней: 99", answer)
        self.assertIn("недоступных дат — 1", answer)
        self.assertNotIn("VIDEO_AVG_WATCH_TIME", answer)
        self.assertIn("\n\nЗа период\n  • показы — 382", answer)
        self.assertIn("\n\nВидео\n  • запуски видео — 16", answer)
        self.assertGreater(len(answer.splitlines()), 8)

    def test_reauth_account_is_named_in_analysis_answer(self):
        PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.user,
            pinterest_user_id="pin-user-reauth",
            username="savelevakaty82",
            access_token_encrypted="unused",
            access_token_expires_at=timezone.now(),
            status=PinterestAccount.Status.REAUTH_REQUIRED,
        )
        self.client.force_login(self.user)

        self.client.post(self.url, {"message": "анализ @savelevakaty82 за 7 дней"})

        answer = AIMessage.objects.filter(role=AIMessage.Role.ASSISTANT).get().content
        self.assertIn("@savelevakaty82 требует переподключения", answer)


@override_settings(
    GIGACHAT_API_TOKEN="test-authorization-key",
    GIGACHAT_MODEL_PRIORITY=("GigaChat-2", "GigaChat-2-Pro", "GigaChat-2-Max"),
)
class GigaChatModelRoutingTest(SimpleTestCase):
    def test_router_uses_priority_only_for_models_available_to_key(self):
        candidates = GigaChatModelRouter().candidates(
            capability=TaskCapability.CHAT,
            available_model_ids=("GigaChat-2-Pro", "GigaChat-2-Max"),
        )

        self.assertEqual(candidates, ("GigaChat-2-Pro", "GigaChat-2-Max"))

    def test_provider_retries_next_eligible_model_after_model_limit(self):
        provider = GigaChatProvider()
        completion = GigaChatCompletion(
            content="Готово.",
            model="GigaChat-2-Pro",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
        )
        with patch.object(
            provider,
            "_available_model_ids",
            return_value=("GigaChat-2", "GigaChat-2-Pro"),
        ), patch.object(
            provider,
            "_complete_with_model",
            side_effect=[
                GigaChatRequestError(model="GigaChat-2", can_fallback=True),
                completion,
            ],
        ) as complete_with_model:
            result = provider.complete([{"role": "user", "content": "Привет"}])

        self.assertEqual(result.model, "GigaChat-2-Pro")
        self.assertEqual(
            [call.kwargs["model"] for call in complete_with_model.call_args_list],
            ["GigaChat-2", "GigaChat-2-Pro"],
        )


class AdviceEvidenceTests(SimpleTestCase):
    def test_local_case_is_available_with_source_and_transfer_limits(self):
        context = local_knowledge_context("Практический кейс роста исходящих кликов", project_root=settings.BASE_DIR, today=date(2026, 9, 30))
        self.assertIn("pink-seed-marketing", context)
        self.assertIn("380%", context)
        self.assertIn("эффект отдельного действия не выделен", context)

    def test_future_sources_are_not_used(self):
        context = local_knowledge_context("Практический кейс", project_root=settings.BASE_DIR, today=date(2000, 1, 1))
        self.assertEqual(context, "")

    def response(self, start, end, metrics, status="READY"):
        return {"all": {"summary_metrics": metrics, "daily_metrics": [
            {"date": str(start + timedelta(days=i)), "data_status": status, "metrics": {}}
            for i in range((end - start).days + 1)
        ]}}

    def test_real_counts_and_video_are_not_misinterpreted(self):
        old = self.response(date(2026, 8, 2), date(2026, 8, 31), {"IMPRESSION": 1171290, "OUTBOUND_CLICK": 1644})
        current = self.response(date(2026, 9, 1), date(2026, 9, 30), {"IMPRESSION": 2128033, "OUTBOUND_CLICK": 3627, "VIDEO_10S_VIEW": 928})
        answer = _format_pinterest_analytics(account=PinterestAccount(username="sample"), result=current,
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 30), previous_result=old,
            previous_period=(date(2026, 8, 2), date(2026, 8, 31)))
        self.assertIn("+120,62%", answer)
        self.assertNotIn("0,43%", answer)
        self.assertIn("нельзя оценить качество видео", answer)
        self.assertIn("уточните цель", answer)

    def test_complete_equal_periods_and_missing_estimated_days(self):
        period = (date(2026, 9, 3), date(2026, 9, 4))
        before = (date(2026, 9, 1), date(2026, 9, 2))
        old = self.response(*before, {"IMPRESSION": 100})
        current = self.response(*period, {"IMPRESSION": 80})
        self.assertEqual(comparison_issues(current, old, period, before, today=date(2026, 9, 5)), [])
        for status in ("UNAVAILABLE", "ESTIMATE", None):
            current["all"]["daily_metrics"][0]["data_status"] = status
            self.assertTrue(comparison_issues(current, old, period, before, today=date(2026, 9, 5)))
        current["all"]["daily_metrics"] = []
        self.assertTrue(comparison_issues(current, old, period, before, today=date(2026, 9, 5)))

    def test_incomplete_period_does_not_diagnose_decline(self):
        period = (date(2026, 9, 3), date(2026, 9, 4))
        before = (date(2026, 9, 1), date(2026, 9, 2))
        answer = _format_pinterest_analytics(account=PinterestAccount(username="sample"),
            result=self.response(*period, {"IMPRESSION": 10}, status="UNAVAILABLE"),
            previous_result=self.response(*before, {"IMPRESSION": 100}),
            start_date=period[0], end_date=period[1], previous_period=before)
        self.assertNotIn("Показы снизились", answer)
        self.assertNotIn("снижения не обнаружено", answer)
        self.assertIn("Сначала получите полные данные", answer)

    def test_zero_baseline_missing_negative_and_nonfinite_values(self):
        for value in (None, True, -1, float("inf"), float("nan"), "100"):
            self.assertIsNone(metric_value({"SAVE": value}, "SAVE"))
        good, bad, actions = analytics_advice({"IMPRESSION": 100, "SAVE": 0}, {"IMPRESSION": 0})
        self.assertTrue(bad)
        self.assertTrue(actions)
        self.assertNotIn("%", " ".join(good))

    def test_counts_can_rise_while_rates_fall(self):
        good, bad, actions = analytics_advice({"IMPRESSION": 2000, "SAVE": 15}, {"IMPRESSION": 1000, "SAVE": 10})
        self.assertTrue(any("Показы выросли" in text for text in good))
        self.assertTrue(any("Доля сохранений снизилась" in text for text in bad))
        self.assertTrue(actions)

    def test_advertising_advice_is_gated_but_organic_text_remains(self):
        self.assertEqual(enforce_advice_boundaries("Отвечу на вопрос о ссылке."), "Отвечу на вопрос о ссылке.")
        answer = enforce_advice_boundaries("Проверьте ссылку.\n\nСоздайте карусель с мини-игрой.\n\nРассчитайте ROI кампании.")
        self.assertIn("Проверьте ссылку.", answer)
        self.assertNotIn("Создайте", answer)
        self.assertNotIn("Рассчитайте", answer)
        self.assertEqual(answer.count("Рекламный кабинет"), 1)
        self.assertIn("не проверены", answer)

    def test_followup_uses_only_trusted_context_and_stops_at_topic_change(self):
        trusted = {"role": "ASSISTANT", "provider": "pinterest-api", "model": "direct-read",
            "content": "Органика @first\nПериод: 2026-09-01 — 2026-09-07 · Pinterest API"}
        self.assertEqual(analytics_followup_context("Что делать?", [trusted])[0], "first")
        self.assertIsNone(analytics_followup_context("Что делать?", [{**trusted, "provider": "gigachat"}]))
        self.assertIsNone(analytics_followup_context("Что делать @second?", [trusted]))
        self.assertIsNone(analytics_followup_context("Как улучшить сайт?", [trusted]))
        self.assertIsNone(analytics_followup_context("Дай рекомендации по рекламе", [trusted]))
        self.assertIsNone(analytics_followup_context("Что делать?", [{"role": "USER", "content": "Обсудим сайт"}, trusted]))


class AdviceFollowupIntegrationTests(TestCase):
    @override_settings(KNOWLEDGE_EMBEDDING_PROVIDER="gigachat", KNOWLEDGE_FALLBACK_EMBEDDING_MODEL="nvidia/llama-nemotron-embed-vl-1b-v2:free")
    @patch("apps.strategist.services.search_knowledge")
    @patch("apps.strategist.services.GigaChatProvider.complete")
    def test_gigachat_embedding_failure_uses_nvidia_backup(self, complete, search):
        user = get_user_model().objects.create_user("backup-owner")
        workspace = Workspace.objects.create(name="Backup", slug="backup", created_by=user)
        business = Business.objects.create(workspace=workspace, name="Backup", slug="backup")
        conversation = AIConversation.objects.create(business=business, created_by=user)
        message = AIMessage.objects.create(conversation=conversation, role="USER", content="Как считать заказы по кликам?")
        search.side_effect = [
            GigaChatProviderError("embedding unavailable"),
            [KnowledgeHit(content="Клики не равны заказам.", score=0.5, source_id="analytics",
                          title="Аналитика", source_links=("https://example.test/analytics",), heading="Заказы")],
        ]
        complete.return_value = GigaChatCompletion(content="По кликам число заказов неизвестно.", model="mock", prompt_tokens=10, completion_tokens=5, total_tokens=15)

        respond_to_message(user_message=message)

        self.assertEqual(search.call_count, 2)
        self.assertTrue(search.call_args.kwargs["fallback"])
        self.assertEqual(search.call_args.kwargs["model"], "nvidia/llama-nemotron-embed-vl-1b-v2:free")
        self.assertIn("Клики не равны заказам", complete.call_args.args[0][0]["content"])

    @patch("apps.strategist.services.GigaChatProvider.complete")
    @patch("apps.strategist.services._pinterest_analytics_answer", return_value="Проверенные показатели")
    def test_followup_keeps_account_and_exact_dates_with_multiple_accounts(self, analytics, complete):
        user = get_user_model().objects.create_user("followup-owner")
        workspace = Workspace.objects.create(name="Followup", slug="followup", created_by=user)
        business = Business.objects.create(workspace=workspace, name="Sample", slug="sample")
        for username in ("first", "second"):
            PinterestAccount.objects.create(business=business, connected_by=user, pinterest_user_id=username,
                username=username, access_token_encrypted="unused", access_token_expires_at=timezone.now() + timedelta(days=1))
        conversation = AIConversation.objects.create(business=business, created_by=user)
        AIMessage.objects.create(conversation=conversation, role="ASSISTANT", provider="pinterest-api", model="direct-read",
            content="Органика @second\nПериод: 2026-09-01 — 2026-09-07 · Pinterest API")
        message = AIMessage.objects.create(conversation=conversation, role="USER", content="А ГДЕ ВЫВОДЫ? ЧТО ХОРОШО ЧТО ПЛОХО? КАК УЛУЧШИТЬ?")
        answer = respond_to_message(user_message=message)
        self.assertEqual(answer.content, "Проверенные показатели")
        self.assertEqual(analytics.call_args.kwargs["account"].username, "second")
        self.assertEqual(analytics.call_args.kwargs["start_date"], date(2026, 9, 1))
        self.assertEqual(analytics.call_args.kwargs["end_date"], date(2026, 9, 7))
        complete.assert_not_called()


    @patch("apps.strategist.services.search_knowledge", side_effect=RuntimeError("embedding unavailable"))
    @patch("apps.strategist.services.GigaChatProvider.complete")
    def test_embedding_failure_uses_local_case_and_gates_stored_answer(self, complete, search):
        user = get_user_model().objects.create_user("local-case-owner")
        workspace = Workspace.objects.create(name="Local case", slug="local-case", created_by=user)
        business = Business.objects.create(workspace=workspace, name="Case", slug="case")
        conversation = AIConversation.objects.create(business=business, created_by=user)
        message = AIMessage.objects.create(conversation=conversation, role="USER", content="Приведи практический кейс роста исходящих кликов")
        complete.return_value = GigaChatCompletion(content="Проверьте целевую ссылку.\n\nСоздайте карусель с опросом.", model="mock", prompt_tokens=10, completion_tokens=5, total_tokens=15)
        answer = respond_to_message(user_message=message)
        system = complete.call_args.args[0][0]["content"]
        self.assertIn("pink-seed-marketing", system)
        self.assertIn("эффект отдельного действия не выделен", system)
        self.assertIn("Проверьте целевую ссылку", answer.content)
        self.assertNotIn("Создайте карусель", answer.content)
        self.assertEqual(answer.total_tokens, 15)
