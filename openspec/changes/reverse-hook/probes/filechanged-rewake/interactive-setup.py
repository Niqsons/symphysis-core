# Ручная проба пробуждения в интерактивном клиенте: создаёт временный проект и печатает его путь.
import json, pathlib, shutil, sys, tempfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
PY = shutil.which("py") or "py"


def hook_cmd(script):
    return f'"{PY}" -3.13 -I "{HERE / script}"'


project = pathlib.Path(tempfile.mkdtemp(prefix="fc-probe-i-"))
(project / ".symphysis" / "viewer").mkdir(parents=True)
(project / ".symphysis" / "viewer" / "events.jsonl").write_text("", encoding="utf-8")
answers = project / "openspec" / "changes" / "demo" / "answers"
answers.mkdir(parents=True)
(answers / "2026-11-04.md").write_text("- F-01: A — (без слова)\n", encoding="utf-8")
(project / ".claude").mkdir()
(project / ".claude" / "settings.json").write_text(json.dumps({
    "hooks": {
        "SessionStart": [{"hooks": [{"type": "command", "command": hook_cmd("start.py")}]}],
        "FileChanged": [{"matcher": "events.jsonl", "hooks": [
            {"type": "command", "command": hook_cmd("wake.py"), "asyncRewake": True, "timeout": 30}]}],
        "PostToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": hook_cmd("read.py")}]}],
    }}, ensure_ascii=False), encoding="utf-8")
print(project.as_posix())
