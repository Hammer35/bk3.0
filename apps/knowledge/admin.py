from django.contrib import admin

from .models import KnowledgeChunk, KnowledgeDocument


class KnowledgeChunkInline(admin.TabularInline):
    model = KnowledgeChunk
    fields = ("ordinal", "heading", "content", "embedding_model")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = False
    verbose_name = "фрагмент"
    verbose_name_plural = "фрагменты документа"


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "source_id", "language", "scope", "status", "source_checked", "effective_until")
    list_filter = ("language", "scope", "status", "source_checked")
    search_fields = ("title", "source_id", "source_path", "content_hash")
    readonly_fields = (
        "source_id",
        "title",
        "source_path",
        "language",
        "scope",
        "source_checked",
        "effective_until",
        "source_links",
        "metadata",
        "content_hash",
        "indexer_version",
        "status",
        "public_id",
        "created_at",
        "updated_at",
    )
    inlines = (KnowledgeChunkInline,)
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
