# symphysis

Схема OpenSpec для конвейера проектирования на сильной модели:
рамка OpenSpec, механики GSD — в instruction артефактов. Обкатка —
на рабочей задаче в проекте flow-specs (`C:\Work\flow-specs`, ветка
`feature/<задача>`), материалы задачи лежат там.

## Где что

- `docs/plan-flexible-pipeline.md` — план и решения человека; читать
  перед любой работой над схемой. Что берём из OpenSpec и GSD и почему
  пока без BMAD — раздел «Решение по основе».
- `docs/analysis/sdd-frameworks-proactive-design.md` — механики поиска
  умолчаний с цитатами `путь:строка`: при переносе edge probe,
  prohibition probe, Failure Analyst в instruction.
- `docs/analysis/sdd-frameworks-extensibility.md` — что OpenSpec держит
  и чего не держит: при проектировании артефакта, гейта, вызова своего
  скилла.
- `docs/plan-implementation.tasks.md` — план задач по частям 0, A–F
  (окружение, журнал и скрипты, схема, форк, скиллы, инсталлятор,
  сухой прогон): файлы, сигнатуры, тесты, коммиты; исполнять
  по задачам, у каждой — свой тест.
- `docs/plan-implementation.md` — план реализации (прикидка): поставки
  П1–П7, этапы Э0–Э5, сводка развилок. Развилки с уликами —
  `docs/plan-implementation.journal.json` (источник; `.journal.md` —
  его рендер, руками не править); человек решает их
  в `docs/plan-implementation.html`, собранном командой
  `tools/journal.py render-html` из шаблона `tools/playground-template.html`.
  Шаблон просмотрщика описан в `docs/playground-template-llm-pipeline.md`.
- `tools/journal*.py` — фасад `journal.py` (CLI, публичные имена) и модули:
  `journal_model` (схема, проверка, импорт md), `journal_render` (md, html,
  design.md), `journal_apply` (сверка улик, внесение правок), `journal_cli`;
  модули импортируют друг друга по имени, не через фасад.
- `installer/` — npm-пакет `@niqsons/symphysis`: `install`/`check`;
  `payload/` генерируется из корня (`scripts/sync-payload.js`), не правится.
- `docs/analysis/step0-sources.md` — чтение источников шага 0
  с вердиктами: что берём как есть, что дорабатываем, что
  переписываем; при составлении instruction и формата журнала.
- `upstream/openspec` — исходники OpenSpec 1.15.0, форк для правок:
  встроенная схема — `schemas/spec-driven/`, workflow-скиллы —
  `src/core/templates/workflows/*.ts`, статус артефакта —
  `src/core/artifact-graph/instruction-loader.ts`.
- `upstream/gsd-core` — исходники GSD Core: пробы —
  `gsd-core/references/edge-probe.md`, `prohibition-probe.md`;
  интервью — `gsd-core/workflows/spec-phase.md`, `discuss-phase.md`;
  установка проверяющих — `agents/*.md`, строка «FORCE stance».
- `docs/analysis/gsd-openspec-integration.md` — разбор чужой связки
  GSD Core ↔ OpenSpec: механик GSD над требованиями там нет; семь
  уроков из ошибок автора и три механики-кандидата (схема вердикта,
  классы расхождений, mutation check). Клон удалён, в разборе —
  как восстановить.
- BMAD и spec-kit — клоны вне проекта; коммиты — в разборе
  proactive-design, по ним клоны восстанавливаются.
- OpenSpec 1.13.1 — глобальный пакет
  `%APPDATA%\npm\node_modules\@fission-ai\openspec\`; разборы
  2026-10-29 читали его, `step0-sources.md` — уже 1.15.0.

## Ограничения схемы

- Своё — в схеме (`openspec/schemas/<имя>/`) и своих скиллах:
  сгенерированные workflow-скиллы OpenSpec `openspec update`
  перезаписывает. Правки самого OpenSpec — в форке
  `upstream/openspec`; решением 2026-10-29 (F-02, F-03) форк
  меняется в двух точках: статус артефакта по вердикту
  и workflow-шаблон `continue` с проверкой вердикта. Каждый выпуск
  upstream сначала разбирается, потом решается, втягивать ли.
- Ванильный CLI считает артефакт готовым, когда файл существует;
  форк считает по вердикту во frontmatter `attack.md`. Скрипты
  сверки — сигнал, не стоп (F-12).
- Адресаты парковки — материалы, человек, ИБ (F-11). Канон ИБ
  (инъекции, пути, токены) — чек-листом, не записями журнала.
- Первая версия — OpenSpec и GSD. BMAD подключается после обкатки,
  туда, где схема окажется слабой.
- Edge probe переносим текстом: классификатор GSD — код и читает только
  английский; тип требования определяет модель.
- Копии файлов GSD и BMAD (MIT) несут их copyright notice.

## Как работаем

- Решение человека — в план дословно, с датой.
- Развилки обсуждаются в просмотрщике, не в чате: все варианты,
  включая маловероятные с причиной; решения возвращаются промптом
  и вносятся в журнал без переписывания. Брейншторм в чате — только
  для сложного.
- Утверждение о фреймворке — с `путь:строка` и цитатой; не сверенное
  по файлу помечается «по разбору агента».
- План и разборы правятся здесь; копии во flow-specs заморожены.

## Окружение

- Python — `py -3.13`: под 3.14 нет пакетов, pip получает 403.
- В Git Bash нет `jq` — скрипты хуков пишутся без него.
- Тесты symphysis — `py -3.13 -m pytest` (pytest, jsonschema —
  `requirements-dev.txt`). Тесты форка — `pnpm --dir upstream/openspec test`,
  сборка — `pnpm --dir upstream/openspec build`; CLI форка до сборки
  пакета — `node upstream/openspec/bin/openspec.js`.
- git: ветка работ `impl/plan-tasks`; `upstream/` в `.gitignore`, форк —
  своя ветка `symphysis` в `upstream/openspec` с пином в `UPSTREAM.md`.
