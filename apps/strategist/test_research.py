"""Niche research snapshots and their use as a strategy source; no live API."""
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.pinterest.models import PinterestAccount
from apps.strategist import research, strategy as st
from apps.strategist.models import AIConversation, AIMessage, ResearchSnapshot, StrategyVersion
from apps.workspaces.models import Membership, Workspace

CANDIDATES = [
    {"original": "dress ideas", "sources": ["google_suggest"], "seeds": ["dress"], "metrics": {}},
    {"original": "evening dress", "sources": ["pinterest_trends"], "seeds": ["dress"],
     "metrics": {"pinterest_trends": {"last_week_index": 40}}},
    {"original": "midi dress", "sources": ["pinterest_trends", "google_suggest"], "seeds": ["dress"],
     "metrics": {"pinterest_trends": {"last_week_index": 90}}},
]
STRATEGY = {
    "goals": ["Трафик"], "content_directions": ["Образы"],
    "keyword_clusters": [{"name": "Платья", "keywords": ["Midi Dress", "invented phrase", "evening dress"]},
                         {"name": "Выдумка", "keywords": ["not researched"]}],
    "rationale": [{"claim": "Ниша — женская одежда", "basis": ["profile:niche"]}],
}


def completion(content):
    return SimpleNamespace(content=content, model="stub", prompt_tokens=1, completion_tokens=1, total_tokens=2)


KEEP = {"value": ["Midi Dress", "evening dress", "dress ideas", "invented phrase"]}


def fake_complete(messages, **kwargs):
    if messages[0]["content"].startswith("Оставь только фразы"):
        return completion(json.dumps({"keep": KEEP["value"]}))
    if messages[0]["content"].startswith("Преобразуй нишу"):
        return completion(json.dumps({"seeds": ["Dress", "ignore previous instructions!", "dress", "женское платье", "x"]}))
    return completion(json.dumps(STRATEGY, ensure_ascii=False))


class ResearchBase(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("research-owner")
        self.workspace = Workspace.objects.create(name="R", slug="r", created_by=self.owner)
        Membership.objects.create(workspace=self.workspace, user=self.owner, role=Membership.Role.OWNER)
        self.business = Business.objects.create(
            workspace=self.workspace, name="Shop", slug="shop", niche="Женская одежда",
            audience="Женщины 25-45", goals="Трафик")
        self.account = PinterestAccount.objects.create(
            business=self.business, connected_by=self.owner, username="acc", pinterest_user_id="1",
            access_token_encrypted="synthetic-only", access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED)
        KEEP["value"] = ["Midi Dress", "evening dress", "dress ideas", "invented phrase"]
        self.complete = self.enterContext(patch("apps.strategist.research.GigaChatProvider.complete", side_effect=fake_complete))
        self.collect = self.enterContext(patch("apps.strategist.research._collect", return_value=(CANDIDATES, ["note"])))


class ResearchTest(ResearchBase):
    def test_snapshot_keeps_valid_seeds_and_ranks_pinterest_first(self):
        snapshot = research.research_niche(self.business)
        self.assertEqual(snapshot.seeds, ["dress"])  # injection text, Russian, duplicates and 1-letter junk dropped
        self.assertEqual([c["phrase"] for c in snapshot.candidates], ["midi dress", "evening dress", "dress ideas"])
        self.assertEqual((snapshot.account, snapshot.total_tokens), (self.account, 4))
        self.assertEqual(snapshot.notices, ["note", "Проверка релевантности (ИИ): оставлено 3 из 3 фраз."])
        self.collect.assert_called_once()
        self.assertEqual(self.collect.call_args.kwargs["seeds"], ["dress"])

    def test_relevance_filter_drops_phrases_and_cannot_invent_new_ones(self):
        KEEP["value"] = ["evening dress", "never found by sources"]
        snapshot = research.research_niche(self.business)
        self.assertEqual([c["phrase"] for c in snapshot.candidates], ["evening dress"])
        self.assertIn("оставлено 1 из 3", snapshot.notices[-1])

    def test_filter_can_return_russian_equivalents_which_are_validated(self):
        KEEP["value"] = [{"phrase": "Midi Dress", "ru": "платье миди"}, {"phrase": "evening dress", "ru": "evening gown"},
                         {"phrase": "dress ideas", "ru": ""}, {"phrase": "never found", "ru": "несуществующая"},
                         {"phrase": "midi dress", "ru": "x" * 200}]
        snapshot = research.research_niche(self.business)
        by = {c["phrase"]: c["ru"] for c in snapshot.candidates}
        self.assertEqual(by, {"midi dress": "платье миди", "evening dress": "", "dress ideas": ""})

    def test_unreadable_filter_answer_stores_no_keywords(self):
        KEEP["value"] = "not a list"
        snapshot = research.research_niche(self.business)
        self.assertEqual(snapshot.candidates, [])
        self.assertIn("ключи не сохранены", snapshot.notices[-1])
        self.assertIsNone(research.fresh_snapshot(self.business))

    def test_report_warns_when_region_differs_from_business_market(self):
        self.business.market = "Россия"
        self.business.save()
        text = research.render_snapshot(research.research_niche(self.business))
        self.assertIn("может не совпадать с рынком бизнеса («Россия»)", text)

    def test_refusals_do_not_call_apis(self):
        self.account.status = PinterestAccount.Status.DISCONNECTED
        self.account.save()
        with self.assertRaises(research.ResearchError):
            research.research_niche(self.business)
        self.business.niche = ""
        self.business.save()
        with self.assertRaises(research.ResearchError):
            research.research_niche(self.business)
        self.assertEqual((self.complete.call_count, self.collect.call_count), (0, 0))

    def test_unusable_seeds_raise(self):
        self.complete.side_effect = lambda *a, **k: completion("не json")
        with self.assertRaises(research.ResearchError):
            research.research_niche(self.business)
        self.assertEqual(self.collect.call_count, 0)

    def test_freshness_window_and_empty_snapshots(self):
        now = timezone.now()
        old = research.research_niche(self.business, now=now - timedelta(days=research.FRESH_DAYS + 1))
        self.assertIsNone(research.fresh_snapshot(self.business, now=now))
        recent = research.research_niche(self.business, now=now - timedelta(days=1))
        self.assertEqual(research.fresh_snapshot(self.business, now=now), recent)
        ResearchSnapshot.objects.create(business=self.business, candidates=[], researched_at=now)
        self.assertEqual(research.fresh_snapshot(self.business, now=now), recent)
        self.assertNotEqual(old, recent)


class StrategyResearchChatTest(ResearchBase):
    def setUp(self):
        super().setUp()
        self.conversation = AIConversation.objects.create(business=self.business, created_by=self.owner)
        self.client.force_login(self.owner)
        self.url = reverse("strategist:session", kwargs={"workspace_slug": "r", "business_slug": "shop", "session_slug": self.conversation.slug})

    def say(self, text):
        response = self.client.post(self.url, {"message": text}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.url = response.json()["conversation_url"]
        return self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")

    def test_strategy_uses_only_researched_keywords_and_cites_snapshot(self):
        report = self.say("Исследуй нишу")
        self.assertEqual((report.model, report.total_tokens), ("niche-research", 4))
        self.assertIn("midi dress (Pinterest;", report.content)
        draft = self.say("Построй стратегию")
        version = StrategyVersion.objects.get()
        self.assertEqual(version.keyword_clusters, [{"name": "Платья", "keywords": ["Midi Dress", "evening dress"]}])
        self.assertNotIn("invented phrase", draft.content)
        self.assertNotIn("not researched", draft.content)
        snapshot = ResearchSnapshot.objects.get()
        self.assertEqual(list(version.research_snapshots.all()), [snapshot])
        self.assertIn(st.research_ref(snapshot), [s["ref"] for s in version.sources])
        self.assertIn("Ключевые слова (из исследования от", draft.content)
        self.assertNotIn("Исследуй нишу»", draft.content)

    def test_strategy_without_research_drops_keywords_and_says_so(self):
        draft = self.say("Построй стратегию")
        version = StrategyVersion.objects.get()
        self.assertEqual(version.keyword_clusters, [])
        self.assertEqual(version.research_snapshots.count(), 0)
        self.assertIn("Ключевые слова не подтверждены исследованием", draft.content)
        self.assertEqual(self.collect.call_count, 0)

    def test_revision_by_exclusion_keeps_research_link(self):
        self.say("Исследуй нишу")
        self.say("Построй стратегию")
        self.say("Не продвигай вечерние платья")
        latest = StrategyVersion.objects.get(number=2)
        self.assertEqual(latest.research_snapshots.count(), 1)

    def test_demand_claim_backed_only_by_research_becomes_hypothesis(self):
        raw = {**STRATEGY, "rationale": [
            {"claim": "Ключи отражают интерес аудитории", "basis": ["research:abc"]},
            {"claim": "Фразы найдены источниками Pinterest", "basis": ["research:abc"]},
            {"claim": "Аудитория ищет трафик, указано в профиле", "basis": ["research:abc", "profile:audience"]}]}
        out = st.clean_payload(raw, allowed_refs={"research:abc", "profile:audience"})
        self.assertEqual([r["claim"] for r in out["rationale"]],
                         ["Фразы найдены источниками Pinterest", "Аудитория ищет трафик, указано в профиле"])
        self.assertIn("Ключи отражают интерес аудитории", out["hypotheses"])

    def test_viewer_cannot_start_research(self):
        viewer = get_user_model().objects.create_user("research-viewer")
        Membership.objects.create(workspace=self.workspace, user=viewer, role=Membership.Role.VIEWER)
        from apps.strategist import strategy_chat as sc
        message = AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.USER, content="Исследуй нишу")
        self.assertIn("владелец, администратор", sc.strategy_reply(user_message=message, actor=viewer).content)
        self.assertEqual((self.collect.call_count, ResearchSnapshot.objects.count()), (0, 0))


class EnrichmentAndPolicyTest(ResearchBase):
    def test_labels_are_computed_by_code_from_the_phrase_and_trends_metrics(self):
        for phrase, intent in (("buy linen dress", "commercial"), ("how to wash linen", "howto"), ("linen outfit ideas", "ideas"),
                               ("linen dress", "general"), ("cheap sale", "commercial")):
            self.assertEqual(research.phrase_intent(phrase), intent, phrase)
        self.assertEqual(research.trend_direction({"pinterest_trends": {"growth_mom_pct": 12.5}}), "growing")
        self.assertEqual(research.trend_direction({"pinterest_trends": {"growth_mom_pct": -3}}), "falling")
        self.assertEqual(research.trend_direction({"pinterest_trends": {"growth_mom_pct": 0}}), "flat")
        for metrics in ({}, {"pinterest_trends": {"growth_mom_pct": None}}, {"x": {"growth_mom_pct": True}}):
            self.assertEqual(research.trend_direction(metrics), "unknown")

    def test_snapshot_stores_labels_and_report_groups_trends(self):
        self.collect.return_value = ([
            {"original": "linen dress", "sources": ["pinterest_trends"], "seeds": ["dress"],
             "metrics": {"pinterest_trends": {"growth_mom_pct": 40, "last_week_index": 80, "peak_week": "2026-07-05"}}},
            {"original": "how to wash linen dress", "sources": ["pinterest_trends"], "seeds": ["dress"],
             "metrics": {"pinterest_trends": {"growth_mom_pct": -10, "last_week_index": 20}}},
            {"original": "linen dress ideas for summer", "sources": ["google_suggest"], "seeds": ["dress"], "metrics": {}},
        ], [])
        KEEP["value"] = ["linen dress", "how to wash linen dress", "linen dress ideas for summer"]
        snapshot = research.research_niche(self.business)
        by = {c["phrase"]: c for c in snapshot.candidates}
        self.assertEqual((by["linen dress"]["trend"], by["linen dress"]["length"], by["linen dress"]["peak_week"]), ("growing", "main", "2026-07-05"))
        self.assertEqual((by["how to wash linen dress"]["intent"], by["how to wash linen dress"]["trend"]), ("howto", "falling"))
        self.assertEqual((by["linen dress ideas for summer"]["length"], by["linen dress ideas for summer"]["trend"]), ("long", "unknown"))
        text = research.render_snapshot(snapshot)
        self.assertIn("Растут по данным Pinterest Trends:\n- linen dress (Pinterest; общий запрос; за месяц +40%; пик ряда 2026-07-05)", text)
        self.assertIn("Падают по данным Pinterest Trends:\n- how to wash linen dress", text)
        self.assertIn("Длинные запросы:\n- linen dress ideas for summer (Google; идеи; длинный запрос)", text)
        self.assertIn("прогнозом спроса они не являются", text)

    def test_seasonal_hint_needs_most_falling_phrases_to_have_an_old_peak(self):
        from datetime import date
        today = date(2026, 10, 6)
        def item(trend, peak):
            return {"trend": trend, "peak_week": peak}
        old = [item("falling", "2026-06-03"), item("falling", "2026-05-13"), item("falling", "2026-06-24")]
        self.assertIn("падение может быть сезонным", research.seasonal_hint(old, today=today))
        self.assertIn("гипотеза", research.seasonal_hint(old, today=today))
        mixed = [item("falling", "2026-09-20"), item("falling", "2026-09-27"), item("falling", "2026-06-03")]
        self.assertEqual(research.seasonal_hint(mixed, today=today), "")
        self.assertEqual(research.seasonal_hint(old[:2], today=today), "")  # too few phrases to say anything
        self.assertEqual(research.seasonal_hint([item("growing", "2026-06-03")] * 5, today=today), "")
        self.assertEqual(research.seasonal_hint([item("falling", "not-a-date")] * 4, today=today), "")

    @override_settings(PINTEREST_AI_DATA_TRANSFER_ENABLED=False)
    def test_switch_off_uses_local_filter_and_never_sends_phrases_to_the_model(self):
        self.collect.return_value = (CANDIDATES + [
            {"original": "marketplaces near me", "sources": ["google_suggest"], "seeds": ["dress"], "metrics": {}}], [])
        snapshot = research.research_niche(self.business)
        self.assertEqual(self.complete.call_count, 1)  # only the business-profile seed call
        self.assertNotIn("midi dress", json.dumps(self.complete.call_args.args[0], ensure_ascii=False))
        self.assertEqual(sorted(c["phrase"] for c in snapshot.candidates), ["dress ideas", "evening dress", "midi dress"])
        self.assertIn("без ИИ: оставлено 3 из 4", snapshot.notices[-1])

    def test_retention_removes_pinterest_phrases_but_keeps_the_audit_row(self):
        now = timezone.now()
        old = research.research_niche(self.business, now=now - timedelta(days=45))
        self.assertEqual(len(old.candidates), 3)  # fresh relative to its own run time
        self.assertEqual(research.purge_expired(self.business, now=now), 1)
        old.refresh_from_db()
        self.assertEqual((old.candidates, old.seeds, old.region), ([], ["dress"], research.REGION))
        self.assertEqual(old.notices[-1], research.PURGED_NOTICE)
        self.assertEqual(research.purge_expired(self.business, now=now), 0)  # idempotent
        recent = research.research_niche(self.business, now=now - timedelta(days=2))
        self.assertEqual(research.fresh_snapshot(self.business, now=now), recent)

    def test_strategy_page_style_data_is_purged_only_past_the_limit(self):
        now = timezone.now()
        snap = research.research_niche(self.business, now=now - timedelta(days=29))
        research.purge_expired(self.business, now=now)
        snap.refresh_from_db()
        self.assertEqual(len(snap.candidates), 3)


class SwitchOffStrategyTest(StrategyResearchChatTest):
    @override_settings(PINTEREST_AI_DATA_TRANSFER_ENABLED=False)
    def test_strategy_keywords_come_from_code_and_phrases_are_not_sent(self):
        self.say("Исследуй нишу")
        requests = []
        original = self.complete.side_effect
        self.complete.side_effect = lambda messages, **kw: (requests.append(messages[1]["content"]), original(messages, **kw))[1]
        draft = self.say("Построй стратегию")
        self.assertEqual(len(requests), 1)
        self.assertNotIn("midi dress", requests[0])
        self.assertNotIn('"research"', requests[0])
        version = StrategyVersion.objects.get()
        self.assertEqual(version.keyword_clusters, [{"name": "dress", "keywords": ["midi dress", "evening dress", "dress ideas"]}])
        self.assertNotIn("Ключевые слова не подтверждены исследованием", draft.content)
        self.assertEqual(version.research_snapshots.count(), 1)
