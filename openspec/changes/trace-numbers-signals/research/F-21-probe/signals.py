"""Проба F-21: сигналы графа без форка. Зовёт trace_graph из каталога инструментов пробы как модуль и печатает
строки graph_signals(...) с signal_context — те же, что раздел «Сигналы графа» отчёта report/freeze, без находок
openspec validate (форка во временном корне нет). Вызов: python -X utf8 signals.py <tools> <корень> <изменение>."""
import importlib.util, sys
from pathlib import Path

tools, root, change = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(tools))
spec = importlib.util.spec_from_file_location("trace_graph", tools / "trace_graph.py")
tg = importlib.util.module_from_spec(spec)
sys.modules["trace_graph"] = tg  # dataclass при `from __future__ import annotations` ищет модуль здесь
spec.loader.exec_module(tg)
graph, duplicates, unresolved = tg.build_graph_with_signals(root, change)
context = tg.signal_context(root, change)
for line in tg.graph_signals(graph, duplicates, unresolved, context):
    print(line)
for rid, place in context["unbased"]:
    print(f"[!!] {tg.UNBASED}: {rid[4:]} — {place}")
