# Ручная проба F-32: печатает журнал обработчиков по времени. Аргумент: путь проекта.
import json, pathlib, sys

sys.stdout.reconfigure(encoding="utf-8")
log = pathlib.Path(sys.argv[1]) / "probe-log"
rows = sorted((json.loads(p.read_text(encoding="utf-8")) for p in log.glob("*.json")), key=lambda x: x["t"]) if log.exists() else []
for r in rows:
    print(r["t"], r["ev"], r.get("source") or "", r.get("file") or "")
print("запусков:", len(rows))
