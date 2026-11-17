# Исходный код до реализации

Снимки строк из коммита `8455a0f1` сохраняют исторические улики решений и описи последствий. Текущая реализация изменила эти места.

## Инструкция атаки

Источник `attack/skills/symphysis-attack/SKILL.md`, строка 241.

```text
- Механизм не назван — `блокер`, воздержания нет: ответ выводится из design.
```

## Заморозка исходной базы

Источник `trace/trace_graph.py`, строка 2105.

```python
found.setdefault(folder.name, {}).setdefault(req.name, entry)
```

## Разбор локальных целей отчёта

Источник `attack/attack_table.py`, строка 45.

```python
if (m := RE_TARGET_PATH.match(line)):
```
