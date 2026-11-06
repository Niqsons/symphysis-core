# symphysis

Схема OpenSpec для конвейера проектирования на сильной модели:  
рамка OpenSpec, механики GSD — в instruction артефактов. Обкатка —  
на рабочей задаче в проекте flow-specs, материалы задачи лежат там.

## Где что

- `.context/` — локальный пакет контекста ядра, вне git: начинать с
  `00-start-here.md`, дальше слот по задаче. Из worktree читается только
  по пути основного клона, `X:\symphysis\.context\`.
- `docs/repo-contract.md` — контракт с плагином `symphysis-vscode`: подпись
  коммитов, что считается сменой контракта, пуш и пауза; читать перед правкой
  инструментов журнала и страницы.
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
  design.md), `journal_apply` (сверка улик, внесение правок), `journal_sites`
  (места кода из улик, подкоманда `code-sites`), `journal_consequences` (две
  проверки описи `consequences.md` внутри `check`), `journal_cli`; модули
  импортируют друг друга по имени, не через фасад.
- `tools/symphysis_config.py` — состав выбора из личного `symphysis.yaml`, единственный
  читатель файла: журнал этот модуль не импортирует и настройки не читает, а
  `symphysis config` и `symphysis check` зовут его. Случаи —
  `tests/fixtures/settings-cases.json`.
- `installer/` — npm-пакет `@niqsons/symphysis`: `install`/`check`/`config`;
  `payload/` генерируется из корня (`scripts/sync-payload.js`), не правится.
- `docs/skills-canon.md` — канон тела скилла и агента: скелет, правило с уровнем
  RFC 2119, таблицы только для справки, провенанс в `<!-- src: -->`, водитель по brief;
  читать перед правкой `skills/`. Ревью, по которому он написан, —
  `docs/analysis/skills-review-2026-11-05.md`; проверка терминов —
  `docs/analysis/terms-check-2026-11-06.md`.
- `skills/shared/*.md` — общие файлы скиллов (`terms.md`, `journal-cli.md`, `config.md`,
  `candidate.md`, `attack-table.md`, `driver.md`): payload кладёт их в `docs/`, инсталлятор —
  в `.symphysis/docs/`. `skills/<имя>/sources/` — выписки доноров и заметки перевода,
  контур разработки: в payload не идут, как и комментарии `<!-- src: -->` в телах;
  уведомления MIT — `installer/THIRD-PARTY-NOTICES.md`.
- `agents/symphysis-*-driver.md` — тела агентов-водителей (атака, пробы, опись,
  исследование): называют скилл и brief, не пересказывают; payload несёт их в `agents/`,
  инсталлятор кладёт в каталог агентов рядом с каждым каталогом скиллов (`.claude/agents/`),
  параметр `--agents-dir`. Какой шаг идёт водителю — ключ `drivers` в `symphysis.yaml`.
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
  меняется не в двух точках, как решалось сначала, а по перечню правок
  в `upstream/openspec/UPSTREAM.md` (версия форка `1.15.0-symphysis.4`).
  Каждый выпуск upstream сначала разбирается, потом решается, втягивать ли.
- Первый артефакт схемы — `intent` (`intent.md`: намерение словами
  человека); без него `decisions` заблокирован (F-13.A). Второй круг
  брейншторма — в конце шага `research`, не в `attack-decisions`.
- Шаг `consequences` стоит между `specs` и `design`: опись в `consequences.md`, в журнал
  идут только ветка или допущение без сценария и причины провала. Скрипт сверяет места
  и цитаты, сигнал, не стоп; настройки читает `symphysis_config.py`.
- Атаки `attack-decisions` и `attack-artifacts` необязательные (признак
  `optional` форка): `continue` без имени их пропускает, вызов —
  `/opsx:continue <изменение> attack-artifacts`. Вызванная атака гейтует
  зависимые артефакты и apply, пока вердикт не `passed`; вердикт с чужим
  хешем целей — `stale` (F-06.A, F-26.E).
- Перед архивом дельты изменения переносятся в `openspec/specs/`
  операцией агента `/opsx:sync` (F-20.B).
- Ванильный CLI считает артефакт готовым, когда файл существует;
  форк считает по вердикту во frontmatter `attack.md`. Скрипты
  сверки — сигнал, не стоп (F-12).
- Водители: атака, пробы, опись и исследование могут идти субагенту по brief
  (`<каталог изменения>/briefs/<скилл>-<дата>/`), ключ `drivers` в `symphysis.yaml`;
  умолчание — атака и исследование вкл, пробы и опись выкл (Р11-A, 2026-11-06); хвост
  после слова человека — главная нить; форма — `docs/skills-canon.md`, раздел 10.
- Адресаты парковки — материалы, человек, ИБ (F-11). Канон ИБ
  (инъекции, пути, токены) — чек-листом, не записями журнала.
- Первая версия — OpenSpec и GSD. BMAD подключается после обкатки,
  туда, где схема окажется слабой.
- Edge probe переносим текстом: классификатор GSD — код и читает только
  английский; тип требования определяет модель.
- Копии файлов GSD и BMAD (MIT) несут их copyright notice.

## Как работаем

- Решение человека — в план дословно, с датой.
- Файл, который должен прочитать человек, передаётся в чате ссылкой
  `[имя](путь)`, а не голым путём (слово владельца, 2026-11-03).
- Развилки обсуждаются в просмотрщике, но решить их человек может и в чате
  (слово владельца, 2026-11-03): все варианты, включая маловероятные с причиной; решения возвращаются промптом
  и вносятся в журнал без переписывания. Брейншторм в чате — только
  для сложного.
- Утверждение о фреймворке — с `путь:строка` и цитатой; не сверенное
  по файлу помечается «по разбору агента».
- План и разборы правятся здесь; копии во flow-specs заморожены.

## Окружение

- Python — `python`, версия не закрепляется. Запрет на внешние пакеты (Р19, 2026-11-01)
  снят словом владельца 2026-11-05: можно добавлять «любой пакет, если его можно получить
  в корпоративном хранилище или собрать самим. Но лишние зависимости нежелательны».
  Сейчас `tools/journal*.py` пакетов не требуют. PyYAML нужен только
  `tools/symphysis_config.py`: файл настроек есть, а пакета нет — всё включено и сигнал
  с командой установки.
- В Git Bash нет `jq` — скрипты хуков пишутся без него.
- Тесты symphysis — `python -X utf8 -m pytest` — **всегда с xdist**:
  `-n 12` стоит в `pytest.ini` (`addopts`), без него тесты не запускаются
  (правило владельца, 2026-10-30); пакеты — pytest, pytest-xdist, jsonschema,
  pyyaml (`requirements-dev.txt`). `jsonschema` — только эталон сверки проверщика
  (`tests/test_journal_validator.py`): без него сверка показывается пропуском
  и пройденной не считается. Тесты форка — `pnpm --dir upstream/openspec test`,
  сборка — `pnpm --dir upstream/openspec build`; CLI форка до сборки
  пакета — `node upstream/openspec/bin/openspec.js`.
- git: работа идёт от `main`, своя ветка — свой worktree (`docs/repo-contract.md`);
  `upstream/` в `.gitignore`, форк —
  своя ветка `symphysis` в `upstream/openspec` с пином в `UPSTREAM.md`.
