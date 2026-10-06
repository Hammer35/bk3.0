"""Content plan from a confirmed strategy version; the model is a stub, no live API."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.businesses.models import Business
from apps.strategist import content_plan as cp
from apps.strategist import strategy as st
from apps.strategist.models import AIConversation, AIMessage, BusinessMemory, ContentPlan, StrategyVersion
from apps.workspaces.models import Membership, Workspace

VERSION_RAW = {
    "goals": ["Трафик"],
    "content_directions": ["Образы с платьями", "Гайды по уходу"],
    "recommended_boards": [{"name": "Вечерние платья", "purpose": ""}],
    "keyword_clusters": [{"name": "Платья", "keywords": ["evening dress", "midi dress"]}],
}
ITEMS = {"items": [
    {"target_week": 2, "direction": "образы с платьями", "board": "вечерние платья", "keyword": "Evening Dress",
     "search_intent": "идеи", "content_type": "PIN", "priority": 1, "idea": "Вечерний образ с платьем миди"},
    {"target_week": 1, "direction": "Гайды по уходу", "board": "Выдуманная доска", "keyword": "invented",
     "content_type": "GIF", "priority": 9, "idea": "Как стирать лён"},
    {"target_week": 1, "direction": "Выдуманное направление", "idea": "Не должно пройти"},
    {"target_week": 9, "direction": "Гайды по уходу", "idea": "Неделя вне горизонта"},
    {"target_week": 3, "direction": "Гайды по уходу", "idea": "как стирать лён"},   # duplicate
    {"target_week": "1", "direction": "Гайды по уходу", "idea": "Строковая неделя"},
    {"target_week": 4, "direction": "Гайды по уходу", "idea": ""},
    "bad",
]}


def completion(payload):
    return SimpleNamespace(content=json.dumps(payload, ensure_ascii=False), model="stub", prompt_tokens=3, completion_tokens=4, total_tokens=7)


class CleanItemsTest(SimpleTestCase):
    version = SimpleNamespace(
        content_directions=VERSION_RAW["content_directions"], recommended_boards=VERSION_RAW["recommended_boards"],
        keyword_clusters=VERSION_RAW["keyword_clusters"], exclusions=[])

    def test_items_must_point_at_real_parts_of_the_strategy(self):
        items = cp.clean_items(ITEMS, self.version)
        self.assertEqual([i["idea"] for i in items], ["Как стирать лён", "Вечерний образ с платьем миди"])
        first, second = items
        self.assertEqual((first["board"], first["keyword"], first["content_type"], first["priority"]), ("", "", "PIN", 2))
        self.assertEqual((second["board"], second["keyword"], second["direction"]), ("Вечерние платья", "evening dress", "Образы с платьями"))

    def test_exclusions_and_empty_results(self):
        self.version.exclusions = ["лён"]
        with self.assertRaises(cp.PlanError):
            cp.clean_items({"items": [ITEMS["items"][1]]}, self.version)
        self.version.exclusions = []
        for raw in (None, {}, {"items": []}, {"items": "x"}, [1]):
            with self.subTest(raw=raw), self.assertRaises(cp.PlanError):
                cp.clean_items(raw, self.version)

    def test_item_count_is_bounded(self):
        many = {"items": [{"target_week": 1, "direction": "Гайды по уходу", "idea": f"идея {i}"} for i in range(60)]}
        self.assertEqual(len(cp.clean_items(many, self.version)), cp.MAX_ITEMS)


class ContentPlanChatTest(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("plan-owner")
        self.workspace = Workspace.objects.create(name="P", slug="p", created_by=self.owner)
        Membership.objects.create(workspace=self.workspace, user=self.owner, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=self.workspace, name="Shop", slug="shop", niche="Одежда", audience="Женщины", goals="Трафик")
        self.conversation = AIConversation.objects.create(business=self.business, created_by=self.owner)
        self.client.force_login(self.owner)
        self.complete = self.enterContext(patch("apps.strategist.content_plan.GigaChatProvider.complete", return_value=completion(ITEMS)))
        self.url = reverse("strategist:session", kwargs={"workspace_slug": "p", "business_slug": "shop", "session_slug": self.conversation.slug})

    def confirmed_version(self):
        payload = st.clean_payload(VERSION_RAW, allowed_refs=set(), allowed_keywords=None)
        return st.confirm_version(st.create_draft(self.business, self.owner, payload, sources=[]), self.owner)

    def say(self, text):
        response = self.client.post(self.url, {"message": text}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.url = response.json()["conversation_url"]
        return self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")

    def test_plan_requires_confirmed_strategy(self):
        self.assertIn("подтверждённой стратегии", self.say("Составь контент-план").content)
        st.create_draft(self.business, self.owner, st.clean_payload(VERSION_RAW, allowed_refs=set()), sources=[])
        self.assertIn("подтверждённой стратегии", self.say("Составь контент-план").content)  # a draft is not enough
        self.complete.assert_not_called()
        self.assertFalse(ContentPlan.objects.exists())

    def test_build_show_confirm_and_record_decision(self):
        version = self.confirmed_version()
        answer = self.say("Составь контент-план")
        self.assertEqual((answer.provider, answer.total_tokens), ("content-plan", 7))
        self.assertIn("Неделя 1:\n- Как стирать лён [Гайды по уходу]", answer.content)
        self.assertIn("Неделя 2:\n- Вечерний образ с платьем миди [Образы с платьями; доска «Вечерние платья»; ключ: evening dress; идеи]", answer.content)
        self.assertIn("не расписание публикаций", answer.content)
        plan = ContentPlan.objects.get()
        self.assertEqual((plan.status, plan.strategy_version, plan.items.count()), ("DRAFT", version, 2))
        confirmed = self.say("Подтверждаю контент-план")
        self.assertEqual(confirmed.model, "content-plan-confirmed")
        plan.refresh_from_db()
        self.assertEqual((plan.status, plan.confirmed_by), ("CONFIRMED", self.owner))
        self.assertTrue(BusinessMemory.objects.filter(kind="DECISION", text__startswith="Подтверждён контент-план").exists())

    def test_confirming_strategy_phrases_do_not_cross_over(self):
        self.confirmed_version()
        self.say("Составь контент-план")
        self.assertFalse(cp._CONFIRM.match("Подтверждаю стратегию"))
        self.assertFalse(StrategyVersion.objects.filter(status="DRAFT").exists())
        from apps.strategist import strategy_chat as sc
        self.assertFalse(sc._is_confirmation("Подтверждаю контент-план"))

    def test_new_draft_supersedes_old_and_stale_strategy_blocks_confirmation(self):
        version = self.confirmed_version()
        self.say("Составь контент-план")
        self.say("Составь контент-план")
        self.assertEqual(sorted(ContentPlan.objects.values_list("status", flat=True)), ["DRAFT", "SUPERSEDED"])
        newer = st.create_draft(self.business, self.owner, st.clean_payload(VERSION_RAW, allowed_refs=set()), sources=[])
        st.confirm_version(newer, self.owner)
        self.assertIn("уже заменена", self.say("Подтверждаю контент-план").content)
        self.assertEqual(ContentPlan.objects.get(status="DRAFT").strategy_version, version)

    def test_invalid_model_output_and_viewer(self):
        self.confirmed_version()
        self.complete.return_value = completion({"items": [{"target_week": 1, "direction": "нет такого", "idea": "x"}]})
        self.assertIn("Не получилось собрать надёжный контент-план", self.say("Составь контент-план").content)
        self.assertFalse(ContentPlan.objects.exists())
        viewer = get_user_model().objects.create_user("plan-viewer")
        Membership.objects.create(workspace=self.workspace, user=viewer, role=Membership.Role.VIEWER)
        message = AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.USER, content="Составь контент-план")
        self.assertIn("владелец, администратор", cp.content_plan_reply(user_message=message, actor=viewer).content)
