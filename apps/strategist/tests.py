from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.businesses.models import Business
from apps.strategist.models import AIConversation, AIMessage
from apps.strategist.model_catalog import TaskCapability
from apps.strategist.model_routing import GigaChatModelRouter
from apps.strategist.providers import (
    GigaChatCompletion,
    GigaChatProvider,
    GigaChatRequestError,
)
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
