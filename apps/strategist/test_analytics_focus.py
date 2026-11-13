"""A question about one Pinterest metric gets that metric, not the full report."""
import json
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.pinterest.models import PinterestAccount
from apps.strategist.models import AIConversation, AIMessage
from apps.strategist.services import _requested_metrics
from apps.workspaces.models import Membership, Workspace

CURRENT = {"IMPRESSION": 1394708, "PIN_CLICK": 41746, "PIN_CLICK_RATE": 0.0299, "SAVE": 3978,
           "SAVE_RATE": 0.0029, "OUTBOUND_CLICK": 2212, "VIDEO_START": 54335, "VIDEO_MRC_VIEW": 34580}
PREVIOUS = {"IMPRESSION": 1870410, "PIN_CLICK": 60015, "SAVE": 5695, "OUTBOUND_CLICK": 3126}


class RequestedMetricsTest(SimpleTestCase):
    def test_named_metrics(self):
        for text, expected in (
            ("за месяц статистику по переходам на другие ресурсы аккаунта @PinAutomation", ("OUTBOUND_CLICK",)),
            ("сколько исходящих кликов за неделю", ("OUTBOUND_CLICK",)),
            ("покажи показы за 30 дней", ("IMPRESSION",)),
            ("сколько сохранений", ("SAVE",)),
            ("открытия пина за месяц", ("PIN_CLICK",)),
            ("клики по пинам за месяц", ("PIN_CLICK",)),
            ("показы и сохранения за 30 дней", ("IMPRESSION", "SAVE")),
            ("статистика по видео за месяц", ("VIDEO",)),
        ):
            with self.subTest(text=text):
                self.assertEqual(_requested_metrics(text), expected)

    def test_general_requests_keep_the_full_report(self):
        for text in ("статистика аккаунта за месяц", "покажи всю статистику за 30 дней",
                     "полный отчёт по показам", "подробно по переходам", "как дела у аккаунта"):
            with self.subTest(text=text):
                self.assertIsNone(_requested_metrics(text))


class FocusedAnswerTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("focus-owner")
        workspace = Workspace.objects.create(name="Focus", slug="focus", created_by=self.user)
        Membership.objects.create(workspace=workspace, user=self.user, role=Membership.Role.OWNER)
        business = Business.objects.create(workspace=workspace, name="Shop", slug="shop", goals="Продажи")
        PinterestAccount.objects.create(
            business=business, connected_by=self.user, username="PinAutomation", pinterest_user_id="1",
            access_token_encrypted="mock-only", access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED)
        self.conversation = AIConversation.objects.create(business=business, created_by=self.user)
        self.url = reverse("strategist:session", kwargs={"workspace_slug": "focus", "business_slug": "shop", "session_slug": self.conversation.slug})
        self.client.force_login(self.user)
        self.enterContext(patch("apps.strategist.services.fresh_snapshot_resource", return_value=None))
        self.enterContext(patch("apps.strategist.services.GigaChatProvider.complete", side_effect=AssertionError("no model")))

        def read(**kwargs):
            options = kwargs["arguments"]["options"] if "arguments" in kwargs else kwargs.get("options", {})
            start = options.get("start_date", "")
            return {"x": {"summary_metrics": CURRENT if start >= str(date.today() - timedelta(days=31)) else PREVIOUS}}
        self.read = self.enterContext(patch("apps.strategist.services._read_pinterest_resource", side_effect=read))

    def say(self, text):
        response = self.client.post(self.url, {"message": text}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.url = response.json()["conversation_url"]
        return self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at").content

    def test_one_metric_question_returns_only_that_metric(self):
        answer = self.say("за 30 дней статистику по переходам на другие ресурсы аккаунта @PinAutomation")
        self.assertIn("исходящие клики — 2212", answer)
        self.assertIn("исходящие клики 3126 → 2212 (-914; -29,24%)", answer)
        for noise in ("показы", "сохранения", "открытия пина", "Видео", "Что сделать", "Максимум показов",
                      "Для цели продаж", "Определения показателей"):
            self.assertNotIn(noise, answer)
        self.assertIn("покажи всю статистику", answer)

    def test_general_question_still_gets_the_full_report(self):
        answer = self.say("статистика @PinAutomation за 30 дней")
        for part in ("показы", "сохранения", "исходящие клики", "Видео"):
            self.assertIn(part, answer)

    def test_period_choice_keeps_the_original_focus(self):
        first = self.say("статистику по сохранениям аккаунта @PinAutomation")
        self.assertIn("Выбери период", first)
        answer = self.say("30")
        self.assertIn("сохранения —", answer)
        self.assertNotIn("исходящие клики", answer)
        self.assertNotIn("Видео", answer)

    def test_full_report_on_request_after_focused_answer(self):
        self.say("за 30 дней статистика по показам @PinAutomation")
        answer = self.say("покажи всю статистику @PinAutomation за 30 дней")
        for part in ("сохранения", "исходящие клики", "Видео"):
            self.assertIn(part, answer)
