# RESULT-019

Исполнитель: opencode-cli; модель: `openrouter/qwen/qwen3.8-27b:free`.
Сессия: ses_efe0c6592ffegyPEYqPDvcDGWL.
Статус: ожидает приёмки Codex.

Прочитаны оба файла (`apps/strategist/test_tool_acceptance.py` 208 строк целиком, `apps/pinterest/strategist_tools.py` 369 строк целиком). Файлы не изменял, тесты не запускал.

Факты, на которые опираются тесты:
- `top_pins` → `{user_accounts:read, pins:read}`, обязательные опции `start_date/end_date/sort_by` (strategist_tools.py:46, :95); проверка скопов до `_request` (:170-177), ошибка scope → `{"error": ...}` → read-error (аналог `test_missing_scope_is_rejected`).
- Транспорт 403 → `PinterestReadError("...HTTP 403...")` (:353); 403 не меняет статус — только 401 после refresh помечает REAUTH_REQUIRED (:340-351).
- Даты валидируются как ISO `YYYY-MM-DD`, окно ≤90 дней, не позже сегодня (`_validate_date_range` :291-305).
- Paginated-ресурс `pins`: первая страница с `bookmark` → сервис возвращает модель на второй вызов (по образцу `test_complete_pagination_preserves_answer`); ошибка второго вызова → read-error без финальной completion (по образцу `test_upstream_unavailability_stops_model_inference`).

Три test-метода (вставка в существующий `ToolAcceptanceTest`, без изменений import/setup, ~57 строк):

```python
    def test_top_pins_requires_pins_read_scope(self):
        now = timezone.now()
        options = json.dumps({
            "start_date": (now - timedelta(days=7)).date().isoformat(),
            "end_date": (now - timedelta(days=1)).date().isoformat(),
            "sort_by": "OUTBOUND_CLICK",
        })
        self.assert_read_error(self.ask_tool(self.arguments(resource="top_pins", options=options)))
        self.request.assert_not_called()

    def test_top_pins_http_403_keeps_account_connected(self):
        from apps.pinterest.strategist_tools import PinterestReadError

        now = timezone.now()
        options = json.dumps({
            "start_date": (now - timedelta(days=7)).date().isoformat(),
            "end_date": (now - timedelta(days=1)).date().isoformat(),
            "sort_by": "OUTBOUND_CLICK",
        })
        self.account.granted_scopes = ["user_accounts:read", "pins:read"]
        self.account.save(update_fields=["granted_scopes"])
        self.request.side_effect = PinterestReadError("Pinterest API вернул HTTP 403 для чтения данных.")
        answer = self.ask_tool(self.arguments(resource="top_pins", options=options))
        self.assert_read_error(answer)
        self.assertIn("HTTP 403", answer.content)
        self.request.assert_called_once()
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, PinterestAccount.Status.CONNECTED)

    def test_pins_followup_page_error_is_reported_not_total(self):
        from apps.pinterest.strategist_tools import PinterestReadError

        self.account.granted_scopes = ["boards:read", "pins:read"]
        self.account.save(update_fields=["granted_scopes"])
        first = self.arguments(resource="pins")
        second = {**first, "bookmark": "next"}
        self.complete.side_effect = [
            GigaChatCompletion(content="", model="mock", prompt_tokens=10, completion_tokens=2,
                total_tokens=12, function_call={"name": "read_pinterest_data", "arguments": first}),
            GigaChatCompletion(content="", model="mock", prompt_tokens=10, completion_tokens=2,
                total_tokens=12, function_call={"name": "read_pinterest_data", "arguments": second}),
        ]
        self.request.side_effect = [
            {"items": [{"id": 1}, {"id": 2}], "bookmark": "next"},
            PinterestReadError("Pinterest API вернул HTTP 403 для чтения данных."),
        ]
        answer = self.ask_tool(first, question="Прочитай все пины @alpha. Сколько всего?")
        self.assertEqual((answer.provider, answer.model), ("data-read", "read-error"))
        self.assertIn("Не буду делать выводы без источника", answer.content)
        self.assertNotIn("Всего 2", answer.content)
        self.assertEqual(self.complete.call_count, 2)
        self.assertEqual(self.request.call_count, 2)
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, PinterestAccount.Status.CONNECTED)
```

Допущения и замечания:
- Новый модульного импорта не требуется: `json`, `timedelta`, `timezone`, `GigaChatCompletion` уже есть в модуле; `PinterestReadError` импортируется локально в теле метода — существующий паттерн (`test_upstream_unavailability_stops_model_inference`, :147).
- В тесте 3 сознательно не утверждаю `answer.total_tokens`: накопление токенов read-error после двух tool-call'ов не видно из разрешённых двух файлов (поilaku service.py не читал); остальное подтверждено существующими тестами класса.
- Хелперы использованы без правок: `ask_tool`, `arguments`, `assert_read_error`; патчи только существующие `self.complete` / `self.request`.
- Тесты не запускались; результат оформлен как «ожидает приёмки».
