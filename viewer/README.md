---
name: viewer
kind: доменный
dependencies:
  - repo: symphysis-core
    module: decisions
  - repo: symphysis-core
    module: runtime
---

# viewer

Страница просмотра развилок: шаблон `playground-template.html` и сборка страницы из журнала.

## Вложенные каталоги

- [skills/](skills/) — скиллы модуля: тела `SKILL.md` и выписки доноров (просмотрщик)
- [tests/](tests/) — тесты модуля; в поставку пользователю не идут
