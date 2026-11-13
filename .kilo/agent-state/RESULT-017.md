# RESULT-017

Исполнитель: opencode-cli; модель: `openrouter/qwen/qwen3.8-27b:free`.
Сессия: ses_efea3fa3effeo7FXr5h9bMAZmN.
Статус: ожидает приёмки Codex.

Прочитал точные исходники: `apps/pinterest/strategist_tools.py` (`_request`, строки 312–357) и `apps/pinterest/tests.py` (класс `PinterestOAuthFlowTest`, примеры `test_persistent_401_marks_account_for_reconnect` и `test_resource_401_keeps_valid_profile_connected`).

Проверка логики `_request`:
- 403: не попадает в ветку 401 → `PinterestReadError` «HTTP 403», аккаунт не трогается, refresh не вызывается (токен жив ещё сутки → проактивный refresh тоже не срабатывает).
- 401→refresh→401: `path != "/user_account"` → контрольный GET `/user_account` = 503 → не 200 и не 401 → «Состояние доступа к профилю не подтверждено», до `.update()` на REAUTH_REQUIRED не доходит.

## Code proposal

Дополнить конец класса `PinterestOAuthFlowTest` (после `test_resource_401_keeps_valid_profile_connected`, `apps/pinterest/tests.py:170`) ровно двумя методами:

```python
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
```

44 строки; все имена (`PinterestAccount`, `PinterestReadError`, `_request`, `encrypt_token`, `patch`, `SimpleNamespace`, `timedelta`, `timezone`) уже импортированы в модуле — импорты, класс и setUp не нужны.

## Итоговый отчёт

- Файлы не изменял, команды не запускал, живых API не трогал.
- Тесты не запускал и не запускал; это code proposal для приёмки Codex'ом (`docker compose exec web python manage.py test apps.pinterest.tests.PinterestOAuthFlowTest --noinput`).
- Синтетический аккаунт создаётся так же, как в соседних тестах; дефолтный статус модели — CONNECTED, поэтому `refresh_from_db()` + assert по статусу проверяет сохранение CONNECTED.
- Замыкания: `refresh_account_token` и `_get` замоканы в модуле `apps.pinterest.strategist_tools`; externally-вызовов в тестах нет.
