# TASK-019: pins/top_pins регрессии
<!-- runner
{"read_files":["apps/strategist/test_tool_acceptance.py","apps/pinterest/strategist_tools.py"]}
-->
Ты OpenCode. Не один в проекте: чужие изменения не отменять, файлы не править.
Владеешь только proposal RESULT019, который запишет runner; Codex проверяет.
Никаких команд, API, секретов. Прочитай указанные два файла.
Graph home-evgen-bk3.0 Verify generation2026-10-03T13:07:42Z,ready;
read_pinterest_data145-179,_endpoint182-288; coverage обоих файлов metadata_match
без зарегистрированных gaps. Scope только mocked ToolAcceptanceTest.

Верни три test-метода для существующего класса без import/setup:
1. top_pins требует pins:read: у self.account есть только user_accounts:read;
валидные dates (timezone.now minus7/minus1days), sort_by OUTBOUND_CLICK.
assert_read_error, self.request не вызывается.
2. При нужных scopes top_pins транспорт выбрасывает PinterestReadError HTTP403;
chat безопасно сообщает ошибку, не пустой топ; статусCONNECTED сохраняется.
3. pins первая страница с items/bookmark, следующая ошибка: две function-call
completion и затем read-error, без ложного полного списка; scope boards:read/pins:read.
Используй существующие helpers/patch, при нужном импорте предложи его отдельно.
Всего до100строк, не утверждай запуск тестов.
