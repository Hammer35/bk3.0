import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from django.conf import settings
from django.core.cache import cache

from apps.strategist.providers import GigaChatEmbeddingBatch, GigaChatProvider

logger = logging.getLogger(__name__)


class OpenRouterEmbeddingError(Exception):
    pass


class OpenRouterEmbeddingProvider:
    def embed(self, texts: list[str], *, model: str) -> GigaChatEmbeddingBatch:
        if not texts:
            return GigaChatEmbeddingBatch(vectors=[], prompt_tokens=0)
        key = settings.OPENROUTER_API_KEY.strip()
        if not key:
            raise OpenRouterEmbeddingError("OpenRouter API key is not configured.")
        failure_cache_key = f"knowledge:openrouter:embedding-unavailable:{model}"
        if cache.get(failure_cache_key):
            raise OpenRouterEmbeddingError("OpenRouter embedding is temporarily unavailable.")

        request = Request(
            "https://openrouter.ai/api/v1/embeddings",
            data=json.dumps({"model": model, "input": texts}).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            proxy = settings.OPENROUTER_PROXY_URL.strip()
            open_request = build_opener(ProxyHandler({"https": proxy})).open if proxy else urlopen
            with open_request(request, timeout=15) as response:
                payload = json.load(response)
        except HTTPError as error:
            logger.warning("OpenRouter embedding failed: status_code=%s", error.code)
            if error.code in {401, 403, 429} or error.code >= 500:
                cache.set(failure_cache_key, True, timeout=120)
            raise OpenRouterEmbeddingError(f"OpenRouter embedding HTTP {error.code}.") from error
        except (URLError, TimeoutError, ValueError) as error:
            logger.warning("OpenRouter embedding failed: error_type=%s", type(error).__name__)
            cache.set(failure_cache_key, True, timeout=120)
            raise OpenRouterEmbeddingError("OpenRouter embedding request failed.") from error

        try:
            ordered = sorted(payload["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in ordered]
            if len(vectors) != len(texts) or any(not vector for vector in vectors):
                raise ValueError("Incomplete embedding response")
            if [item["index"] for item in ordered] != list(range(len(texts))):
                raise ValueError("Invalid embedding indexes")
            prompt_tokens = int(payload.get("usage", {}).get("prompt_tokens", 0))
        except (KeyError, TypeError, ValueError) as error:
            raise OpenRouterEmbeddingError("OpenRouter returned an invalid embedding response.") from error
        return GigaChatEmbeddingBatch(vectors=vectors, prompt_tokens=prompt_tokens)


def get_knowledge_embedder():
    if settings.KNOWLEDGE_EMBEDDING_PROVIDER == "openrouter":
        return OpenRouterEmbeddingProvider()
    if settings.KNOWLEDGE_EMBEDDING_PROVIDER == "gigachat":
        return GigaChatProvider()
    raise ValueError("Unknown knowledge embedding provider.")
