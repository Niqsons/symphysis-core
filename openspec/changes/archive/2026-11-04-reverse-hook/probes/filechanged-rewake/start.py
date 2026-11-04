# SessionStart пробы: называет абсолютный путь файла событий для FileChanged.
import json, os, pathlib, time

root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".")
log = os.environ.get("FC_PROBE_LOG") or str(root / "probe.log")
events = os.environ.get("FC_PROBE_EVENTS") or str(root / ".symphysis" / "viewer" / "events.jsonl")
with open(log, "a", encoding="utf-8") as f:
    f.write(f"{time.time():.1f} SessionStart\n")
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "watchPaths": [events]}}))
