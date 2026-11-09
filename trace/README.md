---
name: trace
kind: доменный
dependencies:
  - repo: symphysis-core
    module: roots
  - repo: symphysis-core
    module: decisions
  - repo: symphysis-core
    module: openspec-run
---

# trace

Граф трассируемости изменения: сборка, отчёт, проверка, заморозка.

`trace_graph.py` соединяет артефакты и структуру, проверяет и замораживает граф,
выдаёт отчёт и текст диаграммы. `trace_modules.py` читает переносимые объявления
и обследует дерево в разрешённых корнях. `module-declarations.md` — общий протокол
обследования для скиллов decisions/research, в поставке `.symphysis/docs/`.

## Вложенные каталоги

- [tests/](tests/) — тесты модуля; в поставку пользователю не идут
