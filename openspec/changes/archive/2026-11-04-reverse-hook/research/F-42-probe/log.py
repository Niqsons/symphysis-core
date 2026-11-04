# PostToolUse пробы F-42: один файл на запуск. Аргумент: номер формы условия if.
# Не общий журнал: клиент запускает обработчики разом, а дозапись на Windows при этом рвёт строки (первая версия пробы).
import json, os, pathlib, sys, time

label = sys.argv[1]
data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
line = json.dumps({"t": round(time.time(), 2), "form": label, "tool": data.get("tool_name"),
                   "file_path": (data.get("tool_input") or {}).get("file_path"),
                   "project_dir": os.environ.get("CLAUDE_PROJECT_DIR")}, ensure_ascii=False)
d = pathlib.Path(os.environ["RH_F42_LOG"])
d.mkdir(exist_ok=True)
(d / f"{time.time_ns()}-{os.getpid()}.json").write_text(line, encoding="utf-8")
