from django.db import models

from apps.core.models import BaseModel


class KnowledgeDocument(BaseModel):
    class Scope(models.TextChoices):
        GLOBAL = "global", "Общая база знаний"

    class Status(models.TextChoices):
        APPROVED = "approved", "Утверждён"

    source_id = models.CharField(max_length=180, unique=True, verbose_name="идентификатор источника")
    title = models.CharField(max_length=240, verbose_name="название документа")
    source_path = models.CharField(max_length=500, verbose_name="путь к исходному файлу")
    language = models.CharField(max_length=12, default="ru", verbose_name="язык")
    scope = models.CharField(max_length=40, choices=Scope.choices, default=Scope.GLOBAL, verbose_name="область применения")
    source_checked = models.DateField(null=True, blank=True, verbose_name="дата проверки источника")
    effective_until = models.DateField(null=True, blank=True, verbose_name="действует до")
    source_links = models.JSONField(default=list, blank=True, verbose_name="ссылки на источники")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="метаданные документа")
    content_hash = models.CharField(max_length=64, verbose_name="контрольная сумма содержимого")
    indexer_version = models.PositiveSmallIntegerField(default=1, verbose_name="версия индексатора")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.APPROVED, verbose_name="статус")

    class Meta:
        ordering = ("source_id",)
        verbose_name = "документ базы знаний"
        verbose_name_plural = "документы базы знаний"


class KnowledgeChunk(BaseModel):
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks", verbose_name="документ")
    ordinal = models.PositiveIntegerField(verbose_name="номер фрагмента")
    heading = models.CharField(max_length=240, blank=True, verbose_name="раздел")
    content = models.TextField(verbose_name="текст фрагмента")
    embedding = models.JSONField(default=list, blank=True, verbose_name="векторное представление")
    embedding_model = models.CharField(max_length=80, blank=True, verbose_name="модель эмбеддингов")

    class Meta:
        ordering = ("document_id", "ordinal")
        verbose_name = "фрагмент базы знаний"
        verbose_name_plural = "фрагменты базы знаний"
        constraints = [
            models.UniqueConstraint(fields=("document", "ordinal"), name="knowledge_chunk_document_ordinal_uniq"),
        ]
