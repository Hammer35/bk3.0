import secrets
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core import signing
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.businesses.models import Business
from apps.workspaces.permissions import can_manage_businesses

from .models import PinterestAccount
from .services import PinterestOAuthError, authorization_url, connect_account, disconnect_account, exchange_code, fetch_profile

STATE_TTL_SECONDS = 600
DISCONNECT_CONFIRMATION_SALT = "pinterest.disconnect-confirmation"


@login_required
@require_POST
def connect(request, business_id):
    business = get_object_or_404(Business, public_id=business_id, status=Business.Status.ACTIVE)
    if not can_manage_businesses(user=request.user, workspace=business.workspace):
        raise Http404
    state = secrets.token_urlsafe(32)
    cache.set(
        f"pinterest-oauth:{state}",
        {"user_id": request.user.pk, "business_id": str(business.public_id), "created_at": timezone.now().isoformat()},
        timeout=STATE_TTL_SECONDS,
    )
    try:
        return redirect(authorization_url(state))
    except ImproperlyConfigured:
        cache.delete(f"pinterest-oauth:{state}")
        messages.error(request, "Подключение Pinterest пока не настроено администратором.")
        return redirect("core:home")
    except Exception:
        cache.delete(f"pinterest-oauth:{state}")
        raise


@login_required
@require_POST
def reconnect(request, account_id):
    account = get_object_or_404(
        PinterestAccount.objects.select_related("business__workspace"),
        public_id=account_id,
        deleted_at__isnull=True,
        business__status=Business.Status.ACTIVE,
    )
    if not can_manage_businesses(user=request.user, workspace=account.business.workspace):
        raise Http404
    state = secrets.token_urlsafe(32)
    cache.set(
        f"pinterest-oauth:{state}",
        {
            "user_id": request.user.pk,
            "business_id": str(account.business.public_id),
            "pinterest_user_id": account.pinterest_user_id,
            "created_at": timezone.now().isoformat(),
        },
        timeout=STATE_TTL_SECONDS,
    )
    try:
        return redirect(authorization_url(state))
    except ImproperlyConfigured:
        cache.delete(f"pinterest-oauth:{state}")
        messages.error(request, "Подключение Pinterest пока не настроено администратором.")
        return redirect("core:home")
    except Exception:
        cache.delete(f"pinterest-oauth:{state}")
        raise


@login_required
@require_http_methods(["GET", "POST"])
def disconnect(request, account_id):
    account = get_object_or_404(
        PinterestAccount.objects.select_related("business__workspace"),
        public_id=account_id,
        deleted_at__isnull=True,
        business__status=Business.Status.ACTIVE,
    )
    if not can_manage_businesses(user=request.user, workspace=account.business.workspace):
        raise Http404

    if request.method == "GET":
        confirmation_token = signing.dumps(
            {"account_id": str(account.public_id), "user_id": request.user.pk},
            salt=DISCONNECT_CONFIRMATION_SALT,
        )
        return render(
            request,
            "pinterest/confirm_disconnect.html",
            {"account": account, "confirmation_token": confirmation_token},
        )

    try:
        confirmation = signing.loads(
            request.POST.get("confirmation_token", ""),
            salt=DISCONNECT_CONFIRMATION_SALT,
            max_age=600,
        )
    except signing.BadSignature:
        return HttpResponseBadRequest("Требуется подтверждение отключения Pinterest.")
    if confirmation != {"account_id": str(account.public_id), "user_id": request.user.pk}:
        return HttpResponseBadRequest("Подтверждение отключения Pinterest недействительно.")

    disconnect_account(account)
    messages.success(request, "Pinterest аккаунт отключён. OAuth-токены удалены.")
    return redirect("core:home")


@login_required
@require_GET
def callback(request):
    state = request.GET.get("state", "")
    state_key = f"pinterest-oauth:{state}"
    lock_key = f"{state_key}:callback-lock"
    locked = bool(state and cache.add(lock_key, "1", timeout=60))
    state_data = cache.get(state_key) if locked else None
    if not state_data or state_data["user_id"] != request.user.pk:
        if locked:
            cache.delete(lock_key)
        raise Http404
    cache.delete(state_key)

    business = get_object_or_404(
        Business,
        public_id=state_data["business_id"],
        status=Business.Status.ACTIVE,
    )
    if not can_manage_businesses(user=request.user, workspace=business.workspace):
        raise Http404
    if timezone.now() - datetime.fromisoformat(state_data["created_at"]) > timedelta(seconds=STATE_TTL_SECONDS):
        cache.delete(lock_key)
        messages.error(request, "Срок подключения Pinterest истёк. Попробуйте ещё раз.")
        return redirect("core:home")
    if request.GET.get("error"):
        cache.delete(lock_key)
        messages.error(request, "Pinterest отменил или отклонил авторизацию.")
        return redirect("core:home")
    code = request.GET.get("code", "")
    if not code:
        cache.delete(lock_key)
        messages.error(request, "Pinterest не вернул код авторизации.")
        return redirect("core:home")

    try:
        token_data = exchange_code(code)
        profile = fetch_profile(token_data["access_token"])
        if state_data.get("pinterest_user_id") and str(profile.get("id")) != state_data["pinterest_user_id"]:
            raise PinterestOAuthError("Pinterest account changed during reconnect.")
        account = connect_account(business=business, user=request.user, token_data=token_data, profile=profile)
    except (PinterestOAuthError, KeyError, ValueError):
        cache.delete(lock_key)
        messages.error(request, "Не удалось подключить Pinterest. Проверьте настройки и попробуйте снова.")
        return redirect("core:home")

    cache.delete(lock_key)
    messages.success(request, f"Pinterest аккаунт @{account.username or account.pinterest_user_id} подключён.")
    return redirect("core:home")
