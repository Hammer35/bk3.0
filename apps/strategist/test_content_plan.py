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

    def test_rejected_answer_is_retried_once_with_a_note_and_tokens_are_summed(self):
        self.confirmed_version()
        bad = completion({"items": [{"target_week": 1, "direction": "нет такого", "idea": "x"}]})
        self.complete.side_effect = [bad, completion(ITEMS)]
        answer = self.say("Составь контент-план")
        self.assertEqual((answer.provider, answer.total_tokens), ("content-plan", 14))
        self.assertEqual(self.complete.call_count, 2)
        second_messages = self.complete.call_args.args[0]
        self.assertEqual(second_messages[-1]["content"], cp.RETRY_NOTE)
        self.assertEqual(ContentPlan.objects.count(), 1)
        self.complete.side_effect = [bad, bad]
        self.assertIn("Не получилось собрать надёжный контент-план", self.say("Составь контент-план").content)
        self.assertEqual(self.complete.call_count, 4)  # never more than two attempts per request

    def test_plan_request_carries_the_business_profile_so_ideas_stay_grounded(self):
        import json as _json
        from apps.strategist import content_plan as plan_module
        self.confirmed_version()
        self.say("Составь контент-план")
        request = _json.loads(self.complete.call_args.args[0][1]["content"])
        self.assertEqual(request["business"]["niche"], "Одежда")
        self.assertIn("Образы с платьями", request["strategy"]["content_directions"])
        system = self.complete.call_args.args[0][0]["content"]
        self.assertIn("не вводи товары, категории, бренды и ниши, которых нет", system)
        self.assertEqual(system, plan_module.SYSTEM)

    def test_instruction_like_ideas_and_invented_offers_are_dropped_and_trigger_one_retry(self):
        self.confirmed_version()
        def item(idea, week=1):
            return {"target_week": week, "direction": "Образы с платьями", "idea": idea}
        bad = completion({"items": [item("Пин с подборкой платьев с хештегами #лён"), item("Опубликовать пин со скидкой 20%"),
                                    item("Создать серию пинов про лён"), item("Акционные предложения на платья"), item("Как носить льняное платье летом", 2)]})
        good = completion({"items": [item("Как носить льняное платье летом"), item("С чем сочетать льняной костюм", 2)]})
        self.complete.side_effect = [bad, good]
        self.say("Составь контент-план")
        self.assertEqual(self.complete.call_count, 2)
        self.assertEqual(self.complete.call_args.args[0][-1]["content"], cp.RETRY_NOTE)
        self.assertEqual(sorted(ContentPlan.objects.get().items.values_list("idea", flat=True)),
                         ["Как носить льняное платье летом", "С чем сочетать льняной костюм"])

    def test_valid_part_of_the_first_answer_survives_a_failed_retry(self):
        self.confirmed_version()
        first = completion({"items": [{"target_week": 1, "direction": "Образы с платьями", "idea": "Как носить льняное платье"},
                                      {"target_week": 1, "direction": "Образы с платьями", "idea": "Пин с акцией"}]})
        broken = completion({"items": [{"target_week": 1, "direction": "нет такого", "idea": "x"}]})
        self.complete.side_effect = [first, broken]
        self.say("Составь контент-план")
        self.assertEqual(list(ContentPlan.objects.get().items.values_list("idea", flat=True)), ["Как носить льняное платье"])

    def test_confirmation_with_nothing_to_confirm_gets_a_short_answer_without_a_model(self):
        self.confirmed_version()
        self.assertIn("нет черновика контент-плана", self.say("Подтверждаю контент-план").content)
        self.assertIn("нет черновика стратегии", self.say("Подтверждаю стратегию").content)
        self.complete.assert_not_called()
        self.assertEqual(AIMessage.objects.filter(role="ASSISTANT", provider="gigachat").count(), 0)

    def test_invalid_model_output_and_viewer(self):
        self.confirmed_version()
        self.complete.return_value = completion({"items": [{"target_week": 1, "direction": "нет такого", "idea": "x"}]})
        self.assertIn("Не получилось собрать надёжный контент-план", self.say("Составь контент-план").content)
        self.assertFalse(ContentPlan.objects.exists())
        viewer = get_user_model().objects.create_user("plan-viewer")
        Membership.objects.create(workspace=self.workspace, user=viewer, role=Membership.Role.VIEWER)
        message = AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.USER, content="Составь контент-план")
        self.assertIn("владелец, администратор", cp.content_plan_reply(user_message=message, actor=viewer).content)


class BusinessDeletionTest(TestCase):
    def test_business_with_strategy_plan_memory_and_research_can_be_deleted(self):
        from django.utils import timezone
        from apps.strategist import memory as mem
        from apps.strategist.models import ResearchSnapshot, Strategy
        owner = get_user_model().objects.create_user("delete-owner")
        workspace = Workspace.objects.create(name="D", slug="d", created_by=owner)
        business = Business.objects.create(workspace=workspace, name="Shop", slug="shop")
        version = st.confirm_version(st.create_draft(business, owner, st.clean_payload(VERSION_RAW, allowed_refs=set()), sources=[]), owner)
        cp.create_plan(business, owner, version, cp.clean_items(ITEMS, version))
        mem.record_decision(business, owner, "решение", source_ref="x")
        ResearchSnapshot.objects.create(business=business, candidates=[], researched_at=timezone.now())
        business.delete()
        self.assertEqual((Strategy.objects.count(), StrategyVersion.objects.count(), ContentPlan.objects.count(),
                          BusinessMemory.objects.count(), ResearchSnapshot.objects.count()), (0, 0, 0, 0, 0))


class PlanBuildOnThePageTest(TestCase):
    """The content plan can be built from the strategy page, not only from the chat."""

    def setUp(self):
        self.owner = get_user_model().objects.create_user("build-owner")
        self.workspace = Workspace.objects.create(name="B", slug="b", created_by=self.owner)
        Membership.objects.create(workspace=self.workspace, user=self.owner, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=self.workspace, name="Shop", slug="shop", niche="Одежда", audience="Женщины", goals="Трафик")
        self.client.force_login(self.owner)
        self.page = reverse("strategist:strategy", kwargs={"workspace_slug": "b", "business_slug": "shop"})
        self.build = reverse("strategist:plan-build", kwargs={"workspace_slug": "b", "business_slug": "shop"})
        self.generate = reverse("strategist:pin-generate", kwargs={"workspace_slug": "b", "business_slug": "shop"})
        self.complete = self.enterContext(patch("apps.strategist.content_plan.GigaChatProvider.complete", return_value=completion(ITEMS)))

    def confirm_strategy(self):
        payload = st.clean_payload(VERSION_RAW, allowed_refs=set(), allowed_keywords=None)
        return st.confirm_version(st.create_draft(self.business, self.owner, payload, sources=[]), self.owner)

    def test_button_appears_only_for_an_active_strategy_without_a_plan(self):
        self.assertNotIn(self.build, self.client.get(self.page).content.decode())
        self.confirm_strategy()
        html = self.client.get(self.page).content.decode()
        self.assertIn(self.build, html)
        self.assertIn("Составить контент-план", html)

    def test_post_builds_a_draft_plan_shown_with_confirm_and_rebuild(self):
        self.confirm_strategy()
        response = self.client.post(self.build, follow=True)
        self.assertContains(response, "Контент-план составлен")
        self.assertEqual(ContentPlan.objects.get().status, "DRAFT")
        self.assertContains(response, "Подтвердить контент-план")
        self.assertContains(response, "Составить заново")
        self.client.post(self.build)
        self.assertEqual(sorted(ContentPlan.objects.values_list("status", flat=True)), ["DRAFT", "SUPERSEDED"])

    def test_refusals_and_failures_are_explained_without_a_model_call_or_a_plan(self):
        self.assertContains(self.client.post(self.build, follow=True), "Контент-план строится по подтверждённой стратегии")
        self.complete.assert_not_called()
        self.confirm_strategy()
        self.complete.return_value = completion({"items": [{"target_week": 1, "direction": "нет такого", "idea": "x"}]})
        self.assertContains(self.client.post(self.build, follow=True), "Не получилось собрать надёжный контент-план")
        from apps.strategist.providers import GigaChatProviderError
        self.complete.side_effect = GigaChatProviderError("down")
        self.assertContains(self.client.post(self.build, follow=True), "Модель сейчас недоступна")
        self.assertFalse(ContentPlan.objects.exists())

    def test_rights_and_method(self):
        self.confirm_strategy()
        self.assertEqual(self.client.get(self.build).status_code, 404)
        viewer = get_user_model().objects.create_user("build-viewer")
        Membership.objects.create(workspace=self.workspace, user=viewer, role=Membership.Role.VIEWER)
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(self.build).status_code, 404)
        self.assertNotIn(self.build, self.client.get(self.page).content.decode())
        self.complete.assert_not_called()

    def test_generation_page_shows_the_steps_and_the_one_next_action(self):
        html = self.client.get(self.generate).content.decode()
        self.assertIn("Чтобы создавать пины, нужны два шага", html)
        self.assertIn("Стратегии пока нет", html)
        self.assertIn("Настрой стратегию", html)
        draft = st.create_draft(self.business, self.owner, st.clean_payload(VERSION_RAW, allowed_refs=set(), allowed_keywords=None), sources=[])
        html = self.client.get(self.generate).content.decode()
        self.assertIn("Есть черновик, он ждёт подтверждения", html)
        st.confirm_version(draft, self.owner)
        html = self.client.get(self.generate).content.decode()
        self.assertIn("Подтверждена, версия 1", html)
        self.assertIn(self.build, html)  # the next action is a button that builds the plan right here
        self.client.post(self.build)
        html = self.client.get(self.generate).content.decode()
        self.assertIn("Проверить и подтвердить контент-план", html)
        self.client.post(reverse("strategist:plan-confirm", kwargs={"workspace_slug": "b", "business_slug": "shop"}))
        self.assertIn("data-gen-form", self.client.get(self.generate).content.decode())
