# -*- coding: utf-8 -*-
"""Проба к шагу security: 1) что с запросом, если хук завис, и помогает ли поле `timeout` записи; 2) какие из вызовов git, что плагин будет делать при активации,
исполняют `core.fsmonitor` из настроек репозитория. Проект и репозиторий временные, настройки пользователя не читаются. Наружу уходит только тестовый вопрос к haiku. След — security-probe.log рядом."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).parent
LOG = HERE / "security-probe.log"
QUESTION = "Какую служебную метку ты видишь в своём контексте? Ответь только меткой. Если метки нет, ответь словом НЕТ."
GUARD = ("import os,runpy,sys\n"
         "p=sys.argv[1]\n"
         "try:\n"
         "    os.path.isfile(p) and runpy.run_path(p,run_name='__main__')\n"
         "except BaseException:\n"
         "    pass\n")
HANG = """# -*- coding: utf-8 -*-
import sys, time
sys.stdout.reconfigure(encoding="utf-8")
print("Служебная метка: ЗАВИСШИЙ-3030", flush=True)
time.sleep(25)
"""
env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE", "CLAUDE_PROJECT", "ELECTRON_", "VSCODE_"))
       and k not in ("NoDefaultCurrentDirectoryInExePath", "PYTHONIOENCODING")}
out = []


def hook_case(name, extra):
    work = Path(tempfile.mkdtemp(prefix="symphysis hook проба "))
    try:
        viewer = work / ".symphysis" / "viewer"
        viewer.mkdir(parents=True)
        (viewer / "hook.py").write_text(HANG, encoding="utf-8")
        (work / ".claude").mkdir()
        handler = {"type": "command", "command": sys.executable, "args": ["-I", "-X", "utf8", "-c", GUARD, "${CLAUDE_PROJECT_DIR}/.symphysis/viewer/hook.py"], **extra}
        (work / ".claude" / "settings.local.json").write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [handler]}]}}, ensure_ascii=False, indent=1), encoding="utf-8")
        t0 = time.time()
        run = subprocess.run([shutil.which("claude"), "-p", QUESTION, "--model", "haiku", "--output-format", "json", "--setting-sources", "project,local", "--max-turns", "1", "--tools", "", "--no-session-persistence"],
                             cwd=work, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=180)
        seconds = round(time.time() - t0, 1)
        try:
            reply = json.loads(run.stdout)
        except ValueError:
            reply = {"result": run.stdout[:300]}
        out.append(json.dumps({"client": "claude", "case": name, "code": run.returncode, "seconds": seconds, "is_error": reply.get("is_error"), "reply": str(reply.get("result"))[:200]}, ensure_ascii=False))
    finally:
        sanitized = "".join(c if c.isascii() and c.isalnum() else "-" for c in str(work))
        sessions = Path.home() / ".claude" / "projects" / sanitized
        if "symphysis-hook" in sanitized and sessions.is_dir():
            shutil.rmtree(sessions, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)


def git_case():
    git = shutil.which("git")
    repo = Path(tempfile.mkdtemp(prefix="fsmonitor проба "))
    try:
        subprocess.run([git, "init", "-q"], cwd=repo, env=env, check=True)
        (repo / "a.txt").write_text("a\n", encoding="utf-8")
        subprocess.run([git, "add", "a.txt"], cwd=repo, env=env, check=True)
        marker = repo / "marker.txt"
        subprocess.run([git, "config", "core.fsmonitor", "echo x > marker.txt; true"], cwd=repo, env=env, check=True)
        calls = (["rev-parse", "--git-path", "info/exclude"], ["ls-files", "--error-unmatch", "a.txt"], ["worktree", "list", "--porcelain"], ["status", "--porcelain"])
        for prefix, label in (([], "без защиты"), (["-c", "core.fsmonitor=false"], "с core.fsmonitor=false")):
            for args in calls:
                if marker.exists():
                    marker.unlink()
                run = subprocess.run([git, *prefix, *args], cwd=repo, env=env, capture_output=True, encoding="utf-8", errors="replace")
                out.append(json.dumps({"client": "git", "mode": label, "args": " ".join(args), "code": run.returncode, "marker": marker.exists()}, ensure_ascii=False))
    finally:
        shutil.rmtree(repo, ignore_errors=True)


try:
    hook_case("скрипт висит 25 с, поле timeout 2", {"timeout": 2})
    git_case()
finally:
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
print(LOG.read_text(encoding="utf-8"))
