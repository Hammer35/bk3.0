"""The chat model must not claim it launched, published or saved anything."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.businesses.models import Business
from apps.strategist.advice import FAKE_ACTION_NOTE, enforce_no_fake_actions
from apps.strategist.models import AIConversation, Strategy
from apps.strategist.prompts import build_strategist_system_prompt
from apps.strategist.providers import GigaChatCompletion
from apps.workspaces.models import Membership, Workspace


class EnforceTest(SimpleTestCase):
    def test_claims_of_launch_publication_or_saving_get_a_correction(self):
        for text in ("Стратегия запущена. Следующий шаг — публикация.", "Хорошо, приступаю к реализации стратегии.",
                     "Запускаю стратегию прямо сейчас", "Контент опубликован", "Публикую пины завтра", "План сохранён."):
            with self.subTest(text=text):
                out = enforce_no_fake_actions(text)
                self.assertTrue(out.startswith(text))
                self.assertTrue(out.endswith(FAKE_ACTION_NOTE))

    def test_ordinary_replies_and_repeats_are_untouched(self):
        for text in ("Стратегия строится по профилю бизнеса: сначала цели, потом ключи.", "Для публикации нужно ваше одобрение.", "", None):
            self.assertEqual(enforce_no_fake_actions(text), text)
        once = enforce_no_fake_actions("Стратегия запущена.")
        self.assertEqual(enforce_no_fake_actions(once), once)  # never appended twice

    def test_system_prompt_forbids_pretending_and_names_the_commands(self):
        business = type("B", (), dict(name="B", website="", niche="N", subniche="", market="", audience="", goals=""))()
        prompt = build_strategist_system_prompt(business)
        for part in ("Ты сам ничего не запускаешь", "Построй стратегию", "Составь контент-план", "Создай пины по контент-плану"):
            self.assertIn(part, prompt)


class ChatFlowTest(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("fake-owner")
        workspace = Workspace.objects.create(name="F", slug="f", created_by=user)
        Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=workspace, name="Shop", slug="shop", niche="Лён", audience="Женщины", goals="Трафик")
        conversation = AIConversation.objects.create(business=self.business, created_by=user)
        self.client.force_login(user)
        self.url = reverse("strategist:session", kwargs={"workspace_slug": "f", "business_slug": "shop", "session_slug": conversation.slug})

    def test_a_loose_request_for_a_strategy_goes_to_the_structured_flow_not_to_free_chat(self):
        reply = GigaChatCompletion(content='{"goals":["Трафик"],"content_directions":["Образы"]}', model="m", prompt_tokens=1,
                                   completion_tokens=1, total_tokens=2)
        with patch("apps.strategist.strategy_chat.GigaChatProvider.complete", return_value=reply):
            response = self.client.post(self.url, {"message": "Настрой стратегия"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Strategy.objects.count(), 1)
        self.assertIn("Стратегия, версия 1 (черновик)", response.json()["messages_html"])

    def test_a_fake_launch_claim_from_the_free_chat_model_is_corrected(self):
        claim = GigaChatCompletion(content="Хорошо, приступаю к реализации. Стратегия запущена.", model="m", prompt_tokens=1,
                                   completion_tokens=1, total_tokens=2)
        with patch("apps.strategist.services.GigaChatProvider.complete", return_value=claim), \
             patch("apps.strategist.services.search_knowledge", return_value=[]), patch("apps.strategist.services.search_knowledge_lexical", return_value=[]):
            response = self.client.post(self.url, {"message": "Расскажи, как поднять охват"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        html = response.json()["messages_html"]
        self.assertIn("я ничего не запускал", html)
        self.assertEqual(Strategy.objects.count(), 0)
