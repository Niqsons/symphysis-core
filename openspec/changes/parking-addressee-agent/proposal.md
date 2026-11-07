# Proposal

## Why

Адресат парковки `материалы` называет вещь, а не того, кто отвечает: слово владельца — «адресация идет к кому-то, а не к чему-то» (F-01), и человеку, который выбирает эту парковку на странице или в плагине, «слабо понятно, что это означает» (F-02). Владелец выбрал вариант A развилки Р2 ревью: переименовать значение в `агент` везде, поднять номер контракта, обновить плагин с `Needs:` (F-03, F-04). Глоссарий `terms.md` и тела скиллов `symphysis-brainstorm` и `symphysis-research` уже обещают это переименование «отдельным изменением» (F-14) — это оно. Смена значения существующего поля по `docs/repo-contract.md` — смена контракта ядра с плагином (F-09), поэтому делается одним изменением, а не правкой по ходу ревью.

Пятый критерий намерения — водитель исследования как агент общего назначения с правом поиска и проб — код уже выполняет (F-13); это изменение прав водителя не трогает.

## What Changes

- **BREAKING** Значение адресата `материалы` → `агент` в обоих перечислениях схемы журнала — у адресата парковки и у адресата записи (F-06). Новые записи и парковки несут только `агент`; `материалы` остаётся в обоих enum как значение старых журналов, по образцу `recommendation.text` (F-17.A, F-11): архивные журналы и `docs/plan-implementation.journal.json` не правятся, тест `LIVE_JOURNALS` проходит без переписывания данных.
- **BREAKING** Грамматика `apply`: кортеж `PARKING_ADDRESSEES` — `агент | человек | ИБ`; строка «припарковано → агент — «текст»»; строка со старым значением получает отказ кодом 1 (F-07, F-17.A).
- Рендер и CLI: ключ назначения `агент` → `research/` в `PARKING_ANSWERS` и в `parkingDestination` страницы; сигнал `check` — «парковка «агент» без finding при research/F-NN.md» (F-08).
- Страница `symphysis.html`: список `ADDRESSEES`, подсказка `PARK_HINT` («агент» — ответ ищет агент исследования, в файлах или пробой), назначение парковки (F-08, F-02).
- Скиллы и схема шага: тела `symphysis-brainstorm`, `symphysis-research` и его водитель, `symphysis-attack`, `symphysis-viewer`, глоссарий `terms.md`; `schema.yaml`, `steps.md`, правило `rules.decisions` в `config.symphysis.yaml` и `openspec/config.yaml`, шаблон `templates/research.md`. Строка счёта круга — «парковок агенту P». Оговорки «переименование идёт отдельным изменением» снимаются (F-12, F-14, F-18.A).
- Переименование идёт по значению и по падежам, не по слову: места в дательном падеже «материалам» (строка счёта круга, `docs/GUIDE.md`, `steps.md`, мастер-спека `brainstorm-interview`, `research/README.md`) правятся, слово «материалы» в смысле «материалы изменения» («Прочитай материалы», «где искать материалы») не трогается (F-12).
- Мастер-спеки — дельтами трёх capabilities, см. ниже (F-06, F-12).
- Тесты и фикстуры: одиннадцать файлов тестов модулей и схемы, фикстуры `change-demo*`, `answers-round1.md`, `journal-plan*.md`; тест страницы сверяет строку `ADDRESSEES` дословно (F-08, F-12).
- Живые документы: `CLAUDE.md` «Ограничения схемы», `docs/GUIDE.md`, `docs/playground-template-llm-pipeline.md`; `docs/repo-contract.md` получает абзац «С номера 4 …» по образцу абзацев о номерах 2 и 3 (F-09, F-18.A).
- **BREAKING** Контракт ядра с плагином: `CONTRACT = 4` в `journal_render.py`, то же число отдаёт `step_help.py`; коммит ядра называет смену в `Why:` (F-09). Плагин номера 3 с ядром 4 показывает «поставь новый .vsix» и решений не вносит, страница работает (F-10, F-19.A).
- Производные копии: после переименования — `scripts/sync-payload.js`, затем `symphysis install --force` в клоне (F-15).

Не меняется этим изменением:

- данные архива и журнала плана (F-17.A);
- датированные тексты: восемь разборов `docs/analysis/`, отчёты `docs/dry-run-*.md`, планы `docs/plan-*.md`, `docs/recieve-answers.md` (F-18.A);
- права и инструменты водителя исследования (F-13);
- форк `upstream/openspec` — значения не несёт (F-15);
- плагин `symphysis-vscode`: его половина — `ADDRESSEES`, `PARK_HINT`, `EXPECTED_CONTRACT = 4`, тесты, подстановка `CONTRACT = 4` в e2e, коммит с `Needs:` на коммит ядра — идёт пунктом бэклога для сессии плагина, как у `attack-warning-read` (F-19.A, F-16, F-10).

## Capabilities

### New Capabilities

нет

### Modified Capabilities

- `decision-journal`: требование «Обратимость, адресат парковки и исход — из закрытых списков с причиной» — `parking[].addressee` из `агент | человек | ИБ`, `addressee` записи из `агент | человек | ИБ | постановка | ""`; старое значение `материалы` допустимо только как значение старых журналов, новые записи его не пишут; сигнал `check` о парковке без `finding` называет «агент»; сценарии с `addressee: материалы` переписываются на `агент` (F-06, F-08, F-17.A).
- `brainstorm-interview`: маршрут «не прочитать сейчас» — парковка `addressee: агент`; строка закрытия круга «парковок агенту P»; вопрос о новом круге при парковках агенту задаёт `research` (F-12, F-18.A).
- `artifact-graph`: требование «Исследование — файл на каждую парковку «материалы» с жанром» переименовывается в «… парковку «агент» с жанром» (F-21) — парковка адресату «агент»; `none.md` при нуле парковок «агент» с перечнем записей `addressee: агент`; сценарий «Подсказка адресата» — у «агент» сказано, что ответ ищет агент исследования, в файлах или пробой (F-08, F-12).
- `plugin-core-contract`: требование «`view-json` отдаёт номер контракта» — смена значения адресата есть смена контракта: номер 4, `Why:` в коммите ядра, плагин догоняет коммитом с `Needs:` (F-03, F-04, F-09, F-10, F-19.A).

Длинные мастер-требования в MODIFIED делятся на дочерние по правилу `trace-conventions` (F-20): родитель укладывается в 500 знаков, вынесенное стоит в дочерних требованиях со своими сценариями.

## Impact

- Код ядра: `decisions/journal.schema.json` (два enum), `decisions/journal_apply.py` (`PARKING_ADDRESSEES`, отказ), `decisions/journal_render.py` (`PARKING_ANSWERS`, `CONTRACT`), `cli/journal_cli.py` (текст сигнала), `viewer/playground-template.html` (`ADDRESSEES`, `PARK_HINT`, `parkingDestination`) — F-06, F-07, F-08, F-09.
- Схема шага и скиллы: `openspec/schemas/symphysis/{schema.yaml, steps.md, config.symphysis.yaml, templates/research.md}`, `openspec/config.yaml`, `decisions/skills/symphysis-brainstorm`, `research/skills/symphysis-research`, `research/agents/symphysis-research-driver.md`, `research/README.md`, `attack/skills/symphysis-attack`, `viewer/skills/symphysis-viewer`, `skill-shared/terms.md` — F-12, F-14.
- Мастер-спеки через `/opsx:sync`: `decision-journal`, `brainstorm-interview`, `artifact-graph`.
- Тесты: `decisions/tests/` (schema, apply, check, render, design, view_json), `viewer/tests/` (page, browser), `openspec/schemas/symphysis/tests/test_schema.py`, `tests/test_skills.py`; фикстуры `tests/fixtures/` — F-08, F-12.
- Документы: `CLAUDE.md`, `docs/GUIDE.md`, `docs/repo-contract.md`, `docs/playground-template-llm-pipeline.md` — F-09, F-18.A.
- Контракт с плагином: номер 4; плагин до своей сессии несовместим с новым ядром и говорит об этом сам; пункт бэклога с составом из F-10 и `Needs:` на коммит ядра — F-09, F-10, F-19.A, F-16.
- Инсталлятор: `installer/payload/` регенерируется, версия форка не меняется — F-15.

## Отступления от постановки

нет
