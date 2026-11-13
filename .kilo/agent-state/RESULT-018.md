# RESULT-018

Исполнитель: opencode-cli; модель: `openrouter/qwen/qwen3.8-27b:free`.
Сессия: ses_efe2591d1ffesLH6Wvln1N81Vi.
Статус: ожидает приёмки Codex.

Прочитал `apps/pinterest/tests.py` (217 строк) и `apps/pinterest/strategist_tools.py` (369 строк). Проверяю факты:

- `_request` (стр. 312–357): refresh вызывается только при истёкшем токене (`expires_at <= now + 60s`) и при 401. При 429/200 refresh не трогается; при `!=200` поднимается `PinterestReadError(f"Pinterest API вернул HTTP {status_code} для чтения данных.")` (стр. 352–353); при `ValueError` из `response.json()` — `PinterestReadError("Pinterest API вернул некорректный JSON.")` (стр. 354–357), `from error` не попадает в `str()`.
- Соседние тесты (стр. 148–217) задают синтетический аккаунт с `access_token_expires_at=timezone.now() + timedelta(days=1)` — refresh при старте не срабатывает, патчуются `apps.pinterest.strategist_tools._get` и `...refresh_account_token`.

Ниже — ровно два метода, без импортов и setup, 48 строк, вставляются в конец класса `PinterestOAuthFlowTest` (после `test_resource_401_with_unconfirmed_profile_keeps_account_connected`, tests.py:217):

```python
    def test_resource_429_reports_status_and_keeps_account_connected(self):
        account = PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.owner,
            pinterest_user_id="pin-user-429",
            username="pin_user",
            access_token_encrypted=encrypt_token("test-access-token"),
            access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"],
        )
        with (
            patch("apps.pinterest.strategist_tools.refresh_account_token") as refresh,
            patch("apps.pinterest.strategist_tools._get", return_value=SimpleNamespace(status_code=429)) as get,
        ):
            with self.assertRaisesRegex(PinterestReadError, "HTTP 429"):
                _request(account, "/user_account/analytics", {})

        refresh.assert_not_called()
        self.assertEqual(get.call_count, 1)
        account.refresh_from_db()
        self.assertEqual(account.status, PinterestAccount.Status.CONNECTED)

    def test_invalid_json_error_does_not_leak_upstream_details(self):
        account = PinterestAccount.objects.create(
            business=self.business,
            connected_by=self.owner,
            pinterest_user_id="pin-user-bad-json",
            username="pin_user",
            access_token_encrypted=encrypt_token("test-access-token"),
            access_token_expires_at=timezone.now() + timedelta(days=1),
            granted_scopes=["user_accounts:read"],
        )

        def broken_json():
            raise ValueError("private-upstream-secret")

        response = SimpleNamespace(status_code=200, json=broken_json)
        with (
            patch("apps.pinterest.strategist_tools.refresh_account_token") as refresh,
            patch("apps.pinterest.strategist_tools._get", return_value=response) as get,
        ):
            with self.assertRaisesRegex(PinterestReadError, "некорректный JSON") as caught:
                _request(account, "/user_account/analytics", {})

        self.assertNotIn("private-upstream-secret", str(caught.exception))
        refresh.assert_not_called()
        self.assertEqual(get.call_count, 1)
        account.refresh_from_db()
        self.assertEqual(account.status, PinterestAccount.Status.CONNECTED)
```

Соответствие требованиям:
1. Метод 1: `_get` → 429, `PinterestReadError` содержит «HTTP 429», ровно один GET (`get.call_count == 1`), refresh не вызван (`assert_not_called`), статус остаётся `CONNECTED` (проверка после `refresh_from_db`).
2. Метод 2: `_get` → 200, `json()` бросает `ValueError("private-upstream-secret")`, `PinterestReadError` содержит «некорректный JSON» и не содержит секрет, ровно один GET, refresh не вызван, статус `CONNECTED`.

Тесты не запускал — только статический анализ по разрешённым исходникам.
