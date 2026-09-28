from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import PinterestAccount
from .services import refresh_account_token


@shared_task
def refresh_pinterest_tokens():
    cutoff = timezone.now() + timedelta(days=7)
    accounts = PinterestAccount.objects.filter(
        status=PinterestAccount.Status.CONNECTED,
        deleted_at__isnull=True,
        access_token_expires_at__lte=cutoff,
    )
    results = {"checked": accounts.count(), "refreshed": 0, "failed": 0}
    for account in accounts.iterator():
        if refresh_account_token(account):
            results["refreshed"] += 1
        else:
            results["failed"] += 1
    return results
