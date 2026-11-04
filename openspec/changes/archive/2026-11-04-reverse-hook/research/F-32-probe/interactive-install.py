# Ручная проба F-32. Шаг 3: записывает хуки в .claude/settings.local.json идущей сессии. Аргумент: путь проекта.
import json, os, pathlib, shutil, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
PY = shutil.which("py") or "py"
project = pathlib.Path(sys.argv[1])


def h(mode, **extra):
    return {"type": "command", "command": f'"{PY}" -3.13 -I -X utf8 "{HERE / "h.py"}" {mode}', **extra}


settings = project / ".claude" / "settings.local.json"
tmp = settings.with_name(settings.name + ".tmp")
tmp.write_text(json.dumps({"hooks": {
    "SessionStart": [{"hooks": [h("watch-hso")]}],
    "UserPromptSubmit": [{"hooks": [h("log")]}],
    "FileChanged": [{"matcher": "events.jsonl", "hooks": [h("wake", asyncRewake=True, timeout=30)]}],
}}, ensure_ascii=False, indent=2), encoding="utf-8")
os.replace(tmp, settings)
print("записано:", settings.as_posix())
