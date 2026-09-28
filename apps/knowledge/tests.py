from pathlib import Path
from tempfile import TemporaryDirectory

from django.apps import apps
from django.contrib import admin
from django.test import SimpleTestCase, TestCase, override_settings

from apps.strategist.providers import GigaChatEmbeddingBatch

from .chunking import chunk_markdown
from .models import KnowledgeChunk, KnowledgeDocument
from .services import index_knowledge, search_knowledge


class MarkdownChunkingTest(SimpleTestCase):
    def test_chunks_keep_section_boundaries_and_overlap(self):
        paragraph = " ".join(["Pinterest marks repeated Pins as spam."] * 14)
        chunks = chunk_markdown(
            f"# First section\n\n{paragraph}\n\n# Second section\n\nIndependent material.",
            max_chars=256,
            overlap_chars=70,
        )

        first_section = [chunk for chunk in chunks if chunk.heading == "First section"]
        second_section = [chunk for chunk in chunks if chunk.heading == "Second section"]
        self.assertGreater(len(first_section), 1)
        self.assertEqual(len(second_section), 1)
        self.assertTrue(set(first_section[0].content.split()) & set(first_section[1].content.split()))
        self.assertNotIn("Independent material", " ".join(chunk.content for chunk in first_section))

    def test_source_list_links_are_metadata_not_retrieval_chunks(self):
        chunks = chunk_markdown(
            "# Pinterest spam\n\nAvoid repeated Pins.\n\n"
            "## Источники\n\n[Official policy](https://policy.pinterest.test/spam)"
        )

        self.assertEqual(len(chunks), 1)
        self.assertNotIn("Official policy", chunks[0].content)


class KnowledgeIndexTest(TestCase):
    def test_index_is_idempotent_and_search_returns_source_provenance(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_directory = root / "docs" / "ai-knowledge" / "knowledge"
            source_directory.mkdir(parents=True)
            (source_directory / "spam.md").write_text(
                "---\n"
                "id: pinterest-spam-v1\n"
                "status: approved\n"
                "scope: global\n"
                "language: ru\n"
                "source_checked: 2026-01-01\n"
                "---\n\n"
                "# Спам в Pinterest\n\n"
                "Повторяющиеся публикации и нерелевантные ключевые слова могут считаться спамом.\n\n"
                "[Правила](https://policy.pinterest.test/spam)\n",
                encoding="utf-8",
            )

            class FakeEmbedder:
                def __init__(self):
                    self.calls = 0

                def embed(self, texts, *, model):
                    self.calls += 1
                    vectors = [[1.0, 0.0] if "спам" in text.lower() else [0.0, 1.0] for text in texts]
                    return GigaChatEmbeddingBatch(vectors=vectors, prompt_tokens=len(texts) * 12)

            embedder = FakeEmbedder()
            with override_settings(BASE_DIR=root):
                first = index_knowledge(embedder=embedder)
                second = index_knowledge(embedder=embedder)
                hits = search_knowledge(query="проверка спама", embedder=embedder)
                unrelated_hits = search_knowledge(query="совсем посторонняя тема", embedder=embedder)

        self.assertEqual(first["indexed"], 1)
        self.assertEqual(first["prompt_tokens"], 12)
        self.assertEqual(second["unchanged"], 1)
        # One document batch plus one embedding for each semantic query.
        self.assertEqual(embedder.calls, 3)
        self.assertEqual(KnowledgeDocument.objects.count(), 1)
        self.assertEqual(KnowledgeChunk.objects.count(), 1)
        self.assertEqual(hits[0].source_id, "pinterest-spam-v1")
        self.assertIn("https://policy.pinterest.test/spam", hits[0].source_links)
        self.assertEqual(unrelated_hits, [])


class RussianAdminLabelsTest(SimpleTestCase):
    def test_project_apps_and_knowledge_models_have_russian_admin_labels(self):
        self.assertEqual(apps.get_app_config("businesses").verbose_name, "Бизнесы")
        self.assertEqual(apps.get_app_config("workspaces").verbose_name, "Рабочие пространства")
        self.assertEqual(KnowledgeDocument._meta.verbose_name, "документ базы знаний")
        self.assertEqual(KnowledgeChunk._meta.verbose_name_plural, "фрагменты базы знаний")
        self.assertIn(KnowledgeDocument, admin.site._registry)
        self.assertEqual(admin.site.site_header, "Администрирование BOOSTKLIENT®")
