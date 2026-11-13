#!/usr/bin/env python3
"""Запуск файлового поручения через официальный CLI; без повторных попыток."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".kilo/agent-state"
RUNTIME = STATE / "runtime"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run", "status"])
    parser.add_argument("task", help="TASK-002 или путь к TASK-002.md")
    parser.add_argument("--model", help="Явный ID модели; разрешение на расходы проверяет Codex")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--steps", type=int, default=3, help="Limit agentic iterations before final text")
    args = parser.parse_args()
    task_id = Path(args.task).stem
    if not re.fullmatch(r"TASK-\d+", task_id):
        parser.error("нужен TASK-<номер>")
    RUNTIME.mkdir(exist_ok=True, mode=0o700)
    status_path = RUNTIME / f"{task_id}.json"
    if args.action == "status":
        if not status_path.exists():
            print("Не запускалось")
            return
        data = json.loads(status_path.read_text())
        if data.get("status") in {"starting", "running"}:
            try:
                os.kill(data["runner_pid"], 0)
            except ProcessLookupError:
                data["status"] = "stopped_without_result"
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if not args.model or args.timeout < 1 or not 1 <= args.steps <= 5:
        parser.error("укажите --model и положительный --timeout")
    task = STATE / f"{task_id}.md"
    result = STATE / f"RESULT-{task_id[5:]}.md"
    executable = shutil.which("opencode") or str(Path.home() / ".opencode/bin/opencode")
    if not task.is_file() or not Path(executable).is_file():
        parser.error("нет файла поручения или CLI OpenCode")
    lock = (RUNTIME / "worker.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("CLI-исполнитель уже работает; повторный запуск запрещён")
    if result.exists() or status_path.exists():
        parser.error("поручение уже запускалось или имеет результат; создайте новое ID")
    try:
        config = json.loads(task.read_text().split("<!-- runner\n", 1)[1].split("\n-->", 1)[0])
        allowed = config["read_files"]
        if not isinstance(allowed, list) or not allowed:
            raise ValueError("нет списка путей")
    except (ValueError, KeyError, IndexError):
        parser.error("в поручении нужен JSON-блок runner с непустым read_files")
    if any(not isinstance(p, str) or Path(p).is_absolute() or ".." in Path(p).parts
           or any(part.startswith(".env") for part in Path(p).parts) for p in allowed):
        parser.error("недопустимые пути чтения")
    agent = "opencode-cli"
    helper = str(STATE / "agent.sh")

    def helper_call(action, *values):
        subprocess.run([helper, action, agent, *values], cwd=ROOT, check=True, capture_output=True)

    def save(status, **fields):
        data = {"task": task_id, "status": status, "model": args.model,
                "runner_pid": os.getpid(), "updated": int(time.time()), **fields}
        tmp = status_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        tmp.replace(status_path)
        print(json.dumps(data, ensure_ascii=False), flush=True)

    helper_call("claim", str(result.relative_to(ROOT)))
    env = dict(os.environ, AGENT_NAME=agent)
    # Права только текущего процесса, постоянные настройки не меняются.
    env["OPENCODE_PERMISSION"] = json.dumps({"*": "deny", "read": {
        "*": "deny", **{p: "allow" for p in allowed}}})
    env["OPENCODE_AUTO_SHARE"] = "false"
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "true"
    env["OPENCODE_DISABLE_LSP_DOWNLOAD"] = "true"
    # Supported process-local configuration: bound costly read/denial loops.
    ephemeral_config = json.loads(env.get("OPENCODE_CONFIG_CONTENT", "{}"))
    ephemeral_config.setdefault("agent", {}).setdefault("plan", {})["steps"] = args.steps
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(ephemeral_config)
    prompt = ("Выполни приложенное файловое поручение как исполнитель Codex. "
              "Файлы не изменяй, команды и внешние инструменты не запускай. "
              "Читай только разрешённые исходники инструментом read. "
              "Дай итоговый отчёт на русском; запускатель сохранит его в RESULT-файл. "
              "Не утверждай, что запускал тесты. Сначала прочитай точные исходники.")
    proc = None
    save("starting")
    helper_call("note", f"{task_id}: запускаю официальный CLI, модель {args.model}; результат {result.name}.")
    try:
        proc = subprocess.Popen([executable, "run", "--pure", "--format", "json",
                                 "--model", args.model, "--agent", "plan",
                                 "--dir", str(ROOT), "--title", f"Codex {task_id}",
                                 "--file", str(task), "--", prompt],
                                cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, start_new_session=True)
        save("running", worker_pid=proc.pid)
        stdout, _stderr = proc.communicate(timeout=args.timeout)
        texts, sessions, errors, usage = [], set(), [], []
        provider_reason = None
        text_message_id = None
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("sessionID"):
                sessions.add(event["sessionID"])
            if event.get("type") == "error":
                errors.append(event.get("error", {}).get("name", "provider_error"))
                if "free tier can only be used" in json.dumps(event):
                    provider_reason = "Провайдер отклонил бесплатный маршрут: FreeTierError (403)"
            if event.get("type") == "text" and event.get("part", {}).get("text"):
                message_id = event["part"].get("messageID")
                if message_id and message_id != text_message_id:
                    texts = []
                    text_message_id = message_id
                texts.append(event["part"]["text"])
            if event.get("type") == "step_finish":
                part = event.get("part", {})
                usage.append({"tokens": part.get("tokens"), "cost": part.get("cost")})
        if proc.returncode or errors or not any(text.strip() for text in texts):
            save("failed", exit_code=proc.returncode, errors=errors,
                 session_ids=sorted(sessions), usage=usage,
                 reason=provider_reason or "CLI не вернул успешный текстовый ответ")
            helper_call("note", f"{task_id}: CLI завершился ошибкой; подробности статуса в runtime/{task_id}.json; повторов нет.")
            return 1
        result.write_text(f"# RESULT-{task_id[5:]}\n\nИсполнитель: {agent}; модель: `{args.model}`.\n"
                          f"Сессия: {', '.join(sorted(sessions))}.\nСтатус: ожидает приёмки Codex.\n\n"
                          + "\n\n".join(texts) + "\n")
        save("awaiting_review", session_ids=sorted(sessions), result=str(result.relative_to(ROOT)), usage=usage)
        helper_call("note", f"{task_id}: фактический ответ CLI сохранён в {result.name}; требуется проверка Codex.")
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        if proc:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
        save("timed_out_or_interrupted", reason="Повторный запрос не выполнялся")
        helper_call("note", f"{task_id}: остановлено по тайм-ауту/прерыванию, повторного запроса нет.")
        return 1
    except OSError:
        save("failed", reason="Ошибка запуска CLI или записи результата")
        helper_call("note", f"{task_id}: ошибка запуска/записи; повторов нет.")
        return 1
    finally:
        helper_call("release", str(result.relative_to(ROOT)))


if __name__ == "__main__":
    raise SystemExit(main())
