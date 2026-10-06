"""PINTEREST_AI_DATA_TRANSFER_ENABLED controls whether Pinterest read tools reach the chat model."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.pinterest.models import PinterestAccount
from apps.strategist.models import AIConversation
from apps.strategist.providers import GigaChatCompletion
from apps.workspaces.models import Membership, Workspace

QUESTION = "Расскажи про тренды в Pinterest и дай идею поста"


class AiTransferSwitchTest(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("switch-owner")
        workspace = Workspace.objects.create(name="Switch", slug="switch", created_by=user)
        Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
        business = Business.objects.create(workspace=workspace, name="Shop", slug="shop", niche="Керамика")
        PinterestAccount.objects.create(
            business=business, connected_by=user, username="alpha", pinterest_user_id="alpha",
            access_token_encrypted="mock-only", access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED)
        conversation = AIConversation.objects.create(business=business, created_by=user)
        self.url = reverse("strategist:session", kwargs={"workspace_slug": "switch", "business_slug": "shop", "session_slug": conversation.slug})
        self.client.force_login(user)
        for target in ("search_knowledge", "search_knowledge_lexical"):
            self.enterContext(patch(f"apps.strategist.services.{target}", return_value=[]))
        self.enterContext(patch("apps.strategist.services.local_knowledge_context", return_value=""))
        self.request = self.enterContext(patch("apps.pinterest.strategist_tools._request"))
        self.complete = self.enterContext(patch(
            "apps.strategist.services.GigaChatProvider.complete",
            return_value=GigaChatCompletion(content="Общий совет.", model="mock", prompt_tokens=1, completion_tokens=1, total_tokens=2)))

    def ask(self):
        response = self.client.post(self.url, {"message": QUESTION}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        return self.complete.call_args

    def test_enabled_by_default_offers_the_read_tool(self):
        call = self.ask()
        self.assertTrue(call.kwargs["functions"])
        self.assertIn("read_pinterest_data", call.args[0][0]["content"])

    @override_settings(PINTEREST_AI_DATA_TRANSFER_ENABLED=False)
    def test_disabled_offers_no_tool_and_tells_the_model_not_to_claim_account_data(self):
        call = self.ask()
        self.assertFalse(call.kwargs["functions"])
        system = call.args[0][0]["content"]
        self.assertIn("отключена настройкой", system)
        self.assertIn("Не утверждай ничего о данных аккаунта Pinterest", system)
        self.assertNotIn("read_pinterest_data", system)
        self.assertNotIn("account_key", system)
        self.request.assert_not_called()
