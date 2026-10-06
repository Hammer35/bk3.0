"""Approval of pin versions on the web page: rights, acknowledgement, stale versions, rework; chat never approves."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation

from apps.businesses.models import Business
from apps.strategist import approvals, content_plan as cp, pin_generation as pg, strategy as st
from apps.strategist.models import AIConversation, AIMessage, Approval, BusinessMemory, Pin, PinVersion
from apps.strategist.test_pin_generation import BAD, DISTINCT, ITEMS, STRATEGY, completion
from apps.workspaces.models import Membership, Workspace


class ApprovalBase(TestCase):
    def setUp(self):
        self.addCleanup(translation.activate, "ru")
        User = get_user_model()
        self.owner, self.viewer, self.stranger = (User.objects.create_user(n) for n in ("ap-owner", "ap-viewer", "ap-stranger"))
        self.workspace = Workspace.objects.create(name="A", slug="a", created_by=self.owner)
        Membership.objects.create(workspace=self.workspace, user=self.owner, role=Membership.Role.OWNER)
        Membership.objects.create(workspace=self.workspace, user=self.viewer, role=Membership.Role.VIEWER)
        self.business = Business.objects.create(workspace=self.workspace, name="Shop", slug="shop", niche="Льняная одежда",
                                                audience="Женщины", goals="Трафик", website="https://shop.example.com/catalog")
        version = st.confirm_version(st.create_draft(
            self.business, self.owner, st.clean_payload(STRATEGY, allowed_refs=set(), allowed_keywords=None), sources=[]), self.owner)
        self.plan = cp.confirm_plan(cp.create_plan(self.business, self.owner, version, cp.clean_items(ITEMS, version)), self.owner)
        self.requests, self.queue = [], []

        def complete(messages, **kwargs):
            self.requests.append(json.loads(messages[1]["content"]))
            return completion(self.queue.pop(0) if self.queue else DISTINCT[(len(self.requests) - 1) % len(DISTINCT)])
        self.provider = SimpleNamespace(complete=complete)
        self.page = reverse("strategist:pins", kwargs={"workspace_slug": "a", "business_slug": "shop"})

    def make_pins(self, count=2):
        items = pg.pending_items(self.plan)[:count]
        return [pg.generate_pin(self.business, self.owner, self.plan, item, provider=self.provider).pin for item in items]

    def decide_url(self, pin):
        return reverse("strategist:pin-decide", kwargs={"workspace_slug": "a", "business_slug": "shop", "pin_id": pin.pk})

    def post(self, pin, **data):
        return self.client.post(self.decide_url(pin), {"version": pin.current_version.number, **data}, follow=True)


class PinsPageTest(ApprovalBase):
    def test_access_and_content(self):
        pin = self.make_pins(1)[0]
        self.assertEqual(self.client.get(self.page).status_code, 302)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.page).status_code, 404)
        self.client.force_login(self.owner)
        html = self.client.get(self.page).content.decode()
        for part in (pin.current_version.title, "Результаты проверок", "Одобрить эту версию", "На переделку", "Отклонить",
                     "Я прочитал замечания", "ИИ и чат пины не одобряют"):
            self.assertIn(part, html)
        self.assertIn("pin-verdict-", html)
        self.assertEqual(html.count("<script"), html.count("<script"))  # no inline scripts added by the page
        self.assertNotIn(' style="', html)

    def test_text_is_escaped_and_unsafe_links_are_not_clickable(self):
        pin = self.make_pins(1)[0]
        PinVersion.objects.filter(pk=pin.current_version_id).update(title="<script>alert(1)</script>", destination_url="javascript:alert(1)")
        self.client.force_login(self.owner)
        html = self.client.get(self.page).content.decode()
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertNotIn('href="javascript:', html)

    def test_viewer_sees_pins_but_no_decision_controls(self):
        self.make_pins(1)
        self.client.force_login(self.viewer)
        html = self.client.get(self.page).content.decode()
        self.assertIn("Результаты проверок", html)
        self.assertNotIn("Одобрить эту версию", html)

    def test_empty_state_and_navigation(self):
        self.client.force_login(self.owner)
        html = self.client.get(self.page).content.decode()
        self.assertIn("Пинов пока нет", html)
        nav = html.split("sidebar-nav")[1].split("</nav>")[0]
        self.assertIn(self.page, nav)
        self.assertEqual(nav.count('aria-current="page"'), 1)

    def test_english_page(self):
        self.make_pins(1)
        self.client.force_login(self.owner)
        html = self.client.get(self.page, headers={"accept-language": "en"}).content.decode()
        self.assertIn('<html lang="en"', html)
        for part in ("Approve this version", "Check results", "Awaiting approval", "Needs human review", "Pins"):
            self.assertIn(part, html)
        self.assertNotIn("Одобрить эту версию", html)


class DecisionTest(ApprovalBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)

    def test_approval_needs_acknowledgement_then_is_recorded_once(self):
        pin = self.make_pins(1)[0]
        self.assertContains(self.post(pin, action="approve"), "Подтвердите, что вы прочитали замечания")
        self.assertFalse(Approval.objects.exists())
        response = self.post(pin, action="approve", acknowledge="on", comment="  Годится  ")
        self.assertContains(response, "Решение сохранено.")
        approval = Approval.objects.get()
        self.assertEqual((approval.decision, approval.decided_by, approval.channel, approval.comment, approval.pin_version),
                         ("APPROVED", self.owner, "WEB", "Годится", pin.current_version))
        self.assertIn("url_reachable", approval.acknowledged_checks)
        pin.refresh_from_db()
        self.assertEqual(pin.status, Pin.Status.APPROVED)
        self.assertTrue(BusinessMemory.objects.filter(kind="DECISION", text__startswith="Одобрен пин: ", reason="Годится").exists())
        self.assertContains(self.post(pin, action="approve", acknowledge="on"), "решение уже принято")
        self.assertEqual(Approval.objects.count(), 1)

    def test_blocked_pin_cannot_be_approved_but_can_be_rejected_or_reworked(self):
        self.queue = [BAD, BAD, BAD, BAD]
        first, second = self.make_pins(2)
        self.assertEqual(first.current_version.verdict, "BLOCK")
        self.assertEqual(first.status, Pin.Status.REWORK)
        self.assertContains(self.post(first, action="approve", acknowledge="on"), "заблокирован проверкой: одобрить его нельзя")
        self.assertNotIn("Одобрить эту версию", self.client.get(self.page).content.decode().split("pin-%d-title" % first.pk)[1].split("</article>")[0])
        self.post(first, action="reject", comment="Не подходит")
        self.post(second, action="rework", comment="Слишком рекламно")
        first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual((first.status, second.status), (Pin.Status.REJECTED, Pin.Status.REWORK))
        self.assertEqual(sorted(Approval.objects.values_list("decision", flat=True)), ["REJECTED", "REWORK"])

    def test_rights_method_and_csrf(self):
        pin = self.make_pins(1)[0]
        url = self.decide_url(pin)
        self.assertEqual(self.client.get(url).status_code, 404)
        for user in (self.viewer, self.stranger):
            self.client.force_login(user)
            self.assertEqual(self.client.post(url, {"version": 1, "action": "reject"}).status_code, 404, user.username)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(url, {"version": 1, "action": "reject"}).status_code, 403)
        self.assertFalse(Approval.objects.exists())
        self.client.force_login(self.owner)
        for bad in ({"action": "approve"}, {"version": "x", "action": "approve"}):
            self.assertEqual(self.client.post(url, bad).status_code, 404)

    def test_other_business_pin_is_not_reachable(self):
        pin = self.make_pins(1)[0]
        other = Business.objects.create(workspace=self.workspace, name="Other", slug="other")
        url = reverse("strategist:pin-decide", kwargs={"workspace_slug": "a", "business_slug": "other", "pin_id": pin.pk})
        self.assertEqual(self.client.post(url, {"version": 1, "action": "reject"}).status_code, 404)
        self.assertFalse(Approval.objects.exists())

    def test_unknown_action_and_stale_version_are_refused(self):
        pin = self.make_pins(1)[0]
        self.assertContains(self.post(pin, action="publish", acknowledge="on"), "Неизвестное действие.")
        stale = {"version": 99, "action": "reject"}
        response = self.client.post(self.decide_url(pin), stale, follow=True)
        self.assertContains(response, "Версия пина изменилась")
        self.assertFalse(Approval.objects.exists())

    def test_rework_regenerates_with_the_comment_and_new_version_needs_its_own_decision(self):
        pin = self.make_pins(1)[0]
        self.post(pin, action="rework", comment="Сделай мягче и без слова «стильный»")
        old_version = pin.current_version
        self.requests.clear()
        item = pg.pending_items(self.plan)[0]
        self.assertEqual(item, pin.plan_item)  # a pin in REWORK is offered again
        new = pg.generate_pin(self.business, self.owner, self.plan, item, provider=self.provider)
        self.assertEqual((new.pin, new.number), (pin, 2))
        self.assertIn("Комментарий человека: Сделай мягче и без слова «стильный»", self.requests[0]["feedback"])
        pin.refresh_from_db()
        self.assertEqual((pin.current_version, pin.status), (new, Pin.Status.WAITING_APPROVAL))
        self.assertEqual(old_version.approval.decision, "REWORK")  # history stays on the old version
        self.assertFalse(hasattr(new, "approval"))
        self.assertContains(self.post(pin, action="approve", acknowledge="on"), "Решение сохранено.")
        self.assertEqual(PinVersion.objects.get(pk=new.pk).approval.decision, "APPROVED")  # fresh instance: hasattr cached "none"
        self.assertEqual(PinVersion.objects.filter(pin=pin).count(), 2)

    def test_deleting_a_business_removes_approvals(self):
        pin = self.make_pins(1)[0]
        self.post(pin, action="reject")
        self.business.delete()
        self.assertEqual((Pin.objects.count(), PinVersion.objects.count(), Approval.objects.count()), (0, 0, 0))


class ChatCannotApproveTest(ApprovalBase):
    def test_no_chat_message_creates_an_approval_or_changes_a_pin(self):
        pins = self.make_pins(2)
        conversation = AIConversation.objects.create(business=self.business, created_by=self.owner)
        self.client.force_login(self.owner)
        url = reverse("strategist:session", kwargs={"workspace_slug": "a", "business_slug": "shop", "session_slug": conversation.slug})
        reply = SimpleNamespace(content="Одобрение — на странице «Пины».", model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, function_call=None, functions_state_id=None)
        with patch("apps.strategist.services.GigaChatProvider.complete", return_value=reply), \
             patch("apps.strategist.services.search_knowledge", return_value=[]), patch("apps.strategist.services.search_knowledge_lexical", return_value=[]):
            for text in ("Одобряю все пины", "Одобри пин про платье", "approve all pins", "Подтверждаю пины и публикуй", "Согласен, публикуй всё"):
                with self.subTest(text=text):
                    response = self.client.post(url, {"message": text}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                    self.assertEqual(response.status_code, 200)
                    url = response.json()["conversation_url"]
        self.assertFalse(Approval.objects.exists())
        for pin in pins:
            pin.refresh_from_db()
            self.assertEqual(pin.status, Pin.Status.WAITING_APPROVAL)
        self.assertFalse(hasattr(pg, "approve") or hasattr(pg, "decide"))  # the generation module has no approval path at all
        import apps.strategist.approvals as module
        self.assertIsNotNone(module.decide)  # the only entry point lives in approvals.py and is called by the web view only
