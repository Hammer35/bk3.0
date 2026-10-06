import uuid

from django.conf import settings
from django.db import models

from apps.businesses.models import Business
from apps.core.models import BaseModel


def default_conversation_slug():
    return f"session-{uuid.uuid4().hex}"


class AIConversation(BaseModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="ai_conversations", verbose_name="бизнес")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="создатель")
    title = models.CharField(max_length=200, blank=True, default="", verbose_name="название сессии")
    slug = models.SlugField(max_length=220, default=default_conversation_slug, editable=False, unique=True, verbose_name="слаг")
    is_active = models.BooleanField(default=True, verbose_name="активна")

    class Meta:
        verbose_name = "сессия ИИ-стратега"
        verbose_name_plural = "сессии ИИ-стратега"


class AIMessage(BaseModel):
    class Role(models.TextChoices):
        USER = "USER", "Пользователь"
        ASSISTANT = "ASSISTANT", "ИИ-стратег"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages", verbose_name="сессия")
    role = models.CharField(max_length=16, choices=Role.choices, verbose_name="отправитель")
    content = models.TextField(verbose_name="сообщение")
    assets = models.JSONField(default=dict, blank=True, verbose_name="данные карточки в чате")
    provider = models.CharField(max_length=32, blank=True, verbose_name="провайдер ИИ")
    model = models.CharField(max_length=80, blank=True, verbose_name="модель ИИ")
    prompt_tokens = models.PositiveIntegerField(default=0, verbose_name="токены запроса")
    completion_tokens = models.PositiveIntegerField(default=0, verbose_name="токены ответа")
    total_tokens = models.PositiveIntegerField(default=0, verbose_name="всего токенов")
    prompt_version = models.CharField(max_length=64, blank=True, default="", verbose_name="версия промпта")
    context_manifest = models.JSONField(default=list, blank=True, verbose_name="источники контекста (manifest)")

    class Meta:
        ordering = ("created_at",)
        verbose_name = "сообщение ИИ-стратега"
        verbose_name_plural = "сообщения ИИ-стратега"


class WBImageAnalysis(BaseModel):
    sha256 = models.CharField(max_length=64, unique=True, verbose_name="хеш изображения")
    description = models.TextField(verbose_name="описание изображения")
    machine_description = models.TextField(blank=True, verbose_name="исходное описание модели")
    person = models.BooleanField(default=False, verbose_name="есть человек")
    person_wears_product = models.BooleanField(default=False, verbose_name="товар на человеке")
    clean = models.BooleanField(default=False, verbose_name="чистое фото")
    reviewed = models.BooleanField(default=False, verbose_name="описание проверено")
    model = models.CharField(max_length=80, default="GigaChat-2-Pro", verbose_name="модель анализа")

    class Meta:
        verbose_name = "анализ изображения WB"
        verbose_name_plural = "анализы изображений WB"


class Strategy(BaseModel):
    """Logical strategy object; content lives only in immutable StrategyVersion rows."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Черновик"
        ACTIVE = "ACTIVE", "Действует"
        ARCHIVED = "ARCHIVED", "В архиве"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="strategies", verbose_name="бизнес")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, verbose_name="статус")
    active_version = models.ForeignKey(
        "StrategyVersion", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="действующая версия",
    )
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name="дата архивации")

    class Meta:
        verbose_name = "стратегия"
        verbose_name_plural = "стратегии"


class StrategyVersion(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Черновик"
        CONFIRMED = "CONFIRMED", "Подтверждена"
        SUPERSEDED = "SUPERSEDED", "Заменена"
        REJECTED = "REJECTED", "Отклонена"

    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, related_name="versions", verbose_name="стратегия")
    number = models.PositiveIntegerField(verbose_name="номер версии")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, verbose_name="статус")
    goals = models.JSONField(default=list, blank=True, verbose_name="цели")
    priorities = models.JSONField(default=list, blank=True, verbose_name="приоритеты")
    keyword_clusters = models.JSONField(default=list, blank=True, verbose_name="группы ключевых слов")
    recommended_boards = models.JSONField(default=list, blank=True, verbose_name="рекомендуемые доски")
    content_directions = models.JSONField(default=list, blank=True, verbose_name="контентные направления")
    publishing_cadence = models.JSONField(default=dict, blank=True, verbose_name="частота публикаций")
    seasonal_plans = models.JSONField(default=list, blank=True, verbose_name="сезонные планы")
    exclusions = models.JSONField(default=list, blank=True, verbose_name="исключения пользователя")
    rationale = models.JSONField(default=list, blank=True, verbose_name="основания")
    hypotheses = models.JSONField(default=list, blank=True, verbose_name="гипотезы")
    missing_data = models.JSONField(default=list, blank=True, verbose_name="недостающие данные")
    sources = models.JSONField(default=list, blank=True, verbose_name="источники (manifest)")
    change_note = models.CharField(max_length=500, blank=True, verbose_name="что изменено")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="создатель",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="+", verbose_name="подтвердил",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="дата подтверждения")
    research_snapshots = models.ManyToManyField(
        "ResearchSnapshot", blank=True, related_name="strategy_versions", verbose_name="снимки исследований",
    )

    class Meta:
        ordering = ("strategy", "number")
        verbose_name = "версия стратегии"
        verbose_name_plural = "версии стратегии"
        constraints = [
            models.UniqueConstraint(fields=["strategy", "number"], name="unique_strategy_version_number"),
        ]


class ResearchSnapshot(BaseModel):
    """Stored result of a niche research run; strategy versions cite it as a source."""

    class Kind(models.TextChoices):
        NICHE_KEYWORDS = "NICHE_KEYWORDS", "Ключевые слова ниши"
        COVERAGE = "COVERAGE", "Охват собственного контента"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="research_snapshots", verbose_name="бизнес")
    account = models.ForeignKey(
        "pinterest.PinterestAccount", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="аккаунт Pinterest",
    )
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.NICHE_KEYWORDS, verbose_name="тип")
    seeds = models.JSONField(default=list, blank=True, verbose_name="поисковые корни")
    region = models.CharField(max_length=40, blank=True, verbose_name="регион")
    candidates = models.JSONField(default=list, blank=True, verbose_name="найденные фразы")
    notices = models.JSONField(default=list, blank=True, verbose_name="замечания источников")
    total_tokens = models.PositiveIntegerField(default=0, verbose_name="токены")
    researched_at = models.DateTimeField(verbose_name="дата исследования")

    class Meta:
        ordering = ("-researched_at",)
        verbose_name = "снимок исследования"
        verbose_name_plural = "снимки исследований"


class BusinessMemory(BaseModel):
    """Confirmed business facts and decisions; never a copy of the chat history."""

    class Kind(models.TextChoices):
        FACT = "FACT", "Факт"
        DECISION = "DECISION", "Решение"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="memory_items", verbose_name="бизнес")
    kind = models.CharField(max_length=16, choices=Kind.choices, verbose_name="тип")
    text = models.CharField(max_length=300, verbose_name="содержание")
    reason = models.CharField(max_length=300, blank=True, verbose_name="причина")
    source_ref = models.CharField(max_length=80, verbose_name="источник")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="подтвердил",
    )

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "запись памяти бизнеса"
        verbose_name_plural = "память бизнеса"
        indexes = [models.Index(fields=["business", "kind"], name="memory_business_kind_idx")]


class ContentPlan(BaseModel):
    """Production plan built from one confirmed strategy version; it is not a set of Pins."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Черновик"
        CONFIRMED = "CONFIRMED", "Подтверждён"
        SUPERSEDED = "SUPERSEDED", "Заменён"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="content_plans", verbose_name="бизнес")
    strategy_version = models.ForeignKey(StrategyVersion, on_delete=models.RESTRICT, related_name="content_plans", verbose_name="версия стратегии")
    horizon_weeks = models.PositiveSmallIntegerField(default=4, verbose_name="горизонт, недель")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, verbose_name="статус")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="создатель")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="подтвердил")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="дата подтверждения")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "контент-план"
        verbose_name_plural = "контент-планы"


class ContentPlanItem(BaseModel):
    class ContentType(models.TextChoices):
        PIN = "PIN", "Пин"
        VIDEO = "VIDEO", "Видео-пин"

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Запланирован"

    plan = models.ForeignKey(ContentPlan, on_delete=models.CASCADE, related_name="items", verbose_name="план")
    position = models.PositiveSmallIntegerField(verbose_name="порядок")
    target_week = models.PositiveSmallIntegerField(verbose_name="неделя плана")
    direction = models.CharField(max_length=300, verbose_name="контентное направление")
    board = models.CharField(max_length=300, blank=True, verbose_name="доска")
    keyword = models.CharField(max_length=300, blank=True, verbose_name="ключевая фраза")
    search_intent = models.CharField(max_length=120, blank=True, verbose_name="поисковое намерение")
    content_type = models.CharField(max_length=8, choices=ContentType.choices, default=ContentType.PIN, verbose_name="тип контента")
    priority = models.PositiveSmallIntegerField(default=2, verbose_name="приоритет")
    idea = models.CharField(max_length=300, verbose_name="идея")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED, verbose_name="статус")

    class Meta:
        ordering = ("plan", "position")
        verbose_name = "пункт контент-плана"
        verbose_name_plural = "пункты контент-плана"
        constraints = [models.UniqueConstraint(fields=["plan", "position"], name="unique_plan_item_position")]


class Pin(BaseModel):
    """Logical pin; text and check results live in immutable PinVersion rows."""

    class Status(models.TextChoices):
        IDEA = "IDEA", "Идея"
        GENERATING = "GENERATING", "Генерируется"
        VALIDATING = "VALIDATING", "Проверяется"
        WAITING_APPROVAL = "WAITING_APPROVAL", "Ждёт одобрения"
        APPROVED = "APPROVED", "Одобрен"
        QUEUED = "QUEUED", "В очереди"
        PUBLISHING = "PUBLISHING", "Отправляется"
        PUBLISHED = "PUBLISHED", "Опубликован"
        REJECTED = "REJECTED", "Отклонён"
        REWORK = "REWORK", "Требуется переделка"
        FAILED = "FAILED", "Ошибка"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="pins", verbose_name="бизнес")
    plan_item = models.OneToOneField(ContentPlanItem, on_delete=models.CASCADE, related_name="pin", verbose_name="пункт контент-плана")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IDEA, verbose_name="статус")
    current_version = models.ForeignKey(
        "PinVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="текущая версия",
    )
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name="дата архивации")

    class Meta:
        verbose_name = "пин"
        verbose_name_plural = "пины"


class PinVersion(BaseModel):
    class Verdict(models.TextChoices):
        PASS = "PASS", "Проверки пройдены"
        REVIEW = "REVIEW", "Нужна оценка человека"
        BLOCK = "BLOCK", "Заблокирован проверкой"

    pin = models.ForeignKey(Pin, on_delete=models.CASCADE, related_name="versions", verbose_name="пин")
    number = models.PositiveIntegerField(verbose_name="номер версии")
    title = models.CharField(max_length=300, verbose_name="заголовок")
    description = models.TextField(blank=True, verbose_name="описание")
    alt_text = models.CharField(max_length=500, blank=True, verbose_name="альтернативный текст")
    destination_url = models.URLField(max_length=500, blank=True, verbose_name="ссылка назначения")
    keyword = models.CharField(max_length=300, blank=True, verbose_name="ключевая фраза")
    board = models.CharField(max_length=300, blank=True, verbose_name="доска")
    checks = models.JSONField(default=list, blank=True, verbose_name="результаты проверок")
    verdict = models.CharField(max_length=8, choices=Verdict.choices, verbose_name="вердикт")
    open_checks = models.JSONField(default=list, blank=True, verbose_name="невыполненные проверки")
    generation = models.JSONField(default=dict, blank=True, verbose_name="происхождение текста")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="создатель")

    class Meta:
        ordering = ("pin", "number")
        verbose_name = "версия пина"
        verbose_name_plural = "версии пинов"
        constraints = [models.UniqueConstraint(fields=["pin", "number"], name="unique_pin_version_number")]


class Approval(BaseModel):
    """The user's own decision on one concrete PinVersion. Never created by the model or the chat."""

    class Decision(models.TextChoices):
        APPROVED = "APPROVED", "Одобрен"
        REJECTED = "REJECTED", "Отклонён"
        REWORK = "REWORK", "На переделку"

    pin_version = models.OneToOneField(PinVersion, on_delete=models.CASCADE, related_name="approval", verbose_name="версия пина")
    decision = models.CharField(max_length=10, choices=Decision.choices, verbose_name="решение")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="решил")
    decided_at = models.DateTimeField(verbose_name="дата решения")
    channel = models.CharField(max_length=16, default="WEB", verbose_name="канал")
    comment = models.CharField(max_length=300, blank=True, verbose_name="комментарий")
    acknowledged_checks = models.JSONField(default=list, blank=True, verbose_name="замечания, с которыми ознакомлен")

    class Meta:
        verbose_name = "решение по пину"
        verbose_name_plural = "решения по пинам"


class AIJob(BaseModel):
    """State of one long-running AI task; PostgreSQL is the source of truth (the broker only delivers)."""

    class Kind(models.TextChoices):
        PIN_GENERATION = "PIN_GENERATION", "Генерация пинов"

    class Status(models.TextChoices):
        PENDING = "PENDING", "В очереди"
        RUNNING = "RUNNING", "Выполняется"
        WAITING_INPUT = "WAITING_INPUT", "Ждёт ответа"
        COMPLETED = "COMPLETED", "Готово"
        FAILED = "FAILED", "Ошибка"
        CANCELLED = "CANCELLED", "Отменена"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="ai_jobs", verbose_name="бизнес")
    kind = models.CharField(max_length=24, choices=Kind.choices, verbose_name="тип")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, verbose_name="статус")
    params = models.JSONField(default=dict, blank=True, verbose_name="параметры")
    total = models.PositiveIntegerField(default=0, verbose_name="всего")
    done = models.PositiveIntegerField(default=0, verbose_name="готово")
    failed = models.PositiveIntegerField(default=0, verbose_name="с ошибкой")
    notes = models.JSONField(default=list, blank=True, verbose_name="сообщения")
    cancel_requested = models.BooleanField(default=False, verbose_name="запрошена отмена")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="создатель")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="начата")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="завершена")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "фоновая задача ИИ"
        verbose_name_plural = "фоновые задачи ИИ"


class GenerationPreset(BaseModel):
    """What the user chose last time on the pin generation page; the page starts from it."""

    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name="generation_preset", verbose_name="бизнес")
    values = models.JSONField(default=dict, blank=True, verbose_name="настройки")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+", verbose_name="изменил")

    class Meta:
        verbose_name = "настройки генерации пинов"
        verbose_name_plural = "настройки генерации пинов"
