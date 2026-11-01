# Spec Delta

## ADDED Requirements

### Requirement: `install` добавляет workflow `continue` и обновляет проект
Команда `symphysis install` SHALL добавлять `continue` в список workflow глобального конфига OpenSpec через `config set` форка, не убирая уже заданные, и обновлять проект так, чтобы в нём появилась `/opsx:continue`; форк SHALL NOT меняться. Требование дополняет «`install` ставит схему, скиллы и инструменты в проект и сливает конфиг» (F-32.A).

#### Scenario: Чистая установка
- **GIVEN** проект после `openspec init --tools claude` и глобальный конфиг без `continue` в списке workflow
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** появляется `.claude/commands/opsx/continue.md`, stdout называет правку глобального конфига

#### Scenario: Список человека сохраняется
- **GIVEN** глобальный конфиг с workflow `propose`, `apply`, `verify`
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** в списке те же три и `continue`

#### Scenario: Тесты не трогают настоящий конфиг
- **GIVEN** `XDG_CONFIG_HOME`, указанный во временный каталог
- **WHEN** тесты инсталлятора вызывают `install`
- **THEN** настоящий глобальный конфиг OpenSpec не изменён байт в байт

#### Scenario: Профиль core на чистой установке
- **GIVEN** глобальный конфиг с `profile: core` без `workflows`
- **WHEN** выполняется `install`
- **THEN** `profile: custom`, `workflows` — шесть профиля `core` и `continue`, stdout называет обе правки, `/opsx:continue` есть

#### Scenario: Workflow уже в списке
- **GIVEN** `continue` в списке и команда в проекте
- **WHEN** `install` выполняется снова
- **THEN** глобальный конфиг не изменён байт в байт, обновление проекта не зовётся, строки о workflow в stdout нет

#### Scenario: Форка нет или клиент не настроен
- **GIVEN** форка нет в PATH или проект без настроенного клиента
- **WHEN** выполняется `install`
- **THEN** схема и скиллы поставлены, stdout называет команду для выполнения позже, код 0; `check` даёт `[!!] continue`
<!-- проба краёв: форма=stateful, io, collection, исходы: F-79 Specify, F-80 Specify, F-81 Specify -->
<!-- проба запретов: исходы: F-100 Specify -->
<!-- проба краёв, без кандидата: empty, ordering — порядок и пустой список закрывает вариант A края F-79 -->

### Requirement: `install` меняет в глобальном конфиге только названное
Команда `symphysis install` MUST NOT менять в глобальном конфиге OpenSpec что-либо, кроме добавления `continue`, названной смены профиля и `telemetry.enabled: false` при незаданном ключе; stdout SHALL называть каждую правку (F-100.A, F-79.A, F-107.A).

#### Scenario: Конфиг до и после
- **GIVEN** временный глобальный конфиг: один случай с заданной человеком телеметрией, другой без ключа
- **WHEN** тест вызывает `install` и сравнивает конфиг до и после
- **THEN** различие — только добавление `continue`, названная смена профиля и `telemetry.enabled: false` во втором случае; заданное человеком значение не изменено, stdout называет каждую правку
<!-- требование из F-100; пробами не проходило -->

### Requirement: `check` называет отсутствие команды `/opsx:continue`
Команда `symphysis check` SHALL давать строку `[!!]` и код 2, если в проекте нет команды `/opsx:continue`, и SHALL называть команду, которая её ставит. Требование дополняет «`check` называет расхождения и версию форка, не чинит» (F-32.A, F-29).

#### Scenario: Команды нет
- **GIVEN** проект, где схема цела, а `.claude/commands/opsx/continue.md` и скилла `openspec-continue-change` нет (F-82.A)
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[!!] continue: команда /opsx:continue не установлена у <клиент> — выполнить: symphysis install`, код 2

#### Scenario: Команда есть
- **GIVEN** проект после `install`
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** строки `[!!] continue` нет

#### Scenario: Команда у настроенного клиента
- **GIVEN** проект с настроенным клиентом
- **WHEN** выполняется `check`
- **THEN** команда считается установленной, если у этого клиента есть файл команды или скилл `openspec-continue-change`; строка называет клиента

#### Scenario: Клиент не настроен
- **GIVEN** каталог без настроенного клиента
- **WHEN** выполняется `check`
- **THEN** `[!!] continue: клиент не настроен — выполнить: openspec init --tools <клиент>`, код 2
<!-- проба краёв: форма=text, io, исходы: F-82 Specify, F-83 Specify -->
<!-- проба запретов: исходы: нет -->
<!-- проба краёв, без кандидата: concurrency — `check` только читает -->

### Requirement: `install` создаёт `symphysis.yaml`, если файла нет, и не перезаписывает его
Команда `symphysis install` SHALL создавать `symphysis.yaml` в корне проекта со всеми выборами включёнными, если файла нет, и SHALL NOT перезаписывать существующий файл, в том числе с `--force` (F-24.A, F-23).

#### Scenario: Первая установка
- **GIVEN** проект без `symphysis.yaml`
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** `symphysis.yaml` создан, ветки отказа, допущения и проба краёв в нём включены

#### Scenario: Файл с правками человека
- **GIVEN** `symphysis.yaml`, где проба краёв выключена
- **WHEN** выполняется `symphysis install --project <каталог> --force`
- **THEN** файл не изменён байт в байт

#### Scenario: BOM и не UTF-8
- **GIVEN** `symphysis.yaml` с BOM и второй случай в CP1251
- **WHEN** выполняется `check`
- **THEN** BOM принимается, не UTF-8 даёт `[!!] symphysis.yaml: не UTF-8`, код 2
<!-- проба краёв: форма=text, stateful, исходы: F-84 Specify -->
<!-- проба запретов: исходы: нет -->
<!-- проба краёв, без кандидата: idempotency — сценарий «Файл с правками человека»; empty — край пустого файла F-50; concurrency — запись одного малого файла -->

### Requirement: `install` вносит `symphysis.yaml` в `.gitignore` проекта
Команда `symphysis install` SHALL добавлять строку `symphysis.yaml` в `.gitignore` проекта, если её там нет, и SHALL NOT дублировать её при повторном запуске: настройка личная, в git проекта файл MUST NOT попадать (F-94.E). Команда `symphysis check` SHALL сигналить, если файл уже отслеживается git (F-111.A).

#### Scenario: Установка вносит строку
- **GIVEN** проект, в `.gitignore` которого нет строки `symphysis.yaml`
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** в `.gitignore` есть строка `symphysis.yaml`, прежние строки на месте

#### Scenario: Повторный запуск не дублирует строку
- **GIVEN** проект после `install`
- **WHEN** `install` выполняется снова
- **THEN** строка `symphysis.yaml` в `.gitignore` одна

#### Scenario: Файла `.gitignore` нет
- **GIVEN** проект без `.gitignore`
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** `.gitignore` создан со строкой `symphysis.yaml`

#### Scenario: Проект не под git
- **GIVEN** каталог, который не является репозиторием git
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** строка внесена в `.gitignore`, ошибки нет, код 0

#### Scenario: Файл уже отслеживается git
- **GIVEN** `symphysis.yaml`, уже вошедший в коммит проекта
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[!!] symphysis.yaml: отслеживается git — выполнить: git rm --cached symphysis.yaml`, код 2

#### Scenario: Правка `.gitignore` названа
- **GIVEN** проект, в `.gitignore` которого нет строки `symphysis.yaml`
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** stdout называет правку `.gitignore`: она уходит в git вместе с работой человека
<!-- требование из F-94; пробами не проходило -->

### Requirement: `check` показывает состав из `symphysis.yaml`
Команда `symphysis check` SHALL давать строку о `symphysis.yaml`: сигнал `[..]` с текущим составом у годного файла и `[!!]` с кодом 2 у неизвестного ключа или недопустимого значения (F-24.A: «строка в `check`»; вариант B отклонён в том числе за то, что опечатку никто не проверит).

#### Scenario: Годный файл
- **GIVEN** `symphysis.yaml`, где допущения выключены
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[..] symphysis.yaml: ветки отказа вкл, допущения выкл, проба краёв вкл`, эта строка на код выхода не влияет

#### Scenario: Опечатка в ключе
- **GIVEN** `symphysis.yaml` с неизвестным ключом `edge-probe`
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[!!] symphysis.yaml: неизвестный ключ edge-probe`, код 2

#### Scenario: Файла настроек нет
- **GIVEN** проект без `symphysis.yaml`
- **WHEN** выполняется `check`
- **THEN** `[..] symphysis.yaml: нет файла, действует всё включено; создать: symphysis install`, код не меняется

#### Scenario: У найденного Python нет PyYAML
- **GIVEN** `symphysis.yaml` и Python, который находит `check`, без пакета PyYAML (F-110.B)
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** состав показан, stdout несёт `[!!] python: нет пакета PyYAML — выполнить: <python> -m pip install pyyaml`, код 2
<!-- проба краёв: форма=text, исходы: F-85 Specify -->
<!-- проба запретов: исходы: нет -->
<!-- проба краёв, без кандидата: encoding — сценарий «Опечатка в ключе» и край значений F-51 -->

### Requirement: Скрипт сборки кладёт тарбол форка в `vendor/`
Скрипт сборки выпуска SHALL собирать тарбол форка и класть его в каталог `vendor/` репозитория; файл SHALL входить в git, а установка из него SHALL давать форк версии пина (F-31.A, F-36.A); предположение: скрипт живёт в `installer/scripts/`; решить при реализации.

#### Scenario: Тарбол в клоне
- **GIVEN** репозиторий после работы скрипта и коммита `vendor/`
- **WHEN** человек клонирует репозиторий и выполняет `npm i -g ./vendor/<тарбол>`
- **THEN** `openspec --version` совпадает с `symphysis.openspecPin` из `installer/package.json`

#### Scenario: Сборки на машине пользователя нет
- **GIVEN** клон репозитория без `upstream/`
- **WHEN** человек ставит форк из `vendor/`
- **THEN** исходники форка и его сборка не требуются; из сети берутся только зависимости форка, из реестра или зеркала

#### Scenario: Скрипт на клоне без форка
- **GIVEN** клон без `upstream/openspec`
- **WHEN** запускается скрипт сборки
- **THEN** код 1, stderr называет ветку `openspec-fork` и команду её получения, `vendor/` не меняется

#### Scenario: Старый тарбол заменяется
- **GIVEN** `vendor/` с тарболом прежней версии
- **WHEN** скрипт кладёт новый
- **THEN** прежний удалён, в каталоге один `*.tgz`

#### Scenario: Версия форка расходится с пином
- **GIVEN** версия в `upstream/openspec/package.json` отличается от `symphysis.openspecPin`
- **WHEN** запускается скрипт сборки
- **THEN** код 1, stderr называет обе версии, тарбол не кладётся

#### Scenario: Строка о форке называет тарбол
- **GIVEN** форка нет
- **WHEN** выполняется `check`
- **THEN** строка называет `vendor/<тарбол>` и команду `npm i -g`; поле `openspecSource` заполнено этим путём
<!-- проба краёв: форма=collection, io, text, исходы: F-86 Specify, F-87 Specify, F-88 Specify, F-89 Specify -->
<!-- проба запретов: исходы: F-101 Specify; канон — F-106 → security.md -->
<!-- проба краёв, без кандидата: ordering — тарбол один при варианте A края F-87; encoding — имя файла задаёт `npm pack` -->

### Requirement: Тарбол собирается только из чистого дерева форка
Скрипт сборки MUST NOT собирать тарбол при грязном дереве `upstream/openspec` и SHALL печатать хеш коммита форка (F-101.A).

#### Scenario: Грязное дерево форка
- **GIVEN** незакоммиченные правки в `upstream/openspec`
- **WHEN** запускается скрипт сборки
- **THEN** код 1, тарбол не кладётся

#### Scenario: Хеш форка в выводе
- **GIVEN** чистое дерево `upstream/openspec`
- **WHEN** запускается скрипт сборки
- **THEN** stdout несёт хеш коммита форка
<!-- требование из F-101; пробами не проходило -->
