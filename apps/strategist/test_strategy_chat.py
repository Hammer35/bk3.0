"""Strategy chat flow through the authenticated view; the model is a stub, no live API."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.businesses.models import Business
from apps.strategist import strategy as st
from apps.strategist import strategy_chat as sc
from apps.strategist.models import AIConversation, AIMessage, Strategy, StrategyVersion
from apps.workspaces.models import Membership, Workspace

MODEL_JSON = {
    "goals": ["Трафик на каталог"],
    "priorities": ["Платья"],
    "keyword_clusters": [{"name": "Платья", "keywords": ["вечернее платье"]}],
    "recommended_boards": [{"name": "Вечерние платья", "purpose": "витрина"}, {"name": "Свадебные платья", "purpose": ""}],
    "content_directions": ["Образы с платьями", "Свадебная коллекция"],
    "publishing_cadence": {"text": "5 пинов в день"},
    "rationale": [{"claim": "Ниша — женская одежда", "basis": ["profile:niche"]},
                  {"claim": "Спрос растёт зимой", "basis": ["trend:invented"]}],
    "hypotheses": [],
    "missing_data": ["Нет данных об аккаунте"],
}


def stub_completion(payload=MODEL_JSON):
    return SimpleNamespace(content=json.dumps(payload, ensure_ascii=False), model="stub",
                           prompt_tokens=10, completion_tokens=20, total_tokens=30)


class IntentTest(SimpleTestCase):
    def test_strategy_intents_are_narrow(self):
        for text in ("Построй мне стратегию", "составь, пожалуйста, стратегию продвижения", "Сделай стратегию для магазина"):
            self.assertTrue(sc._asks_for_strategy(text), text)
        for text in ("Что такое стратегия в Pinterest?", "Расскажи про контент-план", "Почему упали переходы"):
            self.assertFalse(sc._asks_for_strategy(text), text)
        for text in ("Подтверждаю стратегию", "да, подтверждаю", "Согласен."):
            self.assertTrue(sc._is_confirmation(text), text)
        for text in ("Подтверждаю, что у меня 5 досок и вопрос про стратегию", "да", "не согласен"):
            self.assertFalse(sc._is_confirmation(text), text)

    def test_exclusion_stem(self):
        self.assertEqual(sc._exclusion_stem("Не продвигай свадебные товары"), "свадебн")
        self.assertEqual(sc._exclusion_stem("убери детские платья из стратегии"), "детск")
        self.assertIsNone(sc._exclusion_stem("не продвигай товары"))
        self.assertIsNone(sc._exclusion_stem("убери лишнее со стола"))


class StrategyChatTest(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("strategy-owner")
        self.workspace = Workspace.objects.create(name="S", slug="s", created_by=self.owner)
        Membership.objects.create(workspace=self.workspace, user=self.owner, role=Membership.Role.OWNER)
        self.business = Business.objects.create(
            workspace=self.workspace, name="Shop", slug="shop", niche="Женская одежда",
            audience="Женщины 25-45", goals="Больше трафика")
        self.conversation = AIConversation.objects.create(business=self.business, created_by=self.owner)
        self.client.force_login(self.owner)
        self.complete = self.enterContext(patch(
            "apps.strategist.strategy_chat.GigaChatProvider.complete", return_value=stub_completion()))
        self.url = reverse("strategist:session", kwargs={
            "workspace_slug": "s", "business_slug": "shop", "session_slug": self.conversation.slug})

    def say(self, text):
        response = self.client.post(self.url, {"message": text}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.url = response.json()["conversation_url"]
        return self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")

    def test_draft_confirm_exclude_flow(self):
        draft = self.say("Построй стратегию")
        self.assertEqual((draft.provider, draft.total_tokens), ("strategy", 30))
        self.assertIn("версия 1 (черновик)", draft.content)
        self.assertIn("5 пинов в день (гипотеза, данными не подтверждено)", draft.content)
        self.assertIn("Спрос растёт зимой", draft.content.split("Гипотезы")[1])  # no real source -> hypothesis
        self.assertNotIn("trend:invented", draft.content)
        self.assertIn("профиль: ниша", draft.content)
        self.assertIsNone(st.active_version(self.business))

        revised = self.say("Не продвигай свадебные товары")
        self.assertEqual(self.complete.call_count, 1)  # exclusion is deterministic, no model call
        self.assertIn("версия 2 (черновик)", revised.content)
        self.assertNotIn("Свадебн", revised.content.split("Исключено по вашей просьбе")[0])
        v1 = StrategyVersion.objects.get(number=1)
        self.assertEqual(v1.status, StrategyVersion.Status.SUPERSEDED)
        self.assertIn("Свадебные платья", [b["name"] for b in v1.recommended_boards])  # history untouched

        confirmed = self.say("Подтверждаю стратегию")
        self.assertIn("версия 2, подтверждена", confirmed.content)
        active = st.active_version(self.business)
        self.assertEqual((active.number, active.confirmed_by), (2, self.owner))
        self.assertEqual(self.complete.call_count, 1)

    def test_missing_profile_asks_one_question_without_model(self):
        self.business.audience = ""
        self.business.save()
        answer = self.say("Построй стратегию")
        self.assertIn("целевая аудитория", answer.content)
        self.assertEqual(self.complete.call_count, 0)
        self.assertFalse(Strategy.objects.exists())

    def test_viewer_cannot_confirm_or_build(self):
        viewer = get_user_model().objects.create_user("strategy-viewer")
        Membership.objects.create(workspace=self.workspace, user=viewer, role=Membership.Role.VIEWER)
        message = AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.USER, content="Построй стратегию")
        answer = sc.strategy_reply(user_message=message, actor=viewer)
        self.assertIn("владелец, администратор и редактор", answer.content)
        self.assertIn("владелец, администратор и редактор", sc.strategy_reply(user_message=message, actor=None).content)
        self.assertEqual((self.complete.call_count, Strategy.objects.count()), (0, 0))

    def test_confirmation_without_draft_and_ordinary_messages_do_not_touch_strategy(self):
        self.assertIsNone(sc.strategy_reply(
            user_message=AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.USER, content="Подтверждаю стратегию"),
            actor=self.owner))
        self.assertIsNone(sc.strategy_reply(
            user_message=AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.USER, content="Не продвигай свадебные товары"),
            actor=self.owner))
        self.assertFalse(Strategy.objects.exists())

    def test_invalid_model_output_saves_nothing(self):
        for bad in ("не json", "{}", json.dumps({"goals": []})):
            with self.subTest(bad=bad):
                self.complete.return_value = SimpleNamespace(content=bad, model="stub", prompt_tokens=1, completion_tokens=1, total_tokens=2)
                answer = self.say("Построй стратегию")
                self.assertIn("Не получилось собрать надёжный черновик", answer.content)
                self.assertFalse(Strategy.objects.exists())

    def test_model_revision_keeps_user_exclusions(self):
        self.say("Построй стратегию")
        self.say("Не продвигай свадебные товары")
        revised = self.say("Измени стратегию: добавь больше про костюмы")  # model re-adds wedding content
        self.assertIn("версия 3 (черновик)", revised.content)
        self.assertNotIn("Свадебн", revised.content.split("Исключено по вашей просьбе")[0])
        self.assertEqual(self.complete.call_count, 2)
