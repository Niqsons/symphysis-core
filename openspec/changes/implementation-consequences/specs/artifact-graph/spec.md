# Spec Delta

## ADDED Requirements

### Requirement: Артефакт `consequences` стоит между `specs` и `design`
Схема `symphysis` SHALL задавать обязательный артефакт `consequences` с файлом `consequences.md`, который требует `specs`, а `design` SHALL требовать `consequences`; требование дополняет «Граф схемы начинается журналом и кончается атакой артефактов»: прочий порядок не меняется, форк OpenSpec SHALL NOT меняться (F-13.A, F-04).
<!-- проба краёв: форма=collection, stateful, исходы: F-60 Specify, F-61 Specify, F-62 Backstop, F-63 Dismiss -->
<!-- проба запретов: исходы: нет -->

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

#### Scenario: Схема проходит валидацию форка той же версии
- **GIVEN** схема с артефактом `consequences` и форк по текущему пину
- **WHEN** выполняется `openspec schema validate symphysis --json`
- **THEN** `valid: true`, `issues: []`, пин форка не менялся

#### Scenario: Изменение, начатое до артефакта
- **GIVEN** изменение с `design.md` без `consequences.md`
- **WHEN** схема получает артефакт
- **THEN** до правки схемы у него написан `consequences.md` с причиной «шаг появился позже», `status` не ломается

#### Scenario: Файл без описи и без причины
- **GIVEN** `consequences.md` без описи и без причины
- **WHEN** выполняется `journal.py check`
- **THEN** `[!!] consequences.md: нет ни описи, ни причины`, код 0; `status` не меняется
<!-- проба краёв, без кандидата: idempotency — край повторного шага F-44 -->
