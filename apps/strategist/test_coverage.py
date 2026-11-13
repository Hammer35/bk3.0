"""Coverage of niche phrases by the user's own pins; no model call, own account only."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.pinterest.models import PinterestAccount
from apps.strategist import coverage, research
from apps.strategist.models import AIConversation, AIMessage, ResearchSnapshot
from apps.workspaces.models import Membership, Workspace

CANDIDATES = [
    {"phrase": "linen dresses", "ru": "льняные платья", "sources": ["pinterest_trends"], "seeds": ["linen"], "metrics": {}},
    {"phrase": "linen suit", "ru": "льняной костюм", "sources": ["pinterest_trends"], "seeds": ["linen"], "metrics": {}},
    {"phrase": "summer outfits", "ru": "", "sources": ["pinterest_trends"], "seeds": ["linen"], "metrics": {}},
    {"phrase": "linen skirt", "ru": "льняная юбка", "sources": ["google_suggest"], "seeds": ["linen"], "metrics": {}},
]
PINS = [
    {"title": "Льняное платье на лето", "description": "Платья из натурального льна", "alt_text": ""},
    {"title": "Linen dresses for summer", "description": "", "alt_text": ""},
    {"title": "Новая коллекция", "description": "Юбки и топы", "alt_text": "Summer outfits look"},
    "garbage",
]


class MatchingTest(SimpleTestCase):
    def test_stems_ignore_stopwords_short_words_and_yo(self):
        self.assertEqual(coverage._stems("Платья для Лета, ёлка и на"), {"плать", "лета", "елка"})
        self.assertEqual(coverage._stems("the linen dress for me"), {"linen", "dress"})
        self.assertEqual(coverage._stems(""), set())

    def test_phrase_is_covered_in_either_language_and_counts_pins(self):
        rows = {r["phrase"]: r for r in coverage.compute_coverage(CANDIDATES, PINS)}
        self.assertEqual((rows["linen dresses"]["pins"], rows["linen dresses"]["covered"]), (2, True))  # RU and EN pin
        self.assertEqual(rows["linen dresses"]["example"], "Льняное платье на лето")
        self.assertEqual((rows["summer outfits"]["pins"], rows["summer outfits"]["covered"]), (1, True))  # alt text
        for phrase in ("linen suit", "linen skirt"):
            self.assertEqual((rows[phrase]["pins"], rows[phrase]["covered"]), (0, False), phrase)

    def test_all_stems_of_a_phrase_must_match_and_empty_input_is_safe(self):
        rows = coverage.compute_coverage([{"phrase": "linen dress sale", "ru": "", "sources": [], "seeds": [], "metrics": {}}], PINS)
        self.assertFalse(rows[0]["covered"])  # "sale" is missing in every pin
        self.assertEqual(coverage.compute_coverage([], PINS), [])
        self.assertFalse(coverage.compute_coverage(CANDIDATES, [])[0]["covered"])

    def test_intent_is_narrow(self):
        for text in ("Какие запросы не покрыты моим контентом?", "покажи пробелы в контенте", "gap analysis по моему аккаунту",
                     "какие ключи у меня не покрыты пинами", "Покрытие запросов @alpha"):
            self.assertTrue(coverage.asks_for_coverage(text), text)
        for text in ("Покажи статистику", "Построй стратегию", "Исследуй нишу", "Как закрыть пробел в знаниях?"):
            self.assertFalse(coverage.asks_for_coverage(text), text)


class CoverageChatTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("coverage-owner")
        workspace = Workspace.objects.create(name="C", slug="c", created_by=self.user)
        Membership.objects.create(workspace=workspace, user=self.user, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=workspace, name="Shop", slug="shop", niche="Льняная одежда")
        self.account = self.account_named("alpha")
        self.conversation = AIConversation.objects.create(business=self.business, created_by=self.user)
        self.client.force_login(self.user)
        self.url = reverse("strategist:session", kwargs={"workspace_slug": "c", "business_slug": "shop", "session_slug": self.conversation.slug})
        self.complete = self.enterContext(patch("apps.strategist.providers.GigaChatProvider.complete", side_effect=AssertionError("no model call allowed")))
        self.pins = self.enterContext(patch("apps.strategist.services._read_all_pinterest_pages", return_value={"items": PINS}))

    def account_named(self, name):
        return PinterestAccount.objects.create(
            business=self.business, connected_by=self.user, username=name, pinterest_user_id=name,
            access_token_encrypted="mock-only", access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED)

    def niche(self, candidates=CANDIDATES, **kw):
        rows = [{"phrase": c["phrase"], "ru": c["ru"], "sources": c["sources"], "seeds": c["seeds"], "metrics": c["metrics"],
                 "intent": "general", "length": "main", "trend": "unknown", "peak_week": ""} for c in candidates]
        return ResearchSnapshot.objects.create(business=self.business, account=self.account, seeds=["linen"], region="X",
                                               candidates=rows, researched_at=timezone.now(), **kw)

    def say(self, text):
        response = self.client.post(self.url, {"message": text}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.url = response.json()["conversation_url"]
        return self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")

    def test_report_lists_gaps_and_covered_phrases_without_the_model(self):
        self.niche()
        answer = self.say("Какие запросы не покрыты моим контентом?")
        self.assertEqual((answer.provider, answer.total_tokens), ("coverage", 0))
        self.assertIn("Фраз из исследования: 4; без пинов: 2.", answer.content)
        self.assertIn("Пробелы (ни в одном пине нет этих слов):\n- linen suit (льняной костюм)\n- linen skirt (льняная юбка)", answer.content)
        self.assertIn("linen dresses (льняные платья): пинов 2, например «Льняное платье на лето»", answer.content)
        self.assertIn("Прочитано пинов: 4.", answer.content)
        self.assertIn("Это не позиции в поиске, не спрос", answer.content)
        stored = ResearchSnapshot.objects.get(kind="COVERAGE")
        self.assertEqual((stored.account, len(stored.candidates)), (self.account, 4))
        self.pins.assert_called_once()
        self.assertEqual(self.pins.call_args.kwargs["account"], self.account)  # only the user's own account is read

    def test_missing_research_account_or_choice_gives_a_short_instruction(self):
        self.assertIn("Исследуй нишу", self.say("Покажи пробелы в контенте").content)
        self.niche()
        self.account_named("beta")
        self.assertIn("Укажи, чей контент сравнивать: @alpha, @beta.", self.say("Покажи пробелы в контенте").content)
        self.assertIn("пинов 2", self.say("Покажи пробелы в контенте @beta").content)
        self.pins.assert_called_once()
        PinterestAccount.objects.all().update(status="DISCONNECTED")
        self.assertIn("нужен подключённый аккаунт", self.say("Покажи пробелы в контенте").content)

    def test_read_errors_and_truncated_reads_are_stated(self):
        self.niche()
        self.pins.return_value = {"error": "Pinterest API вернул HTTP 500"}
        self.assertIn("Не удалось прочитать пины @alpha: Pinterest API вернул HTTP 500", self.say("Покажи пробелы в контенте").content)
        self.assertFalse(ResearchSnapshot.objects.filter(kind="COVERAGE").exists())
        self.pins.return_value = {"items": PINS, "truncated": True}
        self.assertIn("охват может быть занижен", self.say("Покажи пробелы в контенте").content)

    def test_without_russian_equivalents_the_limit_is_stated(self):
        self.niche([{**c, "ru": ""} for c in CANDIDATES])
        answer = self.say("Покажи пробелы в контенте")
        self.assertIn("Русских эквивалентов фраз нет", answer.content)

    def test_coverage_snapshot_is_purged_like_other_pinterest_data_and_never_replaces_the_niche_one(self):
        niche = self.niche()
        self.say("Покажи пробелы в контенте")
        self.assertEqual(research.fresh_snapshot(self.business), niche)
        self.assertEqual(research.fresh_snapshot(self.business, kind="COVERAGE").kind, "COVERAGE")
        future = timezone.now() + timedelta(days=31)
        self.assertEqual(research.purge_expired(self.business, now=future), 2)
        self.assertFalse(ResearchSnapshot.objects.exclude(candidates=[]).exists())
