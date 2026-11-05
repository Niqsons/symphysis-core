# Spec Delta

## ADDED Requirements

### Requirement: `install` ставит скрипт графа
Команда `symphysis install` SHALL класть скрипт графа в `.symphysis/tools/`: файл SHALL входить в payload и его перечень (F-39). `symphysis check` SHALL называть его пропажу (F-126).

#### Scenario: Новый проект
- **GIVEN** проект без инструментов symphysis
- **WHEN** выполняется `symphysis install` и затем скрипт графа с `--help` из корня проекта
- **THEN** скрипт лежит в `.symphysis/tools/` и печатает помощь

#### Scenario: Обновление без `--force`
- **GIVEN** проект с инструментами до этого изменения
- **WHEN** выполняется `symphysis install` без `--force`
- **THEN** скрипт положен, отличающиеся файлы названы пропущенными с подсказкой `--force`

#### Scenario: Скрипта нет при проверке установки
<!-- F-126 -->
- **GIVEN** проект без скрипта графа
- **WHEN** выполняется `symphysis check`
- **THEN** находка называет файл скрипта и «нет файла», код 2
<!-- проба краёв: форма=stateful, io, исходы: нет -->
<!-- проба запретов: исходы: нет -->

### Requirement: `install` переносит подсказки операций
Кроме `schema` и `rules` слияние `openspec/config.yaml` SHALL переносить ключ `operations` из конфига symphysis, чтобы подсказка заморозки дошла до проекта (F-08, F-49). Списки подсказок SHALL объединяться, как `rules`: чужие подсказки остаются, старые человек удаляет руками (F-110, F-124).

#### Scenario: Конфиг без подсказок
- **GIVEN** `openspec/config.yaml` без ключа `operations`
- **WHEN** выполняется `symphysis install`
- **THEN** `openspec instructions archive --json` отдаёт подсказку заморозки полем `operationGuidance`

#### Scenario: У проекта своя подсказка
- **GIVEN** `openspec/config.yaml` со своей строкой в `operations.archive.guidance`
- **WHEN** выполняется `symphysis install`
- **THEN** своя строка на месте, подсказка заморозки добавлена

#### Scenario: Повторная установка не дублирует
- **GIVEN** проект после `symphysis install`
- **WHEN** `symphysis install` выполняется снова
- **THEN** подсказка заморозки стоит в списке один раз
<!-- проба краёв: форма=collection, stateful, исходы: F-110 Dismiss -->
<!-- проба запретов: исходы: нет -->
