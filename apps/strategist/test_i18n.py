"""English interface: catalog is in sync, language switching works, pages render in English."""
import importlib.util
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import translation

from apps.businesses.models import Business
from apps.strategist import strategy as st
from apps.workspaces.models import Membership, Workspace

SCRIPT = Path(settings.BASE_DIR) / "scripts" / "i18n.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i18n_tool", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CatalogTest(SimpleTestCase):
    def test_catalog_is_complete_and_in_sync(self):
        problems = load_tool().problems()
        self.assertEqual(problems, [], "Run: python scripts/i18n.py extract && python scripts/i18n.py compile\n" + "\n".join(problems))

    def test_every_extracted_message_has_an_english_translation_at_runtime(self):
        tool = load_tool()
        same_in_both = {"Email", "Pinterest"}
        with translation.override("en"):
            for msgid in tool.extract_messages():
                if msgid in same_in_both:
                    continue
                with self.subTest(msgid=msgid[:60]):
                    self.assertNotEqual(translation.gettext(msgid), msgid)

    def test_russian_is_the_source_language(self):
        with translation.override("ru"):
            self.assertEqual(translation.gettext("Выйти"), "Выйти")
        with translation.override("en"):
            self.assertEqual(translation.gettext("Выйти"), "Sign out")
            self.assertEqual(translation.gettext("Неделя %(week)s") % {"week": 2}, "Week 2")


class SwitchingTest(TestCase):
    def setUp(self):
        self.addCleanup(translation.activate, "ru")  # views activate a language per request; do not leak it

    def test_default_is_russian_and_accept_language_selects_english(self):
        ru = self.client.get(reverse("login")).content.decode()
        self.assertIn('lang="ru"', ru)
        self.assertIn("Войти", ru)
        en = self.client.get(reverse("login"), headers={"accept-language": "en"}).content.decode()
        self.assertIn('lang="en"', en)
        self.assertIn("Sign in", en)
        self.assertNotIn("Войти", en)

    def test_language_switch_sets_cookie_and_returns_to_the_page(self):
        response = self.client.post(reverse("set_language"), {"language": "en", "next": reverse("login")})
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertEqual(self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value, "en")
        self.assertIn("Sign in", self.client.get(reverse("login")).content.decode())
        self.client.post(reverse("set_language"), {"language": "ru", "next": reverse("login")})
        self.assertIn("Войти", self.client.get(reverse("login")).content.decode())

    def test_foreign_next_url_and_unknown_language_are_ignored(self):
        response = self.client.post(reverse("set_language"), {"language": "en", "next": "https://evil.example/steal"})
        self.assertEqual(response["Location"], "/")
        self.client.post(reverse("set_language"), {"language": "xx", "next": "/"})
        self.assertNotEqual(self.client.cookies.get(settings.LANGUAGE_COOKIE_NAME).value if settings.LANGUAGE_COOKIE_NAME in self.client.cookies else "", "xx")

    def test_switcher_is_rendered_with_current_language_marked(self):
        html = self.client.get(reverse("login"), headers={"accept-language": "en"}).content.decode()
        self.assertIn('class="language-switch"', html)
        self.assertIn('name="next"', html)
        self.assertIn('aria-current="true"', html)
        self.assertIn('lang="en" class="language-switch-option is-current"', html)


class EnglishPagesTest(TestCase):
    def setUp(self):
        self.addCleanup(translation.activate, "ru")
        self.user = get_user_model().objects.create_user("i18n-owner")
        workspace = Workspace.objects.create(name="W", slug="w", created_by=self.user)
        Membership.objects.create(workspace=workspace, user=self.user, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=workspace, name="Shop", slug="shop", niche="Одежда", audience="Женщины", goals="Трафик")
        raw = {"goals": ["Трафик"], "content_directions": ["Образы"], "publishing_cadence": {"text": "по мере готовности"},
               "hypotheses": ["Зимой спрос выше"], "missing_data": ["Нет данных"]}
        st.create_draft(self.business, self.user, st.clean_payload(raw, allowed_refs=set()), sources=[])
        self.client.force_login(self.user)
        self.url = reverse("strategist:strategy", kwargs={"workspace_slug": "w", "business_slug": "shop"})

    def test_strategy_page_chrome_is_english_and_user_data_is_untouched(self):
        html = self.client.get(self.url, headers={"accept-language": "en"}).content.decode()
        for part in ("Business profile", "Draft, version 1", "Confirm strategy", "Hypotheses (not confirmed)",
                     "Missing data", "Sign out", "Version history", "hypothesis, not confirmed by data", "Light theme"):
            self.assertIn(part, html)
        for russian in ("Профиль бизнеса", "Подтвердить стратегию", "Выйти", "История версий", "Гипотезы (не подтверждены)"):
            self.assertNotIn(russian, html)
        self.assertIn("Зимой спрос выше", html)  # data entered by the user/model is shown as stored

    def test_strategy_page_stays_russian_by_default(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn("Профиль бизнеса", html)
        self.assertIn("Подтвердить стратегию", html)

    def test_confirmation_message_is_english_for_english_users(self):
        response = self.client.post(reverse("strategist:strategy-confirm", kwargs={"workspace_slug": "w", "business_slug": "shop", "number": 1}),
                                    follow=True, headers={"accept-language": "en"})
        self.assertContains(response, "Strategy confirmed.")
        again = self.client.post(reverse("strategist:strategy-confirm", kwargs={"workspace_slug": "w", "business_slug": "shop", "number": 1}),
                                 follow=True, headers={"accept-language": "en"})
        self.assertContains(again, "Only the current draft can be confirmed.")
