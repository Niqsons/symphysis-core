"""Проба F-21: разбор ссылок на записи журнала по правилу A — номер с буквой варианта и с именем журнала,
если оно стоит перед списком. Ссылка — `(номер, буква или None, имя журнала или None)`. Имя берётся из ближайшей
слева метки ``журнал `имя`:`` той же строки, если ссылка стоит до конца её списка: до `;`, `)` или конца строки.
Форма без двоеточия (``F-12.A; слово владельца, журнал `trace-graph` ``) меткой не считается: имя стоит после списка.
Тот же разбор вставлен в патч `patch-rule-A.py`."""
import re

REF = re.compile(r"(?<![\w-])F-(\d+)(?!\d)(?:\.([A-Z])(?![A-Za-z]))?")
LABEL = re.compile(r"журнал[а-я]*\s+`([^`]+)`\s*:")
LIST_END = re.compile(r"[;)]")


def refs(text: str) -> list[tuple[int, str | None, str | None]]:
    scopes = []
    for m in LABEL.finditer(text):
        end = LIST_END.search(text, m.end())
        scopes.append((m.end(), end.start() if end else len(text), m.group(1)))
    out = []
    for m in REF.finditer(text):
        journal = next((name for start, stop, name in scopes if start <= m.start() < stop), None)
        out.append((int(m.group(1)), m.group(2), journal))
    return out


def form(ref: tuple[int, str | None, str | None]) -> str:
    n, letter, journal = ref
    return f"F-{n:02d}" + (f".{letter}" if letter else "") + (f" @{journal}" if journal else "")


def load_trace_graph(tools):
    """trace_graph.py из каталога инструментов пробы как модуль (копия trace/trace_graph.py, см. setup.sh)."""
    import importlib.util, sys
    from pathlib import Path
    tools = Path(tools)
    sys.path.insert(0, str(tools))
    spec = importlib.util.spec_from_file_location("trace_graph", tools / "trace_graph.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["trace_graph"] = module  # dataclass при `from __future__ import annotations` ищет модуль здесь
    spec.loader.exec_module(module)
    return module
