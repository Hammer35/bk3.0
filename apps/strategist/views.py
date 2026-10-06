from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _

from apps.businesses.models import Business

from . import content_plan as plans
from . import memory, research
from . import strategy as strategies
from .forms import StrategistMessageForm
from .models import AIConversation, AIMessage, ContentPlan, StrategyVersion
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
