import base64
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from .crypto import encrypt_token
from .crypto import decrypt_token
from .models import PinterestAccount

OAUTH_URL = "https://www.pinterest.com/oauth/"
TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
API_URL = "https://api.pinterest.com/v5"


class PinterestOAuthError(Exception):
    def __init__(self, message, *, permanent=False):
        super().__init__(message)
        self.permanent = permanent


def validate_oauth_settings():
    if not settings.PINTEREST_CLIENT_ID or not settings.PINTEREST_CLIENT_SECRET or not settings.PINTEREST_REDIRECT_URI:
        raise ImproperlyConfigured("Pinterest OAuth client credentials and redirect URI must be configured.")
    if not settings.PINTEREST_SCOPES:
        raise ImproperlyConfigured("At least one Pinterest OAuth scope must be configured.")
    if not settings.PINTEREST_TOKEN_ENCRYPTION_KEY:
        raise ImproperlyConfigured("PINTEREST_TOKEN_ENCRYPTION_KEY must be configured before connecting an account.")


def authorization_url(state):
    validate_oauth_settings()
    return f"{OAUTH_URL}?{urlencode({'client_id': settings.PINTEREST_CLIENT_ID, 'redirect_uri': settings.PINTEREST_REDIRECT_URI, 'response_type': 'code', 'scope': ','.join(settings.PINTEREST_SCOPES), 'state': state})}"


def _token_request(data):
    validate_oauth_settings()
    credentials = f"{settings.PINTEREST_CLIENT_ID}:{settings.PINTEREST_CLIENT_SECRET}".encode()
    headers = {
        "Authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    try:
        response = requests.post(TOKEN_URL, data=data, headers=headers, timeout=20)
    except requests.RequestException as error:
        raise PinterestOAuthError("Pinterest token endpoint is unavailable.") from error
    if response.status_code != 200:
        raise PinterestOAuthError(
            f"Pinterest token exchange failed (HTTP {response.status_code}).",
            permanent=response.status_code in {400, 401, 403},
        )
    return response.json()


def exchange_code(code):
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": settings.PINTEREST_REDIRECT_URI}
    if settings.PINTEREST_APP_CREATED_BEFORE_CONTINUOUS_REFRESH:
        data["continuous_refresh"] = "true"
    return _token_request(data)


def refresh_tokens(refresh_token):
    return _token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})


def fetch_profile(access_token):
    try:
        response = requests.get(
            f"{API_URL}/user_account",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
    except requests.RequestException as error:
        raise PinterestOAuthError("Pinterest profile endpoint is unavailable.") from error
    if response.status_code != 200:
        raise PinterestOAuthError(f"Pinterest profile request failed (HTTP {response.status_code}).")
    return response.json()


def connect_account(*, business, user, token_data, profile):
    pinterest_user_id = str(profile["id"])
    existing = PinterestAccount.objects.filter(
        pinterest_user_id=pinterest_user_id,
        deleted_at__isnull=True,
    ).first()
    if existing and existing.business_id != business.pk:
        raise PinterestOAuthError("Этот Pinterest аккаунт уже подключён к другому бизнесу.")

    now = timezone.now()
    refresh_expires_in = token_data.get("refresh_token_expires_in")
    defaults = {
        "connected_by": user,
        "username": profile.get("username", ""),
        "access_token_encrypted": encrypt_token(token_data["access_token"]),
        "refresh_token_encrypted": encrypt_token(token_data.get("refresh_token", "")) if token_data.get("refresh_token") else "",
        "access_token_expires_at": now + timedelta(seconds=int(token_data.get("expires_in", 0))),
        "refresh_token_expires_at": now + timedelta(seconds=int(refresh_expires_in)) if refresh_expires_in else None,
        "granted_scopes": token_data.get("scope", "").replace(",", " ").split(),
        "status": PinterestAccount.Status.CONNECTED,
        "last_auth_error": "",
        "deleted_at": None,
    }
    if existing:
        for field, value in {**defaults, "business": business}.items():
            setattr(existing, field, value)
        existing.save()
        account = existing
    else:
        account = PinterestAccount.objects.create(
            pinterest_user_id=pinterest_user_id,
            business=business,
            **defaults,
        )
    return account


def disconnect_account(account):
    """Soft-delete a Pinterest link and erase its OAuth credentials."""
    with transaction.atomic():
        locked = PinterestAccount.objects.select_for_update().get(pk=account.pk)
        if locked.deleted_at:
            return False
        locked.status = PinterestAccount.Status.DISCONNECTED
        locked.access_token_encrypted = ""
        locked.refresh_token_encrypted = ""
        locked.access_token_expires_at = timezone.now()
        locked.refresh_token_expires_at = None
        locked.granted_scopes = []
        locked.username = ""
        locked.last_auth_error = ""
        locked.deleted_at = timezone.now()
        locked.save()
    return True


def refresh_account_token(account):
    if not account.refresh_token_encrypted:
        account.status = PinterestAccount.Status.REAUTH_REQUIRED
        account.last_auth_error = "refresh_token_missing"
        account.save(update_fields=["status", "last_auth_error", "updated_at"])
        return False
    with transaction.atomic():
        locked = PinterestAccount.objects.select_for_update().get(pk=account.pk)
        old_access_token = account.access_token_encrypted
        if locked.access_token_encrypted != old_access_token and locked.status == PinterestAccount.Status.CONNECTED:
            account.refresh_from_db()
            return True
        locked.last_refresh_attempt_at = timezone.now()
        locked.save(update_fields=["last_refresh_attempt_at", "updated_at"])
        try:
            token_data = refresh_tokens(decrypt_token(locked.refresh_token_encrypted))
        except PinterestOAuthError as error:
            locked.last_auth_error = str(error)
            if error.permanent:
                locked.status = PinterestAccount.Status.REAUTH_REQUIRED
            locked.save(update_fields=["status", "last_auth_error", "updated_at"])
            return False
        now = timezone.now()
        locked.access_token_encrypted = encrypt_token(token_data["access_token"])
        if token_data.get("refresh_token"):
            locked.refresh_token_encrypted = encrypt_token(token_data["refresh_token"])
        locked.access_token_expires_at = now + timedelta(seconds=int(token_data.get("expires_in", 0)))
        if token_data.get("refresh_token_expires_in"):
            locked.refresh_token_expires_at = now + timedelta(seconds=int(token_data["refresh_token_expires_in"]))
        locked.granted_scopes = token_data.get("scope", "").replace(",", " ").split() or locked.granted_scopes
        locked.status = PinterestAccount.Status.CONNECTED
        locked.last_auth_error = ""
        locked.save()
    account.refresh_from_db()
    return True
