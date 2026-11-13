"""Refresh boundary checks using synthetic credentials and mocked transport."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.workspaces.models import Membership, Workspace
from apps.strategist.models import AIConversation
from django.contrib.auth import get_user_model

from .crypto import encrypt_token
from .models import PinterestAccount
from .services import disconnect_account, refresh_account_token, _token_request, PinterestOAuthError


@override_settings(PINTEREST_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
    PINTEREST_CLIENT_ID="synthetic", PINTEREST_CLIENT_SECRET="synthetic", PINTEREST_REDIRECT_URI="http://localhost/callback/",
    PINTEREST_SCOPES=("user_accounts:read",))
class RefreshBoundaryTest(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("refresh-owner")
        workspace = Workspace.objects.create(name="Refresh", slug="refresh", created_by=user)
        Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
        self.client.force_login(user)
        business = Business.objects.create(workspace=workspace, name="Shop", slug="shop")
        self.account = PinterestAccount.objects.create(business=business, connected_by=user,
            pinterest_user_id="synthetic-refresh", username="synthetic",
            access_token_encrypted=encrypt_token("old-access"), refresh_token_encrypted=encrypt_token("old-refresh"),
            access_token_expires_at=timezone.now()+timedelta(days=1), granted_scopes=["user_accounts:read"])

    def test_stale_instance_cannot_refresh_disconnected_account(self):
        stale = PinterestAccount.objects.get(pk=self.account.pk)
        disconnect_account(self.account)
        with patch("apps.pinterest.services.refresh_tokens", return_value={"access_token": "new-access", "expires_in": 3600}) as refresh:
            self.assertFalse(refresh_account_token(stale))
        refresh.assert_not_called()
        stale.refresh_from_db()
        self.assertEqual(stale.status, PinterestAccount.Status.DISCONNECTED)
        self.assertEqual(stale.access_token_encrypted, "")

    def test_stale_missing_refresh_does_not_mark_connected_account_for_reauth(self):
        self.account.refresh_token_encrypted = ""
        with patch("apps.pinterest.services.refresh_tokens", return_value={"access_token": "new-access", "expires_in": 3600}) as refresh:
            self.assertTrue(refresh_account_token(self.account))
        refresh.assert_called_once_with("old-refresh")
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, PinterestAccount.Status.CONNECTED)

    def test_invalid_token_json_raises_safe_oauth_error(self):
        def broken_json():
            raise ValueError("private-upstream")
        with patch("apps.pinterest.services.requests.post", return_value=SimpleNamespace(status_code=200,json=broken_json)):
            with self.assertRaises(PinterestOAuthError) as caught:
                _token_request({"grant_type": "refresh_token"})
        self.assertNotIn("private-upstream", str(caught.exception))

    def test_malformed_refresh_does_not_overwrite_credentials(self):
        for data in (None, [], {}, {"access_token": "", "expires_in": 3600}, {"access_token": "new", "expires_in": "bad"}):
            with self.subTest(data=data):
                before = self.account.access_token_encrypted
                with patch("apps.pinterest.services.refresh_tokens", return_value=data):
                    self.assertFalse(refresh_account_token(self.account))
                self.account.refresh_from_db()
                self.assertEqual(self.account.access_token_encrypted, before)
                self.assertEqual(self.account.status, PinterestAccount.Status.CONNECTED)

    def test_invalid_saved_ciphertext_does_not_call_provider(self):
        self.account.refresh_token_encrypted = "invalid-ciphertext"
        self.account.save(update_fields=["refresh_token_encrypted"])
        with patch("apps.pinterest.services.refresh_tokens") as refresh:
            self.assertFalse(refresh_account_token(self.account))
        refresh.assert_not_called()
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, PinterestAccount.Status.CONNECTED)

    def test_already_rotated_token_uses_locked_state_without_new_request(self):
        stale = PinterestAccount.objects.get(pk=self.account.pk)
        self.account.access_token_encrypted = encrypt_token("rotated-access")
        self.account.save(update_fields=["access_token_encrypted"])
        with patch("apps.pinterest.services.refresh_tokens") as refresh:
            self.assertTrue(refresh_account_token(stale))
        refresh.assert_not_called()
        self.assertEqual(stale.access_token_encrypted, self.account.access_token_encrypted)

    def test_expired_token_refresh_reaches_chat_counter(self):
        self.account.access_token_expires_at = timezone.now()-timedelta(hours=1)
        self.account.save(update_fields=["access_token_expires_at"])
        c = AIConversation.objects.create(business=self.account.business, created_by=self.account.connected_by)
        url = reverse("strategist:session", kwargs={"workspace_slug": self.account.business.workspace.slug,
            "business_slug": self.account.business.slug, "session_slug": c.slug})
        with patch("apps.pinterest.services.refresh_tokens", return_value={"access_token": "new-access", "expires_in": 3600}) as refresh, \
             patch("apps.pinterest.strategist_tools._get", return_value=SimpleNamespace(status_code=200, json=lambda: {"follower_count": 12})) as get, \
             patch("apps.strategist.services.GigaChatProvider.complete", side_effect=AssertionError("No LLM expected")):
            response = self.client.post(url, {"message": "Сколько подписчиков у @synthetic?"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertIn("подписчиков: 12", response.json()["messages_html"])
        refresh.assert_called_once_with("old-refresh")
        get.assert_called_once()
        self.assertEqual(get.call_args.args[2], "new-access")

    def test_permanent_refresh_error_is_safe_chat_reconnect(self):
        self.account.access_token_expires_at = timezone.now()-timedelta(hours=1)
        self.account.save(update_fields=["access_token_expires_at"])
        c = AIConversation.objects.create(business=self.account.business, created_by=self.account.connected_by)
        url = reverse("strategist:session", kwargs={"workspace_slug": self.account.business.workspace.slug,
            "business_slug": self.account.business.slug, "session_slug": c.slug})
        with patch("apps.pinterest.services.refresh_tokens", side_effect=PinterestOAuthError("HTTP401", permanent=True)), \
             patch("apps.pinterest.strategist_tools._get") as get:
            response = self.client.post(url, {"message": "Сколько подписчиков у @synthetic?"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Переподключи", response.json()["messages_html"])
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, PinterestAccount.Status.REAUTH_REQUIRED)
        get.assert_not_called()
