# Spec Delta

## ADDED Requirements

### Requirement: `install` обновляет проект так, чтобы появилась `/opsx:continue`
Форк по пину SHALL включать `continue` в профиль `core`. Команда `symphysis install` SHALL обновлять проект так, чтобы в нём появилась `/opsx:continue`, и SHALL NOT менять профиль и список workflow глобального конфига OpenSpec (F-126.A, слово человека к F-123). Требование дополняет «`install` ставит схему, скиллы и инструменты в проект и сливает конфиг» (F-32.A).

#### Scenario: Чистая установка
- **GIVEN** проект после `openspec init --tools claude` и глобальный конфиг с профилем `core`, заданным или по умолчанию
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** появляется `.claude/commands/opsx/continue.md`; профиль и список workflow в конфиге не изменены

#### Scenario: Вызов форка через `openspec.cmd`
- **GIVEN** Windows, форк из PATH как `openspec.cmd` и путь проекта с пробелом
- **WHEN** выполняется `install`
- **THEN** проект обновлён; отказ форка назван своим текстом, а не «openspec не найден»

#### Scenario: Список человека сохраняется
- **GIVEN** глобальный конфиг с `profile: custom` и workflow `propose`, `apply`, `verify`
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** список не изменён байт в байт, stdout называет, что `continue` в нём нет и как добавить: `openspec config profile`; `check` даёт `[!!] continue`

#### Scenario: Тесты не трогают настоящий конфиг
- **GIVEN** `XDG_CONFIG_HOME`, указанный во временный каталог
- **WHEN** тесты инсталлятора вызывают `install`
- **THEN** настоящий глобальный конфиг OpenSpec не изменён байт в байт

#### Scenario: Команда уже есть
- **GIVEN** команда `/opsx:continue` в проекте
- **WHEN** `install` выполняется снова
- **THEN** обновление проекта не зовётся

#### Scenario: Команды нет в этом проекте
- **GIVEN** второй проект на той же машине, инициализированный до установки новой версии форка, без команды
- **WHEN** выполняется `install`
- **THEN** обновление проекта зовётся, команда появляется

#### Scenario: Форка нет или клиент не настроен
- **GIVEN** форка нет в PATH или проект без настроенного клиента
- **WHEN** выполняется `install`
- **THEN** схема и скиллы поставлены, stdout называет команду для выполнения позже и подсказку из сценария «Клиент не настроен», код 0; `check` даёт `[!!] continue`
<!-- проба краёв: форма=stateful, io, collection, исходы: F-79 Specify, F-80 Specify, F-81 Specify -->
<!-- проба запретов: исходы: F-100 Specify -->

### Requirement: `install` меняет в глобальном конфиге только названное
Команда `symphysis install` MUST NOT менять в глобальном конфиге OpenSpec что-либо, кроме `telemetry.enabled: false` при незаданном ключе; умолчания, которые `config set` форка дописывает сам, в счёт не идут. Вызовы форка из `install` SHALL идти с `OPENSPEC_TELEMETRY=0`, stdout SHALL называть правку и путь конфига (F-100.A, F-107.A, F-116.A, F-126.A).

#### Scenario: Конфиг до и после
- **GIVEN** временный глобальный конфиг: один случай с заданной человеком телеметрией, другой без ключа
- **WHEN** тест вызывает `install` и сравнивает конфиг до и после
- **THEN** с умолчаниями форка, подставленными с обеих сторон, различие — только `telemetry.enabled: false` во втором случае; заданное человеком значение не изменено, stdout называет правку и путь конфига

#### Scenario: Инсталлятор сам телеметрию не порождает
- **GIVEN** временный глобальный конфиг без ключей телеметрии
- **WHEN** выполняется `install`
- **THEN** в конфиге нет `anonymousId` и `noticeSeen`: вызовы форка шли с `OPENSPEC_TELEMETRY=0`
<!-- требование из F-100; пробами не проходило -->

### Requirement: `check` называет отсутствие команды `/opsx:continue`
Команда `symphysis check` SHALL давать строку `[!!]` и код 2, если у выбранного клиента нет команды `/opsx:continue`, и SHALL называть команду, которая её ставит. Клиента выбирает человек параметром `--skills-dir`, умолчание — `.claude/skills`; инсталлятор SHALL NOT искать клиентов сам (F-115.D). При нескольких каталогах `[!!]` SHALL быть, только если команды нет ни в одном (F-124.A). Требование дополняет «`check` называет расхождения и версию форка, не чинит» (F-32.A, F-29).

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
- **THEN** команда считается установленной, если у этого клиента есть файл команды или скилл `openspec-continue-change`; клиент в строке — имя выбранного каталога без точки

#### Scenario: Два каталога
- **GIVEN** `--skills-dir .claude/skills --skills-dir .agents/skills`, команда есть у `.claude`, файлов форка у `.agents` нет
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** строки `[!!] continue` нет, stdout несёт `[..] .agents: файлов форка нет, туда поставлены только скиллы symphysis` (F-124.A)

#### Scenario: Клиент не настроен
- **GIVEN** выбранный каталог клиента, в котором нет созданных форком `skills/openspec-*` и `commands/opsx/`
- **WHEN** выполняется `check`
- **THEN** `[!!] continue: клиент не настроен — выполнить: openspec init --tools <клиент>`, код 2; подсказка называет, как выбрать клиента: `where.exe claude`, `where.exe opencode` в PowerShell и `which` в bash (F-115.D)
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
- **THEN** состав показан, stdout несёт `[!!] python: нет пакета PyYAML, инструменты журнала считают всё включённым — выполнить: <python> -m pip install pyyaml`, код 2 (F-121.A)
<!-- проба краёв: форма=text, исходы: F-85 Specify -->
<!-- проба запретов: исходы: нет -->
<!-- проба краёв, без кандидата: encoding — сценарий «Опечатка в ключе» и край значений F-51 -->

### Requirement: `check` называет действующий глобальный конфиг
Команда `symphysis check` SHALL строкой `[..]` называть путь глобального конфига OpenSpec, действующий в этой оболочке, и второй файл конфига, если он есть: `XDG_CONFIG_HOME`, заданная не во всех оболочках, даёт два конфига, а `openspec update` приводит проект к тому, что прочитал (F-122). Команда `symphysis install` SHALL писать только в подкаталог `openspec/` этой переменной.

#### Scenario: Один конфиг
- **GIVEN** один файл глобального конфига OpenSpec
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[..] openspec: глобальный конфиг <путь>`, код не меняется

#### Scenario: Два конфига
- **GIVEN** заданная `XDG_CONFIG_HOME` с конфигом OpenSpec и второй файл конфига по пути без этой переменной
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[..] openspec: глобальный конфиг <путь>; есть ещё <путь>, он действует без XDG_CONFIG_HOME`, код не меняется

#### Scenario: Соседи в `XDG_CONFIG_HOME` не тронуты
- **GIVEN** `XDG_CONFIG_HOME` с подкаталогом другой программы
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** подкаталог другой программы не изменён байт в байт, запись идёт только в `<XDG_CONFIG_HOME>/openspec/`
<!-- требование из слова человека об XDG_CONFIG_HOME; пробами не проходило -->

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
<!-- требование из F-114; пробами не проходило -->

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

#### Scenario: Имена в тарболе
- **GIVEN** распакованный тарбол перед коммитом `vendor/`
- **WHEN** гейт имён идёт по его файлам
- **THEN** находок нет; класс «внешний адрес» к чужому коду неприменим, остальные классы останавливают коммит
<!-- требование из F-101; пробами не проходило -->
