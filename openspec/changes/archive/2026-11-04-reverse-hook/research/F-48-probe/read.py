# PostToolUse пробы F-48: какой файл прочитала модель.
import json, os, pathlib, sys, time

root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".")
data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
with open(root / "probe.log", "a", encoding="utf-8") as f:
    f.write(json.dumps({"t": round(time.time(), 2), "ev": "PostToolUse", "tool": data.get("tool_name"),
                        "file": os.path.basename((data.get("tool_input") or {}).get("file_path") or "")},
                       ensure_ascii=False) + "\n")
