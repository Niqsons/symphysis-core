# Ручная проба: дописывает строку в файл событий внешним процессом, как плагин при «Внести». Аргумент: путь проекта.
import json, pathlib, sys

sys.stdout.reconfigure(encoding="utf-8")
events = pathlib.Path(sys.argv[1]) / ".symphysis" / "viewer" / "events.jsonl"
with open(events, "a", encoding="utf-8") as f:
    f.write(json.dumps({"change": "demo", "answers": "openspec/changes/demo/answers/2026-11-04.md"}) + "\n")
print("дописано:", events.as_posix())
