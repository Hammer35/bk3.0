from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.workspaces.models import Membership, Workspace

from .crypto import decrypt_token, encrypt_token
from .models import PinterestAccount
from .strategist_tools import PinterestReadError, _request


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    PINTEREST_CLIENT_ID="test-client",
    PINTEREST_CLIENT_SECRET="test-secret",
    PINTEREST_REDIRECT_URI="http://localhost:8000/pinterest/callback/",
    PINTEREST_SCOPES=("user_accounts:read", "boards:read", "boards:write", "pins:read", "pins:write"),
    PINTEREST_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode("ascii"),
)
class PinterestOAuthFlowTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user("pinterest-owner", password="test-password")
        self.viewer = user_model.objects.create_user("pinterest-viewer", password="test-password")
        self.workspace = Workspace.objects.create(name="Test", slug="pinterest-test", created_by=self.owner)
        Membership.objects.create(workspace=self.workspace, user=self.owner, role=Membership.Role.OWNER)
        Membership.objects.create(workspace=self.workspace, user=self.viewer, role=Membership.Role.VIEWER)
        self.business = Business.objects.create(
            workspace=self.workspace,
            name="Test business",
            slug="test-business",
        )

    def test_connect_redirect_uses_registered_callback_and_random_state(self):
        self.client.force_login(self.owner)

        response = self.client.post(reverse("pinterest:connect", args=[self.business.public_id]))

        self.assertEqual(response.status_code, 302)
        authorization = urlparse(response["Location"])
        params = parse_qs(authorization.query)
        self.assertEqual(f"{authorization.scheme}://{authorization.netloc}{authorization.path}", "https://www.pinterest.com/oauth/")
        self.assertEqual(params["redirect_uri"], ["http://localhost:8000/pinterest/callback/"])
        self.assertEqual(len(params["state"][0]), 43)
        self.assertTrue(cache.get(f"pinterest-oauth:{params['state'][0]}"))

    def test_viewer_cannot_start_oauth(self):
        self.client.force_login(self.viewer)

        response = self.client.post(reverse("pinterest:connect", args=[self.business.public_id]))

        self.assertEqual(response.status_code, 404)

    def test_callback_is_one_time_and_saves_encrypted_tokens(self):
        self.client.force_login(self.owner)
        state = "one-time-test-state"
        cache.set(
            f"pinterest-oauth:{state}",
            {
                "user_id": self.owner.pk,
                "business_id": str(self.business.public_id),
                "created_at": timezone.now().isoformat(),
            },
            timeout=600,
        )
        token_data = {
            "access_token": "plain-access-token",
            "refresh_token": "plain-refresh-token",
            "expires_in": 3600,
            "refresh_token_expires_in": 60 * 86400,
            "scope": "user_accounts:read boards:read pins:read",
        }
        with (
            patch("apps.pinterest.views.exchange_code", return_value=token_data),
            patch("apps.pinterest.views.fetch_profile", return_value={"id": "pin-user-123", "username": "pin_user"}),
        ):
            response = self.client.get(reverse("pinterest:callback"), {"state": state, "code": "one-time-code"})

        self.assertRedirects(response, reverse("core:home"))
        account = PinterestAccount.objects.get(pinterest_user_id="pin-user-123")
        self.assertEqual(decrypt_token(account.access_token_encrypted), "plain-access-token")
        self.assertEqual(decrypt_token(account.refresh_token_encrypted), "plain-refresh-token")
        self.assertNotEqual(account.access_token_encrypted, "plain-access-token")
        self.assertEqual(account.business, self.business)
        self.assertEqual(account.status, PinterestAccount.Status.CONNECTED)
        self.assertIsNone(cache.get(f"pinterest-oauth:{state}"))

    def test_callback_rejects_expired_state(self):
        self.client.force_login(self.owner)
        state = "expired-state"
        cache.set(
            f"pinterest-oauth:{state}",
            {
                "user_id": self.owner.pk,
                "business_id": str(self.business.public_id),
                "created_at": (timezone.now() - timedelta(minutes=11)).isoformat(),
            },
            timeout=600,
        )

        response = self.client.get(reverse("pinterest:callback"), {"state": state, "code": "code"})

        self.assertRedirects(response, reverse("core:home"))
        self.assertFalse(PinterestAccount.objects.exists())

    def test_token_ciphertext_fails_closed_after_key_rotation(self):
        ciphertext = encrypt_token("secret-token")
        with override_settings(PINTEREST_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode("ascii")):
            with self.assertRaises(ValueError):
                decrypt_token(ciphertext)

    def test_persistent_401_marks_account_for_reconnect(self):
        account = PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.owner,
            pinterest_user_id="pin-user-401",
            username="pin_user",
            access_token_encrypted=encrypt_token("test-access-token"),
            access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"],
        )
        with (
            patch("apps.pinterest.strategist_tools.refresh_account_token", return_value=True) as refresh,
            patch("apps.pinterest.strategist_tools._get", side_effect=[
                SimpleNamespace(status_code=401),
                SimpleNamespace(status_code=401),
                SimpleNamespace(status_code=401),
            ]) as get,
        ):
            with self.assertRaisesRegex(PinterestReadError, "Переподключи"):
                _request(account, "/user_account/analytics", {})

        refresh.assert_called_once()
        self.assertEqual(get.call_count, 3)
        account.refresh_from_db()
        self.assertEqual(account.status, PinterestAccount.Status.REAUTH_REQUIRED)
        self.assertEqual(account.last_auth_error, "api_http_401_after_refresh")

    def test_resource_401_keeps_valid_profile_connected(self):
        account = PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.owner,
            pinterest_user_id="pin-user-resource-401",
            username="pin_user",
            access_token_encrypted=encrypt_token("test-access-token"),
            access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"],
        )
        with (
            patch("apps.pinterest.strategist_tools.refresh_account_token", return_value=True),
            patch("apps.pinterest.strategist_tools._get", side_effect=[
                SimpleNamespace(status_code=401),
                SimpleNamespace(status_code=401),
                SimpleNamespace(status_code=200),
            ]),
        ):
            with self.assertRaisesRegex(PinterestReadError, "Доступ к профилю работает"):
                _request(account, "/user_account/analytics", {})

        account.refresh_from_db()
        self.assertEqual(account.status, PinterestAccount.Status.CONNECTED)

    def test_resource_403_keeps_account_connected(self):
        account = PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.owner,
            pinterest_user_id="pin-user-403",
            username="pin_user",
            access_token_encrypted=encrypt_token("test-access-token"),
            access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"],
        )
        with (
            patch("apps.pinterest.strategist_tools.refresh_account_token") as refresh,
            patch("apps.pinterest.strategist_tools._get", return_value=SimpleNamespace(status_code=403)) as get,
        ):
            with self.assertRaisesRegex(PinterestReadError, "HTTP 403"):
                _request(account, "/user_account/analytics", {})

        refresh.assert_not_called()
        self.assertEqual(get.call_count, 1)
        account.refresh_from_db()
        self.assertEqual(account.status, PinterestAccount.Status.CONNECTED)

    def test_resource_401_with_unconfirmed_profile_keeps_account_connected(self):
        account = PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.owner,
            pinterest_user_id="pin-user-401-profile-503",
            username="pin_user",
            access_token_encrypted=encrypt_token("test-access-token"),
            access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"],
        )
        with (
            patch("apps.pinterest.strategist_tools.refresh_account_token", return_value=True),
            patch("apps.pinterest.strategist_tools._get", side_effect=[
                SimpleNamespace(status_code=401),
                SimpleNamespace(status_code=401),
                SimpleNamespace(status_code=503),
            ]) as get,
        ):
            with self.assertRaisesRegex(PinterestReadError, "не подтверждено"):
                _request(account, "/user_account/analytics", {})

        self.assertEqual(get.call_count, 3)
        account.refresh_from_db()
        self.assertEqual(account.status, PinterestAccount.Status.CONNECTED)
