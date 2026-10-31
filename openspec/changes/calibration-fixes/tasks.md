# Tasks

<!-- Группы по зависимостям Migration Plan дизайна; номера F-NN — записи журнала. Проверка каждой задачи — в строке.
     Предположения помечены словом и дорогой «решить»; их три: форма пометки отступления (5.1), строка версии форка (3.5),
     код выхода check при включённой телеметрии (8.3). -->

## 1. Подготовка: intent задним числом (F-19.A) — до правки схемы

- [x] 1.1 Написать `openspec/changes/symphysis-schema/intent.md` из вводной его журнала («Перенос журнала плана реализации») и плана `docs/plan-implementation.md`, словами источника без правок — проверка: файл существует; каждая его цитата находится грепом в источнике.
- [x] 1.2 Написать `openspec/changes/calibration-fixes/intent.md` из слова владельца «атаки должны быть включаемы, а не обязательны» и разборов калибровки (F-01, F-06) — проверка: файл существует; после 4.1 `openspec status --change calibration-fixes --json` показывает `intent` — `done`, остальные статусы не меняются.

## 2. Перенос базы спек (F-20.B) — по слову владельца

- [ ] 2.1 По слову владельца выполнить `/opsx:sync symphysis-schema`: девять `openspec/specs/<capability>/spec.md` из дельт `ADDED` — проверка: `openspec validate --specs` код 0; скрипт сравнения заголовков `### Requirement:` и `#### Scenario:` дельт против главных спек даёт пустой diff.
- [ ] 2.2 Убедиться, что `MODIFIED` этого изменения применимы: `openspec validate calibration-fixes --strict --json` — проверка: в `issues` нет INFO «Archive would refuse this delta».
- [ ] 2.3 Журнал `symphysis-schema`: F-36 закрыть ссылкой на F-16, F-79 — на F-21 и F-57 этого изменения (строки `notes[]`, `consequences`) — проверка: `py -3.13 .symphysis/tools/journal.py check openspec/changes/symphysis-schema/decisions.json` код 0; строки в `notes[]`.

## 3. Форк OpenSpec (F-06.A, F-26.E, F-29.E, F-30.E, F-31.E, F-52.E)

- [x] 3.1 `src/core/artifact-graph/schema.ts`: признак `optional: boolean` у артефакта, валидатор схемы его принимает — проверка: `test/core/artifact-graph/schema.test.ts` — схема с `optional: true` валидна, без признака — поведение прежнее.
- [x] 3.2 `instruction-loader.ts` и `state.ts`: optional без файла не блокирует зависимые и не входит в `isPlanningComplete`, `status --json` несёт `optional: true` и явный признак отсутствия файла; с файлом — правило вердикта; `target_sha256` и `targets[].sha256` против текущих хешей целей → `verdict: stale`, зависимые `blocked` — проверка: `instruction-loader.test.ts`, `state.test.ts` — сценарии «Необязательный артефакт без файла», «Необязательный артефакт с файлом», «Файл вызванной атаки удалён», «Вердикт с чужим хешем», «Планирование без вызванных атак».
- [x] 3.3 Workflow `continue` (`src/core/templates/workflows/continue-change.ts`): второй аргумент — имя артефакта, точное сравнение с `id` (иначе отказ с перечнем `id` без записи файлов), повтор по имени при равных хешах — «вердикт действителен» без перезаписи, без имени optional пропускаются — проверка: `test/core/templates/continue-verdict.test.ts` — текст шаблона несёт все четыре правила; `openspec update` в проекте обновляет `.claude/skills/openspec-continue-change/SKILL.md`.
- [x] 3.4 Workflow `apply`: при невызванных атаках печатает «атаки не вызывались: attack-decisions, attack-artifacts» — проверка: новый `test/core/templates/apply-optional.test.ts`; строка в сгенерированном SKILL.md.
- [x] 3.5 `upstream/openspec/UPSTREAM.md`: таблица правок (optional, stale, continue по имени, apply) и строка версии форка (предположение: `1.15.0-symphysis.2`; решить при ревью) — проверка: `pnpm --dir upstream/openspec test` зелёный, `pnpm --dir upstream/openspec build`, `node upstream/openspec/bin/openspec.js --version` печатает новую строку.

## 4. Схема symphysis и шаблоны (F-13.A, F-24.E, F-06.A, F-16.A, F-27.E, F-08.A)

- [x] 4.1 `openspec/schemas/symphysis/schema.yaml`: артефакт `intent` первым (`generates: intent.md`; instruction — «если файла нет или он пуст, спроси намерение у человека и сохрани его слова дословно; содержания не пиши»), `requires: [intent]` у `decisions`; `optional: true` у `attack-decisions` и `attack-artifacts`, `proposal` требует `research`, `apply.requires: [tasks]` — проверка: `openspec schema validate symphysis --json` — `valid: true`; `tests/test_schema.py` — порядок артефактов, признак optional, сценарий «Новое изменение» по fixture.
- [x] 4.2 Instruction `research` и `templates/research.md`: нуль парковок → `research/none.md` с frontmatter (`question: none`) и отрицанием по рецепту; первая парковка «материалы» удаляет `none.md` — проверка: `tests/test_schema.py` — instruction и шаблон содержат оба правила; fixture-изменение без парковок с `none.md` даёт `research` — `done` в `status`.
- [x] 4.3 `templates/intent.md` (намерение словами человека; критерии готовности; «Без критериев готовности» допустимо) и `templates/proposal.md` — раздел «Отступления от постановки» со строкой «нет» по умолчанию — проверка: `openspec instructions proposal --change <fixture> --json` отдаёт шаблон с разделом; `tests/test_schema.py` — оба шаблона на месте с нужными строками.
- [x] 4.4 Payload схемы: `node installer/scripts/sync-payload.js` — проверка: `installer/test/payload.test.js` — байты схемы и шаблонов в payload равны корню.

## 5. Журнал и инструменты (F-17.A, F-12.A, F-35.E, F-09.A, F-37.E, F-38.E, F-21.A, F-39.E, F-40.E, F-41.E, F-42, F-23.A, F-34.E, F-45.E, F-46.E)

- [ ] 5.1 `docs/journal.schema.json`: значение `постановка` в enum `addressee` записи; пометка «отступление от постановки» — предположение: поле `deviation` с номером факта постановки у развилки, альтернатива — префикс `[отступление]` в `question`; решить с владельцем до правки схемы — проверка: `tests/test_journal_schema.py` — факт с `постановка` годен, fixtures журналов плеч годны, `Постановка` отвергается с полем в ошибке.
- [x] 5.2 `journal_model.validate_journal`: факт без улики → код 1, если нет парковки и статус не `припаркован`; `recommendation.why` пустой → код 1; парковка «материалы» без `finding` при `research/<F-NN>.md` → строка `[!!]`, код 0, с `--strict` — 2 — проверка: `tests/test_journal_check.py` — сценарии «Факт без улики», «Припаркованный факт без улики», «Пустое why», «Парковка без находки при файле».
- [x] 5.3 `journal_apply._resolve`: нормализация разделителей и регистра диска, `resolve()` ссылок, проверка «внутри корня», вердикт «вне корня» без чтения файла — проверка: `tests/test_journal_check.py` — «Выход за корень» (`../../Windows/win.ini`), «Разделители и регистр диска», «Ссылка наружу» (junction во временном каталоге; без прав на junction тест пропускается с причиной).
- [x] 5.4 `check`: бинарный файл → «не проверить: бинарный файл», `found: null`, остальные улики сверены, код 0; тест-страховка F-42 — NUL на границе 8 КиБ, UTF-16 с BOM, PNG — проверка: `tests/test_journal_check.py`, три файла в `tests/fixtures/`.
- [x] 5.5 `check`: сверка без нормализации — NBSP против пробела → «цитаты нет дословно», CRLF против LF → найдена — проверка: `tests/test_journal_check.py` (сценарий «Сверка без нормализации»).
- [x] 5.6 `journal_render.render_design`: Decisions только из развилок без `outcome`; «ничего не менять» — с пометкой «конструкция не меняется»; без решённых развилок — строка «нет: решённых развилок в журнале нет», код 0; записи с `outcome` — в Open Questions только при Defer — проверка: `tests/test_journal_design.py` — сценарии «Decisions только из развилок», «Журнал без решённых развилок», «Решение «ничего не менять»».
- [x] 5.7 Разбор строки атаки в `journal_render`: `\|` — литеральная черта, `\\` — литеральная косая, черта внутри backticks — текст; незакрытый backtick и пустая обязательная ячейка — ошибка с файлом, строкой и столбцом, код 2 — проверка: `tests/test_journal_render.py` — «Черта в backticks и экранированная черта», «Экранированная косая и незакрытый backtick», «Пустая ячейка», «Битый файл атаки»; `render-html --attack openspec/changes/calibration-fixes/attack/decisions.md` код 0.
- [x] 5.8 Payload инструментов: `node installer/scripts/sync-payload.js` после 5.1–5.7 — проверка: `installer/test/payload.test.js`; `.symphysis/docs/journal.schema.json` равен `docs/journal.schema.json`.

## 6. Просмотрщик (F-18.A, F-47.E, F-48.E, F-56.E, F-49.E, F-21.A, F-07.A)

- [x] 6.1 `tools/playground-template.html`, режим «атака»: фильтр по линзе («все» и слуги), счётчики тяжести по всему файлу видны при любом фильтре — проверка: `tests/test_journal_render.py` — HTML с `--attack` содержит переключатель линз и блок счётчиков вне фильтра; в браузере по сценарию «Фильтр и счётчик блокеров».
- [x] 6.2 Скрываемый блок с текстом записи `F-NN, поле` у каждой строки атаки — проверка: HTML содержит текст вопроса записи рядом со строкой; сценарий «Текст записи у строки» в браузере.
- [x] 6.3 Промпт возврата из состояния: внесённые `apply` строки уходят; очистка поля замечаний очищает промпт; ответ в поле спора строки «вопрос человеку» с разделом `F-NN, decision` → `- F-NN: <буква> — «…»`, одна строка на запись, конфликт при двух ответах, дубликат внесённого решения не добавляется; слово к выбору необязательно — проверка: тест логики промпта (`tests/test_viewer_prompt.py` через node на извлечённой функции) по сценариям «Внесённое уходит из промпта», «Спор становится словом», «Два ответа к одному решению», «Ответ повторяет внесённое решение», «Выбор без слова».
- [x] 6.4 Экранирование: все 9 вставок `innerHTML` идут через `esc()` (плюс одинарная кавычка), backticks → `<code>` после экранирования содержимого, атрибуты и URL из данных журнала не строятся — проверка: `tests/test_journal_render.py` — слово `<script>alert(1)</script>`, цитата с `<img onerror>`, ячейка атаки с тем же показаны текстом; `<b>` в тексте записи — текст, `` `код` `` — `<code>`.
- [x] 6.5 Группировка по новому списку слугов (артефакты — `scenario-run`, `claim-extraction`; журнал — `context-compliance`, `claim-authority`, `claim-extraction`, `coverage`), прежние слуги — группа «вне списка» — проверка: рендер `openspec/changes/symphysis-schema/attack/artifacts.md` — строки в «вне списка»; `openspec/changes/calibration-fixes/attack/decisions.md` — все строки в своих группах.
- [x] 6.6 `skills/symphysis-viewer/SKILL.md`: режим «атака» (фильтр, блок записи, промпт из состояния), правило ячейки — проверка: `tests/test_skills.py` — текст несёт все пункты.

## 7. Скиллы (F-07.A, F-12.A, F-08.A, F-09.A, F-13.A, F-23.A, F-34.E, F-53.E, F-54.E, F-43.E, F-44.E, F-55.E, F-61.A)

- [x] 7.1 `skills/symphysis-attack/SKILL.md`: линзы артефактов `scenario-run` (форма строки: сценарий, механизм, код `путь:строка`, исход, THEN; строка на пару сценарий × механизм; механизм не назван — блокер) и `claim-extraction`; линзы журнала; гигиену не репортить; правило ячейки (`\|`, backticks, `\\|`); «читает, не исполняет»; понижение тяжести только с причиной; `references/` и `TRANSLATION-NOTES.md` — измерение SELF — проверка: `tests/test_skills.py` — тексты правил; `attack/decisions.md` этого изменения проходит разбор 5.7.
- [ ] 7.2 `skills/symphysis-brainstorm/SKILL.md`: `intent.md` первым, факты `постановка` с цитатами, нуль критериев → вопрос «назови критерии готовности» и строка в `notes[]`, «Без критериев готовности» — заполненные критерии, дедупликация во втором круге, пометка отступления, правило предписания (факт с конструкцией → развилка), слово к выбору необязательно — проверка: `tests/test_skills.py`; круг 1 на fixture-изменении с `intent.md` даёт первой записью факт `постановка`.
- [x] 7.3 `skills/symphysis-edge-probe/SKILL.md` и `skills/symphysis-prohibition-probe/SKILL.md`: четыре конкретных текста исходов на кандидата (Specify — сценарий в строку; Dismiss — что не покрывается и почему допустимо; Backstop — какой тест; Defer — что остаётся открытым и до чего), токены — заголовки вариантов — проверка: `tests/test_skills.py`; кандидаты пробы на fixture несут разные тексты четырёх вариантов.
- [ ] 7.4 Отступление без замка: fixture журнала с фактом постановки, развилкой-отступлением и словом человека — проверка: `tests/test_journal_check.py` — `check` код 0; `attack/` строка по такой развилке — `справка` (правило в 7.1).

## 8. Инсталлятор (F-13.A, F-15.B, F-50.E, F-21.A, F-51.E, F-57.E)

- [x] 8.1 Payload и раскладка: `intent.md` в каталоге изменения, `.gigacode/` не создаётся и не читается, `.symphysis/` без переименования — проверка: `installer/test/install.test.js`, `installer/test/paths.test.js`; `grep -rn gigacode installer/lib` пусто.
- [x] 8.2 `install`: при обновлении схемы каждый пропущенный файл схемы — отдельной строкой с подсказкой `--force`; `check`: расхождение байтов схемы — `[!!]`, код 2 — проверка: `installer/test/install.test.js`, `installer/test/check.test.js` по сценарию «Обновление схемы».
- [x] 8.3 Телеметрия: `install` выставляет `telemetry.enabled: false` в глобальном конфиге OpenSpec, если ключ не задан (ключ допустим для `config set` — `upstream/openspec/src/core/config-schema.ts:63`); `check`: `[..] telemetry: выключена` код 0, «конфиг OpenSpec не найден» код 0, `[!!] telemetry: включена — выключить: openspec config set telemetry.enabled false` (предположение: код 2, как у расхождений установки; решить при ревью) — проверка: `installer/test/check.test.js`, `installer/test/install.test.js` с временным домашним каталогом по трём сценариям спеки.
- [x] 8.4 `installer/README.md`: раздел о телеметрии форка (наследуется от OpenSpec, выключена по умолчанию, команда выключения, `anonymousId` — идентификатор, политика upstream ссылкой) и раскладка входа `intent.md` — проверка: `grep -c -i telemetry installer/README.md` не меньше 1; `installer/test/cli.test.js` зелёный.
- [x] 8.5 Пин версии форка в `installer/lib/check.js` и `installer/test/check.test.js` — после 3.5 — проверка: `symphysis check --project X:\symphysis` печатает `check: ok`.

## 9. Документы

- [x] 9.1 `docs/dry-run-report.md`, раздел 3: кандидаты K2, K3, K10, K13 помечены решениями этого изменения (F-23, F-12, F-16, F-26) — проверка: строки таблицы кандидатов несут номера F.
- [x] 9.2 `CLAUDE.md` проекта: артефакт `intent`, optional-атаки и вызов атаки по имени, `/opsx:sync` до архива — проверка: чтение файла; `tests/test_skills.py` зелёный.
- [x] 9.3 `docs/plan-implementation.tasks.md`: часть «правки по калибровке» ссылкой на `openspec/changes/calibration-fixes/tasks.md` без дублирования списка — проверка: ссылка на месте.

## 10. Замер после правок (F-10.C, F-11.B)

- [ ] 10.1 Ограда: права на чтение `X:\demo-live\judge` и `X:\_archive\camunda-bid\yardstick` закрыты для контроллера и агента плеча; правило записано в `archive/RUN-PREP-symphysis-2026-10-30.md` §6 — проверка: чтение из-под учётки агента даёт отказ; строка в RUN-PREP.
- [ ] 10.2 Прогон плеча P-чел на camunda-bid с правками — новый run в `X:\demo-live\runs` — проверка: `status` плеча — планирование завершено; транскрипт и `score.json` на месте.
- [ ] 10.3 Поэлементное сравнение с текущими листами (К7, К3) и записка в `docs/analysis/` — проверка: таблица по пунктам с номерами F; вывод по правилу §4 RUN-PREP.
