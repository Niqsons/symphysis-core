# Spec Delta

## ADDED Requirements

### Requirement: Артефакт `consequences` стоит между `specs` и `design`
Схема `symphysis` SHALL задавать обязательный артефакт `consequences` с файлом `consequences.md`, который требует `specs`, а `design` SHALL требовать `consequences`; требование дополняет «Граф схемы начинается журналом и кончается атакой артефактов»: прочий порядок не меняется, форк OpenSpec SHALL NOT меняться (F-13.A, F-04).
<!-- проба краёв: форма=collection, stateful, исходы: F-60 открыт, F-61 открыт, F-62 открыт, F-63 открыт -->
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
<!-- проба краёв, без кандидата: idempotency — край повторного шага F-44 -->
