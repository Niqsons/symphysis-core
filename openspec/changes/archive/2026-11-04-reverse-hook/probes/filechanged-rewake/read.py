# PostToolUse пробы: какие поля приходят при чтении файла.
import json, os, pathlib, sys, time

root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".")
log = os.environ.get("FC_PROBE_LOG") or str(root / "probe.log")
data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
with open(log, "a", encoding="utf-8") as f:
    f.write(f"{time.time():.1f} PostToolUse tool={data.get('tool_name')} keys={sorted((data.get('tool_input') or {}).keys())} "
            f"path={(data.get('tool_input') or {}).get('file_path')} session={bool(data.get('session_id'))}\n")
