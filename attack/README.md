---
name: attack
kind: доменный
dependencies:
  - repo: symphysis-core
    module: decisions
---

# attack

Шаг атаки журнала и артефактов: таблица линз и её разбор (`attack_table.py`: `parse_attack_md`, `parse_attack_text`; `set_severity` правит ячейку тяжести и `status` по слову человека), состав устаревшего вердикта — какие записи добавлены после атаки, какие цели изменились (`attack_scope.py`, один расчёт для `journal.py check` и справки шага).

## Вложенные каталоги

- [agents/](agents/) — тела агентов-водителей модуля
- [skills/](skills/) — скиллы модуля: тела `SKILL.md` и выписки доноров
- [tests/](tests/) — тесты модуля; в поставку пользователю не идут
