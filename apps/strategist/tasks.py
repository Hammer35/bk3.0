from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from .models import AIJob
from .pin_jobs import run_job


@shared_task(name="strategist.run_pin_generation")
def run_pin_generation(job_id: int) -> None:
    try:
        run_job(job_id)
    except SoftTimeLimitExceeded:
        AIJob.objects.filter(pk=job_id, status=AIJob.Status.RUNNING).update(
            status=AIJob.Status.FAILED, notes=["Время выполнения вышло: часть пунктов не обработана. Повторите запуск."])
