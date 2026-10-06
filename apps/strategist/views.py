from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _

from apps.businesses.models import Business

from . import approvals, pin_jobs
from . import pin_settings as ps
from . import content_plan as plans
from . import memory, research
from . import strategy as strategies
from .forms import StrategistMessageForm
from .pin_forms import PinGenerationForm, initial_values
from .models import AIConversation, AIJob, AIMessage, ContentPlan, GenerationPreset, Pin, StrategyVersion
from .providers import GigaChatConfigurationError, GigaChatProviderError
from .services import conversation_slug, create_conversation, respond_to_message


def _get_business(request, workspace_slug, business_slug):
    return get_object_or_404(
        Business.objects.select_related("workspace"),
        slug=business_slug,
        workspace__slug=workspace_slug,
        workspace__memberships__user=request.user,
    )


@login_required
def chat(request, workspace_slug, business_slug, session_slug=None):
    business = _get_business(request, workspace_slug, business_slug)
    conversations = AIConversation.objects.filter(
        business=business,
        created_by=request.user,
        is_active=True,
    ).order_by("-updated_at", "-created_at")
    conversation = (
        get_object_or_404(conversations, slug=session_slug)
        if session_slug
        else conversations.first()
    )
    form = StrategistMessageForm(request.POST or None)
    if request.method == "POST" and conversation is None and form.is_valid():
        conversation = create_conversation(business=business, user=request.user)
        conversations = conversations.order_by("-updated_at", "-created_at")

    if request.method == "POST" and conversation and form.is_valid():
        submitted_message = form.cleaned_data["message"]
        is_first_question = not conversation.messages.filter(role=AIMessage.Role.USER).exists()
        user_message = AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.USER,
            content=submitted_message,
        )
        if is_first_question:
            conversation.title = submitted_message[:200]
            conversation.slug = conversation_slug(title=submitted_message, conversation=conversation)
        conversation.save(update_fields=["title", "slug", "updated_at"])
        session_url = reverse(
            "strategist:session",
            kwargs={
                "workspace_slug": business.workspace.slug,
                "business_slug": business.slug,
                "session_slug": conversation.slug,
            },
        )
        delete_url = reverse(
            "strategist:delete-session",
            kwargs={
                "workspace_slug": business.workspace.slug,
                "business_slug": business.slug,
                "session_slug": conversation.slug,
            },
        )

        try:
            assistant_message = respond_to_message(user_message=user_message, actor=request.user)
        except GigaChatConfigurationError:
            error_message = _("Ключ GigaChat не настроен.")
        except GigaChatProviderError:
            error_message = _("GigaChat временно недоступен. Повторите запрос.")
        else:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "messages_html": render_to_string(
                            "strategist/_chat_messages.html",
                            {"chat_messages": [user_message, assistant_message]},
                            request=request,
                        ),
                        "conversation_url": session_url,
                        "conversation_title": conversation.title,
                        "conversation_slug": conversation.slug,
                        "delete_url": delete_url,
                    }
                )
            return redirect(session_url + "#chat-composer")

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "messages_html": render_to_string(
                        "strategist/_chat_messages.html",
                        {"chat_messages": [user_message]},
                        request=request,
                    ),
                    "error": str(error_message),
                    "conversation_url": session_url,
                    "conversation_title": conversation.title,
                    "conversation_slug": conversation.slug,
                    "delete_url": delete_url,
                },
                status=503,
            )
        messages.error(request, error_message)

    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    if request.method == "POST" and conversation is None:
        messages.error(request, _("Сначала создайте сессию ИИ-стратега."))

    chat_messages = list(conversation.messages.all()) if conversation else []
    return render(
        request,
        "strategist/chat.html",
        {
            "business": business,
            "conversation": conversation,
            "strategist_business": business,
            "strategist_sessions": list(conversations),
            "form": form,
            "chat_messages": chat_messages,
            "chat_questions": [message for message in chat_messages if message.role == AIMessage.Role.USER],
        },
    )


@login_required
def new_session(request, workspace_slug, business_slug):
    if request.method != "POST":
        raise Http404
    business = _get_business(request, workspace_slug, business_slug)
    conversation = create_conversation(business=business, user=request.user)
    return redirect(
        "strategist:session",
        workspace_slug=business.workspace.slug,
        business_slug=business.slug,
        session_slug=conversation.slug,
    )


@login_required
def delete_session(request, workspace_slug, business_slug, session_slug):
    if request.method != "POST":
        raise Http404
    business = _get_business(request, workspace_slug, business_slug)
    conversation = get_object_or_404(
        AIConversation,
        business=business,
        created_by=request.user,
        slug=session_slug,
    )
    conversation.delete()
    return redirect("strategist:chat", workspace_slug=workspace_slug, business_slug=business_slug)


@login_required
def legacy_chat_redirect(request, business_id):
    business = get_object_or_404(
        Business.objects.select_related("workspace"),
        public_id=business_id,
        workspace__memberships__user=request.user,
    )
    return redirect(
        "strategist:chat",
        workspace_slug=business.workspace.slug,
        business_slug=business.slug,
        permanent=True,
    )


def _rationale_view(version):
    return [{"claim": r["claim"], "sources": [strategies.ref_label(b) for b in r["basis"]]} for r in version.rationale]


def _version_view(version):
    if version is None:
        return None
    cadence = version.publishing_cadence
    return {
        "version": version,
        "rationale": _rationale_view(version),
        "cadence": cadence.get("text") if cadence else "",
        "cadence_confirmed": bool(cadence) and cadence.get("basis") == "user",
        "snapshot": version.research_snapshots.filter(kind="NICHE_KEYWORDS").order_by("-researched_at").first(),
    }


@login_required
def strategy_page(request, workspace_slug, business_slug):
    business = _get_business(request, workspace_slug, business_slug)
    strategy = business.strategies.exclude(status="ARCHIVED").order_by("-created_at").first()
    active = strategies.active_version(business)
    draft = strategies.pending_draft(business)
    plan = (business.content_plans.filter(status__in=[ContentPlan.Status.DRAFT, ContentPlan.Status.CONFIRMED])
            .select_related("strategy_version").order_by("-created_at").first())
    history = list(strategy.versions.order_by("-number")[:20]) if strategy else []
    weeks = {}
    for item in (plan.items.all() if plan else []):
        weeks.setdefault(item.target_week, []).append(item)
    return render(request, "strategist/strategy.html", {
        "business": business, "strategist_business": business,
        "strategist_sessions": list(business.ai_conversations.filter(is_active=True).order_by("-updated_at")),
        "can_edit": memory.actor_can_edit(business, request.user),
        "active": _version_view(active), "draft": _version_view(draft),
        "history": history, "plan": plan, "plan_weeks": sorted(weeks.items()),
        "can_build_plan": bool(active) and memory.actor_can_edit(business, request.user) and (plan is None or plan.status == ContentPlan.Status.DRAFT),
        "plan_stale": bool(plan and plan.status == ContentPlan.Status.DRAFT and plan.strategy_version.status != StrategyVersion.Status.CONFIRMED),
        "profile_missing": [gettext(label) for label in strategies.missing_profile_fields(business)],
        "memory_facts": memory.facts(business),
        "snapshot_fresh": research.fresh_snapshot(business),
    })


def _editable_business(request, workspace_slug, business_slug):
    if request.method != "POST":
        raise Http404
    business = _get_business(request, workspace_slug, business_slug)
    if not memory.actor_can_edit(business, request.user):
        raise Http404
    return business


@login_required
def strategy_confirm(request, workspace_slug, business_slug, number):
    business = _editable_business(request, workspace_slug, business_slug)
    version = get_object_or_404(StrategyVersion, strategy__business=business, number=number)
    try:
        strategies.confirm_with_decision(version, request.user)
    except strategies.StrategyError as error:
        messages.error(request, gettext(str(error)))
    else:
        messages.success(request, _("Стратегия подтверждена."))
    return redirect("strategist:strategy", workspace_slug=business.workspace.slug, business_slug=business.slug)


@login_required
def plan_build(request, workspace_slug, business_slug):
    business = _editable_business(request, workspace_slug, business_slug)
    version = strategies.active_version(business)
    target = redirect("strategist:strategy", workspace_slug=business.workspace.slug, business_slug=business.slug)
    if version is None or not version.content_directions:
        messages.error(request, _("Контент-план строится по подтверждённой стратегии с контентными направлениями."))
        return target
    try:
        plan, _completion = plans.generate_plan(business, request.user, version)
    except (GigaChatConfigurationError, GigaChatProviderError):
        messages.error(request, _("Модель сейчас недоступна. Повторите попытку позже."))
        return target
    if plan is None:
        messages.error(request, _("Не получилось собрать надёжный контент-план по этой стратегии. Попробуйте ещё раз."))
    else:
        messages.success(request, _("Контент-план составлен. Проверьте его и подтвердите."))
    return target


@login_required
def plan_confirm(request, workspace_slug, business_slug):
    business = _editable_business(request, workspace_slug, business_slug)
    plan = plans.pending_plan(business)
    if plan is None:
        raise Http404
    try:
        plans.confirm_with_decision(plan, request.user)
    except plans.PlanError as error:
        messages.error(request, gettext(str(error)))
    else:
        messages.success(request, _("Контент-план подтверждён."))
    return redirect("strategist:strategy", workspace_slug=business.workspace.slug, business_slug=business.slug)


PIN_STATUS_LABELS = {
    "IDEA": _("Идея"), "GENERATING": _("Генерируется"), "VALIDATING": _("Проверяется"), "WAITING_APPROVAL": _("Ждёт одобрения"),
    "APPROVED": _("Одобрен"), "QUEUED": _("В очереди"), "PUBLISHING": _("Отправляется"), "PUBLISHED": _("Опубликован"),
    "REJECTED": _("Отклонён"), "REWORK": _("Требуется переделка"), "FAILED": _("Ошибка"),
}
VERDICT_LABELS = {"PASS": _("Проверки пройдены"), "REVIEW": _("Нужна оценка человека"), "BLOCK": _("Заблокирован проверкой")}
CHECK_LABELS = {"pass": _("пройдена"), "review": _("нужна оценка"), "block": _("блок"), "not_checked": _("не проверено")}
DECISION_LABELS = {"APPROVED": _("Одобрен"), "REJECTED": _("Отклонён"), "REWORK": _("Отправлен на переделку")}


def _pin_card(pin):
    version = pin.current_version
    approval = getattr(version, "approval", None) if version else None
    can_decide = version is not None and approval is None and pin.status in (Pin.Status.WAITING_APPROVAL, Pin.Status.REWORK)
    return {
        "pin": pin, "version": version, "approval": approval,
        "status_label": PIN_STATUS_LABELS.get(pin.status, pin.status),
        "verdict_label": VERDICT_LABELS.get(version.verdict, "") if version else "",
        "checks": [{**c, "label": CHECK_LABELS.get(c["status"], c["status"])} for c in (version.checks if version else [])],
        "decision_label": DECISION_LABELS.get(approval.decision, "") if approval else "",
        "can_decide": can_decide, "can_approve": can_decide and pin.status == Pin.Status.WAITING_APPROVAL and version.verdict != "BLOCK",
        "link_is_web": bool(version and version.destination_url.startswith(("http://", "https://"))),
    }


@login_required
def pins_page(request, workspace_slug, business_slug):
    business = _get_business(request, workspace_slug, business_slug)
    pins = list(business.pins.select_related("current_version", "plan_item", "current_version__approval").order_by("plan_item__position"))
    return render(request, "strategist/pins.html", {
        "business": business, "strategist_business": business,
        "strategist_sessions": list(business.ai_conversations.filter(is_active=True).order_by("-updated_at")),
        "can_edit": memory.actor_can_edit(business, request.user),
        "cards": [_pin_card(p) for p in pins],
    })


@login_required
def pin_decide(request, workspace_slug, business_slug, pin_id):
    business = _editable_business(request, workspace_slug, business_slug)
    pin = get_object_or_404(Pin, pk=pin_id, business=business)
    try:
        version_number = int(request.POST.get("version", ""))
    except ValueError:
        raise Http404
    try:
        approvals.decide(pin, request.user, action=request.POST.get("action", ""), version_number=version_number,
                         comment=request.POST.get("comment", ""), acknowledged=request.POST.get("acknowledge") == "on")
    except approvals.ApprovalError as error:
        messages.error(request, gettext(str(error)))
    else:
        messages.success(request, _("Решение сохранено."))
    return redirect("strategist:pins", workspace_slug=business.workspace.slug, business_slug=business.slug)


JOB_STATUS_LABELS = {
    "PENDING": _("В очереди"), "RUNNING": _("Выполняется"), "WAITING_INPUT": _("Ждёт ответа"),
    "COMPLETED": _("Готово"), "FAILED": _("Ошибка"), "CANCELLED": _("Отменена"),
}
SOURCE_LABELS = {"profile": _("из профиля бизнеса"), "strategy": _("из стратегии"), "account": _("из аккаунта Pinterest"),
                 "preset": _("из ваших прошлых настроек"), "default": _("по умолчанию")}
ADVANCED_FIELDS = ("keyword_mode", "forbidden_words", "instruction", "utm_source", "utm_medium", "utm_campaign", "product_url")


def _auto_values(business, version, accounts) -> dict:
    """What the page can fill in by itself, and where it comes from."""
    defaults = ps.normalize({})
    auto = {name: ("default", str(value)) for name, value in (
        ("tone", defaults["tone"]), ("cta", defaults["cta"]), ("length", defaults["length"]),
        ("keyword_mode", defaults["keyword_mode"]), ("rewrite", "on"), ("remember", "on"),
        ("utm_source", ""), ("utm_medium", ""), ("utm_campaign", ""), ("instruction", ""), ("product_url", ""), ("account", ""))}
    auto["destination_url"] = ("profile", (business.website or "").strip()) if (business.website or "").strip() else ("default", "")
    exclusions = ", ".join(version.exclusions) if version else ""
    auto["forbidden_words"] = ("strategy", exclusions) if exclusions else ("default", "")
    if len(accounts) == 1:
        auto["account"] = ("account", str(accounts[0].pk))
    return auto


def _account_boards(account) -> list[str]:
    from apps.pinterest.sync import fresh_snapshot_resource
    if account is None:
        return []
    snapshot = fresh_snapshot_resource(account=account, resource="boards") or {}
    return [str(b.get("name")) for b in snapshot.get("items", []) if isinstance(b, dict) and b.get("name")]


def _job_card(job):
    percent = int((job.done + job.failed) * 100 / job.total) if job.total else 0
    return {"job": job, "label": JOB_STATUS_LABELS.get(job.status, job.status), "percent": min(percent, 100),
            "active": job.status in pin_jobs.ACTIVE}


def _editable_page_business(request, workspace_slug, business_slug):
    business = _get_business(request, workspace_slug, business_slug)
    if not memory.actor_can_edit(business, request.user):
        raise Http404
    return business


@login_required
def pin_generate(request, workspace_slug, business_slug):
    from .pin_generation import confirmed_plan, pending_items
    business = _editable_page_business(request, workspace_slug, business_slug)
    pin_jobs.reap_stale(business)
    plan = confirmed_plan(business)
    accounts = list(connected_accounts(business))
    preset = ps.normalize(getattr(getattr(business, "generation_preset", None), "values", None))
    has_preset = hasattr(business, "generation_preset")
    auto = _auto_values(business, plan.strategy_version if plan else None, accounts)
    pending = {i.pk for i in pending_items(plan)} if plan else set()
    items = list(plan.items.select_related("pin").order_by("position")) if plan else []
    form_kwargs = {"business": business}
    if request.method == "POST":
        form = PinGenerationForm(request.POST, **form_kwargs)
        selected = [int(v) for v in request.POST.getlist("items") if v.isdigit()]
    else:
        initial = initial_values(preset) if has_preset else {}
        for name, (source, value) in auto.items():
            if not initial.get(name) and name not in ("rewrite", "remember") and value:
                initial[name] = int(value) if name == "account" else value
        if not has_preset:
            initial.update({"rewrite": True, "remember": True})
        form = PinGenerationForm(initial=initial, **form_kwargs)
        selected = [i.pk for i in items if i.pk in pending][:3]
    boards_posted = {str(i.pk): request.POST.get(f"board_{i.pk}", "") for i in items} if request.method == "POST" else {}
    if request.method == "POST" and form.is_valid() and plan:
        options = form.options({k: v for k, v in boards_posted.items() if v and int(k) in selected})
        try:
            with transaction.atomic():
                job = pin_jobs.start_job(business, request.user, selected, options)
                if options["remember"]:
                    stored = {k: v for k, v in options.items() if k not in ("boards", "product_facts")}
                    GenerationPreset.objects.update_or_create(business=business, defaults={"values": stored, "updated_by": request.user})
                from .tasks import run_pin_generation
                transaction.on_commit(lambda: run_pin_generation.delay(job.pk))
        except pin_jobs.JobError as error:
            messages.error(request, gettext(str(error)))
        else:
            messages.success(request, _("Генерация запущена. Результаты появятся на странице «Пины» по мере готовности."))
            return redirect("strategist:pin-generate", workspace_slug=business.workspace.slug, business_slug=business.slug)
    selected_account = None
    if form.is_bound:
        selected_account = form.cleaned_data.get("account") if form.is_valid() else None
    elif form.initial.get("account"):
        selected_account = next((a for a in accounts if a.pk == form.initial["account"]), None)
    strategy_boards = [b["name"] for b in plan.strategy_version.recommended_boards] if plan else []
    board_choices = list(dict.fromkeys([*strategy_boards, *_account_boards(selected_account)]))
    meta, preset_form = {}, (initial_values(preset) if has_preset else {})
    for name in form.fields:
        source, value = auto.get(name, ("default", ""))
        remembered = preset_form.get(name)
        if remembered not in (None, "", False) and str(remembered) != value:
            source = "preset"  # the value comes from the user's earlier choice, not from the auto-fill
        meta[name] = {"source": source, "source_label": SOURCE_LABELS[source], "auto": value}
        form[name].field.widget.attrs["data-auto"] = value
    rows = []
    for item in items:
        pin = getattr(item, "pin", None)
        rows.append({"item": item, "pin": pin, "selectable": item.pk in pending, "checked": item.pk in selected,
                     "board": boards_posted.get(str(item.pk)) or item.board,
                     "status": PIN_STATUS_LABELS.get(pin.status, pin.status) if pin else ""})
    return render(request, "strategist/pin_generate.html", {
        "business": business, "strategist_business": business,
        "strategist_sessions": list(business.ai_conversations.filter(is_active=True).order_by("-updated_at")),
        "plan": plan, "form": form, "meta": meta, "rows": rows, "board_choices": board_choices,
        "advanced": [form[n] for n in ADVANCED_FIELDS], "max_items": ps.MAX_ITEMS,
        "jobs": [_job_card(j) for j in business.ai_jobs.filter(kind=AIJob.Kind.PIN_GENERATION)[:5]],
        "job_labels": {k: str(v) for k, v in JOB_STATUS_LABELS.items()},
        "accounts_missing": not accounts,
        "steps": _generation_steps(business),
    })


def connected_accounts(business):
    from apps.pinterest.models import PinterestAccount
    return PinterestAccount.objects.filter(business=business, deleted_at__isnull=True,
                                           status=PinterestAccount.Status.CONNECTED).order_by("created_at")


@login_required
def pin_job_status(request, workspace_slug, business_slug, job_id):
    business = _get_business(request, workspace_slug, business_slug)
    pin_jobs.reap_stale(business)
    job = get_object_or_404(AIJob, pk=job_id, business=business)
    return JsonResponse({**pin_jobs.summary(job), "label": str(JOB_STATUS_LABELS.get(job.status, job.status))})


@login_required
def pin_job_cancel(request, workspace_slug, business_slug, job_id):
    business = _editable_business(request, workspace_slug, business_slug)
    job = get_object_or_404(AIJob, pk=job_id, business=business)
    pin_jobs.request_cancel(job)
    messages.success(request, _("Отмена запрошена: текущий пин будет дописан, остальные не обрабатываются."))
    return redirect("strategist:pin-generate", workspace_slug=business.workspace.slug, business_slug=business.slug)


def _generation_steps(business):
    """Where the business is on the way to pin generation, and the one next action."""
    active = strategies.active_version(business)
    draft = strategies.pending_draft(business)
    plan = business.content_plans.exclude(status=ContentPlan.Status.SUPERSEDED).order_by("-created_at").first()
    strategy_state = ("done", _("Подтверждена, версия %(number)s") % {"number": active.number}) if active else (
        ("todo", _("Есть черновик, он ждёт подтверждения")) if draft else ("todo", _("Стратегии пока нет")))
    if plan is None:
        plan_state = ("todo", _("Контент-плана пока нет"))
    elif plan.status == ContentPlan.Status.CONFIRMED:
        plan_state = ("done", _("Подтверждён"))
    else:
        plan_state = ("todo", _("Есть черновик, он ждёт подтверждения"))
    if active is None:
        action = "strategy" if draft else "chat"
    elif plan is None:
        action = "build"
    else:
        action = "confirm"
    return {"strategy": strategy_state, "plan": plan_state, "action": action}
