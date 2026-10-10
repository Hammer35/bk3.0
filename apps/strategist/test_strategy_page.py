"""Strategy page: access, content, confirmation roles; no live API."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.businesses.models import Business
from apps.strategist import content_plan as cp
from apps.strategist import strategy as st
from apps.strategist.models import BusinessMemory, ContentPlan, StrategyVersion
from apps.workspaces.models import Membership, Workspace

RAW = {
    "goals": ["Получать трафик <b>на каталог</b>"], "priorities": ["Платья"],
    "keyword_clusters": [{"name": "Платья", "keywords": ["evening dress"]}],
    "recommended_boards": [{"name": "Вечерние платья", "purpose": "витрина"}],
    "content_directions": ["Образы с платьями"],
    "publishing_cadence": {"text": "по мере готовности"},
    "rationale": [{"claim": "Ниша — одежда", "basis": ["profile:niche"]}],
    "hypotheses": ["Зимой спрос выше"], "missing_data": ["Нет данных аккаунта"],
}


class StrategyPageTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("page-owner")
        self.viewer = User.objects.create_user("page-viewer")
        self.stranger = User.objects.create_user("page-stranger")
        self.workspace = Workspace.objects.create(name="W", slug="w", created_by=self.owner)
        Membership.objects.create(workspace=self.workspace, user=self.owner, role=Membership.Role.OWNER)
        Membership.objects.create(workspace=self.workspace, user=self.viewer, role=Membership.Role.VIEWER)
        self.business = Business.objects.create(workspace=self.workspace, name="Shop", slug="shop", niche="Одежда", audience="Женщины", goals="Трафик")
        self.url = reverse("strategist:strategy", kwargs={"workspace_slug": "w", "business_slug": "shop"})
        self.draft = st.create_draft(self.business, self.owner, st.clean_payload(RAW, allowed_refs={"profile:niche"}, allowed_keywords=None), sources=[])

    def confirm_url(self, number=1):
        return reverse("strategist:strategy-confirm", kwargs={"workspace_slug": "w", "business_slug": "shop", "number": number})

    def test_access_rules(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)  # anonymous goes to login
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.confirm_url()).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_profile_card_shows_real_business_facts_escaped(self):
        self.business.website = "https://example.com/shop"
        self.business.audience = "Женщины <i>25-45</i>"
        self.business.save()
        self.client.force_login(self.owner)
        html = self.client.get(self.url).content.decode()
        for part in ("Профиль бизнеса", "Одежда", "Женщины &lt;i&gt;25-45&lt;/i&gt;", 'href="https://example.com/shop"', "Трафик"):
            self.assertIn(part, html)
        self.assertNotIn("<i>25-45</i>", html)
        Business.objects.filter(pk=self.business.pk).update(website="javascript:alert(1)")  # bypasses form validation
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('href="javascript:', html)
        self.assertIn("javascript:alert(1)", html)  # shown as plain text, never as a link

    def test_empty_state_explains_missing_profile(self):
        StrategyVersion.objects.all().delete()
        self.business.audience = ""
        self.business.save()
        self.client.force_login(self.owner)
        html = self.client.get(self.url).content.decode()
        self.assertIn("Стратегии пока нет", html)
        self.assertIn("целевая аудитория", html)

    def test_draft_is_shown_escaped_with_sources_and_confirm_button(self):
        self.client.force_login(self.owner)
        html = self.client.get(self.url).content.decode()
        self.assertIn("Черновик, версия 1", html)
        self.assertIn("&lt;b&gt;на каталог&lt;/b&gt;", html)  # model/user text is never rendered as HTML
        self.assertNotIn("<b>на каталог</b>", html)
        self.assertIn("[профиль: ниша]", html)
        self.assertIn("гипотеза, данными не подтверждено", html)
        self.assertIn("Гипотезы (не подтверждены)", html)
        self.assertIn("Подтвердить стратегию", html)
        self.assertIn('csrfmiddlewaretoken', html)
        self.assertNotIn("<script", html.split("</header>")[1].split("</main>")[0] if "</main>" in html else html.split("</header>")[1])
        self.assertNotIn(' style="', html)

    def test_viewer_sees_but_cannot_confirm(self):
        self.client.force_login(self.viewer)
        html = self.client.get(self.url).content.decode()
        self.assertIn("Черновик, версия 1", html)
        self.assertNotIn("Подтвердить стратегию", html)
        self.assertEqual(self.client.post(self.confirm_url()).status_code, 404)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "DRAFT")

    def test_confirm_via_post_activates_and_records_decision(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.confirm_url()).status_code, 404)  # GET never confirms
        response = self.client.post(self.confirm_url(), follow=True)
        self.assertContains(response, "Стратегия подтверждена.")
        self.assertContains(response, "Действует")
        self.assertEqual(st.active_version(self.business).number, 1)
        self.assertTrue(BusinessMemory.objects.filter(kind="DECISION", text="Подтверждена стратегия, версия 1").exists())
        again = self.client.post(self.confirm_url(), follow=True)
        self.assertContains(again, "Подтвердить можно только актуальный черновик.")
        self.assertEqual(self.client.post(self.confirm_url(99)).status_code, 404)

    def test_other_business_numbers_are_not_reachable(self):
        other = Business.objects.create(workspace=self.workspace, name="Other", slug="other", niche="n", audience="a", goals="g")
        st.create_draft(other, self.owner, st.clean_payload(RAW, allowed_refs=set()), sources=[])
        self.client.force_login(self.owner)
        url = reverse("strategist:strategy-confirm", kwargs={"workspace_slug": "w", "business_slug": "shop", "number": 1})
        self.client.post(url)
        self.assertEqual(StrategyVersion.objects.get(strategy__business=other).status, "DRAFT")

    def test_content_plan_section_and_confirmation(self):
        st.confirm_version(self.draft, self.owner)
        items = cp.clean_items({"items": [
            {"target_week": 1, "direction": "Образы с платьями", "board": "Вечерние платья", "keyword": "evening dress", "idea": "Образ на выпускной"},
            {"target_week": 2, "direction": "Образы с платьями", "idea": "Образ для свадьбы гостя"}]}, self.draft)
        plan = cp.create_plan(self.business, self.owner, self.draft, items)
        plan_url = reverse("strategist:plan-confirm", kwargs={"workspace_slug": "w", "business_slug": "shop"})
        self.client.force_login(self.viewer)
        self.assertNotIn("Подтвердить контент-план", self.client.get(self.url).content.decode())
        self.assertEqual(self.client.post(plan_url).status_code, 404)
        self.client.force_login(self.owner)
        html = self.client.get(self.url).content.decode()
        for part in ("Контент-план по версии 1", "Неделя 1", "Образ на выпускной", "доска «Вечерние платья»", "Подтвердить контент-план"):
            self.assertIn(part, html)
        response = self.client.post(plan_url, follow=True)
        self.assertContains(response, "Контент-план подтверждён.")
        plan.refresh_from_db()
        self.assertEqual((plan.status, plan.confirmed_by), (ContentPlan.Status.CONFIRMED, self.owner))
        self.assertEqual(self.client.post(plan_url).status_code, 404)  # nothing pending any more

    def test_navigation_link_and_history(self):
        st.confirm_version(self.draft, self.owner)
        st.confirm_version(st.create_draft(self.business, self.owner, st.clean_payload(RAW, allowed_refs=set()), sources=[], change_note="Поправил цели"), self.owner)
        self.client.force_login(self.owner)
        html = self.client.get(self.url).content.decode()
        self.assertIn(self.url, html.split("sidebar-nav")[1].split("</nav>")[0])
        self.assertIn('aria-current="page"', html.split("sidebar-nav")[1].split("</nav>")[0])
        self.assertIn("История версий", html)
        self.assertIn("Поправил цели", html)
        self.assertIn("Заменена", html)
