# Spec Delta

## ADDED Requirements

### Requirement: README модуля схемы в проект не ставится
`symphysis install` SHALL ставить из каталога схемы только файлы схемы: `README.md` модуля схемы SHALL NOT попадать ни в payload, ни в `openspec/schemas/symphysis/` проекта, а `symphysis check` SHALL NOT называть его отсутствие расхождением (F-36).

#### Scenario: Установка без README схемы
- **GIVEN** в каталоге схемы репозитория лежит `README.md` модуля
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** в `openspec/schemas/symphysis/` проекта есть `schema.yaml`, `templates/` и `steps.md`, а `README.md` нет

#### Scenario: Сверка не ждёт README
- **GIVEN** проект после `symphysis install`
- **WHEN** выполняется `symphysis check`
- **THEN** строки о `README.md` каталога схемы нет
<!-- проба краёв: форма=io, collection, stateful, исходы: нет -->
<!-- проба запретов: исходы: нет -->
