"""Strategy versions and validation; no live model or Pinterest calls."""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.businesses.models import Business
from apps.strategist import strategy as st
from apps.strategist.models import Strategy, StrategyVersion
from apps.workspaces.models import Workspace

RAW = {
    "goals": ["Получать органический трафик на каталог"],
    "priorities": ["Платья", "Костюмы"],
    "keyword_clusters": [{"name": "Платья", "keywords": ["вечернее платье", "платье миди"]}],
    "recommended_boards": [{"name": "Вечерние платья", "purpose": "витрина"}, "Свадебные платья"],
    "content_directions": ["Образы с платьями", "Свадебная коллекция"],
    "publishing_cadence": {"text": "3 пина в день"},
    "seasonal_plans": [{"period": "Декабрь", "idea": "Новогодние платья"}],
    "rationale": [
        {"claim": "Ниша — женская одежда", "basis": ["profile:niche", "profile:fake"]},
        {"claim": "Аудитория ищет вечерние платья", "basis": ["profile:nonexistent"]},
        {"claim": "", "basis": ["profile:niche"]},
    ],
    "hypotheses": ["Зимой спрос выше"],
    "missing_data": ["Бюджет не указан"],
}
REFS = {"profile:niche", "profile:audience", "user_message:7"}


class CleanPayloadTest(SimpleTestCase):
    def test_rationale_without_real_source_becomes_hypothesis(self):
        out = st.clean_payload(RAW, allowed_refs=REFS)
        self.assertEqual(out["rationale"], [{"claim": "Ниша — женская одежда", "basis": ["profile:niche"]}])
        self.assertIn("Аудитория ищет вечерние платья", out["hypotheses"])
        self.assertIn("Зимой спрос выше", out["hypotheses"])

    def test_cadence_is_hypothesis_unless_user_stated_it(self):
        self.assertEqual(st.clean_payload(RAW, allowed_refs=REFS)["publishing_cadence"],
                         {"text": "3 пина в день", "basis": "hypothesis"})
        stated = st.clean_payload(RAW, allowed_refs=REFS, user_stated_cadence="3 пина в день")
        self.assertEqual(stated["publishing_cadence"]["basis"], "user")

    def test_user_exclusions_are_enforced_in_code(self):
        out = st.clean_payload(RAW, allowed_refs=REFS, exclusions=["свадебн"])
        kept = {k: v for k, v in out.items() if k != "exclusions"}
        self.assertNotIn("свадебн", repr(kept).casefold())
        self.assertEqual([b["name"] for b in out["recommended_boards"]], ["Вечерние платья"])
        self.assertEqual(out["content_directions"], ["Образы с платьями"])
        self.assertEqual(out["exclusions"], ["свадебн"])

    def test_bounds_and_junk_are_dropped(self):
        raw = {"goals": ["g"] * 20 + [None, 5, {"x": 1}], "content_directions": ["x" * 1000],
               "keyword_clusters": [{"name": "A", "keywords": ["k"] * 40}, {"name": "", "keywords": ["z"]}, "bad"],
               "seasonal_plans": [{"period": "Май"}, "bad"], "unknown_key": "ignored"}
        out = st.clean_payload(raw, allowed_refs=REFS)
        self.assertEqual(len(out["goals"]), 5)
        self.assertEqual(len(out["content_directions"][0]), st.TEXT_LIMIT)
        self.assertEqual(len(out["keyword_clusters"]), 1)
        self.assertEqual(len(out["keyword_clusters"][0]["keywords"]), st.KEYWORDS_PER_CLUSTER)
        self.assertEqual(out["seasonal_plans"], [])
        self.assertNotIn("unknown_key", out)

    def test_internal_field_names_never_reach_the_user(self):
        raw = {**RAW,
               "missing_data": ["Нет ключевых слов из research.keywords", "Нет данных об аккаунте"],
               "hypotheses": ["Опираясь на profile:niche, спрос растёт", "Зимой спрос выше"],
               "priorities": ["Платья", "Использовать allowed_refs"],
               "rationale": [{"claim": "Берём business_memory как факт", "basis": ["profile:niche"]},
                             {"claim": "Ниша — женская одежда", "basis": ["profile:niche"]}]}
        out = st.clean_payload(raw, allowed_refs=REFS)
        self.assertEqual(out["missing_data"], ["Нет данных об аккаунте"])
        self.assertEqual(out["hypotheses"], ["Зимой спрос выше"])
        self.assertEqual(out["priorities"], ["Платья"])
        self.assertEqual([r["claim"] for r in out["rationale"]], ["Ниша — женская одежда"])

    def test_unusable_draft_is_refused(self):
        for raw in (None, [], "text", {}, {"goals": [], "content_directions": []}):
            with self.subTest(raw=raw), self.assertRaises(st.StrategyError):
                st.clean_payload(raw, allowed_refs=REFS)


class StrategyVersionTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="s", email="s@example.com", password="x")
        self.workspace = Workspace.objects.create(name="W", slug="w", created_by=self.user)
        self.business = Business.objects.create(
            workspace=self.workspace, name="Shop", slug="shop", niche="Женская одежда",
            audience="Женщины 25-45", goals="Трафик",
        )

    def draft(self, **extra):
        payload = st.clean_payload({**RAW, **extra}, allowed_refs=REFS)
        return st.create_draft(self.business, self.user, payload, sources=st.build_sources(st.profile_facts(self.business)))

    def test_profile_facts_and_missing_fields(self):
        self.assertEqual(set(st.profile_facts(self.business)), {
            "profile:name", "profile:niche", "profile:audience", "profile:goals"})
        self.assertEqual(st.missing_profile_fields(self.business), [])
        empty = Business.objects.create(workspace=self.workspace, name="E", slug="e")
        self.assertEqual(st.missing_profile_fields(empty), ["ниша", "целевая аудитория", "цели бизнеса"])

    def test_versions_are_numbered_and_old_draft_is_superseded(self):
        first, second = self.draft(), self.draft()
        first.refresh_from_db()
        self.assertEqual((first.number, second.number), (1, 2))
        self.assertEqual(first.status, StrategyVersion.Status.SUPERSEDED)
        self.assertEqual(Strategy.objects.filter(business=self.business).count(), 1)
        self.assertEqual(st.pending_draft(self.business), second)
        self.assertIsNone(st.active_version(self.business))
        self.assertTrue(any(s["ref"] == "profile:niche" for s in second.sources))

    def test_confirmation_activates_and_supersedes_previous_confirmed(self):
        v1 = st.confirm_version(self.draft(), self.user)
        self.assertEqual(st.active_version(self.business), v1)
        self.assertEqual((v1.confirmed_by, v1.status), (self.user, StrategyVersion.Status.CONFIRMED))
        v2 = st.confirm_version(self.draft(change_note="x"), self.user)
        v1.refresh_from_db()
        self.assertEqual(v1.status, StrategyVersion.Status.SUPERSEDED)
        self.assertEqual(st.active_version(self.business), v2)
        self.assertEqual(Strategy.objects.get().status, Strategy.Status.ACTIVE)
        self.assertEqual(v1.goals, RAW["goals"])  # history is never rewritten

    def test_only_current_draft_can_be_confirmed(self):
        old, new = self.draft(), self.draft()
        with self.assertRaises(st.StrategyError):
            st.confirm_version(old, self.user)
        st.confirm_version(new, self.user)
        with self.assertRaises(st.StrategyError):
            st.confirm_version(new, self.user)

    def test_other_business_has_no_strategy(self):
        self.draft()
        other = Business.objects.create(workspace=self.workspace, name="O", slug="o")
        self.assertIsNone(st.pending_draft(other))
        self.assertIsNone(st.active_version(other))
