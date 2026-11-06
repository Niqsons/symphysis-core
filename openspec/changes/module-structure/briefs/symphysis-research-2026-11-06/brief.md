---
skill: symphysis-research
artifact: research
change: module-structure
question: F-20
inputs:
  - tools/
  - tests/conftest.py
  - tests/
  - CLAUDE.md
  - docs/repo-contract.md
  - openspec/config.yaml
  - openspec/config.symphysis.yaml
  - installer/scripts/sync-payload.js
  - vscode/test/unit/fixture-project.ts
  - vscode/test/unit/step-help.test.ts
  - vscode/test/e2e/harness.mjs
  - vscode/test/e2e/demo.mjs
report: openspec/changes/module-structure/briefs/symphysis-research-2026-11-06/report.md
---

Исполнить шаги 4–8 скилла `symphysis-research` по одной парковке.

Запись: `Как код модулей находит друг друга и свои файлы в исходнике?`

Слово человека: `«Перечислить в `tools/*.py` все места, где код находит файлы от `ROOT` или `__file__` (схема JSON, шаблон страницы, файл корней, файл версии, путь `journal.py` для подсказок), и все точки запуска из исходника (`CLAUDE.md`, `docs/repo-contract.md`, правила архивации в `openspec/config.yaml`, хуки `tools/hooks/`, тесты ядра и плагина). Для вариантов A и B — что меняется в каждом месте и как `<root>` файла корней ведёт себя в исходнике и в установке.»`

Выяснить:
1. Где в `tools/*.py` и `tools/hooks/*.py` код находит файлы от `ROOT` или `__file__`: схема JSON, шаблон страницы, файл корней, файл версии, путь `journal.py` для подсказок, каталог скиллов — каждое место цитатой.
2. Где проект запускает скрипты из исходника `tools/…`, а не из установки `.symphysis/tools/…`: `CLAUDE.md`, `docs/repo-contract.md`, правила архивации в `openspec/config.yaml`, хуки `tools/hooks/`, `tests/conftest.py` и тесты ядра, тесты плагина (`vscode/test/…`).
3. Как `<root>` и `<home>` файла корней раскрываются (`tools/journal_apply.py`): чему равен `<root>` у исходника `tools/` и у установленной копии `.symphysis/tools/`; от какого дерева написан `tools/journal-roots.json`.
4. Человек выбрал вариант A: точки входа (`journal.py`, `trace_graph.py`, `step_help.py`, `symphysis_config.py`) в исходнике добавляют каталоги модулей в `sys.path`, тесты — через `conftest.py`; свои файлы модуль ищет рядом с кодом в исходнике и по плоской раскладке `.symphysis/tools/`, `.symphysis/docs/` в установке. Какие из мест пунктов 1–3 этот вариант задевает — связкой с местом, без выбора.

Область: `tools/`, `tests/conftest.py`, `tests/`, `CLAUDE.md`, `docs/repo-contract.md`, `openspec/config.yaml`, `openspec/config.symphysis.yaml`, `installer/scripts/sync-payload.js`, `vscode/test/unit/fixture-project.ts`, `vscode/test/unit/step-help.test.ts`, `vscode/test/e2e/harness.mjs`, `vscode/test/e2e/demo.mjs`.

Жанр: `устройство`

Среда: корень проекта — `X:\symphysis-module-structure` (worktree ветки `feat/module-structure`). Установки `.symphysis/` в нём нет: общие файлы скиллов — `X:\symphysis\.symphysis\docs\`, скрипты — `tools/` корня проекта, шаблон `research.md` — поле `template` вывода `openspec instructions research --change module-structure --json` (запускать с `OPENSPEC_TELEMETRY=0`). Пути плагина в находках — с префиксом `vscode/` (каталог `X:\symphysis-vscode`), как в `openspec/changes/module-structure/probes/journal-roots.json`.

Писать: `openspec/changes/module-structure/research/F-20.md`, `openspec/changes/module-structure/research/F-20-probe/`

Не делать: `decisions.json`, `specs/`, код проекта, вопросы человеку, чтение вне области.
