"""Authorized live evaluation via Django's chat view in an isolated test DB.

Run: docker compose exec -T web python manage.py shell < scripts/evaluate_strategist_release.py
Uses real configured providers; never retries a failed scenario automatically.
"""
import json
import time
import uuid
from pathlib import Path
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from unittest.mock import patch
import yaml

from django.contrib.auth import get_user_model
from django.core import serializers
from django.db import connections
from django.test import Client, override_settings
from django.test.utils import setup_databases, teardown_databases
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument
from apps.pinterest.models import PinterestAccount
from apps.pinterest.strategist_tools import read_pinterest_data
from apps.strategist.models import AIConversation, AIMessage
from apps.strategist.providers import GigaChatProvider
from apps.workspaces.models import Membership, Workspace


def load_cases(case_file):
    data = yaml.safe_load(Path(case_file).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("indexed_in_rag") is not False:
        raise ValueError("Evaluation cases must explicitly be outside RAG")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Nonempty cases list required")
    ids = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Case must be a mapping")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in ids:
            raise ValueError("Case IDs must be nonempty and unique")
        ids.add(case_id)
        if not isinstance(case.get("business_profile"), str) or case["business_profile"] not in {"known", "empty"}:
            raise ValueError(f"Invalid business profile: {case_id}")
        if not isinstance(case.get("family"), str) or not case["family"].strip():
            raise ValueError(f"Missing family: {case_id}")
        for field in ("messages", "expected"):
            values = case.get(field)
            if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError(f"Invalid {field}: {case_id}")
        if len(case["messages"]) > 2:
            raise ValueError(f"At most two messages per case: {case_id}")
        mode = case.get("knowledge_mode", "normal")
        if not isinstance(mode, str) or mode not in {"normal", "unavailable"}:
            raise ValueError(f"Invalid knowledge mode: {case_id}")
        fixture = case.get("tool_fixture")
        if fixture is not None and (not isinstance(fixture, str) or fixture not in {"followers", "failure", "missing_scope", "paginated", "page_failure"}):
            raise ValueError(f"Invalid tool fixture: {case_id}")
        history = case.get("history", [])
        if not isinstance(history, list):
            raise ValueError(f"Invalid synthetic history: {case_id}")
        for message in history:
            if not isinstance(message, dict) or message.get("role") not in {"USER", "ASSISTANT"} or not isinstance(message.get("content"), str):
                raise ValueError(f"Invalid synthetic history: {case_id}")
    return cases


@contextmanager
def tool_fixture_context(business, user, mode):
    """Real tool validation, synthetic transport; only disposable test DB rows."""
    accounts = []
    trace = {"synthetic_transport": True, "calls": [], "requests": [], "model_calls": []}
    try:
        for username in ("fixture_alpha", "fixture_beta"):
            accounts.append(PinterestAccount.objects.create(
                business=business, connected_by=user, username=username,
                pinterest_user_id=f"evaluation-{uuid.uuid4().hex}",
                access_token_encrypted="synthetic-never-decrypted",
                access_token_expires_at=timezone.now() + timedelta(days=1),
                granted_scopes=[] if mode == "missing_scope" else ["user_accounts:read"],
                status=PinterestAccount.Status.CONNECTED,
            ))
        names = {str(account.public_id): account.username for account in accounts}

        def read(*, business, arguments):
            trace["calls"].append({"account": names.get(str(arguments.get("account_key")), "unknown"),
                                   "account_key": arguments.get("account_key"),
                                   "resource": arguments.get("resource")})
            return read_pinterest_data(business=business, arguments=arguments)

        original_complete = GigaChatProvider.complete

        def complete(provider, *args, **kwargs):
            result = original_complete(provider, *args, **kwargs)
            trace["model_calls"].append({"model": result.model, "tokens": result.total_tokens,
                                         "function": (result.function_call or {}).get("name")})
            return result

        def request(account, path, params):
            trace["requests"].append({"account": account.username, "path": path, "bookmark": params.get("bookmark")})
            if mode == "failure":
                from apps.pinterest.strategist_tools import PinterestReadError
                raise PinterestReadError("Pinterest API сейчас недоступен.")
            if path != "/user_account/followers":
                return {"error": "Fixture поддерживает только followers; другие данные не загружены."}
            if mode in {"paginated", "page_failure"}:
                if not params.get("bookmark"):
                    return {"items": [{"username": "synthetic_reader_one"}, {"username": "synthetic_reader_two"}], "bookmark": "synthetic_next_page"}
                if params["bookmark"] != "synthetic_next_page":
                    return {"error": "Неверный bookmark в fixture."}
                if mode == "page_failure":
                    from apps.pinterest.strategist_tools import PinterestReadError
                    raise PinterestReadError("Следующая страница Pinterest сейчас недоступна.")
                return {"items": [{"username": "synthetic_reader_three"}], "bookmark": None}
            items = [{"username": "synthetic_reader_one"}, {"username": "synthetic_reader_two"}]
            if account.username == "fixture_beta":
                items = items[:1]
            return {"items": items, "bookmark": None}

        with patch("apps.strategist.services.read_pinterest_data", side_effect=read), \
             patch.object(GigaChatProvider, "complete", new=complete), \
             patch("apps.pinterest.strategist_tools._request", side_effect=request), \
             patch("apps.pinterest.strategist_tools._get", side_effect=AssertionError("Live Pinterest forbidden")):
            yield trace
    finally:
        PinterestAccount.objects.filter(pk__in=[account.pk for account in accounts]).delete()


def evaluate(case_file=None, repetitions=3, output_path="/tmp/strategist-release.json", case_ids=None):
    if type(repetitions) is not int or not 1 <= repetitions <= 3:
        raise ValueError("Repetitions must be between 1 and 3")
    # Copy only approved global reference knowledge, never real business data.
    documents = KnowledgeDocument.objects.filter(status="approved", scope="global")
    knowledge = serializers.serialize("json", list(documents) + list(KnowledgeChunk.objects.filter(document__in=documents)))
    connection = connections["default"]
    original_test_name = connection.settings_dict["TEST"].get("NAME")
    connection.settings_dict["TEST"]["NAME"] = f"test_strategist_release_{uuid.uuid4().hex[:12]}"
    old_config = None
    rows = []
    scenarios = [
        ["Сколько пинов публиковать каждый день? Это правило Pinterest?"],
        ["По 12 исходящим кликам Pinterest можно понять, сколько было заказов? Ответь коротко."],
        ["Какие темы запрещены Правилами сообщества Pinterest?"],
        ["Какая оптимальная длина заголовка и описания Pin? Это правило Pinterest?"],
        ["Придумай короткую подпись для Pin: синяя керамическая кружка ручной работы."],
        ["Предложи CTA для Pin с керамической кружкой.", "А это не запрещено Pinterest? Дай прямой ответ."],
        ["Как развивать Pinterest для небольшого магазина? Один первый шаг."],
        ["Почему вчера было больше переходов из Pinterest? Сколько было заказов?"],
    ]
    cases = load_cases(case_file) if case_file else [
        {"id": f"release-{index}", "family": "release", "business_profile": "known", "messages": messages, "expected": []}
        for index, messages in enumerate(scenarios, 1)
    ]
    if case_ids is not None:
        if not isinstance(case_ids, list) or not case_ids or any(not isinstance(value, str) for value in case_ids) or len(set(case_ids)) != len(case_ids):
            raise ValueError("Explicit nonempty unique case selection required")
        if set(case_ids) - {case["id"] for case in cases}:
            raise ValueError("Unknown selected case ID")
        cases = [case for case in cases if case["id"] in case_ids]
    output = Path(output_path)

    def save_report():
        output.write_text(json.dumps({"case_file": case_file, "completed_answers": len(rows), "chat_tokens": sum(row["tokens"] or 0 for row in rows), "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    save_report()  # Detect output permissions before spending tokens.
    try:
        old_config = setup_databases(verbosity=0, interactive=False)
        for obj in serializers.deserialize("json", knowledge):
            obj.save()
        with override_settings(ALLOWED_HOSTS=["testserver"], CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "strategist-release"}}):
            user = get_user_model().objects.create_user("release-fixture")
            workspace = Workspace.objects.create(name="Проверка", slug="release", created_by=user)
            Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
            business = Business.objects.create(workspace=workspace, name="Мастерская керамики", slug="ceramics", niche="керамика ручной работы", market="Россия", audience="покупатели подарков и декора")
            empty_business = Business.objects.create(workspace=workspace, name="Новый бизнес", slug="empty")
            client = Client()
            client.force_login(user)
            tokens = 0
            for repetition in range(1, repetitions + 1):
                for scenario, case in enumerate(cases, 1):
                    selected_business = business if case["business_profile"] == "known" else empty_business
                    conversation = AIConversation.objects.create(business=selected_business, created_by=user)
                    for seed in case.get("history", []):
                        AIMessage.objects.create(conversation=conversation, role=seed["role"], content=seed["content"], provider="evaluation-fixture", model="synthetic-history")
                    for step, question in enumerate(case["messages"], 1):
                        if tokens >= 60000:
                            raise RuntimeError("Evaluation token budget reached; no further model calls")
                        conversation.refresh_from_db()
                        url = reverse("strategist:session", kwargs={"workspace_slug": workspace.slug, "business_slug": selected_business.slug, "session_slug": conversation.slug})
                        started = time.monotonic()
                        tool_trace = None
                        with ExitStack() as stack:
                            if case.get("tool_fixture"):
                                tool_trace = stack.enter_context(tool_fixture_context(selected_business, user, case["tool_fixture"]))
                            if case.get("knowledge_mode") == "unavailable":
                                stack.enter_context(patch("apps.strategist.grounded_answers._approved_source", return_value=None))
                                stack.enter_context(patch("apps.strategist.services.load_source", side_effect=ValueError("Evaluation: knowledge unavailable")))
                                stack.enter_context(patch("apps.strategist.services.search_knowledge", return_value=[]))
                                stack.enter_context(patch("apps.strategist.services.search_knowledge_lexical", return_value=[]))
                                stack.enter_context(patch("apps.strategist.services.local_knowledge_context", return_value=""))
                            response = client.post(url, {"message": question}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                        answer = conversation.messages.filter(role=AIMessage.Role.ASSISTANT).order_by("-created_at").first()
                        if response.status_code != 200 or answer is None:
                            raise RuntimeError(f"Scenario {scenario}, repetition {repetition}: HTTP {response.status_code}; no retry")
                        html = response.json().get("messages_html", "")
                        if not html:
                            raise RuntimeError("Chat view did not render messages")
                        tokens += answer.total_tokens or 0
                        rows.append({"case_id": case["id"], "family": case["family"], "step": step, "expected": case["expected"], "repetition": repetition, "scenario": scenario, "question": question, "answer": answer.content, "provider": answer.provider, "model": answer.model, "tokens": answer.total_tokens, "seconds": round(time.monotonic() - started, 2), "http_status": response.status_code})
                        if tool_trace is not None:
                            rows[-1]["tool_trace"] = tool_trace
                        save_report()
                        print(f"Run {repetition}, scenario {scenario}: {answer.provider}/{answer.model}, {answer.total_tokens} tokens", flush=True)
    finally:
        try:
            save_report()
        finally:
            try:
                if old_config is not None:
                    teardown_databases(old_config, verbosity=0)
            finally:
                connection.settings_dict["TEST"]["NAME"] = original_test_name


if not globals().get("EVALUATION_LOAD_ONLY", False):
    evaluate(case_file=globals().get("EVALUATION_CASE_FILE"), repetitions=globals().get("EVALUATION_REPETITIONS", 3), output_path=globals().get("EVALUATION_OUTPUT", "/tmp/strategist-release.json"), case_ids=globals().get("EVALUATION_CASE_IDS"))
