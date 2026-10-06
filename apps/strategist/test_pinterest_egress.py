"""Canary tests: with PINTEREST_AI_DATA_TRANSFER_ENABLED off, nothing derived from Pinterest data may
reach the model in any flow. Each flow is also run with the switch on as a positive control, so the
test would notice if the canary stopped being visible to the model at all."""
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
from apps.strategist import pin_keywords, research, strategy as st
from apps.strategist.models import AIConversation, AIMessage, ResearchSnapshot
from apps.workspaces.models import Membership, Workspace

KEYWORD = "CANARYKEY linen phrase"
API_DATA = "CANARYDATA 1394708 impressions"
STRATEGY = {"goals": ["Трафик"], "content_directions": ["Образы"], "recommended_boards": [{"name": "Витрина", "purpose": ""}],
            "keyword_clusters": [{"name": "Лён", "keywords": [KEYWORD]}]}
PLAN = {"items": [{"target_week": 1, "direction": "Образы", "board": "Витрина", "keyword": KEYWORD, "idea": "Образ с льном"}]}


def completion(payload):
    content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return SimpleNamespace(content=content, model="stub", prompt_tokens=1, completion_tokens=1, total_tokens=2,
                           function_call=None, functions_state_id=None)


class EgressTest(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("egress-owner")
        self.user = user
        workspace = Workspace.objects.create(name="E", slug="e", created_by=user)
        Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=workspace, name="Shop", slug="shop", niche="Льняная одежда",
                                                audience="Женщины", goals="Трафик")
        self.account = PinterestAccount.objects.create(
            business=self.business, connected_by=user, username="alpha", pinterest_user_id="alpha",
            access_token_encrypted="mock-only", access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED)
        self.snapshot = ResearchSnapshot.objects.create(
            business=self.business, account=self.account, seeds=["linen"], region="X", researched_at=timezone.now(),
            candidates=[{"phrase": KEYWORD, "sources": ["pinterest_trends"], "seeds": ["linen"], "metrics": {},
                         "intent": "general", "length": "long", "trend": "unknown", "peak_week": ""}])
        self.conversation = AIConversation.objects.create(business=self.business, created_by=user)
        self.client.force_login(user)
        self.url = reverse("strategist:session", kwargs={"workspace_slug": "e", "business_slug": "shop", "session_slug": self.conversation.slug})
        self.calls = []
        self.responder = lambda messages, **kw: completion("ok")

        def fake_complete(_provider, messages, **kwargs):
            self.calls.append(json.dumps(messages, ensure_ascii=False) + json.dumps(kwargs.get("functions") and "functions" or "", default=str))
            return self.responder(messages, **kwargs)
        self.enterContext(patch("apps.strategist.providers.GigaChatProvider.complete", fake_complete))
        for target in ("search_knowledge", "search_knowledge_lexical"):
            self.enterContext(patch(f"apps.strategist.services.{target}", return_value=[]))
        self.enterContext(patch("apps.strategist.services.local_knowledge_context", return_value=""))
        self.enterContext(patch("apps.pinterest.strategist_tools._request"))

    def say(self, text):
        response = self.client.post(self.url, {"message": text}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.url = response.json()["conversation_url"]

    def sent(self) -> str:
        return "\n".join(self.calls)

    def check(self, canary, run):
        """Run `run` with the switch off (canary must be absent) and on (canary must be visible)."""
        for enabled in (False, True):
            with self.subTest(transfer_enabled=enabled), override_settings(PINTEREST_AI_DATA_TRANSFER_ENABLED=enabled):
                self.calls.clear()
                run()
                self.assertTrue(self.calls, "the flow must have called the model")
                (self.assertIn if enabled else self.assertNotIn)(canary, self.sent())

    def draft(self, **extra):
        payload = st.clean_payload({**STRATEGY, **extra}, allowed_refs=set(), allowed_keywords=None)
        return st.create_draft(self.business, self.user, payload, sources=[])

    def test_chat_history_does_not_carry_direct_pinterest_answers(self):
        AIMessage.objects.create(conversation=self.conversation, role="USER", content="Статистика @alpha за 30 дней")
        AIMessage.objects.create(conversation=self.conversation, role="ASSISTANT", content=API_DATA,
                                 provider="pinterest-api", model="direct-read")
        AIMessage.objects.create(conversation=self.conversation, role="ASSISTANT", content="Стратегия: " + KEYWORD,
                                 provider="strategy", model="strategy-draft")
        self.check("CANARYDATA", lambda: self.say("Расскажи про тренды в Pinterest и дай идею поста"))
        self.check("CANARYKEY", lambda: self.say("Дай ещё одну идею для поста"))

    def test_strategy_build_does_not_send_researched_phrases(self):
        self.responder = lambda messages, **kw: completion(STRATEGY)
        self.check(KEYWORD, lambda: self.say("Построй стратегию"))

    def test_strategy_revision_does_not_send_earlier_keyword_clusters(self):
        self.responder = lambda messages, **kw: completion(STRATEGY)
        self.draft()
        self.check(KEYWORD, lambda: self.say("Измени стратегию: добавь больше про костюмы"))

    def test_content_plan_does_not_send_keywords(self):
        self.responder = lambda messages, **kw: completion(PLAN)
        st.confirm_version(self.draft(), self.user)
        self.check(KEYWORD, lambda: self.say("Составь контент-план"))

    def test_niche_research_filter_is_skipped_and_pin_keyword_research_is_closed(self):
        self.responder = lambda messages, **kw: completion({"seeds": ["linen"], "keep": [KEYWORD]})
        candidates = [{"original": KEYWORD, "sources": ["pinterest_trends"], "seeds": ["linen"], "metrics": {}}]
        with patch("apps.strategist.research._collect", return_value=(candidates, [])) as collect:
            with override_settings(PINTEREST_AI_DATA_TRANSFER_ENABLED=False):
                research.research_niche(self.business)
                self.assertNotIn(KEYWORD, self.sent())  # only the business profile reached the model
                self.calls.clear()
                with self.assertRaises(PermissionError):
                    research._relevant(self.business, candidates, SimpleNamespace(complete=lambda *a, **k: None))
                with patch("apps.strategist.pin_keywords._collect") as pin_collect:
                    result = pin_keywords.research_pin_keywords(business=self.business, account=self.account, product={"title": "Платье"})
                self.assertIn("отключена настройкой", result["error"])
                pin_collect.assert_not_called()
                with self.assertRaises(PermissionError):
                    pin_keywords._select(candidates=candidates, product={}, business=self.business, provider=None)
                self.assertEqual(self.calls, [])
            self.calls.clear()
            research.research_niche(self.business)  # positive control: filter sends the phrases when on
            self.assertIn(KEYWORD, self.sent())
        self.assertEqual(collect.call_count, 2)
