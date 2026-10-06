"""The pin generation page: access, auto-filled values with their sources, validation, preset, jobs."""
import re
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from apps.pinterest.models import PinterestAccount
from apps.strategist import pin_jobs as pj
from apps.strategist import pin_settings as ps
from apps.strategist.models import AIJob, GenerationPreset
from apps.strategist.test_approvals import ApprovalBase


class GeneratePageBase(ApprovalBase):
    def setUp(self):
        super().setUp()
        self.url = reverse("strategist:pin-generate", kwargs={"workspace_slug": "a", "business_slug": "shop"})
        self.account = PinterestAccount.objects.create(
            business=self.business, connected_by=self.owner, username="alpha", pinterest_user_id="a",
            access_token_encrypted="x", access_token_expires_at="2030-01-01T00:00:00Z", granted_scopes=[], status="CONNECTED")
        self.client.force_login(self.owner)

    def items(self):
        return [i.pk for i in self.plan.items.order_by("position")]

    def payload(self, ids=None, **extra):
        data = {"tone": "neutral", "cta": "none", "length": "standard", "keyword_mode": "both", "rewrite": "on", "remember": "on",
                "account": str(self.account.pk), "destination_url": "https://shop.example.com/catalog"}
        data.update(extra)
        data["items"] = [str(i) for i in (self.items()[:2] if ids is None else ids)]
        return data

    def post(self, **kwargs):
        with patch("apps.strategist.tasks.run_pin_generation.delay") as delay, self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(self.url, self.payload(**kwargs), follow=True)  # callbacks run while the patch is still active
        return response, delay, callbacks


class AccessAndRenderTest(GeneratePageBase):
    def test_access_rules(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        for user in (self.stranger, self.viewer):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, 404, user.username)
            self.assertEqual(self.client.post(self.url, self.payload()).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_without_a_confirmed_plan_the_page_explains_what_to_do(self):
        self.plan.status = "SUPERSEDED"
        self.plan.save()
        html = self.client.get(self.url).content.decode()
        self.assertIn("Чтобы создавать пины, нужны два шага", html)
        self.assertIn("Подтверждена, версия 1", html)  # the strategy is fine; only the plan is missing
        self.assertIn("Контент-плана пока нет", html)  # a superseded plan does not count
        self.assertNotIn("data-gen-form", html)

    def test_autofilled_values_show_their_source_and_the_auto_value(self):
        html = self.client.get(self.url).content.decode()
        for part in ("из профиля бизнеса", "из аккаунта Pinterest", "по умолчанию", 'data-auto="https://shop.example.com/catalog"',
                     f'data-auto="{self.account.pk}"', "Дополнительно", "Все 12 проверок выполняются всегда"):
            self.assertIn(part, html)
        self.assertEqual(len(re.findall(r"data-gen-item", html)), 5)
        self.assertEqual(len(re.findall(r"data-gen-item[^>]*checked", html)), 3)  # the first three open items are preselected
        self.assertIn('value="https://shop.example.com/catalog"', html)

    def test_strategy_exclusions_prefill_the_forbidden_words(self):
        from apps.strategist import strategy as st
        raw = {**__import__("apps.strategist.test_pin_generation", fromlist=["STRATEGY"]).STRATEGY, "exclusions": ["свадебн"]}
        payload = st.clean_payload(raw, allowed_refs=set(), allowed_keywords=None, exclusions=["свадебн"])
        st.confirm_version(st.create_draft(self.business, self.owner, payload, sources=[]), self.owner)
        from apps.strategist import content_plan as cp
        version = st.active_version(self.business)
        self.plan.status = "SUPERSEDED"
        self.plan.save()
        cp.confirm_plan(cp.create_plan(self.business, self.owner, version, cp.clean_items(
            {"items": [{"target_week": 1, "direction": "Образы с платьями", "idea": "Новая идея"}]}, version)), self.owner)
        html = self.client.get(self.url).content.decode()
        self.assertIn("из стратегии", html)
        self.assertIn("свадебн", html)

    def test_page_has_no_inline_script_or_style_and_escapes_data(self):
        item = self.plan.items.first()
        type(item).objects.filter(pk=item.pk).update(idea="<script>alert(1)</script>")
        html = self.client.get(self.url).content.decode()
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)", html)
        self.assertNotIn(' style="', html)
        self.assertEqual(len(re.findall(r"<script(?![^>]*\bsrc=)", html)), 0)
        self.assertIn("js/strategist/pin-generate.js", html)

    def test_pins_page_links_to_generation_for_editors_only(self):
        pins = reverse("strategist:pins", kwargs={"workspace_slug": "a", "business_slug": "shop"})
        self.assertIn(self.url, self.client.get(pins).content.decode())
        self.client.force_login(self.viewer)
        self.assertNotIn(self.url, self.client.get(pins).content.decode())

    def test_menu_item_is_shown_to_editors_only_and_marked_current_on_the_page(self):
        def nav(response):
            return response.content.decode().split("sidebar-nav")[1].split("</nav>")[0]
        menu = nav(self.client.get(self.url))
        self.assertIn(f'href="{self.url}"', menu)
        self.assertIn("Создание пинов", menu)
        self.assertEqual(menu.count('aria-current="page"'), 1)
        self.assertRegex(menu, rf'href="{re.escape(self.url)}"[^>]*aria-current="page"')
        pins = reverse("strategist:pins", kwargs={"workspace_slug": "a", "business_slug": "shop"})
        self.assertNotRegex(nav(self.client.get(pins)), rf'href="{re.escape(self.url)}"[^>]*aria-current')
        self.client.force_login(self.viewer)
        self.assertNotIn(self.url, nav(self.client.get(pins)))  # a viewer would only get a 404 there
        self.client.force_login(self.owner)
        english = nav(self.client.get(self.url, headers={"accept-language": "en"}))
        self.assertIn("Create pins", english)

    def test_english_page(self):
        html = self.client.get(self.url, headers={"accept-language": "en"}).content.decode()
        for part in ("Create pins", "What to create", "Summary", "from the business profile", "Generate", "Tone"):
            self.assertIn(part, html)
        self.assertNotIn("Что создаём", html)


class SubmitTest(GeneratePageBase):
    def test_valid_post_creates_a_job_queues_it_and_remembers_the_settings(self):
        response, delay, callbacks = self.post(tone="expert", utm_source="pinterest", forbidden_words="дёшево, акция", instruction="Коротко")
        job = AIJob.objects.get()
        self.assertEqual((job.status, job.total, job.created_by), ("PENDING", 2, self.owner))
        self.assertEqual(job.params["options"]["tone"], "expert")
        self.assertEqual(job.params["options"]["utm"]["source"], "pinterest")
        self.assertEqual(job.params["options"]["forbidden_words"], ["дёшево", "акция"])
        delay.assert_called_once_with(job.pk)  # enqueued only after the transaction committed
        self.assertContains(response, "Генерация запущена")
        preset = GenerationPreset.objects.get()
        self.assertEqual((preset.values["tone"], preset.updated_by), ("expert", self.owner))
        self.assertNotIn("boards", preset.values)  # boards belong to plan items, not to the preset

    def test_preset_is_loaded_next_time_with_its_own_badge_and_the_auto_value_kept(self):
        self.post(tone="premium", length="short")
        AIJob.objects.update(status="COMPLETED")
        html = self.client.get(self.url).content.decode()
        self.assertRegex(html, r'<option value="premium" selected>')
        self.assertIn("из ваших прошлых настроек", html)
        self.assertRegex(html, r'data-auto="neutral"')  # "reset to auto" goes back to the default, not to the preset

    def test_not_remembering_stores_no_preset(self):
        data = self.payload()
        data.pop("remember")
        with patch("apps.strategist.tasks.run_pin_generation.delay"), self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, data)
        self.assertEqual((AIJob.objects.count(), GenerationPreset.objects.count()), (1, 0))

    def test_invalid_fields_rerender_with_errors_and_start_nothing(self):
        for bad in ({"utm_source": "bad value!"}, {"destination_url": "not a url"}, {"instruction": "я" * 600}, {"tone": "evil"}, {"account": "999999"}):
            with self.subTest(bad=bad):
                response, delay, _ = self.post(**bad)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "form-errors")
                delay.assert_not_called()
        self.assertFalse(AIJob.objects.exists())

    def test_selection_rules(self):
        response, _, _ = self.post(ids=[])
        self.assertContains(response, "Выберите хотя бы один пункт")
        with patch.object(ps, "MAX_ITEMS", 1):
            response, _, _ = self.post()
            self.assertContains(response, "не больше 1 пинов")
        self.assertFalse(AIJob.objects.exists())
        first, _, _ = self.post()
        self.assertEqual(AIJob.objects.count(), 1)
        second, delay, _ = self.post(ids=self.items()[2:3])
        self.assertContains(second, "Генерация уже идёт")
        delay.assert_not_called()

    def test_chosen_boards_are_saved_in_the_job_per_item(self):
        first, second = self.items()[:2]
        data = self.payload(ids=[first, second])
        data[f"board_{first}"] = "Доска из аккаунта"
        data[f"board_{second}"] = ""
        with patch("apps.strategist.tasks.run_pin_generation.delay"), self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, data)
        self.assertEqual(AIJob.objects.get().params["options"]["boards"], {str(first): "Доска из аккаунта"})

    def test_account_boards_appear_as_choices(self):
        with patch("apps.pinterest.sync.fresh_snapshot_resource", return_value={"items": [{"name": "Моя доска Pinterest"}, {"name": 5}, "x"]}):
            html = self.client.get(self.url).content.decode()
        self.assertIn('<option value="Моя доска Pinterest"', html)
        self.assertIn('<option value="Льняные платья"', html)  # the strategy's boards are always offered


class JobEndpointsTest(GeneratePageBase):
    def make_job(self):
        return pj.start_job(self.business, self.owner, self.items()[:2], {})

    def test_status_is_visible_to_members_only_and_scoped_to_the_business(self):
        job = self.make_job()
        url = reverse("strategist:pin-job-status", kwargs={"workspace_slug": "a", "business_slug": "shop", "job_id": job.pk})
        data = self.client.get(url).json()
        self.assertEqual((data["status"], data["total"], data["done"], data["finished"], data["label"]), ("PENDING", 2, 0, False, "В очереди"))
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(url).status_code, 404)
        other = type(self.business).objects.create(workspace=self.workspace, name="Other", slug="other")
        foreign = reverse("strategist:pin-job-status", kwargs={"workspace_slug": "a", "business_slug": "other", "job_id": job.pk})
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(foreign).status_code, 404)

    def test_cancel_is_a_post_by_an_editor(self):
        job = self.make_job()
        url = reverse("strategist:pin-job-cancel", kwargs={"workspace_slug": "a", "business_slug": "shop", "job_id": job.pk})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.post(url, follow=True)
        self.assertContains(response, "Отмена запрошена")
        job.refresh_from_db()
        self.assertEqual(job.status, "CANCELLED")

    def test_job_card_shows_progress_notes_and_a_cancel_button_only_while_active(self):
        job = self.make_job()
        AIJob.objects.filter(pk=job.pk).update(status="RUNNING", done=1, notes=["Модель сейчас недоступна: оставшиеся пункты не обработаны. Повторите запуск позже."])
        html = self.client.get(self.url).content.decode()
        self.assertIn("Выполняется", html)
        self.assertIn("Готово 1 из 2", html)
        self.assertIn("Модель сейчас недоступна", html)
        self.assertIn("data-job-status-url", html)
        self.assertIn('value="50"', html)
        AIJob.objects.filter(pk=job.pk).update(status="COMPLETED")
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("data-job-status-url", html)
        self.assertNotIn("Отменить", html)
