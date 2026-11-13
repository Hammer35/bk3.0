"""Business memory commands, isolation, prompt use and decision history; no live model."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.businesses.models import Business
from apps.strategist import memory as mem
from apps.strategist.models import AIConversation, AIMessage, BusinessMemory
from apps.strategist.prompts import build_strategist_system_prompt
from apps.workspaces.models import Membership, Workspace


class CommandPatternTest(SimpleTestCase):
    def test_commands_are_anchored_to_message_start(self):
        for text in ("Запомни: у нас нет бюджета на рекламу", "запомни, что мы шьём из льна", "Запиши — доставка по РФ"):
            self.assertTrue(mem._REMEMBER.match(text), text)
        for text in ("Я не могу запомнить пароль от кабинета", "Как запомнить аудиторию?", "что запомнить для стратегии?"):
            self.assertFalse(mem._REMEMBER.match(text), text)
        self.assertTrue(mem._FORGET.match("Забудь: про бюджет"))
        self.assertFalse(mem._FORGET.match("Я не забуду про бюджет"))
        for text in ("Что ты помнишь?", "что ты знаешь о моём бизнесе", "Покажи память"):
            self.assertTrue(mem._SHOW.search(text), text)

    def test_sensitive_text_is_detected(self):
        for text in ("мой пароль 12345", "api key: abc", "почта ivan@example.com", "карта 4276 1234 5678 9012",
                     "телефон +7 912 345-67-89", "токен доступа"):
            self.assertTrue(mem._SENSITIVE.search(text), text)
        for text in ("шьём из льна и хлопка", "доставка за 3 дня", "цена от 1990 до 4990 рублей"):
            self.assertFalse(mem._SENSITIVE.search(text), text)


class MemoryChatTest(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("memory-owner")
        self.workspace = Workspace.objects.create(name="M", slug="m", created_by=self.owner)
        Membership.objects.create(workspace=self.workspace, user=self.owner, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=self.workspace, name="Shop", slug="shop", niche="Одежда", audience="Женщины", goals="Трафик")
        self.conversation = AIConversation.objects.create(business=self.business, created_by=self.owner)
        self.client.force_login(self.owner)
        self.complete = self.enterContext(patch("apps.strategist.strategy_chat.GigaChatProvider.complete"))
        self.url = reverse("strategist:session", kwargs={"workspace_slug": "m", "business_slug": "shop", "session_slug": self.conversation.slug})

    def say(self, text):
        response = self.client.post(self.url, {"message": text}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.url = response.json()["conversation_url"]
        return self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")

    def test_remember_show_forget(self):
        answer = self.say("Запомни: бюджета на рекламу нет")
        self.assertEqual((answer.provider, answer.total_tokens), ("memory", 0))
        self.assertIn("не проверял его по внешним источникам", answer.content)
        item = BusinessMemory.objects.get()
        self.assertEqual((item.kind, item.text, item.created_by), ("FACT", "бюджета на рекламу нет", self.owner))
        self.assertTrue(item.source_ref.startswith("user_message:"))
        self.assertIn("бюджета на рекламу нет", self.say("Что ты помнишь?").content)
        self.assertIn("уже помню", self.say("Запомни: Бюджета на рекламу нет").content)
        self.assertIn("Забыл:\n- бюджета на рекламу нет", self.say("Забудь: бюджета").content)
        self.assertFalse(BusinessMemory.objects.exists())
        self.assertIn("Не нашёл", self.say("Забудь: бюджета").content)
        self.assertIn("Пока ничего не помню", self.say("Что ты помнишь?").content)
        self.complete.assert_not_called()

    def test_refusals(self):
        for text, expected in (("Запомни: пароль от кабинета 123", "не храню пароли"),
                               ("Запомни: " + "ж" * 301, "Слишком длинно"),
                               ("Забудь: да", "хотя бы три символа")):
            with self.subTest(text=text[:30]):
                self.assertIn(expected, self.say(text).content)
        self.assertFalse(BusinessMemory.objects.exists())

    def test_limit_of_facts(self):
        for i in range(mem.MAX_FACTS):
            BusinessMemory.objects.create(business=self.business, kind="FACT", text=f"факт {i}", source_ref="x", created_by=self.owner)
        self.assertIn("уже 50 фактов", self.say("Запомни: ещё один").content)
        self.assertEqual(BusinessMemory.objects.count(), mem.MAX_FACTS)

    def test_viewer_can_read_but_not_write(self):
        viewer = get_user_model().objects.create_user("memory-viewer")
        Membership.objects.create(workspace=self.workspace, user=viewer, role=Membership.Role.VIEWER)
        BusinessMemory.objects.create(business=self.business, kind="FACT", text="льняная одежда", source_ref="x", created_by=self.owner)

        def ask(text, actor):
            message = AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.USER, content=text)
            return mem.memory_reply(user_message=message, actor=actor).content
        self.assertIn("льняная одежда", ask("Что ты помнишь?", viewer))
        for text in ("Запомни: новый факт", "Забудь: льняная"):
            self.assertIn("владелец, администратор", ask(text, viewer))
            self.assertIn("владелец, администратор", ask(text, None))
        self.assertEqual(list(BusinessMemory.objects.values_list("text", flat=True)), ["льняная одежда"])

    def test_memory_is_isolated_per_business_and_deleted_with_it(self):
        other = Business.objects.create(workspace=self.workspace, name="Other", slug="other")
        BusinessMemory.objects.create(business=other, kind="FACT", text="чужой факт", source_ref="x", created_by=self.owner)
        self.assertEqual(mem.prompt_lines(self.business), [])
        self.say("Запомни: свой факт")
        self.assertEqual(mem.prompt_lines(self.business), ["свой факт"])
        self.assertNotIn("чужой факт", self.say("Что ты помнишь?").content)
        self.business.delete()
        self.assertEqual(list(BusinessMemory.objects.values_list("text", flat=True)), ["чужой факт"])

    def test_system_prompt_marks_memory_as_user_reported(self):
        plain = build_strategist_system_prompt(self.business)
        self.assertNotIn("попросил запомнить", plain)
        with_memory = build_strategist_system_prompt(self.business, memory_facts=["шьём из льна"])
        self.assertIn("попросил запомнить", with_memory)
        self.assertIn("- шьём из льна", with_memory)
        self.assertIn("не проверенные внешние факты", with_memory)

    def test_strategy_can_cite_memory_and_decisions_are_recorded(self):
        self.say("Запомни: шьём только из льна")
        item = BusinessMemory.objects.get(kind="FACT")

        def model(messages, **kwargs):
            request = json.loads(messages[1]["content"])
            self.assertEqual(request["business_memory"], {f"memory:{item.pk}": "шьём только из льна"})
            return SimpleNamespace(content=json.dumps({
                "goals": ["Трафик"], "content_directions": ["Лён"],
                "rationale": [{"claim": "Все изделия льняные", "basis": [f"memory:{item.pk}", "memory:999999"]}]},
                ensure_ascii=False), model="stub", prompt_tokens=1, completion_tokens=1, total_tokens=2)
        self.complete.side_effect = model
        draft = self.say("Построй стратегию")
        self.assertIn("Все изделия льняные [память бизнеса]", draft.content)
        self.say("Не продвигай свадебные товары")
        self.say("Подтверждаю стратегию")
        decisions = list(BusinessMemory.objects.filter(kind="DECISION").values_list("text", "reason"))
        self.assertIn(("Исключено из стратегии: свадебн…", "по просьбе пользователя"), decisions)
        self.assertTrue(any(t.startswith("Подтверждена стратегия, версия 2") for t, _ in decisions))
        shown = self.say("Что ты помнишь?").content
        self.assertIn("Факты, которые ты просил запомнить:", shown)
        self.assertIn("Последние решения:", shown)
        self.assertIn("Подтверждена стратегия, версия 2", shown)
        self.assertEqual(mem.prompt_lines(self.business), ["шьём только из льна"])  # decisions never enter the prompt
