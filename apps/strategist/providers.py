import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from .model_catalog import TaskCapability
from .model_routing import GigaChatModelRouter

logger = logging.getLogger(__name__)


class GigaChatConfigurationError(Exception):
    pass


class GigaChatProviderError(Exception):
    pass


class GigaChatRequestError(GigaChatProviderError):
    def __init__(self, *, model: str, can_fallback: bool):
        super().__init__("GigaChat request failed.")
        self.model = model
        self.can_fallback = can_fallback


@dataclass(frozen=True)
class GigaChatCompletion:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class GigaChatEmbeddingBatch:
    vectors: list[list[float]]
    prompt_tokens: int


class GigaChatProvider:
    """Small adapter around the official SDK used by the strategist only."""

    role_map = {
        "system": MessagesRole.SYSTEM,
        "user": MessagesRole.USER,
        "assistant": MessagesRole.ASSISTANT,
    }

    def __init__(self, router: GigaChatModelRouter | None = None):
        self.router = router or GigaChatModelRouter()

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        capability: TaskCapability = TaskCapability.CHAT,
    ) -> GigaChatCompletion:
        credentials = settings.GIGACHAT_API_TOKEN.strip()
        if not credentials:
            raise GigaChatConfigurationError("GigaChat authorization key is not configured.")

        candidates = self.router.candidates(
            capability=capability,
            available_model_ids=self._available_model_ids(),
        )
        if not candidates:
            raise GigaChatProviderError("No configured GigaChat model supports this task.")

        last_error = None
        for model in candidates:
            try:
                return self._complete_with_model(messages=messages, model=model)
            except GigaChatRequestError as error:
                last_error = error
                if not error.can_fallback:
                    raise
                logger.warning("GigaChat model unavailable; trying fallback: %s", model)

        raise GigaChatProviderError("All eligible GigaChat models are unavailable.") from last_error

    def embed(self, texts: list[str], *, model: str | None = None) -> GigaChatEmbeddingBatch:
        credentials = settings.GIGACHAT_API_TOKEN.strip()
        if not credentials:
            raise GigaChatConfigurationError("GigaChat authorization key is not configured.")
        if not texts:
            return GigaChatEmbeddingBatch(vectors=[], prompt_tokens=0)

        try:
            with self._client() as client:
                response = client.embeddings(texts, model=model or settings.GIGACHAT_EMBEDDING_MODEL)
        except Exception as error:
            raise GigaChatProviderError("GigaChat embedding request failed.") from error

        ordered = sorted(response.data, key=lambda item: item.index)
        if len(ordered) != len(texts) or [item.index for item in ordered] != list(range(len(texts))):
            raise GigaChatProviderError("GigaChat returned an incomplete embedding response.")
        return GigaChatEmbeddingBatch(
            vectors=[item.embedding for item in ordered],
            prompt_tokens=sum(item.usage.prompt_tokens for item in ordered),
        )

    def _available_model_ids(self) -> tuple[str, ...]:
        cache_key = "strategist:gigachat:available-models:v1"
        cached_model_ids = cache.get(cache_key)
        if cached_model_ids is not None:
            return tuple(cached_model_ids)

        try:
            with self._client() as client:
                model_ids = tuple(model.id_ for model in client.get_models().data)
        except Exception as error:
            logger.warning("GigaChat model discovery failed: %s", type(error).__name__)
            return ()

        cache.set(cache_key, model_ids, settings.GIGACHAT_AVAILABLE_MODELS_CACHE_SECONDS)
        return model_ids

    def _complete_with_model(self, *, messages: list[dict[str, str]], model: str) -> GigaChatCompletion:
        try:
            chat = Chat(
                model=model,
                messages=[
                    Messages(role=self.role_map[message["role"]], content=message["content"])
                    for message in messages
                ],
                max_tokens=1200,
            )
            with self._client() as client:
                response = client.chat(chat)
        except Exception as error:
            raise GigaChatRequestError(
                model=model,
                can_fallback=self._can_fallback(error),
            ) from error

        content = response.choices[0].message.content.strip() if response.choices else ""
        if not content:
            raise GigaChatRequestError(model=model, can_fallback=False)

        usage = response.usage
        return GigaChatCompletion(
            content=content,
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
        )

    @staticmethod
    def _can_fallback(error: Exception) -> bool:
        error_text = str(error).lower()
        return any(
            marker in error_text
            for marker in ("404", "429", "500", "502", "503", "504", "no such model", "quota")
        )

    @staticmethod
    def _client() -> GigaChat:
        return GigaChat(
            credentials=settings.GIGACHAT_API_TOKEN,
            scope=settings.GIGACHAT_SCOPE,
            base_url=settings.GIGACHAT_BASE_URL,
            timeout=settings.GIGACHAT_TIMEOUT_SECONDS,
            ca_bundle_file=settings.GIGACHAT_CA_BUNDLE_FILE,
            verify_ssl_certs=True,
        )
