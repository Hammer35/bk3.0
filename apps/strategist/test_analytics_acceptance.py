"""Analytics acceptance at the authenticated chat boundary; no external calls."""

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
from apps.workspaces.models import Membership, Workspace


class AnalyticsAcceptanceTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("analytics-owner")
        workspace = Workspace.objects.create(name="Analytics", slug="analytics", created_by=self.user)
        Membership.objects.create(workspace=workspace, user=self.user, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=workspace, name="Shop", slug="shop", goals="Продажи")
        self.accounts = []
        for name in ("alpha", "beta"):
            self.accounts.append(PinterestAccount.objects.create(
                business=self.business, connected_by=self.user, username=name,
                pinterest_user_id=name, access_token_encrypted="mock-only",
                access_token_expires_at=timezone.now() + timedelta(days=1),
                granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED,
            ))
        self.conversation = AIConversation.objects.create(business=self.business, created_by=self.user)
        self.url = reverse("strategist:session", kwargs={
            "workspace_slug": workspace.slug, "business_slug": self.business.slug,
            "session_slug": self.conversation.slug,
        })
        self.client.force_login(self.user)
        self.read = self.enterContext(patch("apps.strategist.services.read_pinterest_data"))
        self.enterContext(patch("apps.strategist.services.fresh_snapshot_resource", return_value=None))
        self.complete = self.enterContext(patch("apps.strategist.services.GigaChatProvider.complete",
                                              side_effect=AssertionError("Unexpected LLM request")))

    def ask(self, question):
        response = self.client.post(self.url, {"message": question}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.conversation.refresh_from_db()
        self.url = reverse("strategist:session", kwargs={
            "workspace_slug": self.business.workspace.slug, "business_slug": self.business.slug,
            "session_slug": self.conversation.slug,
        })
        answer = self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")
        self.assertIn(answer.content.splitlines()[0], response.json()["messages_html"])
        self.complete.assert_not_called()
        return answer

    def report(self, clicks=12):
        return {"all": {"summary_metrics": {"IMPRESSION": 100, "OUTBOUND_CLICK": clicks}, "daily_metrics": []}}

    def test_two_accounts_require_selection(self):
        answer = self.ask("Покажи статистику Pinterest за 7 дней")
        self.assertIn("Уточни профиль", answer.content)
        self.assertIn("@alpha", answer.content)
        self.assertIn("@beta", answer.content)
        self.read.assert_not_called()

    def test_unknown_account_does_not_fall_back(self):
        answer = self.ask("Статистика @unknown за 7 дней")
        self.assertIn("не подключён", answer.content)
        self.read.assert_not_called()

    def test_selected_account_and_equal_periods(self):
        self.read.side_effect = [self.report(12), self.report(6)]
        answer = self.ask("Статистика @beta за 7 дней")
        self.assertEqual((answer.provider, answer.model), ("pinterest-api", "direct-read"))
        self.assertIn("исходящие клики — 12", answer.content)
        self.assertIn("+100,00%", answer.content)
        self.assertIn("текущая статистика их не подтверждает", answer.content)
        self.assertEqual(self.read.call_count, 2)
        periods = []
        for call in self.read.call_args_list:
            arguments = call.kwargs["arguments"]
            self.assertEqual(arguments["account_key"], str(self.accounts[1].public_id))
            options = json.loads(arguments["options"])
            self.assertEqual(options["content_type"], "ORGANIC")
            periods.append((timezone.datetime.fromisoformat(options["start_date"]).date(),
                            timezone.datetime.fromisoformat(options["end_date"]).date()))
        self.assertEqual((periods[0][1] - periods[0][0]).days, 6)
        self.assertEqual((periods[1][1] - periods[1][0]).days, 6)
        self.assertEqual(periods[1][1] + timedelta(days=1), periods[0][0])

    def test_period_selection_keeps_account(self):
        self.ask("Покажи статистику @beta")
        self.read.assert_not_called()
        self.read.side_effect = [self.report(), self.report()]
        self.ask("7")
        for call in self.read.call_args_list:
            self.assertEqual(call.kwargs["arguments"]["account_key"], str(self.accounts[1].public_id))

    def test_explicit_account_switch(self):
        self.read.side_effect = [self.report()] * 4
        self.ask("Статистика @alpha за 7 дней")
        self.ask("Статистика @beta за 7 дней")
        keys = [call.kwargs["arguments"]["account_key"] for call in self.read.call_args_list]
        self.assertEqual(keys, [str(self.accounts[0].public_id)] * 2 + [str(self.accounts[1].public_id)] * 2)

    def test_api_failure_is_not_zero_data(self):
        self.read.return_value = {"error": "Pinterest временно недоступен. Повтори позже."}
        answer = self.ask("Статистика @alpha за 7 дней")
        self.assertIn("Не удалось получить статистику", answer.content)
        self.assertNotIn("клики — 0", answer.content)
        self.assertEqual(self.read.call_count, 1)

    def test_previous_period_failure_does_not_invent_change(self):
        self.read.side_effect = [self.report(), {"error": "Недоступно"}]
        answer = self.ask("Статистика @alpha за 7 дней")
        self.assertIn("исходящие клики — 12", answer.content)
        self.assertIn("Сравнение с предыдущим равным периодом недоступно", answer.content)
        self.assertNotIn("+100", answer.content)

    def test_foreign_business_account_is_not_read(self):
        other = Business.objects.create(workspace=self.business.workspace, name="Other", slug="other")
        self.accounts[1].business = other
        self.accounts[1].save(update_fields=["business"])
        answer = self.ask("Статистика @beta за 7 дней")
        self.assertIn("не подключён", answer.content)
        self.read.assert_not_called()

    def test_malformed_api_response_is_not_interpreted(self):
        self.read.side_effect = [{"unexpected": [123]}, self.report()]
        answer = self.ask("Статистика @alpha за 7 дней")
        self.assertIn("неподдерживаемом формате", answer.content)
        self.assertNotIn("клики —", answer.content)

    def test_orders_after_analytics_are_not_inferred_from_clicks(self):
        self.read.side_effect = [self.report(), self.report()]
        self.ask("Статистика @alpha за 7 дней")
        self.read.reset_mock()
        answer = self.ask("Сколько было заказов по 12 исходящим кликам Pinterest?")
        self.assertIn("неизвестно", answer.content)
        self.read.assert_not_called()
