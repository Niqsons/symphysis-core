# Spec Delta

## MODIFIED Requirements

### Requirement: Граф схемы начинается журналом и кончается атакой артефактов
Схема `symphysis` SHALL задавать артефакты в порядке зависимостей `intent` → `decisions` → `research` → `attack-decisions` → `proposal` → `specs` → `consequences` → `design` → `security`, `tasks` → `attack-artifacts`. Артефакт `intent` SHALL быть первым: файл `intent.md` в каталоге изменения несёт намерение человека его словами; если файла нет или он пуст, шаг схемы SHALL спросить намерение у человека и сохранить его слова дословно как `intent.md`, содержания модель не пишет; дальше файл не правится; схема SHALL NOT делать для `intent` исключений (F-13.A, F-19.A, F-24.E). Артефакты `attack-decisions` и `attack-artifacts` SHALL нести признак `optional`: пока их файла нет, они SHALL NOT блокировать зависящие артефакты и `isPlanningComplete`; вызванная атака SHALL оставаться гейтом — её файл с вердиктом не `passed` блокирует зависимые всегда, с чужим хешем целей (`stale`) — пока не начался следующий шаг: у `attack-decisions` — пока нет файла `proposal.md`, у `attack-artifacts` — пока в `tasks.md` нет отмеченной задачи; дальше `stale` — видимый сигнал, не гейт (F-06.A, F-26.E, F-64.B). `apply` SHALL требовать `tasks` и `status: passed` у `attack-artifacts`, если атака вызвана, с тем же окном для `stale` (F-04.A, F-13.B, F-06.A, F-64.B).
<!-- проба краёв: форма=collection, stateful, исходы: F-24 Specify, F-25 Specify, F-26 Specify -->
<!-- проба запретов: исходы: F-52 Specify -->

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

## ADDED Requirements

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
