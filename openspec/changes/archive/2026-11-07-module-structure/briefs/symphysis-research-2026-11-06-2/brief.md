---
skill: symphysis-research
artifact: research
change: module-structure
question: F-27
inputs:
  - tools/
  - skills/
  - agents/
  - docs/journal.schema.json
  - openspec/config.symphysis.yaml
  - installer/scripts/sync-payload.js
  - docs/analysis/requirements-traceability-graph-of-symphysis.md
  - vscode/src/
  - vscode/hook/
  - vscode/media/icon.svg
  - vscode/build.mjs
  - vscode/package.mjs
report: openspec/changes/module-structure/briefs/symphysis-research-2026-11-06-2/report.md
---

Исполнить шаги 4–8 скилла `symphysis-research` по одной парковке.

Запись: `Как файлы и функции ядра и плагина раскладываются по модулям выбранных в F-18 и F-31 вариантов и какие зависимости между модулями появятся?`

Слово человека: `«Разложить по модулям каждый файл `tools/`, `skills/`, `skills/shared/`, `agents/`, а также `docs/journal.schema.json` и `openspec/config.symphysis.yaml` — каждый к одному модулю. Для `tools/journal_render.py`, `tools/journal_cli.py` и `tools/journal_apply.py` — по функциям: какие уходят в другой модуль, какие импорты между будущими модулями появятся, нет ли циклов (например, `decisions` и `viewer` через `render-html`), куда идут `view-json` и номер контракта. Итог: таблица файлов и граф зависимостей модулей; развилки резки — во втором круге. В плагине — каждый файл `src/`, `hook/`, `media/icon.svg`, `build.mjs`, `package.mjs` к модулю F-31: импорты между модулями, общее для стороны VS Code и страниц, путь `hook/hook.py`, который читает код.»`

Модули, выбранные человеком (журнал водителю не нужен):
- ядро, F-18 A — доменные: `decisions` (журнал, проверка, `apply`, скилл брейншторма), `viewer` (страница, скилл просмотрщика), `consequences` (места кода, опись, скилл, водитель), `attack` (скилл, таблица линз, водитель), `probes` (две пробы, водители), `research` (скилл, водитель), `trace` (граф), `step-help` (справка о шаге); технические: `openspec-run` (запуск форка), `settings` (`symphysis.yaml`), `installer`; схема `openspec/schemas/symphysis/` — модуль с местом от OpenSpec. Скилл и водитель лежат в модуле своей механики.
- плагин, F-31 A — `viewer` (карточки решений и внесение), `search`, `scheme`, `step-help`, `hook` (хук агента и `hook/hook.py`), `core` (поиск ядра и Python, вызов `journal.py`, номер контракта); у модуля в одном каталоге части стороны VS Code и страницы; общее для них — технический модуль `protocol`.

Выяснить:
1. Каждый файл `tools/` (кроме `tools/hooks/` и списков `allowed-*.txt` — это контур разработки), `skills/`, `skills/shared/`, `agents/`, `docs/journal.schema.json`, `openspec/config.symphysis.yaml` — к какому модулю ядра по содержанию и по тому, кто его зовёт или читает; цитата, на которой стоит отнесение. Файл, который не ложится ни в один модуль или ложится в два, — отдельной строкой.
2. `tools/journal_render.py`, `tools/journal_cli.py`, `tools/journal_apply.py`, `tools/journal_model.py` — по функциям и константам: к какой ответственности каждая, кто её импортирует (`путь:строка` импорта); куда идут `view-json` и номер контракта `CONTRACT`.
3. Какие импорты между модулями ядра появятся при такой раскладке и есть ли циклы — граф зависимостей модулей с опорой на строки импорта.
4. Каждый файл `vscode/src/`, `vscode/hook/`, `vscode/media/icon.svg`, `vscode/build.mjs`, `vscode/package.mjs` — к модулю плагина; импорты между модулями плагина и циклы; файлы, которые ни к одному модулю не ложатся.

Область: `tools/`, `skills/`, `agents/`, `docs/journal.schema.json`, `openspec/config.symphysis.yaml`, `installer/scripts/sync-payload.js`, `docs/analysis/requirements-traceability-graph-of-symphysis.md` (раздел «Компоненты и модули»), `vscode/src/`, `vscode/hook/`, `vscode/media/icon.svg`, `vscode/build.mjs`, `vscode/package.mjs`.

Жанр: `размещение`

Среда: корень проекта — `X:\symphysis-module-structure` (worktree ветки `feat/module-structure`). Установки `.symphysis/` в нём нет: общие файлы скиллов — `X:\symphysis\.symphysis\docs\`, скрипты — `tools/` корня проекта, шаблон `research.md` — поле `template` вывода `openspec instructions research --change module-structure --json` (запускать с `OPENSPEC_TELEMETRY=0`). Пути плагина в находках — с префиксом `vscode/` (каталог `X:\symphysis-vscode`), как в `openspec/changes/module-structure/probes/journal-roots.json`. Таблица файлов может занять много строк: каждая строка — файл, модуль и опора `путь:строка «цитата»`.

Писать: `openspec/changes/module-structure/research/F-27.md`, `openspec/changes/module-structure/research/F-27-probe/`

Не делать: `decisions.json`, `specs/`, код проекта, вопросы человеку, чтение вне области.
