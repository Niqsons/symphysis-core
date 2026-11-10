# Source evidence before implementation

Baseline commit: c6651d852fb84fc2c90a794f2419a21dbf6103ce. These quotes describe the pre-change mechanisms recorded in the journal, not the new implementation.

## F-10 — trace/trace_graph.py

```python
READERS = {"decisions": _read_records
```

## F-10 — trace/trace_graph.py

```python
# Узел — словарь: `id`, `kind` (`cap`, `req`, `scn`, `rec`, `task`, `sec`, `branch`)
```

## F-11 — trace/trace_graph.py

```python
SOURCE_FILES = {"decisions": "decisions.json"
```

## F-11 — trace/trace_graph.py

```python
return [{"prefix": no_paths(prefix, root), "commit": root_commit(folder)}
```

## F-11 — trace/trace_graph.py

```python
GRAPH_FORMAT = 2
```

## F-11 — trace/trace_graph.py

```python
data["format"] != GRAPH_FORMAT
```

## F-22 — trace/trace_graph.py

```python
"commit": root_commit(folder)
```

## F-24 — trace/trace_graph.py

```python
DIAGRAM = {
```

## F-27 — trace/trace_graph.py

```python
    return [{"path": rel, "sha256": _lf_hash(base / rel)} for rel in sorted(set(rels)) if (base / rel).is_file()]
```

## F-27 — trace/trace_graph.py

```python
        attach = ("task", "rec", "sec", "branch")
```

## F-31 — roots/roots.py

```python
Префикс пути улики -> каталог — только из файла корней
```

## F-34 — trace/trace_graph.py

```python
def _read_tasks(base: Path, claims: list[dict])
```

## F-34 — trace/trace_graph.py

```python
Новый артефакт схемы без строки здесь даёт красный тест
```

## F-37 — trace/trace_graph.py

```python
return [{"path": rel, "sha256": _lf_hash(base / rel)}
```

## F-48 — roots/roots.py

```python
if not path.startswith(prefix.replace("\\", "/")):
```

## F-49 — roots/roots.py

```python
return None, VERDICT_UNREADABLE
```

## F-50 — trace/trace_graph.py

```python
raise Refusal(f"{rel}: файл не в UTF-8 ({e.reason}, байт {e.start}): граф не собран") from None
```

## F-51 — trace/trace_graph.py

```python
text = build_report(root, change, frozen).rstrip("\n") + "\n"
```

## F-52 — trace/trace_graph.py

```python
raw = data.get("base") if isinstance(data, dict) and data.get("format") == GRAPH_FORMAT else None
```

## Consequences — trace/trace_graph.py

```python
if not problems and data["format"] != GRAPH_FORMAT:
```

## Consequences — trace/trace_graph.py

```python
return ([f"{rel}: исходник изменён после сборки" for rel in sorted(old.keys() & now.keys()) if old[rel] != now[rel]]
```

## Consequences — trace/trace_graph.py

```python
+ [f"{rel}: новый исходник, в графе его нет" for rel in sorted(now.keys() - old.keys())]
```

## Consequences — trace/trace_graph.py

```python
+ [f"{rel}: исходник удалён" for rel in sorted(old.keys() - now.keys())])
```
