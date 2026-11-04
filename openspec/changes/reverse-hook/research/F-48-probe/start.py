# SessionStart пробы F-48: называет абсолютный путь файла событий для FileChanged.
import json, os, pathlib, time

root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".")
with open(root / "probe.log", "a", encoding="utf-8") as f:
    f.write(json.dumps({"t": round(time.time(), 2), "ev": "SessionStart"}) + "\n")
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                         "watchPaths": [str(root / ".symphysis" / "viewer" / "events.jsonl")]}}))
