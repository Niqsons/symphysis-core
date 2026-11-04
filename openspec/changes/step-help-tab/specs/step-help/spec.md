# Spec Delta

## ADDED Requirements

### Requirement: Вывод несёт карту ссылок
Вывод `step_help.py` SHALL нести поле `file_links`: ключ — путь или текст из вывода без хвоста `:строка`, значение — путь от корня проекта с разделителем `/`, без кодирования (F-44). В карту SHALL попадать только существующие файлы внутри корней улик и каталога изменения, их собирает общий код ядра. Абсолютных путей SHALL NOT быть (F-51). При сбое расчёта поле SHALL оставаться.

#### Scenario: Файл шага
- **GIVEN** `specs/a/spec.md` есть
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** его путь есть в `file_links`, а путь ещё не созданного `design.md` нет

#### Scenario: Файл в тексте шага
- **GIVEN** в тексте шага `` `tools/journal.py` `` и `` `нет.md` ``
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** в карте только первый, файл есть в проекте

#### Scenario: Путь с пробелом и кириллицей
- **GIVEN** файл шага `сп ек/a.md`
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** значение карты `openspec/changes/demo/сп ек/a.md`, без `%20`

#### Scenario: Сбой расчёта
- **GIVEN** `openspec` не найден
- **WHEN** выполняется `step_help.py`
- **THEN** код 1, поле `file_links` есть

#### Scenario: Перечень полей
- **GIVEN** тест формы вывода
- **WHEN** он сверяет поля
- **THEN** `file_links` в перечне, номер контракта прежний

<!-- проба краёв: форма=collection, text, исходы: нет -->
<!-- проба запретов: исходы: канон — F-54 → security.md -->

### Requirement: У шага есть поле `skills`
У каждого шага вывод SHALL нести поле `skills`: скиллы, названные в тексте шага, `name`, `path` и `base` (F-46, F-56). Поиск SHALL идти сначала в проекте, `.claude/skills`, `.opencode/skills`, `.agents/skills`, затем в каталоге из аргумента. `base` SHALL называть, от чего идёт путь: `project` или `install`; абсолютного пути SHALL NOT быть (F-51). Не найден — `path` равен `null`.

#### Scenario: Скилл в проекте
- **GIVEN** в тексте шага `` `symphysis-brainstorm` ``, файл `.claude/skills/symphysis-brainstorm/SKILL.md`
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** у шага запись с этим именем, путём от корня и `base` `project`, его путь есть и в `file_links`

#### Scenario: Порядок каталогов
- **GIVEN** файл скилла есть в `.claude/skills` и в `.opencode/skills`
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** путь из `.claude/skills`, запись одна

#### Scenario: Скилла нет
- **GIVEN** скилл назван, файла нигде нет
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** запись с этим именем, `path` равен `null`, код 0

#### Scenario: Шаг без скиллов
- **GIVEN** в тексте шага скилл не назван
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** поле `skills` — пустой список

#### Scenario: Схема без текстов
- **GIVEN** проект, где `steps.md` нет
- **WHEN** выполняется `step_help.py`
- **THEN** код 0, у шагов `skills` пуст

<!-- проба краёв: форма=collection, io, исходы: F-86 Dismiss -->
<!-- проба запретов: исходы: нет -->

### Requirement: Каталог установки задаётся необязательным аргументом
`step_help.py` SHALL принимать необязательный `--install-dir <каталог>`, где после проекта ищутся скиллы (F-46, F-62). Без аргумента поиск SHALL идти только в проекте: так считает страница. Номер контракта SHALL NOT расти (F-35). Каталога нет — не сбой: скилл просто SHALL считаться не найденным. Аргумент SHALL NOT менять корень проекта и файлы вывода.

#### Scenario: Скилл только в установке
- **GIVEN** файла скилла нет в проекте, он есть в каталоге установки
- **WHEN** выполняется `step_help.py --install-dir <каталог>`
- **THEN** путь от каталога установки, `base` `install`, строки каталога в выводе нет

#### Scenario: Проект важнее
- **GIVEN** файл скилла есть и в проекте, и в каталоге установки
- **WHEN** выполняется `step_help.py --install-dir <каталог>`
- **THEN** `base` `project`

#### Scenario: Каталога нет
- **GIVEN** `--install-dir` указывает на несуществующий каталог
- **WHEN** выполняется `step_help.py`
- **THEN** код 0, `path` равен `null`, `error` пуст

#### Scenario: Без аргумента
- **GIVEN** файл скилла только в каталоге установки
- **WHEN** выполняется `step_help.py`
- **THEN** `path` равен `null`

<!-- проба краёв: форма=text, io, исходы: нет -->
<!-- проба запретов: исходы: канон — F-88 → security.md -->

### Requirement: Текст текущего шага не повторяет счётчик задач
`current_text` на шаге `apply` SHALL NOT нести фразу о закрытых задачах: счётчик живёт в шапке (F-43, F-55). Поле `tasks` SHALL оставаться прежним, о том, что держит реализацию, текст SHALL говорить как раньше.

#### Scenario: Задачи идут
- **GIVEN** шаг `apply`, закрыто 2 из 5
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** в `current_text` нет слов «Задач закрыто», `tasks.complete` равно 2

#### Scenario: Реализация заблокирована
- **GIVEN** шаг `apply`, реализацию держит `security`
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** `current_text` называет `security`

<!-- проба краёв: форма=text, исходы: нет -->
<!-- проба запретов: исходы: нет -->
