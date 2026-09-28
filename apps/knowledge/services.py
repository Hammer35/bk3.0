from dataclasses import dataclass
from datetime import date
import math
from pathlib import Path
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .chunking import chunk_markdown
from .models import KnowledgeChunk, KnowledgeDocument
from .sources import load_approved_sources

MIN_SIMILARITY_SCORE = 0.55
INDEXER_VERSION = 2


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
        if (
            existing
            and existing.content_hash == source.content_hash
            and existing.indexer_version == INDEXER_VERSION
            and not force
        ):
            stats["unchanged"] += 1
            continue

        chunks = chunk_markdown(source.content)
        vectors, prompt_tokens = _embed_in_batches(embedder, [chunk.content for chunk in chunks])
        if len(vectors) != len(chunks):
            raise ValueError(f"Embedding count does not match chunk count for {source.source_id}")

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
                    embedding_model=settings.GIGACHAT_EMBEDDING_MODEL,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ])
        stats["indexed"] += 1
        stats["chunks"] += len(chunks)
        stats["prompt_tokens"] += prompt_tokens
    return stats


def search_knowledge(*, query: str, embedder, limit: int = 5, min_score: float = MIN_SIMILARITY_SCORE) -> list[KnowledgeHit]:
    if not query.strip() or limit <= 0:
        return []

    today = timezone.localdate()
    chunks = list(
        KnowledgeChunk.objects.select_related("document")
        .filter(
            document__status="approved",
            document__scope="global",
            document__language="ru",
            embedding_model=settings.GIGACHAT_EMBEDDING_MODEL,
        )
        .exclude(embedding=[])
        .filter(document__source_checked__lte=today)
        .order_by("document_id", "ordinal")
    )
    chunks = [chunk for chunk in chunks if not chunk.document.effective_until or chunk.document.effective_until >= today]
    if not chunks:
        return []

    query_vectors, _ = _embed_in_batches(embedder, [query])
    query_vector = query_vectors[0]
    ranked = []
    for chunk in chunks:
        score = _cosine_similarity(query_vector, chunk.embedding)
        if score >= min_score:
            ranked.append((score, chunk))
    ranked.sort(key=lambda row: row[0], reverse=True)

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


def format_knowledge_context(hits: list[KnowledgeHit]) -> str:
    if not hits:
        return ""
    sections = []
    for hit in hits:
        sources = ", ".join(hit.source_links) if hit.source_links else hit.source_id
        heading = f" / {hit.heading}" if hit.heading else ""
        sections.append(f"Источник: {hit.title}{heading}\nСсылка: {sources}\n{hit.content}")
    return "Проверенные материалы для ответа:\n\n" + "\n\n---\n\n".join(sections)


def _embed_in_batches(embedder, texts: list[str]) -> tuple[list[list[float]], int]:
    vectors = []
    prompt_tokens = 0
    for start in range(0, len(texts), 16):
        result = embedder.embed(texts[start:start + 16], model=settings.GIGACHAT_EMBEDDING_MODEL)
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
