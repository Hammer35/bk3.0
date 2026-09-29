from unittest.mock import patch
from datetime import timedelta
import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.pinterest.models import PinterestAccount
from apps.strategist.models import AIConversation, AIMessage
from apps.strategist.model_catalog import TaskCapability
from apps.strategist.model_routing import GigaChatModelRouter
from apps.strategist.providers import (
    GigaChatCompletion,
    GigaChatProvider,
    GigaChatRequestError,
)
from apps.strategist.services import _format_pinterest_analytics
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
        self.assertLess(len(answer.splitlines()), 8)

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
