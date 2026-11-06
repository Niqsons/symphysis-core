# Spec Delta

## MODIFIED Requirements

### Requirement: `check`, запущенный из клона, сигналит устаревший `payload`
Команда `symphysis check`, запущенная из клона репозитория, SHALL сравнивать `payload` инсталлятора с исходниками и при расхождении SHALL давать `[!!]` и код 2: иначе после `git pull` установка молча кладёт старую версию (F-114.A).

#### Scenario: `payload` старее исходников
- **GIVEN** клон после `git pull` с новыми исходниками и прежний `installer/payload`
- **WHEN** выполняется `node installer/bin/symphysis.js check --project <каталог>`
- **THEN** stdout несёт `[!!] payload старее исходников — выполнить: npm --prefix installer ci`, код 2

#### Scenario: Инсталлятор не из клона
- **GIVEN** инсталлятор из тарбола, исходников рядом с ним нет
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** этой сверки нет, строки о `payload` нет

#### Scenario: Клон в модульной раскладке
<!-- F-60 -->
- **GIVEN** клон в модульной раскладке без каталога `skills/` и прежний `installer/payload`
- **WHEN** из клона выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[!!] payload старее исходников — выполнить: npm --prefix installer ci`, код 2
<!-- проба краёв: форма=io, collection, исходы: F-60 Specify -->
<!-- проба запретов: исходы: нет -->

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
