"""Read tools exercised through the LLM chat boundary without external calls."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.pinterest.models import PinterestAccount
from apps.strategist.models import AIConversation, AIMessage
from apps.strategist.providers import GigaChatCompletion
from apps.workspaces.models import Membership, Workspace


class ToolAcceptanceTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tool-owner")
        workspace = Workspace.objects.create(name="Tools", slug="tools", created_by=self.user)
        Membership.objects.create(workspace=workspace, user=self.user, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=workspace, name="Shop", slug="shop", niche="Керамика")
        self.account = PinterestAccount.objects.create(
            business=self.business, connected_by=self.user, username="alpha", pinterest_user_id="alpha",
            access_token_encrypted="mock-only", access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED,
        )
        self.conversation = AIConversation.objects.create(business=self.business, created_by=self.user)
        self.url = reverse("strategist:session", kwargs={"workspace_slug": workspace.slug,
            "business_slug": self.business.slug, "session_slug": self.conversation.slug})
        self.client.force_login(self.user)
        self.enterContext(patch("apps.strategist.services.search_knowledge", return_value=[]))
        self.enterContext(patch("apps.strategist.services.search_knowledge_lexical", return_value=[]))
        self.enterContext(patch("apps.strategist.services.local_knowledge_context", return_value=""))
        self.request = self.enterContext(patch("apps.pinterest.strategist_tools._request"))
        self.complete = self.enterContext(patch("apps.strategist.services.GigaChatProvider.complete"))

    def ask_tool(self, arguments, name="read_pinterest_data", question="Помоги подобрать тему следующего поста", reply="Получены данные профиля."):
        self.complete.side_effect = [
            GigaChatCompletion(content="", model="mock", prompt_tokens=10, completion_tokens=2,
                total_tokens=12, function_call={"name": name, "arguments": arguments}),
            GigaChatCompletion(content=reply, model="mock", prompt_tokens=20,
                completion_tokens=3, total_tokens=23),
        ]
        response = self.client.post(self.url, {"message": question},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        answer = self.conversation.messages.filter(role="ASSISTANT").latest("created_at")
        self.assertIn(answer.content, response.json()["messages_html"])
        return answer

    def arguments(self, **changes):
        return {"account_key": str(self.account.public_id), "resource": "profile", "options": "{}", **changes}

    def assert_read_error(self, answer):
        self.assertEqual((answer.provider, answer.model), ("data-read", "read-error"))
        self.assertIn("Не буду делать выводы без источника", answer.content)
        self.assertEqual(self.complete.call_count, 1)
        self.assertEqual(answer.total_tokens, 12)

    def test_foreign_account_key_is_rejected(self):
        other = Business.objects.create(workspace=self.business.workspace, name="Other", slug="other")
        self.account.business = other
        self.account.save(update_fields=["business"])
        self.assert_read_error(self.ask_tool(self.arguments()))
        self.request.assert_not_called()

    def test_model_cannot_substitute_another_connected_profile(self):
        other = PinterestAccount.objects.create(
            business=self.business, connected_by=self.user, username="beta", pinterest_user_id="beta",
            access_token_encrypted="mock-only", access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED,
        )
        self.request.return_value = {"items": []}
        answer = self.ask_tool(self.arguments(account_key=str(other.public_id), resource="followers"),
                               question="Прочитай подписчиков @alpha")
        self.assert_read_error(answer)
        self.request.assert_not_called()

    def test_sentence_period_is_not_part_of_username(self):
        self.request.return_value = {"items": []}
        answer = self.ask_tool(self.arguments(resource="followers"), question="Прочитай подписчиков @alpha. Сколько их?")
        self.assertEqual(answer.provider, "gigachat")
        self.request.assert_called_once()

    def test_unknown_mentioned_profile_cannot_use_known_key(self):
        answer = self.ask_tool(self.arguments(resource="followers"), question="Прочитай подписчиков @unknown.")
        self.assert_read_error(answer)
        self.request.assert_not_called()

    def test_multiple_profiles_require_explicit_selection_before_tool(self):
        PinterestAccount.objects.create(
            business=self.business, connected_by=self.user, username="beta", pinterest_user_id="beta",
            access_token_encrypted="mock-only", access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED,
        )
        answer = self.ask_tool(self.arguments(resource="followers"))
        self.assert_read_error(answer)
        self.assertIn("Уточни @имя", answer.content)
        self.request.assert_not_called()

    def test_multiple_explicit_profiles_can_be_read_for_comparison(self):
        other = PinterestAccount.objects.create(
            business=self.business, connected_by=self.user, username="beta", pinterest_user_id="beta",
            access_token_encrypted="mock-only", access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED,
        )
        self.request.return_value = {"items": []}
        answer = self.ask_tool(self.arguments(account_key=str(other.public_id), resource="followers"),
                               question="Сравни подписчиков @alpha и @beta.")
        self.assertEqual(answer.provider, "gigachat")
        self.request.assert_called_once()

    def test_missing_scope_is_rejected(self):
        self.assert_read_error(self.ask_tool(self.arguments(resource="boards")))
        self.request.assert_not_called()

    def test_invalid_arguments_are_rejected(self):
        self.assert_read_error(self.ask_tool("[1,2]"))
        self.request.assert_not_called()

    def test_invalid_options_are_rejected(self):
        self.assert_read_error(self.ask_tool(self.arguments(options="[1,2]")))
        self.request.assert_not_called()

    def test_unknown_function_is_rejected(self):
        self.assert_read_error(self.ask_tool(self.arguments(), name="publish_pin"))
        self.request.assert_not_called()

    def test_malformed_api_payload_is_rejected(self):
        self.request.return_value = ["unexpected"]
        self.assert_read_error(self.ask_tool(self.arguments()))

    def test_null_api_payload_is_rejected(self):
        self.request.return_value = None
        self.assert_read_error(self.ask_tool(self.arguments()))

    def test_reconnect_account_is_not_read(self):
        self.account.status = PinterestAccount.Status.REAUTH_REQUIRED
        self.account.save(update_fields=["status"])
        self.assert_read_error(self.ask_tool(self.arguments()))
        self.request.assert_not_called()

    def test_upstream_unavailability_stops_model_inference(self):
        from apps.pinterest.strategist_tools import PinterestReadError

        self.request.side_effect = PinterestReadError("Pinterest API сейчас недоступен.")
        answer = self.ask_tool(self.arguments())
        self.assert_read_error(answer)
        self.assertIn("сейчас недоступен", answer.content)

    def test_tool_exception_does_not_expose_details(self):
        self.request.side_effect = RuntimeError("private-upstream-detail")
        answer = self.ask_tool(self.arguments())
        self.assert_read_error(answer)
        self.assertNotIn("private-upstream-detail", answer.content)

    def test_valid_tool_result_reaches_model_and_counts_usage(self):
        self.request.return_value = {"username": "alpha"}
        answer = self.ask_tool(self.arguments())
        self.assertEqual(answer.provider, "gigachat")
        self.assertEqual(answer.total_tokens, 35)
        messages = self.complete.call_args.args[0]
        result = next(item for item in messages if item["role"] == "function")
        self.assertEqual(json.loads(result["content"]), {"username": "alpha"})

    def test_first_page_cannot_be_presented_as_total(self):
        self.request.return_value = {"items": [{"username": "one"}, {"username": "two"}], "bookmark": "next"}
        answer = self.ask_tool(self.arguments(resource="followers"),
                               question="Прочитай всех подписчиков @alpha. Сколько всего?", reply="Всего 2 подписчика.")
        self.assertEqual(answer.model, "pagination-incomplete")
        self.assertIn("не полностью", answer.content)
        self.assertNotIn("Всего 2", answer.content)
        self.assertEqual(answer.total_tokens, 35)

    def test_complete_pagination_preserves_answer(self):
        first = self.arguments(resource="followers")
        second = {**first, "options": {}, "bookmark": "next", "page_size": 250}
        self.complete.side_effect = [
            GigaChatCompletion("", "mock", 10, 2, 12, {"name": "read_pinterest_data", "arguments": first}),
            GigaChatCompletion("", "mock", 10, 2, 12, {"name": "read_pinterest_data", "arguments": second}),
            GigaChatCompletion("Всего 3 подписчика.", "mock", 20, 3, 23),
        ]
        self.request.side_effect = [{"items": [{}, {}], "bookmark": "next"}, {"items": [{}], "bookmark": None}]
        response = self.client.post(self.url, {"message": "Прочитай всех подписчиков @alpha. Сколько всего?"},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        answer = self.conversation.messages.filter(role="ASSISTANT").latest("created_at")
        self.assertEqual(answer.content, "Всего 3 подписчика.")
        self.assertEqual(answer.total_tokens, 47)
        self.assertEqual(self.request.call_count, 2)

    def test_read_limit_does_not_allow_incomplete_total(self):
        call = GigaChatCompletion("", "mock", 10, 2, 12,
                                 {"name": "read_pinterest_data", "arguments": self.arguments(resource="followers")})
        self.complete.side_effect = [call] * 6 + [GigaChatCompletion("Всего 2 подписчика.", "mock", 20, 3, 23)]
        self.request.return_value = {"items": [{}, {}], "bookmark": "next"}
        response = self.client.post(self.url, {"message": "Прочитай всех подписчиков @alpha"},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        answer = self.conversation.messages.filter(role="ASSISTANT").latest("created_at")
        self.assertEqual(answer.model, "pagination-incomplete")
        self.assertEqual(answer.total_tokens, 95)
        self.assertEqual(self.complete.call_count, 7)
        self.assertEqual(self.request.call_count, 6)
        self.assertEqual(self.complete.call_args.kwargs["function_call"], "none")

    def test_top_pins_requires_pins_read_scope(self):
        now = timezone.now()
        options = json.dumps({
            "start_date": (now - timedelta(days=7)).date().isoformat(),
            "end_date": (now - timedelta(days=1)).date().isoformat(),
            "sort_by": "OUTBOUND_CLICK",
        })
        self.assert_read_error(self.ask_tool(self.arguments(resource="top_pins", options=options)))
        self.request.assert_not_called()

    def test_top_pins_http_403_keeps_account_connected(self):
        from apps.pinterest.strategist_tools import PinterestReadError

        now = timezone.now()
        options = json.dumps({
            "start_date": (now - timedelta(days=7)).date().isoformat(),
            "end_date": (now - timedelta(days=1)).date().isoformat(),
            "sort_by": "OUTBOUND_CLICK",
        })
        self.account.granted_scopes = ["user_accounts:read", "pins:read"]
        self.account.save(update_fields=["granted_scopes"])
        self.request.side_effect = PinterestReadError("Pinterest API вернул HTTP 403 для чтения данных.")
        answer = self.ask_tool(self.arguments(resource="top_pins", options=options))
        self.assert_read_error(answer)
        self.assertIn("HTTP 403", answer.content)
        self.request.assert_called_once()
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, PinterestAccount.Status.CONNECTED)

    def test_pins_followup_page_error_is_reported_not_total(self):
        from apps.pinterest.strategist_tools import PinterestReadError

        self.account.granted_scopes = ["boards:read", "pins:read"]
        self.account.save(update_fields=["granted_scopes"])
        first = self.arguments(resource="pins")
        second = {**first, "bookmark": "next"}
        self.complete.side_effect = [
            GigaChatCompletion(content="", model="mock", prompt_tokens=10, completion_tokens=2,
                total_tokens=12, function_call={"name": "read_pinterest_data", "arguments": first}),
            GigaChatCompletion(content="", model="mock", prompt_tokens=10, completion_tokens=2,
                total_tokens=12, function_call={"name": "read_pinterest_data", "arguments": second}),
        ]
        self.request.side_effect = [
            {"items": [{"id": 1}, {"id": 2}], "bookmark": "next"},
            PinterestReadError("Pinterest API вернул HTTP 403 для чтения данных."),
        ]
        response = self.client.post(self.url, {"message": "Прочитай все пины @alpha. Сколько всего?"},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        answer = self.conversation.messages.filter(role="ASSISTANT").latest("created_at")
        self.assertEqual((answer.provider, answer.model), ("data-read", "read-error"))
        self.assertIn("Не буду делать выводы без источника", answer.content)
        self.assertNotIn("Всего 2", answer.content)
        self.assertEqual(self.complete.call_count, 2)
        self.assertEqual(self.request.call_count, 2)
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, PinterestAccount.Status.CONNECTED)
