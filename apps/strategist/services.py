import logging

from django.utils.text import slugify

from apps.businesses.models import Business
from apps.knowledge.services import format_knowledge_context, search_knowledge

from .models import AIConversation, AIMessage
from .prompts import build_strategist_system_prompt
from .providers import GigaChatCompletion, GigaChatProvider

logger = logging.getLogger(__name__)


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
    provider = GigaChatProvider()
    try:
        knowledge_hits = search_knowledge(query=user_message.content, embedder=provider)
    except Exception as error:
        logger.warning("Knowledge retrieval failed; continuing without RAG: %s", type(error).__name__)
        knowledge_hits = []

    completion: GigaChatCompletion = provider.complete(
        [
            {
                "role": "system",
                "content": build_strategist_system_prompt(
                    conversation.business,
                    knowledge_context=format_knowledge_context(knowledge_hits),
                ),
            },
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
