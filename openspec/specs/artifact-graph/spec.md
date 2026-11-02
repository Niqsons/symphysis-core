# artifact-graph Specification

## Purpose
Граф артефактов схемы `symphysis`: журнал первым, исследование по парковкам, атака до proposal и после tasks, реализация только после вердикта; F-04, F-05, F-13.

## Requirements

### Requirement: Граф схемы начинается журналом и кончается атакой артефактов
Схема `symphysis` SHALL задавать артефакты в порядке зависимостей `intent` → `decisions` → `research` → `attack-decisions` → `proposal` → `specs` → `consequences` → `design` → `security`, `tasks` → `attack-artifacts`. Артефакт `intent` SHALL быть первым: файл `intent.md` в каталоге изменения несёт намерение человека его словами; если файла нет или он пуст, шаг схемы SHALL спросить намерение у человека и сохранить его слова дословно как `intent.md`, содержания модель не пишет; дальше файл не правится; схема SHALL NOT делать для `intent` исключений (F-13.A, F-19.A, F-24.E). Артефакты `attack-decisions` и `attack-artifacts` SHALL нести признак `optional`: пока их файла нет, они SHALL NOT блокировать зависящие артефакты и `isPlanningComplete`; вызванная атака SHALL оставаться гейтом — её файл с вердиктом не `passed` блокирует зависимые всегда, с чужим хешем целей (`stale`) — пока не начался следующий шаг: у `attack-decisions` — пока нет файла `proposal.md`, у `attack-artifacts` — пока в `tasks.md` нет отмеченной задачи; дальше `stale` — видимый сигнал, не гейт (F-06.A, F-26.E, F-64.B). `apply` SHALL требовать `tasks` и `status: passed` у `attack-artifacts`, если атака вызвана, с тем же окном для `stale` (F-04.A, F-13.B, F-06.A, F-64.B).

#### Scenario: Новое изменение
- **GIVEN** проект с `schema: symphysis` в `openspec/config.yaml` и изменение, созданное `openspec new change <имя>`
- **WHEN** выполняется `openspec status --change <имя> --json`
- **THEN** `intent` — `ready`, `decisions` — `blocked` до появления `intent.md`, `attack-decisions` и `attack-artifacts` помечены `optional`, `applyRequires` содержит `tasks`

#### Scenario: Схема проходит валидацию форка
- **GIVEN** каталог `openspec/schemas/symphysis/` в проекте
- **WHEN** выполняется `openspec schema validate symphysis --json`
- **THEN** `valid: true`, `issues: []`, и `schema which symphysis` называет источник `project`

#### Scenario: Планирование без вызванных атак
- **GIVEN** изменение, у которого написаны все артефакты, кроме `attack-decisions` и `attack-artifacts`
- **WHEN** выполняется `status --json`
- **THEN** `isPlanningComplete: true`; `proposal` и `apply` не ждут файлов атак

#### Scenario: Вызванная атака с gaps_found
- **GIVEN** `attack/artifacts.md` со `status: gaps_found`
- **WHEN** выполняется `status --json`
- **THEN** `attack-artifacts` — `verdict: mismatch`, `apply` заблокирован до `passed`

#### Scenario: Изменения, начатые до появления intent
- **GIVEN** изменения `symphysis-schema` и `calibration-fixes` без `intent.md`
- **WHEN** схема получает артефакт `intent`
- **THEN** у обоих до правки схемы написан `intent.md` из их источников (план реализации; слово владельца и разбор), и `status` ни у одного не ломается

#### Scenario: Намерение не записано
- **GIVEN** `intent.md` отсутствует или пуст (0 байт либо одна строка заголовка)
- **WHEN** человек зовёт `/opsx:continue` на изменении
- **THEN** человеку задан вопрос о намерении, его ответ сохранён дословно в `intent.md`, после чего `decisions` — `ready`; `intent.md`, принесённый человеком заранее, принимается как есть

#### Scenario: Намерение правится после круга
- **GIVEN** факты постановки с цитатами из `intent.md` и круг 1 закончен
- **WHEN** человек меняет `intent.md`
- **THEN** `check` даёт у этих фактов `[!!] цитаты нет дословно` с кодом 0, `status` не меняется, новые факты постановки по новому тексту заводятся только по слову человека

#### Scenario: Вердикт с чужим хешем
- **GIVEN** `attack/artifacts.md` со `status: passed`, чьи `targets[].sha256` не равны текущим хешам specs и design, и в `tasks.md` нет отмеченной задачи
- **WHEN** выполняется `status --json`
- **THEN** `attack-artifacts` — `verdict: stale`, `apply` заблокирован, `continue` зовёт атаку заново

#### Scenario: Устаревший вердикт после начала работы — сигнал
- **GIVEN** тот же `attack/artifacts.md`, и в `tasks.md` отмечена первая задача (`- [x]`)
- **WHEN** выполняются `status --json` и `openspec instructions apply --json`
- **THEN** `attack-artifacts` — `done` с `verdict: stale` и строкой «verdict is stale (signal, not a gate: tasks.md has a checked task)» в `nextSteps`; `apply` не заблокирован этим вердиктом
<!-- проба краёв: форма=collection, stateful, исходы: F-24 Specify, F-25 Specify, F-26 Specify -->
<!-- проба запретов: исходы: F-52 Specify -->

### Requirement: Исследование — файл на каждую парковку «материалы» с жанром
Артефакт `research` SHALL требовать по файлу `research/<F-NN>.md` на каждую парковку журнала с адресатом «материалы»; файл SHALL нести frontmatter `genre` из `устройство | размещение | края | проверка | аналоги`, `question` и `brief`, находки с `путь:строка «цитата»` из прочитанного файла и отрицания по рецепту «не найдено» + «искал: <шаблоны дословно>» (F-05.C). При нуле парковок «материалы» шаг SHALL писать один файл-отрицание `research/none.md` с тем же frontmatter (`question: none`) и отрицанием по рецепту, и этот файл SHALL считаться законным исходом артефакта; при появлении первой парковки «материалы» `none.md` SHALL удаляться (F-16.A, F-27.E).
<!-- проба краёв: форма=collection, io, исходы: F-27 Specify -->
<!-- проба запретов: исходы: нет -->

#### Scenario: Отчёт по парковке
- **GIVEN** запись F-NN с парковкой `addressee: материалы`
- **WHEN** артефакт `research` считается сделанным
- **THEN** существует `research/F-NN.md` с `question: F-NN`, одним значением `genre` и хотя бы одной строкой «Найдено» или «Не найдено» с «искал»

#### Scenario: Отрицание без шаблонов не принимается
- **GIVEN** отчёт со строкой «не найдено» без строки «искал:»
- **WHEN** атака артефактов проходит раздел `research/`
- **THEN** строка «отрицание без шаблонов поиска» с опорой «нет» — предположение: атака артефактов по схеме не целит `research/` (цели — specs, design, security, tasks); решить: добавить ли `research/**/*.md` в цели `attack-artifacts`

#### Scenario: Нуль парковок
- **GIVEN** журнал, в котором ни одна запись не несёт парковки с адресатом «материалы»
- **WHEN** выполняется шаг `research`
- **THEN** существует `research/none.md` с `question: none`, `genre` из списка, строкой «не найдено» с «искал: <шаблоны>» и перечнем записей с `addressee: материалы` на уровне записи как фактов; `status` показывает `research` — `done`

#### Scenario: Парковка после none.md
- **GIVEN** `research/none.md` и парковка «материалы», заведённая во втором круге
- **WHEN** шаг `research` пишет `research/F-NN.md`
- **THEN** `none.md` удалён, в каталоге остаются только отчёты по парковкам

### Requirement: Proposal называет отступления от постановки
Шаблон `proposal.md` схемы SHALL нести раздел «Отступления от постановки»; proposal SHALL перечислять в нём каждую решённую развилку, чей вариант противоречит сценарию факта с `addressee: постановка`, ссылкой на развилку и факт; уточнение без противоречия — не отступление; без таких развилок — строка «нет» (F-08.A, F-17.A, F-28.E).
<!-- проба краёв: форма=collection, исходы: F-28 Specify -->
<!-- проба запретов: исходы: нет -->

#### Scenario: Отступление видно в поставке
- **GIVEN** факт F-NN с `addressee: постановка` («пустой атрибут — дочерний без идентификатора») и развилка F-MM с пометкой «отступление от постановки», решённая вариантом «наследование»
- **WHEN** пишется `proposal.md`
- **THEN** раздел «Отступления от постановки» содержит строку «F-MM против F-NN» с выбранным вариантом, и читатель отличает отступление от требования

#### Scenario: Отступлений нет
- **GIVEN** журнал без развилок с пометкой «отступление от постановки»
- **WHEN** пишется `proposal.md`
- **THEN** раздел присутствует со строкой «нет»

#### Scenario: Уточнение без противоречия
- **GIVEN** развилка сужает критерий факта постановки так, что сценарий факта остаётся верным
- **WHEN** пишутся развилка и proposal
- **THEN** пометки «отступление от постановки» нет, в раздел развилка не попадает

### Requirement: Невызванная атака видна в status
`status --json` MUST NOT показывать изменение как проверенное, когда атаки не вызывались: у `optional`-артефакта без файла SHALL стоять `optional: true` и явный признак отсутствия файла; `isPlanningComplete: true` SHALL сопровождаться этим признаком, и `/opsx:apply` SHALL называть невызванные атаки человеку (F-52.E; проверка — тест форка).
<!-- проба краёв: форма=collection, исходы: кандидатов нет -->
<!-- проба запретов: исходы: нет -->

#### Scenario: Планирование завершено без атак
- **GIVEN** изменение со всеми артефактами, кроме файлов атак
- **WHEN** выполняется `status --json`
- **THEN** у `attack-decisions` и `attack-artifacts` — `optional: true`, файла нет, `isPlanningComplete: true`; тест форка проверяет оба поля, `/opsx:apply` печатает «атаки не вызывались: attack-decisions, attack-artifacts»

### Requirement: Артефакт `consequences` стоит между `specs` и `design`
Схема `symphysis` SHALL задавать обязательный артефакт `consequences` с файлом `consequences.md`, который требует `specs`, а `design` SHALL требовать `consequences`; прочий порядок не меняется, для этого артефакта форк OpenSpec SHALL NOT меняться (F-13.A, F-04).

#### Scenario: Дизайн ждёт опись
- **GIVEN** изменение с готовыми `specs` и без `consequences.md`
- **WHEN** выполняется `openspec status --change <имя> --json`
- **THEN** `consequences` — `ready`, `design` — `blocked` с `missingDeps`, содержащим `consequences`, `isPlanningComplete` — `false`

#### Scenario: Опись открывает дизайн
- **GIVEN** то же изменение после появления `consequences.md`
- **WHEN** выполняется `openspec status --change <имя> --json`
- **THEN** `consequences` — `done`, `design` — `ready`

#### Scenario: Инструкция шага
- **GIVEN** изменение с готовыми `specs`
- **WHEN** выполняется `openspec instructions consequences --change <имя>`
- **THEN** вывод несёт шаблон `consequences.md` и называет скилл шага по имени — предположение: имя скилла `symphysis-consequences`; решить при реализации

#### Scenario: Схема проходит валидацию форка
- **GIVEN** схема с артефактом `consequences` и форк по текущему пину
- **WHEN** выполняется `openspec schema validate symphysis --json`
- **THEN** `valid: true`, `issues: []`

#### Scenario: Изменение, начатое до артефакта
- **GIVEN** изменение с `design.md` без `consequences.md`
- **WHEN** схема получает артефакт
- **THEN** до правки схемы у него написан `consequences.md` с причиной «шаг появился позже», `status` не ломается, сверки мест у него нет (F-128.A)

<!-- проба краёв: форма=collection, stateful, исходы: F-60 Specify, F-61 Specify, F-62 Backstop, F-63 Dismiss -->
<!-- проба запретов: исходы: нет -->
<!-- проба краёв, без кандидата: idempotency — край повторного шага F-44 -->
