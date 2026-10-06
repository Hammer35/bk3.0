"""Background pin generation: validation of a run, the job state machine and the worker loop.

The job row is the source of truth (status, progress, notes); Celery only delivers it to a worker.
Everything shown to the user in `notes` is a fixed safe sentence: no exception text, no model output.
"""
import logging

from django.db import transaction
from django.utils import timezone

from apps.pinterest.models import PinterestAccount

from . import pin_settings as ps
from .models import AIJob, ContentPlanItem, Pin
from .pin_generation import PinError, confirmed_plan, generate_pin, pending_items
from .providers import GigaChatConfigurationError, GigaChatProviderError

logger = logging.getLogger(__name__)
ACTIVE = (AIJob.Status.PENDING, AIJob.Status.RUNNING)
MAX_NOTES = 20


class JobError(Exception):
    """Safe-to-show reason a run could not be started."""


def active_job(business):
    return business.ai_jobs.filter(kind=AIJob.Kind.PIN_GENERATION, status__in=ACTIVE).first()


@transaction.atomic
def start_job(business, user, item_ids, options) -> AIJob:
    options = ps.normalize(options)
    plan = confirmed_plan(business)
    if plan is None:
        raise JobError("Нет подтверждённого контент-плана.")
    available = {item.pk: item for item in pending_items(plan)}
    chosen = [available[i] for i in dict.fromkeys(item_ids) if i in available]
    if not chosen:
        raise JobError("Выберите хотя бы один пункт плана, для которого ещё нет пина.")
    if len(chosen) > ps.MAX_ITEMS:
        raise JobError(f"За один запуск можно подготовить не больше {ps.MAX_ITEMS} пинов.")
    if options["account_id"] is not None and not PinterestAccount.objects.filter(
            pk=options["account_id"], business=business, deleted_at__isnull=True,
            status=PinterestAccount.Status.CONNECTED).exists():
        raise JobError("Выбранный аккаунт Pinterest не подключён к этому бизнесу.")
    if active_job(business):
        raise JobError("Генерация уже идёт. Дождитесь её завершения или отмените её.")
    stored = {k: v for k, v in options.items() if k != "product_facts"}
    return AIJob.objects.create(
        business=business, kind=AIJob.Kind.PIN_GENERATION, created_by=user, total=len(chosen),
        params={"item_ids": [i.pk for i in chosen], "options": stored})


def request_cancel(job: AIJob) -> None:
    if job.status in ACTIVE and not job.cancel_requested:
        job.cancel_requested = True
        job.save(update_fields=["cancel_requested", "updated_at"])
        if job.status == AIJob.Status.PENDING:  # not picked up yet: close it right away
            AIJob.objects.filter(pk=job.pk, status=AIJob.Status.PENDING).update(
                status=AIJob.Status.CANCELLED, finished_at=timezone.now())


def _note(job: AIJob, text: str) -> None:
    job.notes = [*job.notes, text][-MAX_NOTES:]


def _product_facts(url: str) -> tuple[str, str]:
    """Facts text from a Wildberries card (lightweight read, no photos) and a safe note if it failed."""
    from .wb_products import ProductReadError, _read_card, product_link
    link = product_link(url)
    if not link:
        return "", "Ссылка на карточку товара не распознана: соответствие товару не проверено."
    article, _ = link
    try:
        _, card = _read_card(article)
    except (ProductReadError, OSError, ValueError):
        return "", "Карточку товара прочитать не удалось: соответствие товару не проверено."
    parts = [str(card.get("imt_name") or card.get("title") or ""), str(card.get("description") or "")]
    parts += [f"{o.get('name')}: {o.get('value')}" for o in (card.get("options") or []) if isinstance(o, dict)]
    return " ".join(p for p in parts if p)[:3000], ""


def run_job(job_id: int, *, provider=None) -> AIJob | None:
    with transaction.atomic():
        job = AIJob.objects.select_for_update().filter(pk=job_id).first()
        if job is None or job.status != AIJob.Status.PENDING:
            return job  # already running, finished or cancelled: delivery is at-least-once, work is not
        job.status, job.started_at = AIJob.Status.RUNNING, timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])
    options = ps.normalize(job.params.get("options"))
    if options["product_url"]:
        options["product_facts"], warning = _product_facts(options["product_url"])
        if warning:
            _note(job, warning)
    plan = confirmed_plan(job.business)
    items = {i.pk: i for i in plan.items.filter(pk__in=job.params.get("item_ids", []))} if plan else {}
    aborted = False
    for item_id in job.params.get("item_ids", []):
        job.refresh_from_db(fields=["cancel_requested"])
        if job.cancel_requested or aborted:
            break
        item = items.get(item_id)
        if item is None or (hasattr(item, "pin") and item.pin.status != Pin.Status.REWORK):
            job.failed += 1
            _note(job, "Пункт плана изменился: он пропущен.")
        else:
            try:
                generate_pin(job.business, job.created_by, plan, item, provider=provider, options=options)
                job.done += 1
            except PinError:
                job.failed += 1
                _note(job, f"Не получилось собрать надёжный текст для пункта «{item.idea[:60]}».")
            except (GigaChatProviderError, GigaChatConfigurationError):
                job.failed += 1
                aborted = True
                _note(job, "Модель сейчас недоступна: оставшиеся пункты не обработаны. Повторите запуск позже.")
            except Exception as error:  # noqa: BLE001 - one bad item must not kill the run
                logger.warning("Pin generation failed for item %s: %s", item_id, type(error).__name__)
                job.failed += 1
                _note(job, f"Не удалось подготовить пункт «{item.idea[:60]}».")
        job.save(update_fields=["done", "failed", "notes", "updated_at"])
    job.refresh_from_db(fields=["cancel_requested"])
    job.status = (AIJob.Status.CANCELLED if job.cancel_requested
                  else AIJob.Status.FAILED if job.done == 0 and job.failed > 0 else AIJob.Status.COMPLETED)
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "finished_at", "updated_at"])
    return job


STATUS_LABELS = {"PENDING": "В очереди", "RUNNING": "Выполняется", "WAITING_INPUT": "Ждёт ответа",
                 "COMPLETED": "Готово", "FAILED": "Ошибка", "CANCELLED": "Отменена"}


def summary(job: AIJob) -> dict:
    return {"id": job.pk, "status": job.status, "total": job.total, "done": job.done, "failed": job.failed,
            "finished": job.status not in ACTIVE, "notes": job.notes, "cancel_requested": job.cancel_requested}
