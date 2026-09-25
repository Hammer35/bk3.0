from django.utils.text import slugify

from apps.businesses.models import Business

from .models import AIConversation, AIMessage
from .prompts import build_strategist_system_prompt
from .providers import GigaChatCompletion, GigaChatProvider


def create_conversation(*, business: Business, user) -> AIConversation:
    conversation = AIConversation.objects.create(business=business, created_by=user)
    conversation.slug = f"session-{conversation.public_id.hex[:8]}"
    conversation.save(update_fields=["slug"])
    return conversation


def conversation_slug(*, title: str, conversation: AIConversation) -> str:
    base_slug = slugify(title)[:180].rstrip("-") or "session"
    return f"{base_slug}-{conversation.public_id.hex[:8]}"


def respond_to_message(*, user_message: AIMessage) -> AIMessage:
    conversation = user_message.conversation
    history = list(
        conversation.messages.order_by("-created_at").values("role", "content")[:12]
    )
    history.reverse()
    completion: GigaChatCompletion = GigaChatProvider().complete(
        [
            {"role": "system", "content": build_strategist_system_prompt(conversation.business)},
            *[
                {"role": "user" if item["role"] == AIMessage.Role.USER else "assistant", "content": item["content"]}
                for item in history
            ],
        ]
    )
    return AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.ASSISTANT,
        content=completion.content,
        provider="gigachat",
        model=completion.model,
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
        total_tokens=completion.total_tokens,
    )
