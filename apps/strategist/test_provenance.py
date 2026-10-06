"""Prompt versions and context manifests on stored replies; no live model."""
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from apps.businesses.models import Business
from apps.knowledge.services import KnowledgeHit
from apps.pinterest.models import PinterestAccount
from apps.strategist import provenance as pv
from apps.strategist.models import AIConversation, AIMessage, BusinessMemory
from apps.strategist.providers import GigaChatCompletion
from apps.workspaces.models import Membership, Workspace

SECRET_AUDIENCE = "Женщины-секретная-аудитория 25-45"


class VersionRegistryTest(SimpleTestCase):
    def test_every_prompt_template_matches_its_registered_version(self):
        current = pv.template_fingerprints()
        self.assertEqual(set(current), set(pv.FINGERPRINTS))
        for version, digest in current.items():
            with self.subTest(version=version):
                self.assertEqual(
                    pv.FINGERPRINTS[version], digest,
                    f"The template of {version} changed. Bump the version constant in provenance.py "
                    f"(new date/suffix) and register the new hash {digest}.")

    def test_stamp_adds_a_hash_of_the_exact_prompt(self):
        self.assertEqual(pv.stamp("v1"), "v1")
        stamped = pv.stamp("v1", "text")
        self.assertTrue(stamped.startswith("v1#") and len(stamped) == len("v1#") + 12)
        self.assertNotEqual(stamped, pv.stamp("v1", "other text"))

    def test_describe_is_defensive_and_translated(self):
        manifest = [{"type": "business_profile", "fields": ["niche", "goals"]}, {"type": "history", "messages": 3},
                    {"type": "business_memory", "ids": [1, 2]}, {"type": "pinterest_read", "calls": [{"resource": "profile"}, {"resource": "boards"}]},
                    {"type": "knowledge", "documents": [{"title": "Правила"}]}, "junk", {"type": "unknown"}, {"type": "business_memory", "ids": []}]
        with translation.override("ru"):
            self.assertEqual(pv.describe(manifest), [
                "Профиль бизнеса: ниша, цели бизнеса", "История диалога: сообщений 3", "Память бизнеса: фактов 2",
                "Данные Pinterest через API: boards, profile", "База знаний: Правила"])
            self.assertEqual(pv.describe(None), [])
        with translation.override("en"):
            self.assertEqual(pv.describe(manifest[:2]), ["Business profile: niche, business goals", "Conversation history: 3 messages"])


class ReplyProvenanceTest(TestCase):
    def setUp(self):
        self.addCleanup(translation.activate, "ru")
        user = get_user_model().objects.create_user("prov-owner")
        self.user = user
        workspace = Workspace.objects.create(name="P", slug="p", created_by=user)
        Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=workspace, name="Shop", slug="shop", niche="Керамика", audience=SECRET_AUDIENCE, goals="Трафик")
        self.account = PinterestAccount.objects.create(
            business=self.business, connected_by=user, username="alpha", pinterest_user_id="alpha",
            access_token_encrypted="mock-only", access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED)
        self.conversation = AIConversation.objects.create(business=self.business, created_by=user)
        self.client.force_login(user)
        self.url = reverse("strategist:session", kwargs={"workspace_slug": "p", "business_slug": "shop", "session_slug": self.conversation.slug})
        self.hit = KnowledgeHit(content="Правило", score=1.0, source_id="doc-1", title="Официальные правила", source_links=("https://example.com",), heading="Раздел")
        self.enterContext(patch("apps.strategist.services.search_knowledge", return_value=[self.hit]))
        self.enterContext(patch("apps.strategist.services.search_knowledge_lexical", return_value=[]))
        self.request = self.enterContext(patch("apps.pinterest.strategist_tools._request", return_value={"username": "alpha"}))
        self.complete = self.enterContext(patch("apps.strategist.services.GigaChatProvider.complete"))

    def say(self, text):
        response = self.client.post(self.url, {"message": text}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.url = response.json()["conversation_url"]
        return self.conversation.messages.filter(role="ASSISTANT").latest("created_at"), response.json()

    def completion(self, content="Совет.", function_call=None):
        return GigaChatCompletion(content=content, model="mock", prompt_tokens=5, completion_tokens=2, total_tokens=7, function_call=function_call)

    def test_chat_reply_stores_prompt_version_and_manifest_without_data_text(self):
        BusinessMemory.objects.create(business=self.business, kind="FACT", text="СЕКРЕТНЫЙ-ФАКТ", source_ref="x", created_by=self.user)
        self.complete.return_value = self.completion()
        answer, payload = self.say("Дай идею для поста про чашки")
        version, _, digest = answer.prompt_version.partition("#")
        self.assertEqual((version, len(digest)), (pv.CHAT_PROMPT_VERSION, 12))
        kinds = {m["type"]: m for m in answer.context_manifest}
        self.assertEqual(kinds["business_profile"]["fields"], ["name", "niche", "audience", "goals"])
        self.assertEqual(kinds["business_memory"]["ids"], [BusinessMemory.objects.get().pk])
        self.assertEqual(kinds["history"]["messages"], 1)
        self.assertEqual(kinds["knowledge"]["documents"], [{"source_id": "doc-1", "title": "Официальные правила", "heading": "Раздел"}])
        stored = json.dumps(answer.context_manifest, ensure_ascii=False)
        for text in (SECRET_AUDIENCE, "СЕКРЕТНЫЙ-ФАКТ", "Правило"):
            self.assertNotIn(text, stored)
        html = payload["messages_html"]
        self.assertIn("Источники ответа", html)
        self.assertIn("Профиль бизнеса: название, ниша, целевая аудитория, цели бизнеса", html)
        self.assertIn("База знаний: Официальные правила", html)
        self.assertIn(answer.prompt_version, html)
        self.assertNotIn(SECRET_AUDIENCE, html.split("chat-provenance")[1])

    def test_pinterest_tool_reads_are_recorded_by_resource_only(self):
        self.complete.side_effect = [
            self.completion("", {"name": "read_pinterest_data", "arguments": {"account_key": str(self.account.public_id), "resource": "profile", "options": "{}"}}),
            self.completion("Профиль получен."),
        ]
        answer, _ = self.say("Расскажи про профиль в Pinterest @alpha")
        self.assertEqual(answer.provider, "gigachat")
        read = next(m for m in answer.context_manifest if m["type"] == "pinterest_read")
        self.assertEqual(read["calls"], [{"resource": "profile"}])
        self.assertNotIn(str(self.account.public_id), json.dumps(answer.context_manifest))

    def test_strategy_plan_and_research_replies_are_stamped(self):
        from apps.strategist.models import StrategyVersion
        strategy_json = {"goals": ["Трафик"], "content_directions": ["Образы"], "rationale": [{"claim": "Ниша — керамика", "basis": ["profile:niche"]}]}
        self.complete.return_value = SimpleNamespace(content=json.dumps(strategy_json, ensure_ascii=False), model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, function_call=None, functions_state_id=None)
        with patch("apps.strategist.strategy_chat.GigaChatProvider.complete", self.complete):
            draft, _ = self.say("Построй стратегию")
            self.assertEqual(draft.prompt_version, pv.STRATEGY_PROMPT_VERSION)
            self.assertEqual(draft.context_manifest[0]["type"], "sources")
            self.assertIn("profile:niche", draft.context_manifest[0]["refs"])
            self.say("Подтверждаю стратегию")
        plan_json = {"items": [{"target_week": 1, "direction": "Образы", "idea": "Чашки в интерьере"}]}
        self.complete.return_value = SimpleNamespace(content=json.dumps(plan_json, ensure_ascii=False), model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, function_call=None, functions_state_id=None)
        with patch("apps.strategist.content_plan.GigaChatProvider.complete", self.complete):
            plan, _ = self.say("Составь контент-план")
        self.assertEqual(plan.prompt_version, pv.PLAN_PROMPT_VERSION)
        self.assertEqual(plan.context_manifest, [{"type": "strategy_version", "number": StrategyVersion.objects.get().number}])
        replies_without_a_model_call = self.conversation.messages.filter(model="strategy-confirmed").get()
        self.assertEqual((replies_without_a_model_call.prompt_version, replies_without_a_model_call.context_manifest), ("", []))

    def test_user_messages_and_old_rows_have_no_provenance(self):
        user_message = AIMessage.objects.create(conversation=self.conversation, role="USER", content="привет")
        self.assertEqual((user_message.prompt_version, user_message.context_manifest), ("", []))
        self.complete.return_value = self.completion()
        self.say("Дай идею")
        old = AIMessage.objects.create(conversation=self.conversation, role="ASSISTANT", content="старый ответ")
        self.assertEqual(pv.describe(old.context_manifest), [])
        page = self.client.get(self.url).content.decode()
        self.assertEqual(page.count('class="chat-provenance"'), 1)  # only the reply that has a manifest
        english = self.client.get(self.url, headers={"accept-language": "en"}).content.decode()
        self.assertIn("Sources of this answer", english)
        self.assertIn("Business profile: name, niche, target audience, business goals", english)
