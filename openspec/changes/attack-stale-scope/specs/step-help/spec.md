# Spec Delta

## ADDED Requirements

### Requirement: Страница шага атаки несёт вердикт и состав
У страницы шага, для которого `openspec status` отдаёт `verdict`, вывод `step_help.py` SHALL нести поле `verdict` с этим значением (`ok`, `stale`, `mismatch`, `missing`) и поле `stale_scope` — список строк состава по `stale-verdict-scope` при `stale`, иначе пустой; у шагов без `verdict` в `status` обоих полей SHALL NOT быть. Поля новые: номер контракта SHALL NOT расти (F-19, F-13, F-11).

#### Scenario: Вердикт устарел после proposal
- **GIVEN** `attack/decisions.md` со `status: passed`, журнал дописан, `proposal.md` есть
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** у страницы `attack-decisions` поле `verdict` равно `stale`, `stale_scope` несёт строку «после вердикта добавлено N записей: …»

#### Scenario: Вердикт в силе
- **GIVEN** `attack/decisions.md` со `status: passed`, хеш журнала совпал
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** `verdict` равно `ok`, `stale_scope` — пустой список

#### Scenario: Шаг без вердикта
- **GIVEN** страница шага `design`
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** полей `verdict` и `stale_scope` у неё нет

#### Scenario: Атака не вызвана
- **GIVEN** `attack-decisions` без файла, `status` отдаёт его без `verdict`
- **WHEN** выполняется `step_help.py --change demo`
- **THEN** полей `verdict` и `stale_scope` у страницы нет

<!-- проба краёв: форма=io, collection, text, исходы: нет -->
<!-- проба запретов: исходы: нет -->

## MODIFIED Requirements

### Requirement: Справка не выдаёт наличие файла за сделанную работу
Вывод и страница SHALL NOT утверждать, что шаг выполняется прямо сейчас: они SHALL называть текущий шаг как следующий по файлам и чей ход (F-19). Про готовый шаг SHALL быть сказано: файл есть, содержание не проверялось (F-24); у шага с вердиктом вместо этой пометки SHALL стоять вердикт и состав по «Страница шага атаки несёт вердикт и состав» (F-19, F-11 этого изменения). Признаков незавершённости сверх статуса с вердиктом, открытых развилок и задач скрипт SHALL NOT считать (F-24).

#### Scenario: Пустой файл шага
- **GIVEN** `design.md` нулевой длины, `status` считает шаг готовым
- **WHEN** человек открывает страницу шага `design`
- **THEN** шаг показан готовым с пометкой «файл есть, содержание не проверялось»

#### Scenario: Формулировка текущего шага
- **GIVEN** любое изменение с готовым к работе шагом
- **WHEN** тест читает текст текущего шага в выводе
- **THEN** слова «выполняется» в нём нет

#### Scenario: Готовый шаг атаки
- **GIVEN** `attack/decisions.md` со `status: passed`, `status` отдаёт `verdict: stale`
- **WHEN** человек открывает страницу шага `attack-decisions`
- **THEN** пометки «файл есть, содержание не проверялось» нет, показаны вердикт `stale` и строки состава

<!-- проба краёв: форма=text, io, исходы: нет -->
<!-- проба запретов: исходы: нет -->
