# Spec Delta

## MODIFIED Requirements

### Requirement: Скрипт считает текущий шаг и чей ход
`step_help.py` SHALL называть один текущий шаг и чей ход по `openspec status`, журналу и задачам (F-19, F-23, F-26). При развилках со `status: открыт` текущим SHALL быть `viewer`, ход человека (F-08, F-40). Иначе SHALL быть первый `ready`, кроме необязательного без файла, как у `/opsx:continue`, ход модели, а у `intent` человека (F-09, F-27, F-55). Таких нет — SHALL быть `apply`, после закрытых задач `sync` (F-12, F-13). Нечитаемый журнал SHALL NOT давать «открытых 0» (F-41).

#### Scenario: Открытая развилка при готовом следующем шаге
- **GIVEN** журнал с открытой развилкой, а `status` называет `research` готовым
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** текущий шаг `viewer`, ход человека, в выводе число открытых развилок и следующий по `status` шаг `research`

#### Scenario: Припаркованная развилка
- **GIVEN** журнал с одной припаркованной развилкой и без открытых
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** открытых 0, припаркованных 1, ход не человека, текущий шаг по `status`

#### Scenario: Журнал не читается
- **GIVEN** `decisions.json` равен `{}` или содержит ошибку синтаксиса, `status` называет следующим `research`
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** код 0, текущий шаг `research`, в выводе `журнал не читается` вместо числа открытых, показ говорит это словами

#### Scenario: Несколько готовых шагов после `specs`
- **GIVEN** `specs` готов, `ready` у `attack-decisions`, `consequences` и `security`, файла `attack/decisions.md` нет
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** текущий шаг `consequences`, ход модели

#### Scenario: Вызванная атака
- **GIVEN** необязательный `attack-artifacts` с файлом и статусом `ready`, остальные артефакты готовы
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** текущий шаг `attack-artifacts`

#### Scenario: Задачи идут
- **GIVEN** все обязательные артефакты готовы, `instructions apply` отвечает `state=ready`, закрыто 2 из 5
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** текущий шаг `apply`, ход модели, в выводе `total` 5, `complete` 2, `remaining` 3

#### Scenario: Задачи закрыты
- **GIVEN** `instructions apply` отвечает `state=all_done`
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** текущий шаг `sync`, следующий `archive`, а текст говорит, что сделана ли синхронизация, скрипт не видит

#### Scenario: Реализация заблокирована
- **GIVEN** готовых артефактов нет, `instructions apply` отвечает `state=blocked` и называет `security`
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** текущий шаг `apply`, в выводе `security` назван тем, что мешает

#### Scenario: Активных изменений нет
- **GIVEN** проект с установленной схемой без активных изменений
- **WHEN** выполняется `step_help.py`
- **THEN** код 0, `change` равно `null`, текущий шаг `intent`, ход человека

#### Scenario: Изменение только что создано
- **GIVEN** изменение без единого файла шага
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** текущий шаг `intent`, ход человека

#### Scenario: Первые шаги пропущены
- **GIVEN** есть только `proposal.md`, `status` считает готовыми `intent` и `specs`
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** текущий шаг `intent`, как у `/opsx:continue`, ход человека, а у `specs` в списке состояние `ready`

#### Scenario: Текущий шаг совпадает с командой
- **GIVEN** изменение без открытых развилок и с готовым к работе артефактом
- **WHEN** тест сравнивает текущий шаг с шагом, который называет `nextSteps`
- **THEN** это один шаг; разошлись — тест красный
<!-- проба краёв: форма=collection, io, исходы: нет -->
<!-- проба запретов: исходы: нет -->

### Requirement: Справка не становится гейтом и не меняет файлы
`step_help.py` MUST NOT менять файлы проекта: он пишет только в stdout. Скиллы и инструкции схемы MUST NOT звать его перед шагом, а его вывод MUST NOT останавливать шаг или подменять шаг, названный человеком (F-50).

#### Scenario: Дерево проекта не меняется
- **GIVEN** проект с активным изменением
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** тест видит дерево проекта до и после байт в байт

#### Scenario: Скиллы о скрипте не знают
- **GIVEN** тексты скиллов `symphysis-*` и `schema.yaml`, где бы скиллы ни лежали в репозитории (F-26)
- **WHEN** тест ищет имя `step_help`
- **THEN** вхождений нет

#### Scenario: Поиск не нашёл скиллов
<!-- F-54 -->
- **GIVEN** раскладка, где поиск не нашёл ни одного `SKILL.md`
- **WHEN** тест ищет имя `step_help`
- **THEN** тест красный: скиллов ноль
<!-- проба краёв: форма=io, collection, исходы: F-54 Specify -->
<!-- проба запретов: исходы: нет -->
