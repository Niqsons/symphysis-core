"""Проба F-21: сравнение связей `traces` от требований в двух графах (снимок и сборка, или сборка до и после патча).
Вызов: python -X utf8 compare.py <граф A> <граф B> [имя A] [имя B] [--journal decisions.json].
Печатает счёт и разницу по (from, to, at); с `--journal` у каждой разницы — вопрос записи своего журнала."""
import json
import sys
from pathlib import Path

args = sys.argv[1:]
journal = None
if "--journal" in args:
    i = args.index("--journal")
    journal = Path(args[i + 1])
    args = args[:i] + args[i + 2:]
a, b = Path(args[0]), Path(args[1])
na, nb = (args[2] if len(args) > 2 else a.name), (args[3] if len(args) > 3 else b.name)
questions = {}
if journal:
    questions = {"rec:" + r["id"]: " ".join(r["question"].split()) for r in json.loads(journal.read_text(encoding="utf-8"))["records"]}


def req_traces(path):
    data = json.loads(path.read_bytes().decode("utf-8-sig"))
    return {(e["from"], e["to"], e["at"]) for e in data["edges"] if e["type"] == "traces" and e["from"].startswith("req:")}


ta, tb = req_traces(a), req_traces(b)
print(f"{na}: связей traces от требований {len(ta)}; {nb}: {len(tb)}")
for label, diff in ((f"только в «{na}»", sorted(ta - tb)), (f"только в «{nb}»", sorted(tb - ta))):
    print(f"{label}: {len(diff)}")
    for src, dst, at in diff:
        q = questions.get(dst)
        print(f"  {src} -> {dst} @ {at}" + (f"  запись: «{q[:100]}{'…' if len(q) > 100 else ''}»" if q else ""))
