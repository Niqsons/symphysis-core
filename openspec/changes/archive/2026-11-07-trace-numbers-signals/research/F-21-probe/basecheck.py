"""Проба F-21: сверка базы снимка `graph/req-graph.json` (поле `base`) с живым мастером временного корня, где
`openspec/specs` стоит на коммите `roots[0].commit` снимка. Если числа, хеш текста и сценарии совпадают — мастер на
коммите снимка тот же, с которого снималась база, и ключи правила A можно брать из него.
Вызов: python -X utf8 basecheck.py <инструменты> <корень> <изменение>."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import refparse  # noqa: E402

tools, root, change = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
tg = refparse.load_trace_graph(tools)
base = tg.saved_base(root / "openspec" / "changes" / change)
bad = 0
for cap, reqs in sorted(base.items()):
    live = tg.master_base(root, cap)
    for name, entry in reqs.items():
        now = live.get(name)
        if now is None:
            print(f"[!!] {cap}/{name}: в мастере на коммите снимка требования нет")
            bad += 1
            continue
        same = {k: entry[k] == now[k] for k in ("numbers", "text", "scenarios", "traces")}
        mark = "ок" if all(same.values()) else "РАСХОЖДЕНИЕ " + ", ".join(k for k, v in same.items() if not v)
        bad += not all(same.values())
        print(f"{mark}: {cap}/{name}: numbers база {entry['numbers']} мастер {now['numbers']}")
print(f"записей базы: {sum(len(r) for r in base.values())}, расхождений: {bad}")
