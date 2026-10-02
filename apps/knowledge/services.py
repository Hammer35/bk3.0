from collections import Counter
from dataclasses import dataclass
from datetime import date
import logging
import math
from pathlib import Path
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .chunking import chunk_markdown
from .embeddings import OpenRouterEmbeddingError, OpenRouterEmbeddingProvider
from .models import KnowledgeChunk, KnowledgeDocument
from .sources import load_approved_sources

INDEXER_VERSION = 2
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KnowledgeHit:
    content: str
    score: float
    source_id: str
    title: str
    source_links: tuple[str, ...]
    heading: str


def index_knowledge(*, embedder, directory: Path | None = None, force: bool = False) -> dict[str, int]:
    project_root = Path(settings.BASE_DIR)
    source_directory = directory or project_root / "docs" / "ai-knowledge" / "knowledge"
    sources = load_approved_sources(source_directory, project_root=project_root)
    stats = {"documents": len(sources), "indexed": 0, "unchanged": 0, "chunks": 0, "prompt_tokens": 0}

    for source in sources:
        existing = KnowledgeDocument.objects.filter(source_id=source.source_id).first()
        fallback_model = settings.KNOWLEDGE_FALLBACK_EMBEDDING_MODEL
        if (
            existing
            and existing.content_hash == source.content_hash
            and existing.indexer_version == INDEXER_VERSION
            and existing.chunks.filter(embedding_model=settings.KNOWLEDGE_EMBEDDING_MODEL).exists()
            and not existing.chunks.exclude(embedding_model=settings.KNOWLEDGE_EMBEDDING_MODEL).exists()
            and (not fallback_model or not existing.chunks.exclude(fallback_embedding_model=fallback_model).exists())
            and not force
        ):
            stats["unchanged"] += 1
            continue

        chunks = chunk_markdown(source.content)
        vectors, prompt_tokens = _embed_in_batches(embedder, [chunk.content for chunk in chunks])
        if len(vectors) != len(chunks):
            raise ValueError(f"Embedding count does not match chunk count for {source.source_id}")

        old_chunks = {
            (chunk.ordinal, chunk.content): chunk
            for chunk in existing.chunks.all()
        } if existing and existing.content_hash == source.content_hash else {}
        fallback_vectors = []
        if fallback_model:
            for chunk in chunks:
                old = old_chunks.get((chunk.ordinal, chunk.content))
                if old and old.fallback_embedding_model == fallback_model and old.fallback_embedding:
                    fallback_vectors.append(old.fallback_embedding)
                elif old and old.embedding_model == fallback_model and old.embedding:
                    fallback_vectors.append(old.embedding)
                else:
                    fallback_vectors = []
                    break
            if len(fallback_vectors) != len(chunks):
                try:
                    fallback_vectors, fallback_tokens = _embed_in_batches(
                        OpenRouterEmbeddingProvider(), [chunk.content for chunk in chunks],
                        model=fallback_model, provider="openrouter",
                    )
                    stats["prompt_tokens"] += fallback_tokens
                except OpenRouterEmbeddingError as error:
                    logger.warning("Fallback knowledge indexing failed: %s", type(error).__name__)
                    fallback_vectors = []

        with transaction.atomic():
            document, _ = KnowledgeDocument.objects.update_or_create(
                source_id=source.source_id,
                defaults={
                    "title": source.title,
                    "source_path": source.source_path,
                    "language": source.language,
                    "scope": source.scope,
                    "source_checked": source.source_checked,
                    "effective_until": source.effective_until,
                    "source_links": source.source_links,
                    "metadata": _json_safe_metadata(source.metadata),
                    "content_hash": source.content_hash,
                    "indexer_version": INDEXER_VERSION,
                    "status": source.status,
                },
            )
            document.chunks.all().delete()
            KnowledgeChunk.objects.bulk_create([
                KnowledgeChunk(
                    document=document,
                    ordinal=chunk.ordinal,
                    heading=chunk.heading,
                    content=chunk.content,
                    embedding=vector,
                    embedding_model=settings.KNOWLEDGE_EMBEDDING_MODEL,
                    fallback_embedding=fallback_vectors[position] if fallback_vectors else [],
                    fallback_embedding_model=fallback_model if fallback_vectors else "",
                )
                for position, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
            ])
        stats["indexed"] += 1
        stats["chunks"] += len(chunks)
        stats["prompt_tokens"] += prompt_tokens
    return stats


def search_knowledge(*, query: str, embedder, limit: int = 5, min_score: float | None = None,
                     model: str | None = None, provider: str | None = None, fallback: bool = False) -> list[KnowledgeHit]:
    if not query.strip() or limit <= 0:
        return []
    if min_score is None:
        min_score = (settings.KNOWLEDGE_FALLBACK_MIN_SIMILARITY_SCORE if fallback
                     else settings.KNOWLEDGE_MIN_SIMILARITY_SCORE)

    model = model or settings.KNOWLEDGE_EMBEDDING_MODEL
    chunks = _searchable_chunks(require_embedding=True, model=model, fallback=fallback)
    if not chunks:
        return []

    query_vectors, _ = _embed_in_batches(embedder, [query], query=True, model=model, provider=provider)
    query_vector = query_vectors[0]
    ranked = []
    for chunk in chunks:
        score = _cosine_similarity(query_vector, chunk.fallback_embedding if fallback else chunk.embedding)
        if score >= min_score:
            ranked.append((score, chunk))
    ranked.sort(key=lambda row: row[0], reverse=True)
    return _knowledge_hits(ranked, limit=limit)


def search_knowledge_lexical(*, query: str, limit: int = 5) -> list[KnowledgeHit]:
    """Retrieve approved indexed chunks without calling the embedding API."""
    terms = _lexical_terms(query)
    if not terms or limit <= 0:
        return []

    chunks = _searchable_chunks(require_embedding=False)
    if not chunks:
        return []
    chunk_terms = [_lexical_terms(chunk.content) for chunk in chunks]
    frequencies = Counter(term for words in chunk_terms for term in words)
    weights = {term: math.log((len(chunks) + 1) / (frequencies[term] + 1)) + 1 for term in terms}
    ranked = []
    for chunk, words in zip(chunks, chunk_terms, strict=True):
        matched = terms & words
        if not matched:
            continue
        score = sum(weights[term] for term in matched)
        score += 0.5 * sum(weights[term] for term in terms & _lexical_terms(chunk.heading))
        ranked.append((score, chunk))
    ranked.sort(key=lambda row: row[0], reverse=True)
    return _knowledge_hits(ranked, limit=limit)


def _searchable_chunks(*, require_embedding: bool, model: str = "", fallback: bool = False) -> list[KnowledgeChunk]:
    today = timezone.localdate()
    queryset = (
        KnowledgeChunk.objects.select_related("document")
        .filter(
            document__status="approved",
            document__scope="global",
            document__language="ru",
        )
        .filter(document__source_checked__lte=today)
        .order_by("document_id", "ordinal")
    )
    if require_embedding:
        if fallback:
            queryset = queryset.filter(fallback_embedding_model=model).exclude(fallback_embedding=[])
        else:
            queryset = queryset.filter(embedding_model=model).exclude(embedding=[])
    chunks = list(queryset)
    return [chunk for chunk in chunks if not chunk.document.effective_until or chunk.document.effective_until >= today]


def _knowledge_hits(ranked: list[tuple[float, KnowledgeChunk]], *, limit: int) -> list[KnowledgeHit]:
    hits = []
    for score, chunk in ranked:
        if _is_overlap_duplicate(chunk, hits):
            continue
        document = chunk.document
        hits.append(KnowledgeHit(
            content=chunk.content,
            score=score,
            source_id=document.source_id,
            title=document.title,
            source_links=tuple(document.source_links),
            heading=chunk.heading,
        ))
        if len(hits) == limit:
            break
    return hits


def _lexical_terms(text: str) -> set[str]:
    return {word[:5] for word in re.findall(r"[а-яёa-z]{3,}", text.casefold())}


def format_knowledge_context(hits: list[KnowledgeHit]) -> str:
    if not hits:
        return ""
    sections = []
    for hit in hits:
        sources = ", ".join(hit.source_links) if hit.source_links else hit.source_id
        heading = f" / {hit.heading}" if hit.heading else ""
        sections.append(f"Источник: {hit.title}{heading}\nСсылка: {sources}\n{hit.content}")
    return "Проверенные материалы для ответа:\n\n" + "\n\n---\n\n".join(sections)


def _embed_in_batches(embedder, texts: list[str], *, query: bool = False,
                      model: str | None = None, provider: str | None = None) -> tuple[list[list[float]], int]:
    vectors = []
    prompt_tokens = 0
    model = model or settings.KNOWLEDGE_EMBEDDING_MODEL
    provider = provider or settings.KNOWLEDGE_EMBEDDING_PROVIDER
    if provider == "openrouter":
        if model in {
            "nvidia/nemotron-3-embed-1b:free",
            "nvidia/llama-nemotron-embed-vl-1b-v2:free",
        }:
            prefix = "query: " if query else "passage: "
            texts = [prefix + text for text in texts]
        elif model == "liquid/lfm-2.5-embedding-350m:free":
            prefix = "query: " if query else "document: "
            texts = [prefix + text for text in texts]
    for start in range(0, len(texts), 16):
        result = embedder.embed(texts[start:start + 16], model=model)
        vectors.extend(result.vectors)
        prompt_tokens += result.prompt_tokens
    return vectors, prompt_tokens


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _is_overlap_duplicate(chunk: KnowledgeChunk, hits: list[KnowledgeHit]) -> bool:
    words = _normalized_words(chunk.content)
    if not words:
        return False
    for hit in hits:
        if hit.source_id != chunk.document.source_id:
            continue
        other = _normalized_words(hit.content)
        union = words | other
        if union and len(words & other) / len(union) >= 0.72:
            return True
    return False


def _normalized_words(text: str) -> set[str]:
    return set(re.findall(r"[\w-]{3,}", text.casefold()))


def _json_safe_metadata(metadata: dict) -> dict:
    return {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in metadata.items()
    }
