# TASK020 — OAuth refresh tests
<!-- runner
{"read_files":["apps/pinterest/services.py","apps/pinterest/tests.py"]}
-->
OpenCode/Qwen. Ты не один, чужие изменения не отменяй. Только чтение,
не правь файлы, не запускай команды/API. RESULT020 сохраняет runner.
Graph home-evgen-bk3.0 Verify,current indexed generation; services/tests
coverage metadata_match без зарегистрированных gaps. Scope refresh_account_token.
Предложи3testметода существующему PinterestOAuthFlowTest, импорты отдельно:
1. успешный refresh меняетaccess+refresh в зашифрованном виде, сроки/scopes,
передаёт decrypt старогоrefresh; CONNECTED сохраняется;
2. временная PinterestOAuthError сохраняет старыеcredentials/CONNECTED;
3. постоянная PinterestOAuthError ставит REAUTH_REQUIRED.
Все refresh_tokens замоканы, accounts synthetic, секретов/APIнет.
До110строк. Codex проверит и запустит. Не заявляй запуск тестов.
