---
name: cli
kind: технический
dependencies:
  - repo: symphysis-core
    module: attack
  - repo: symphysis-core
    module: consequences
  - repo: symphysis-core
    module: decisions
  - repo: symphysis-core
    module: roots
  - repo: symphysis-core
    module: runtime
  - repo: symphysis-core
    module: step-help
  - repo: symphysis-core
    module: viewer
---

# cli

Фасад командной строки журнала: точка входа `journal.py` и разбор подкоманд; в установке лежит одним файлом в `.symphysis/tools/`.

## Вложенные каталоги

- [tests/](tests/) — тесты модуля; в поставку пользователю не идут
