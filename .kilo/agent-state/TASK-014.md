# TASK-014: границы аргументов инструмента

<!-- runner
{"read_files":["apps/pinterest/strategist_tools.py"]}
-->

Исполнитель OpenCode, openrouter/cohere/north-mini-code:free; результат RESULT-014.md.
Codex принимает решение. Исходники не менять, команды и API не запускать.
Граф home-evgen-bk3.0 ready, generation 2026-10-03T08:36:35Z;
search_graph нашёл read_pinterest_data 145-179, _request 312-357.
Coverage исходника metadata_match без зарегистрированных gaps, Verify.
Прочитай read_pinterest_data и _endpoint. Верни только 3 строки:
какие невалидные типы arguments/options могут привести к исключению,
какие уже отклоняются безопасно, какой минимальный guard предложить.
Не называй проверку запуском тестов. Не читай другие файлы.
