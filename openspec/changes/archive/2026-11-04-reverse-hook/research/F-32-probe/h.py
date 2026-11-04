# Обработчик пробы F-32. Аргумент: log только пишет запуск; watch-hso и watch-top ещё отдают watchPaths; wake для FileChanged.
# Один файл на запуск: клиент запускает обработчики разом, а дозапись на Windows при этом рвёт строки.
import json, os, pathlib, sys, time

MODE = sys.argv[1]
root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".")
deep = root / ".symphysis" / "viewer" / "events.jsonl"
data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
event = data.get("hook_event_name")
changed = data.get("file_path") or ""
try:
    shown = pathlib.Path(changed).relative_to(root).as_posix() if changed else ""
except ValueError:
    shown = "вне-проекта:" + pathlib.Path(changed).name
d = root / "probe-log"
d.mkdir(exist_ok=True)
(d / f"{time.time_ns()}-{os.getpid()}.json").write_text(json.dumps(
    {"t": round(time.time(), 2), "mode": MODE, "ev": event, "source": data.get("source"), "file": shown,
     "change": data.get("event"), "prompt": (data.get("prompt") or "")[:70]}, ensure_ascii=False), encoding="utf-8")

if MODE == "watch-hso":
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "watchPaths": [str(deep)]}}))
elif MODE == "watch-top":
    print(json.dumps({"watchPaths": [str(deep)]}))
elif MODE == "wake":
    if pathlib.Path(changed).name == "seed.txt":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "watchPaths": [str(deep)]}}))
        sys.exit(0)
    sys.stderr.buffer.write("Проба: файл событий изменён. Ответь одним словом: проснулся.\n".encode("utf-8"))
    sys.stderr.buffer.flush()
    sys.exit(2)
