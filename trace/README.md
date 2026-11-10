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
  - repo: symphysis-core
    module: runtime
---

# trace

Граф трассируемости изменения: сборка, отчёт, проверка, заморозка.

`trace_graph.py` соединяет артефакты и структуру, проверяет и замораживает граф,
выдаёт отчёт и текст диаграммы. `trace_modules.py` читает переносимые объявления
и обследует дерево в разрешённых корнях. `module-declarations.md` — общий протокол
обследования для скиллов decisions/research, доступный через
`symphysis resource doc module-declarations.md`.

## Вложенные каталоги

- [tests/](tests/) — тесты модуля; в поставку пользователю не идут

## Выбранный вид графа

`symphysis trace view <изменение>` возвращает JSON для плагина. Без выбора части ответ содержит перечни capability, требований и модулей. Живой источник доступен после появления требований во всех specs capability, перечисленных в proposal.

```text
symphysis trace view demo --capability api
symphysis trace view demo --requirement "req:api/Имя требования"
symphysis trace view demo --module repo/module --capability api --linked-only
symphysis trace view demo --snapshot openspec/changes/archive/demo/graph/req-graph.json --capability api
```

Форматы снимка 2 и 3 поддерживаются, формат 1 получает явный отказ. Историческая структура читается из выбранного снимка. Команда выполняет чтение и сохраняет файлы graph/.

Ответ `view_format: 1` содержит `source`, `selection`, `choices`, `text`, `elements`, `empty`, `unlinked`, `diagnostics`, `incomplete`. `text` равен null до выбора части и при пустой выборке. Ключ `elements` соответствует имени блока Mermaid. Закреплённый рендерер добавляет к нему префикс id рисунка в SVG. Значение хранит канонический id, вид, имя и исходное место узла. Доступная файловая цель добавляется как `target` с полями `file`, `root`, `line`, `journal` после разрешения в настроенных корнях. Плагин повторно проверяет настоящий путь перед открытием.

Модуль задаётся парой repo/module и отбирает требования через явные implements модуля и его файлов. Контекст сохраняет сценарии, задачи, записи и модули совместной реализации. Пересечение модуля и capability может быть пустым.

`unlinked.scope` в текущем выводе равен `change`, список относится ко всему изменению. Связи contains и verifies не подменяют traces к решению. `--linked-only` исключает только узлы без единого ребра выбранной части. Диагностика сборки и область списка сохраняются. Дубли id, неразрешённые ссылки и неполное обследование repo отражаются в диагностике. Отсутствие структурных данных обозначается отдельно.
