# -*- coding: utf-8 -*-
"""Проба F-52: настоящий UserPromptSubmit Claude Code на Windows, проект во временном каталоге с пробелом и кириллицей.
Настройки пользователя не читаются (--setting-sources project,local) и не меняются. Каждый случай — один короткий запрос к модели,
кроме exit2: он блокирует запрос. След — probe.log рядом, пути заменены метками."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
LOG = HERE / "probe.log"
QUESTION = "Какую служебную метку ты видишь в своём контексте? Ответь только меткой. Если метки нет, ответь словом НЕТ."
HOOK = """# -*- coding: utf-8 -*-
import json, os, sys
data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
root = os.environ.get("CLAUDE_PROJECT_DIR") or ""
with open(os.path.join(root, ".symphysis", "viewer", "input.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"keys": sorted(data), "session_id": data.get("session_id"), "cwd": data.get("cwd"), "event": data.get("hook_event_name"),
                        "prompt": data.get("prompt"), "env_project": root}, ensure_ascii=False) + "\\n")
sys.stdout.reconfigure(encoding="utf-8")
print("Служебная метка: " + sys.argv[2])
sys.exit(int(sys.argv[1]))
"""

work = Path(tempfile.mkdtemp(prefix="symphysis hook проба "))
viewer = work / ".symphysis" / "viewer"
viewer.mkdir(parents=True)
(viewer / "hook.py").write_text(HOOK, encoding="utf-8")
(work / ".claude").mkdir()
env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE", "CLAUDE_PROJECT", "ELECTRON_", "VSCODE_"))
       and k not in ("NoDefaultCurrentDirectoryInExePath", "PYTHONIOENCODING")}
out = []
home = str(Path.home())


def clean(text):
    text = str(text)
    for value, mark in ((str(work), "<проект>"), (home, "<home>")):
        for form in (value.replace("\\", "\\\\"), value, value.replace("\\", "/")):
            text = text.replace(form, mark)
    return text


def handler(python, exit_code, label):
    return {"type": "command", "command": python, "args": ["-X", "utf8", "${CLAUDE_PROJECT_DIR}/.symphysis/viewer/hook.py", str(exit_code), label]}


def write_settings(*handlers):
    (work / ".claude" / "settings.local.json").write_text(
        json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": list(handlers)}]}}, ensure_ascii=False, indent=1), encoding="utf-8")


def inputs():
    file = viewer / "input.jsonl"
    rows = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()] if file.exists() else []
    if file.exists():
        file.unlink()
    return rows


def ask(name, *extra):
    cmd = [shutil.which("claude"), "-p", QUESTION, "--model", "haiku", "--output-format", "json", "--setting-sources", "project,local",
           "--max-turns", "1", "--tools", "", *extra]
    run = subprocess.run(cmd, cwd=work, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=180)
    try:
        reply = json.loads(run.stdout)
    except ValueError:
        reply = {"result": run.stdout[:400], "is_error": None}
    seen = inputs()
    out.append(clean(json.dumps({"case": name, "code": run.returncode, "is_error": reply.get("is_error"), "reply": reply.get("result"), "session_id": reply.get("session_id"),
                                 "hook_inputs": seen, "stderr": run.stderr[:300]}, ensure_ascii=False)))
    return reply


def git_state(name):
    run = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=work, env=env, capture_output=True, encoding="utf-8", errors="replace")
    out.append(json.dumps({"case": name, "git_status": run.stdout.splitlines()}, ensure_ascii=False))


py = sys.executable
try:
    out.append(json.dumps({"case": "версии", "python": clean(py), "claude": subprocess.run([shutil.which("claude"), "--version"], capture_output=True, encoding="utf-8", env=env).stdout.strip()}, ensure_ascii=False))
    subprocess.run(["git", "init", "-q"], cwd=work, env=env, check=True)
    write_settings(handler(py, 0, "КЛЮКВА-7341"), handler(py, 0, "БРУСНИКА-2206"))
    git_state("git до запроса: файл создан не клиентом")
    first = ask("два обработчика, exec-форма, код 0")
    git_state("git после запроса")
    if first.get("session_id"):
        ask("та же сессия через --resume", "--resume", first["session_id"])
    write_settings(handler(py, 1, "МОРОШКА-5150"))
    ask("код 1: вывод не должен попасть в контекст, запрос идёт", "--no-session-persistence")
    write_settings(handler(py, 2, "ЧЕРНИКА-9090"))
    ask("код 2: запрос блокируется", "--no-session-persistence")
    write_settings(handler(str(work / "нет такого" / "python.exe"), 0, "ОБЛЕПИХА-1111"))
    ask("интерпретатора нет: запрос идёт", "--no-session-persistence")
finally:
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    # Каталог сессии клиента для этого временного проекта и сам проект: след пробы вне research/ не остаётся.
    sanitized = "".join(c if c.isascii() and (c.isalnum()) else "-" for c in str(work))
    sessions = Path.home() / ".claude" / "projects" / sanitized
    if "symphysis-hook" in sanitized and sessions.is_dir():
        shutil.rmtree(sessions, ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
print(LOG.read_text(encoding="utf-8"))
