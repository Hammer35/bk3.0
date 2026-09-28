from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.chunking import chunk_markdown
from apps.knowledge.sources import load_approved_sources
from apps.knowledge.services import index_knowledge
from apps.strategist.providers import GigaChatProvider, GigaChatProviderError


class Command(BaseCommand):
    help = "Index approved global knowledge documents; embedding calls require --embed."

    def add_arguments(self, parser):
        parser.add_argument("--embed", action="store_true", help="Create and store GigaChat embeddings (billable API call).")
        parser.add_argument("--force", action="store_true", help="Re-embed documents even when their source hash is unchanged.")

    def handle(self, *args, **options):
        directory = Path(settings.BASE_DIR) / "docs" / "ai-knowledge" / "knowledge"
        if not options["embed"]:
            sources = load_approved_sources(directory, project_root=Path(settings.BASE_DIR))
            chunks = [chunk for source in sources for chunk in chunk_markdown(source.content)]
            self.stdout.write(
                f"Dry run: {len(sources)} approved documents, {len(chunks)} semantic chunks, "
                f"{sum(len(chunk.content) for chunk in chunks)} text characters. "
                "No database writes or external API calls. Pass --embed to index."
            )
            return

        try:
            stats = index_knowledge(embedder=GigaChatProvider(), force=options["force"])
        except (GigaChatProviderError, ValueError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {stats['indexed']} document(s), {stats['chunks']} chunks; "
                f"{stats['unchanged']} unchanged. Embeddings used {stats['prompt_tokens']} input tokens."
            )
        )
