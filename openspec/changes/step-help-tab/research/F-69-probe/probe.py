# -*- coding: utf-8 -*-
"""Проба F-69: что с запросом человека, когда запись хука осталась, а скрипта нет. Настоящие Claude Code и opencode, проект во временном каталоге
с пробелом и кириллицей. Настройки пользователя не читаются и не меняются. Наружу уходит только тестовый вопрос. След — probe.log рядом, пути заменены метками;
выдержки документации — docs-excerpts.txt, дословно."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
LOG = HERE / "probe.log"
EXCERPTS = HERE / "docs-excerpts.txt"
QUESTION = "Какую служебную метку ты видишь в своём контексте? Ответь только меткой. Если метки нет, ответь словом НЕТ."
OC_MODEL = "ollama-cloud/deepseek-v4.1-flash"

# Обёртка записи: файла нет или скрипт вышел с любым кодом — код процесса 0. `-I`: каталог вызова не попадает в sys.path.
GUARD = ("import os,runpy,sys\n"
         "p=sys.argv[1]\n"
         "try:\n"
         "    os.path.isfile(p) and runpy.run_path(p,run_name='__main__')\n"
         "except BaseException:\n"
         "    pass\n")
SCRIPT = """# -*- coding: utf-8 -*-
import sys
data = sys.stdin.buffer.read()
sys.stdout.reconfigure(encoding="utf-8")
print("Служебная метка: КАЛИНА-6161, вход " + str(len(data) > 0))
"""
SCRIPT_EXIT2 = """# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
print("Служебная метка: РЯБИНА-7272")
sys.exit(2)
"""
SCRIPT_LONG = """# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
print("Служебная метка: НАЧАЛО-1010")
print("строка наполнения без смысла\\n" * %d)
print("Служебная метка: КОНЕЦ-2020")
"""

work = Path(tempfile.mkdtemp(prefix="symphysis hook проба "))
viewer = work / ".symphysis" / "viewer"
viewer.mkdir(parents=True)
(work / ".claude").mkdir()
env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE", "CLAUDE_PROJECT", "ELECTRON_", "VSCODE_"))
       and k not in ("NoDefaultCurrentDirectoryInExePath", "PYTHONIOENCODING")}
out = []
home = str(Path.home())
py = sys.executable
HOOK_FILE = viewer / "hook.py"
HOOK_ARG = "${CLAUDE_PROJECT_DIR}/.symphysis/viewer/hook.py"


def clean(text):
    text = str(text)
    for value, mark in ((str(work), "<проект>"), (home, "<home>"), (str(Path(py).parent), "<python>")):
        for form in (value.replace("\\", "\\\\\\\\"), value.replace("\\", "\\\\"), value, value.replace("\\", "/")):
            text = text.replace(form, mark)
    return text


def settings(raw_text):
    (work / ".claude" / "settings.local.json").write_text(raw_text, encoding="utf-8")


def bare():
    return {"type": "command", "command": py, "args": ["-X", "utf8", HOOK_ARG]}


def guarded():
    return {"type": "command", "command": py, "args": ["-I", "-X", "utf8", "-c", GUARD, HOOK_ARG]}


def entry(handler):
    return json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [handler]}]}}, ensure_ascii=False, indent=1)


def ask(name, question=QUESTION):
    cmd = [shutil.which("claude"), "-p", question, "--model", "haiku", "--output-format", "json", "--setting-sources", "project,local",
           "--max-turns", "1", "--tools", "", "--no-session-persistence"]
    run = subprocess.run(cmd, cwd=work, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=180)
    try:
        reply = json.loads(run.stdout)
    except ValueError:
        reply = {"result": run.stdout[:500], "is_error": None}
    out.append(clean(json.dumps({"client": "claude", "case": name, "code": run.returncode, "is_error": reply.get("is_error"), "reply": str(reply.get("result"))[:400],
                                 "stderr": run.stderr[:400]}, ensure_ascii=False)))


OC_PLUGIN = r"""
import { execFileSync } from "node:child_process";
export default {
  id: "symphysis-hook-probe",
  async setup(ctx) {
    await ctx.session.hook("prompt", async (event) => {
      %s
    });
  },
};
"""
OC_CAUGHT = r"""
      let text = "";
      try {
        text = execFileSync(%s, ["-I", "-X", "utf8", "-c", "import os,sys\nsys.exit(0 if os.path.isfile(sys.argv[1]) else 2)", "нет-такого.py"], { encoding: "utf8", timeout: 5000 });
      } catch (e) { text = "сбой пойман"; }
      await ctx.session.instructions.entry.put({ sessionID: event.sessionID, key: "symphysis", value: "Служебная метка: БУЗИНА-8383, " + text });
"""
OC_THROW = r"""throw new Error("сбой в файле плагина");"""
OC_SYNTAX = "этот файл не разбирается ((("
OPENCODE = shutil.which("opencode.cmd") or shutil.which("opencode")


def ask_oc(name, plugin_text):
    plugins = work / ".opencode" / "plugins"
    plugins.mkdir(parents=True, exist_ok=True)
    (plugins / "symphysis-hook.js").write_text(plugin_text, encoding="utf-8")
    cmd = [OPENCODE, "run", "--standalone", "--format", "json", "--print-logs", "--log-level", "warn", "-m", OC_MODEL, QUESTION]
    try:
        done = subprocess.run(cmd, cwd=work, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=240)
        code, stdout, stderr = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as e:
        code, stdout, stderr = "timeout", (e.stdout or b"").decode("utf-8", "replace"), (e.stderr or b"").decode("utf-8", "replace")
    texts = []
    for line in stdout.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("text"), str):
            texts.append(row["text"])
        elif isinstance(row, dict) and isinstance(row.get("part"), dict) and isinstance(row["part"].get("text"), str):
            texts.append(row["part"]["text"])
    errors = [line[:200] for line in stderr.splitlines() if re.search(r"plugin|level=ERROR", line)][:6]
    out.append(clean(json.dumps({"client": "opencode", "case": name, "code": code, "reply": "".join(texts)[:300], "log_lines": errors}, ensure_ascii=False)))
    shutil.rmtree(work / ".opencode", ignore_errors=True)


def excerpt(url, patterns, width=320):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "symphysis-research-probe"}), timeout=30) as resp:
            text = resp.read().decode("utf-8", "replace")
    except OSError as e:
        return [f"# {url}", f"не снято: {type(e).__name__}"]
    text = re.sub(r"<[^>]+>", "", text) if "<html" in text[:2000].lower() else text
    rows = [f"# {url}"]
    for pattern in patterns:
        found = re.search(pattern, text)
        rows.append(" ".join(text[found.start():found.start() + width].split()) if found else f"не найдено: {pattern}")
    return rows


try:
    version = subprocess.run([shutil.which("claude"), "--version"], capture_output=True, encoding="utf-8", env=env).stdout.strip()
    oc_version = subprocess.run([OPENCODE, "--version"], capture_output=True, encoding="utf-8", errors="replace", env=env).stdout.strip()
    out.append(json.dumps({"case": "версии", "claude": version, "opencode": oc_version, "python": sys.version.split()[0]}, ensure_ascii=False))
    subprocess.run(["git", "init", "-q"], cwd=work, env=env, check=True)

    # Claude Code: скрипта нет.
    settings(entry(bare()))
    ask("запись как в F-52, файла скрипта нет")
    settings(entry(guarded()))
    ask("запись с обёрткой, файла скрипта нет")
    HOOK_FILE.write_text(SCRIPT, encoding="utf-8")
    ask("запись с обёрткой, скрипт на месте: вход и вывод доходят")
    HOOK_FILE.write_text(SCRIPT_EXIT2, encoding="utf-8")
    ask("запись с обёрткой, скрипт вышел с кодом 2")

    # Claude Code: файл настроек, который чужой разборщик не прочтёт.
    HOOK_FILE.write_text(SCRIPT, encoding="utf-8")
    settings("// комментарий человека\n" + entry(guarded()))
    ask("настройки с комментарием: читает ли их клиент")
    settings(entry(guarded())[:-3])
    ask("настройки с ошибкой синтаксиса: что с запросом и хуком")

    # Claude Code: длинный вывод. 2000 строк по ~30 символов — около 60 КБ.
    HOOK_FILE.write_text(SCRIPT_LONG % 2000, encoding="utf-8")
    settings(entry(guarded()))
    ask("вывод около 60 КБ: какие метки видны", "Какие служебные метки ты видишь в своём контексте? Перечисли только метки. Если их нет, ответь словом НЕТ.")
    shutil.rmtree(work / ".claude", ignore_errors=True)

    # opencode: тот же случай, запись — файл-оболочка.
    ask_oc("оболочка ловит сбой Python, файла скрипта нет", OC_PLUGIN % (OC_CAUGHT % json.dumps(py)))
    ask_oc("оболочка ловит мёртвый путь к Python", OC_PLUGIN % (OC_CAUGHT % json.dumps(str(work / "нет такого" / "python.exe"))))
    ask_oc("необработанное исключение в хуке prompt", OC_PLUGIN % OC_THROW)
    ask_oc("файл плагина не разбирается", OC_SYNTAX)

    # Выдержки сняты один раз при прогоне 2026-11-04 и лежат в docs-excerpts.txt. Страница VS Code названа там словами: её адреса нет в tools/allowed-hosts.txt,
    # а строки этого файла вносятся руками. Функция excerpt осталась для страниц из разрешённых адресов.
finally:
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    sanitized = "".join(c if c.isascii() and (c.isalnum()) else "-" for c in str(work))
    sessions = Path.home() / ".claude" / "projects" / sanitized
    if "symphysis-hook" in sanitized and sessions.is_dir():
        shutil.rmtree(sessions, ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
print(LOG.read_text(encoding="utf-8"))
print(EXCERPTS.read_text(encoding="utf-8") if EXCERPTS.exists() else "выдержек нет")
