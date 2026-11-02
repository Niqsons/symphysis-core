# Spec Delta

## ADDED Requirements

### Requirement: `install` ставит скрипт справки и тексты шагов
Команда `symphysis install` SHALL класть `step_help.py` в `.symphysis/tools/` и `steps.md` в `openspec/schemas/symphysis/`: оба файла SHALL входить в payload и его перечень (F-16, F-20, F-23). `check` SHALL сверять `steps.md` с payload так же, как остальную схему.

#### Scenario: Новый проект
- **GIVEN** проект без инструментов symphysis
- **WHEN** выполняется `symphysis install` и затем `python .symphysis/tools/step_help.py` из корня проекта
- **THEN** оба файла на месте, скрипт печатает JSON, текущий шаг `intent`, тексты шагов не пусты

#### Scenario: Обновление без `--force`
- **GIVEN** проект с инструментами до этого изменения
- **WHEN** выполняется `symphysis install` без `--force`
- **THEN** новые файлы положены, отличающиеся названы пропущенными с подсказкой `--force`

<!-- проба краёв: форма=stateful, io, исходы: нет -->
<!-- проба запретов: исходы: нет -->

### Requirement: `install` записывает версию symphysis
Команда `symphysis install` SHALL записывать в `.symphysis/tools/symphysis-version.txt` версию из `installer/package.json` и короткий хеш клона: `0.1.0+aa50e8f`; без git или при payload старее исходников — только версию (F-36, F-64). Файл SHALL описывать поставленные инструменты: отличающийся SHALL пропускаться без `--force`, как остальные. `check` SHALL NOT сверять этот файл и SHALL NOT давать по нему сигнал (F-36).

#### Scenario: Установка из клона
- **GIVEN** клон на коммите `aa50e8f`, `installer/package.json` с версией `0.1.0`
- **WHEN** выполняется `symphysis install`
- **THEN** файл содержит `0.1.0+aa50e8f`

#### Scenario: Установка без git
- **GIVEN** пакет вне репозитория git
- **WHEN** выполняется `symphysis install`
- **THEN** файл содержит `0.1.0`, код 0

#### Scenario: Клон обновлён, инструменты нет
- **GIVEN** файл содержит `0.1.0+aa50e8f`, клон на другом коммите, payload собран заново
- **WHEN** выполняется `symphysis install` без `--force`
- **THEN** файл не меняется и назван пропущенным; с `--force` содержит новый хеш

#### Scenario: Сигнала `check` нет
- **GIVEN** файл версии с другим хешем или файла нет
- **WHEN** выполняется `symphysis check`
- **THEN** строк `[!!]` о файле версии нет

#### Scenario: Payload старее исходников
- **GIVEN** payload старее исходников
- **WHEN** выполняется `symphysis install`
- **THEN** файл версии содержит только `0.1.0`, без хеша

<!-- проба краёв: форма=stateful, text, исходы: нет -->
<!-- проба запретов: исходы: нет -->
