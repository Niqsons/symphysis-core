# -*- coding: utf-8 -*-
"""Шим форка OpenSpec для тестов: отвечает по `scenario.json` рядом с собой и дописывает каждый вызов в `calls.jsonl`.

Запись: `argv`, безопасные диагностические поля `env`, `cwd`, `pid`. Ключ ответа: `version`, `status_all` (`status --all`), `status`, `apply`
(`instructions apply`), `validate` (`validate …`). Ответ: `stdout`, `stderr`, `stderr_encoding`, `code`, `hang` — сколько секунд висеть до ответа.
Кладёт и наполняет его `install_fork_shim` из `tests/conftest.py`."""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
LOGGED_ENV = ("OPENSPEC_TELEMETRY", "OPENSPEC_NO_UPDATE_CHECK", "OPENSPEC_NO_COMPLETIONS",
              "SYMPHYSIS_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "HOME", "USERPROFILE", "MARK")


def reply_key(argv: list[str]) -> str:
    if argv[:1] == ["--version"]:
        return "version"
    if argv[:1] == ["validate"]:
        return "validate"
    if argv[:2] == ["instructions", "apply"]:
        return "apply"
    return "status_all" if "--all" in argv else "status"


def main() -> int:
    argv = sys.argv[1:]
    record = {"argv": argv, "env": {key: os.environ[key] for key in LOGGED_ENV if key in os.environ},
              "cwd": os.getcwd(), "pid": os.getpid()}
    with (HERE / "calls.jsonl").open("a", encoding="utf-8") as calls:
        calls.write(json.dumps(record, ensure_ascii=False) + "\n")
    reply = json.loads((HERE / "scenario.json").read_text(encoding="utf-8")).get(reply_key(argv), {})
    time.sleep(reply.get("hang", 0))
    sys.stdout.buffer.write(reply.get("stdout", "").encode("utf-8"))
    sys.stderr.buffer.write(reply.get("stderr", "").encode(reply.get("stderr_encoding", "utf-8")))
    return reply.get("code", 0)


if __name__ == "__main__":
    sys.exit(main())
