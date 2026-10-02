import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache

from gigachat import GigaChat
from gigachat.models import Chat, Function, Messages, MessagesRole

from .model_catalog import TaskCapability
from .model_routing import GigaChatModelRouter

logger = logging.getLogger(__name__)


class GigaChatConfigurationError(Exception):
    pass


class GigaChatProviderError(Exception):
    pass


class GigaChatEmbeddingQuotaError(GigaChatProviderError):
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
    function_call: dict[str, Any] | None = None
    functions_state_id: str | None = None


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
        "function": MessagesRole.FUNCTION,
    }

    def __init__(self, router: GigaChatModelRouter | None = None):
        self.router = router or GigaChatModelRouter()

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        capability: TaskCapability = TaskCapability.CHAT,
        functions: list[Function] | None = None,
        function_call: str | None = None,
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
                return self._complete_with_model(
                    messages=messages,
                    model=model,
                    functions=functions,
                    function_call=function_call,
                )
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

        embedding_model = model or settings.GIGACHAT_EMBEDDING_MODEL
        quota_cache_key = f"strategist:gigachat:embedding-quota:{embedding_model}"
        if cache.get(quota_cache_key):
            raise GigaChatEmbeddingQuotaError("GigaChat embedding quota is temporarily unavailable.")
        try:
            with self._client() as client:
                response = client.embeddings(texts, model=embedding_model)
        except Exception as error:
            status_code = getattr(error, "status_code", None)
            if status_code is None:
                status_code = getattr(getattr(error, "response", None), "status_code", None)
            if status_code is None and len(error.args) > 1:
                status_code = error.args[1]
            if not isinstance(status_code, int) or not 100 <= status_code <= 599:
                status_code = "unknown"
            logger.warning(
                "GigaChat embedding failed: error_type=%s status_code=%s",
                type(error).__name__, status_code,
            )
            if status_code == 402:
                cache.set(quota_cache_key, True, timeout=300)
                raise GigaChatEmbeddingQuotaError("GigaChat embedding quota is unavailable.") from error
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

    def _complete_with_model(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        functions: list[Function] | None = None,
        function_call: str | None = None,
    ) -> GigaChatCompletion:
        try:
            chat = Chat(
                model=model,
                messages=[
                    Messages(
                        role=self.role_map[message["role"]],
                        content=message.get("content", ""),
                        name=message.get("name"),
                        function_call=message.get("function_call"),
                        functions_state_id=message.get("functions_state_id"),
                    )
                    for message in messages
                ],
                max_tokens=1200,
                functions=functions,
                function_call=function_call,
            )
            with self._client() as client:
                response = client.chat(chat)
        except Exception as error:
            raise GigaChatRequestError(
                model=model,
                can_fallback=self._can_fallback(error),
            ) from error

        message = response.choices[0].message if response.choices else None
        content = (message.content or "").strip() if message else ""
        call = getattr(message, "function_call", None) if message else None
        if not content and not call:
            raise GigaChatRequestError(model=model, can_fallback=False)

        usage = response.usage
        return GigaChatCompletion(
            content=content,
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
            function_call=(
                {"name": call.name, "arguments": call.arguments or {}}
                if call
                else None
            ),
            functions_state_id=getattr(message, "functions_state_id", None) if message else None,
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
