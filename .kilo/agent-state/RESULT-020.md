# RESULT-020

Исполнитель: opencode-cli; модель: `openrouter/qwen/qwen3.8-27b:free`.
Сессия: ses_efc0513d7ffeNeBmxSscjM4g5D.
Статус: ожидает приёмки Codex.

Прочитаны `apps/pinterest/services.py` и `apps/pinterest/tests.py`. Отчёт по TASK020:

## Итог: 3 тест-метода для `PinterestOAuthFlowTest` (apps/pinterest/tests.py)

**Импорт, добавить в блок импортов (отдельно):**
```python
from .services import PinterestOAuthError, refresh_account_token
```
Все остальные импорты (`timedelta`, `patch`, `timezone`, `encrypt_token`, `decrypt_token`, `PinterestAccount`) уже есть в tests.py.

**Метод 1 — успешный refresh:**
```python
    def test_refresh_success_replaces_encrypted_credentials(self):
        account = PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.owner,
            pinterest_user_id="pin-user-refresh-ok",
            username="pin_user",
            status=PinterestAccount.Status.CONNECTED,
            access_token_encrypted=encrypt_token("old-plain-access-token"),
            refresh_token_encrypted=encrypt_token("old-plain-refresh-token"),
            access_token_expires_at=timezone.now() - timedelta(hours=1),
            granted_scopes=["user_accounts:read"],
        )
        before = timezone.now()
        token_data = {
            "access_token": "new-plain-access-token",
            "refresh_token": "new-plain-refresh-token",
            "expires_in": 3600,
            "refresh_token_expires_in": 60 * 86400,
            "scope": "user_accounts:read,pins:read",
        }
        with patch("apps.pinterest.services.refresh_tokens", return_value=token_data) as refresh:
            self.assertTrue(refresh_account_token(account))

        refresh.assert_called_once_with("old-plain-refresh-token")
        account.refresh_from_db()
        self.assertEqual(decrypt_token(account.access_token_encrypted), "new-plain-access-token")
        self.assertEqual(decrypt_token(account.refresh_token_encrypted), "new-plain-refresh-token")
        self.assertNotEqual(account.access_token_encrypted, "new-plain-access-token")
        self.assertGreater(account.access_token_expires_at, before + timedelta(seconds=3595))
        self.assertLessEqual(account.access_token_expires_at, before + timedelta(seconds=3605))
        self.assertIsNotNone(account.refresh_token_expires_at)
        self.assertEqual(account.granted_scopes, ["user_accounts:read", "pins:read"])
        self.assertEqual(account.status, PinterestAccount.Status.CONNECTED)
        self.assertEqual(account.last_auth_error, "")
```

**Метод 2 — временная ошибка:**
```python
    def test_refresh_transient_error_keeps_credentials_connected(self):
        account = PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.owner,
            pinterest_user_id="pin-user-refresh-transient",
            username="pin_user",
            status=PinterestAccount.Status.CONNECTED,
            access_token_encrypted=encrypt_token("old-plain-access-token"),
            refresh_token_encrypted=encrypt_token("old-plain-refresh-token"),
            access_token_expires_at=timezone.now() - timedelta(hours=1),
            granted_scopes=["user_accounts:read"],
        )
        old_access = account.access_token_encrypted
        old_refresh = account.refresh_token_encrypted
        with patch(
            "apps.pinterest.services.refresh_tokens",
            side_effect=PinterestOAuthError("Pinterest token endpoint is unavailable."),
        ) as refresh:
            self.assertFalse(refresh_account_token(account))

        refresh.assert_called_once()
        account.refresh_from_db()
        self.assertEqual(account.status, PinterestAccount.Status.CONNECTED)
        self.assertEqual(account.last_auth_error, "Pinterest token endpoint is unavailable.")
        self.assertEqual(account.access_token_encrypted, old_access)
        self.assertEqual(account.refresh_token_encrypted, old_refresh)
```

**Метод 3 — постоянная ошибка:**
```python
    def test_refresh_permanent_error_requires_reconnect(self):
        account = PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.owner,
            pinterest_user_id="pin-user-refresh-permanent",
            username="pin_user",
            status=PinterestAccount.Status.CONNECTED,
            access_token_encrypted=encrypt_token("old-plain-access-token"),
            refresh_token_encrypted=encrypt_token("old-plain-refresh-token"),
            access_token_expires_at=timezone.now() - timedelta(hours=1),
            granted_scopes=["user_accounts:read"],
        )
        with patch(
            "apps.pinterest.services.refresh_tokens",
            side_effect=PinterestOAuthError("Pinterest token exchange failed (HTTP 401).", permanent=True),
        ):
            self.assertFalse(refresh_account_token(account))

        account.refresh_from_db()
        self.assertEqual(account.status, PinterestAccount.Status.REAUTH_REQUIRED)
        self.assertEqual(account.last_auth_error, "Pinterest token exchange failed (HTTP 401).")
```

### Обоснование
- Целевая точка мокирования — `apps.pinterest.services.refresh_tokens`: именно модульный вызов из `refresh_account_token` (services.py:156), ни HTTP, ни `requests` не затрагиваются.
- Метод 1 проверяет: `refresh.assert_called_once_with("old-plain-refresh-token")` — сервис передаёт **расшифрованный** старый refresh (services.py:156 `decrypt_token(locked.refresh_token_encrypted)`); замена access/refresh в зашифрованном виде (services.py:164–166), пересчёт `access_token_expires_at` (services.py:167) и `refresh_token_expires_at` (services.py:168–169), конвертация скоп `,` → пробелы (services.py:170), сохранение CONNECTED и сброс `last_auth_error` (services.py:171–172). Окно `3595..3605` сек — допустимая погрешность времени между `timezone.now()` в тесте и в сервисе.
- Метод 2: `permanent=False` (по умолчанию) → сервис только пишет `last_auth_error` и сохраняет status (services.py:157–162) — шифры и CONNECTED не меняются.
- Метод 3: `permanent=True` → статус REAUTH_REQUIRED (services.py:159–160).
- Accounts synthetic (отдельные `pinterest_user_id`), `status` выставлен явно, секретов и реальных токенов нет. Объём с импортом ≈ 84 строки (< 110).
- Запускал тесты я не запускал; проверки и запуск остаются за Codex.
