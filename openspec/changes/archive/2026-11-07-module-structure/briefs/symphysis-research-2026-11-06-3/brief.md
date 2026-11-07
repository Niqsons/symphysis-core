---
skill: symphysis-research
artifact: research
change: module-structure
question: F-28
inputs:
  - openspec/schemas/symphysis/
  - openspec/config.symphysis.yaml
  - openspec/config.yaml
  - installer/scripts/sync-payload.js
  - installer/lib/
  - installer/test/
  - upstream/openspec/src/core/artifact-graph/
report: openspec/changes/module-structure/briefs/symphysis-research-2026-11-06-3/report.md
---

Исполнить шаги 4–8 скилла `symphysis-research` по одной парковке.

Запись: `Как схема становится модулем, если её каталог задаёт OpenSpec?`

Слово человека: `«Читает ли форк лишние файлы в `openspec/schemas/symphysis/` (README.md рядом со `schema.yaml`) и не ломает ли это `openspec schemas`, `status`, `instructions`; уходит ли README в payload по `DIRS` и в проекты пользователей; можно ли перенести `openspec/config.symphysis.yaml` внутрь каталога схемы и где его читает инсталлятор. Где читать: `upstream/openspec/src/core/artifact-graph/`, `installer/scripts/sync-payload.js`, `installer/lib/`.»`

Выяснить:
1. Какие файлы каталога схемы форк перечисляет и разбирает (`upstream/openspec/src/core/artifact-graph/`) и что он сделает с лишним `README.md` рядом со `schema.yaml`: цитата и проба — копия проекта во временном каталоге с `README.md` в `openspec/schemas/symphysis/`, затем `openspec schemas`, `openspec status --change module-structure`, `openspec instructions decisions --change module-structure`; сравнить с выводом без `README.md`.
2. Уходит ли `README.md` каталога схемы в payload (`DIRS` в `installer/scripts/sync-payload.js`) и в проект пользователя при `symphysis install`; что инсталлятор делает с каталогом схемы в проекте (`installer/lib/`), есть ли тесты, которые сверяют состав каталога (`installer/test/`).
3. Где инсталлятор читает `openspec/config.symphysis.yaml` и где его читает форк, если читает; что изменится в `sync-payload.js` и `installer/lib/`, если файл ляжет внутрь `openspec/schemas/symphysis/`, и не примет ли форк его там за часть схемы.

Область: `openspec/schemas/symphysis/`, `openspec/config.symphysis.yaml`, `openspec/config.yaml`, `installer/scripts/sync-payload.js`, `installer/lib/`, `installer/test/`, `upstream/openspec/src/core/artifact-graph/`.

Жанр: `проверка`

Среда: корень проекта — `X:\symphysis-module-structure` (worktree ветки `feat/module-structure`). Установки `.symphysis/` в нём нет: общие файлы скиллов — `X:\symphysis\.symphysis\docs\`, скрипты — `tools/` корня проекта, шаблон `research.md` — поле `template` вывода `openspec instructions research --change module-structure --json`. Форк — `openspec` в `PATH` (версия `1.15.0-symphysis.4`), все вызовы с `OPENSPEC_TELEMETRY=0`. Пути форка в находках — с префиксом `upstream/` (каталог `X:\symphysis\upstream`), как в `openspec/changes/module-structure/probes/journal-roots.json`. Проба — только во временном каталоге системы и в `research/F-28-probe/`; рабочее дерево проекта и каталог схемы в нём не меняются.

Писать: `openspec/changes/module-structure/research/F-28.md`, `openspec/changes/module-structure/research/F-28-probe/`

Не делать: `decisions.json`, `specs/`, код проекта, вопросы человеку, чтение вне области.
