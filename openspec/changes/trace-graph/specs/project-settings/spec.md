# Spec Delta

## MODIFIED Requirements

### Requirement: `symphysis.yaml` в корне проекта задаёт выбор перед запуском шага
Файл `symphysis.yaml` в корне проекта, вне `.symphysis/`, SHALL задавать выборы вложенными ключами: `consequences.failure_branches`, `consequences.assumptions`, `edge_probe.enabled` и ключ на каждую линзу атаки; отсутствие файла или ключа SHALL означать «включено» (F-24.A, F-110.B, F-61, F-63, слова владельца к F-14 и F-18, F-23). предположение: имена ключей линз; решить в design.

#### Scenario: Файла нет
- **GIVEN** проект без `symphysis.yaml`
- **WHEN** начинается шаг `consequences` или проба краёв
- **THEN** ветки отказа, допущения и проба краёв считаются включёнными

#### Scenario: Ключа нет
- **GIVEN** `symphysis.yaml`, где задан только `consequences.assumptions: false`
- **WHEN** начинается шаг `consequences`
- **THEN** допущения выключены, ветки отказа включены

#### Scenario: Файл переживает обновление установки
- **GIVEN** `symphysis.yaml` с правками человека
- **WHEN** выполняется `symphysis install --force`
- **THEN** файл не изменён, а каталог `.symphysis/` обновлён

#### Scenario: Значение не из true и false
- **GIVEN** непустое значение не из `true | false`; пустое значение равно отсутствию ключа (F-109.A)
- **WHEN** файл читают `symphysis check` и скрипт настроек
- **THEN** выбор считается включённым, оба дают `[!!] symphysis.yaml: недопустимое значение <значение>`; у `symphysis check` код 2, у скрипта код 0, с `--strict` 2

#### Scenario: Линзы по умолчанию
- **GIVEN** проект без `symphysis.yaml`
- **WHEN** скилл атаки узнаёт состав скриптом настроек
- **THEN** все линзы обоих файлов атаки включены

#### Scenario: Выключена одна линза
- **GIVEN** `symphysis.yaml`, где выключена одна линза
- **WHEN** выполняется скрипт настроек
- **THEN** вывод называет эту линзу выключенной, остальные включёнными

#### Scenario: Новая установка называет линзы
- **GIVEN** проект без `symphysis.yaml`
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** созданный файл несёт ключ каждой линзы, все включены

#### Scenario: Неизвестная линза
<!-- F-108 -->
- **GIVEN** ключ линзы с неизвестным слугом
- **WHEN** выполняются `symphysis check` и скрипт настроек
- **THEN** `[!!] symphysis.yaml: неизвестная линза <имя>`, этот ключ ни одной линзы не выключает
<!-- проба краёв: форма=text, исходы: F-50 Backstop, F-51 Specify -->
<!-- проба запретов: исходы: F-94 Specify; канон — F-103 → security.md -->
<!-- проба краёв: форма=text, collection, исходы: F-109 Dismiss, F-108 Specify -->
<!-- проба запретов: исходы: нет -->
