from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.businesses.models import Business

from .forms import StrategistMessageForm
from .models import AIConversation, AIMessage
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
