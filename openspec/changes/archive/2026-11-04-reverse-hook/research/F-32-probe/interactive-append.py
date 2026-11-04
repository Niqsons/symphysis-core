# Ручная проба F-32: дописывает строку внешним процессом, как плагин при «Внести».
# Аргументы: путь проекта; deep пишет в .symphysis/viewer/events.jsonl, root в events.jsonl рабочего каталога.
import json, pathlib, sys

sys.stdout.reconfigure(encoding="utf-8")
project = pathlib.Path(sys.argv[1])
events = project / ".symphysis" / "viewer" / "events.jsonl" if sys.argv[2] == "deep" else project / "events.jsonl"
with open(events, "a", encoding="utf-8") as f:
    f.write(json.dumps({"change": "demo"}) + "\n")
print("дописано:", events.as_posix())
