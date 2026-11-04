# FileChanged пробы F-48: код 2 и текст в stderr байтами UTF-8. Аргумент: cursor или last.
# cursor читает все строки от смещения в probe-cursor.json, как read_unread в настоящем hook.py; нечего сказать: код 0.
# last читает только последнюю строку файла, как отклонённый вариант F-56.C.
import json, os, pathlib, sys, time

MODE = sys.argv[1]
root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".")
events = root / ".symphysis" / "viewer" / "events.jsonl"
cursor = root / ".symphysis" / "viewer" / "probe-cursor.json"
started = time.time()
data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
raw = events.read_bytes()
if MODE == "cursor":
    offset = json.loads(cursor.read_text(encoding="utf-8"))["offset"] if cursor.exists() else 0
    end = raw.rfind(b"\n") + 1
    lines = raw[offset:end].split(b"\n")[:-1] if end > offset else []
    new_offset = max(end, offset)
    cursor.write_text(json.dumps({"offset": new_offset}), encoding="utf-8")
else:
    offset = None
    lines = raw.split(b"\n")[:-1][-1:]
answers = [json.loads(line.decode("utf-8"))["answers"] for line in lines]
with open(root / "probe.log", "a", encoding="utf-8") as f:
    f.write(json.dumps({"t": round(started, 2), "ev": "FileChanged", "pid": os.getpid(), "event": data.get("event"),
                        "size": len(raw), "offset": offset, "answers": answers}, ensure_ascii=False) + "\n")
if not answers:
    sys.exit(0)
text = "".join(f"Человек внёс решения кнопкой «Внести» в просмотрщике журнала. Ответ человека лежит в файле {a}. Открой этот файл.\n"
               for a in answers)
sys.stderr.buffer.write(text.encode("utf-8"))
sys.stderr.buffer.flush()
sys.exit(2)
