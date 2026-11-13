# Приёмка TASK-014

Не принят: фактический ответ OpenCode сообщил о незавершённом анализе при
лимите steps=3. Повторный запуск не выполнялся.
Модель `openrouter/cohere/north-mini-code:free`, сессия
`ses_efefe1d82ffegboUhsbePnyPEr`, reported total tokens 24495, cost 0.
Экономия подписки Codex не измерена.

Codex воспроизвёл независимо: JSON array из инструмента приводит к
AttributeError на result.get вне try в respond_to_message, HTTP 500.
Исправление: не-object результаты инструментов отклоняются безопасно;
ошибочные ответы сохраняют уже потраченную token usage.
11 integration-тестов проходят через authenticated AJAX route с
подставной моделью и _request, без внешних запросов.
