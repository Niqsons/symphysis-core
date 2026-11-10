# project-installer Specification

## Purpose
Установщик `@niqsons/symphysis`: кладёт схему, скиллы и инструменты журнала в проект, сливает конфиг, сверяет установку и версию форка; гейт называет, не чинит; F-15, F-16.

## Requirements

### Requirement: `install` ставит схему, скиллы и инструменты в проект и сливает конфиг
Команда `symphysis install --project <dir> [--skills-dir <dir>]…` SHALL положить схему в `openspec/schemas/symphysis/`, скиллы в каждый `--skills-dir` (по умолчанию `.claude/skills`), тела агентов-водителей `symphysis-<скилл>-driver.md` в каждый `--agents-dir` (по умолчанию `agents` рядом с каждым каталогом скиллов: `.claude/agents`), инструменты в `.symphysis/` и создать или слить `openspec/config.yaml` (`schema` → `symphysis`, `rules` объединяются, прочее сохраняется); повторный запуск SHALL ничего не менять, отличающийся файл SHALL пропускаться с подсказкой `--force` — при обновлении схемы каждый пропущенный файл схемы SHALL называться отдельной строкой, а `check` SHALL показывать расхождение байтов схемы как `[!!]`; файл корней SHALL NOT перезаписываться (журнал `symphysis-schema`: F-15.C, F-16.B; журнал `calibration-fixes`: F-50.E). Схема в payload SHALL нести артефакт `intent` и шаблон `intent.md`; вход изменения — `openspec/changes/<имя>/intent.md`; установщик SHALL NOT создавать и читать каталог `.gigacode/`; каталог инструментов SHALL оставаться `.symphysis/` (журнал `calibration-fixes`: F-13.A, F-15.B). Файл mermaid закреплённой версии SHALL ставиться в `.symphysis/tools/` и SHALL NOT лежать в git ядра (F-49, F-53). Каталог `.symphysis/viewer/` с черновиками человека SHALL NOT стираться и при `--force` (`docs/repo-contract.md`, F-20).

#### Scenario: Проект с конфигом другой схемы
- **GIVEN** `openspec/config.yaml` со `schema: spec-driven` и комментариями
- **WHEN** выполняется `install --project <dir>`
- **THEN** `schema: symphysis`, `rules` symphysis добавлены, комментарии на месте, stdout — «config.yaml уже был: схема переключена с spec-driven на symphysis, rules добавлены»

#### Scenario: Повторная установка
- **GIVEN** проект после успешного `install`
- **WHEN** `install` выполняется снова
- **THEN** список записанных файлов пуст, `journal-roots.json` не тронут (его правки пользователя сохранены)

#### Scenario: Блок context при слиянии
- **GIVEN** существующий `config.yaml` без `context`
- **WHEN** выполняется `install`
- **THEN** `context` из `config.symphysis.yaml` в `config.yaml` не появляется — предположение: наблюдение прогона (шаг 5 дневника), слияние переносит только `schema` и `rules`; решить: переносить ли `context` при слиянии

#### Scenario: Тела агентов рядом со скиллами
- **GIVEN** проект без `.claude/`
- **WHEN** выполняется `install --project <dir>` без `--agents-dir`
- **THEN** в `.claude/agents/` лежат пять тел `symphysis-*-driver.md` без комментариев провенанса; с `--skills-dir a/skills` они лежат в `a/agents/`; с `--agents-dir x/agents` — только в `x/agents/`

#### Scenario: Раскладка входа
- **GIVEN** проект после `install` и новое изменение `openspec new change demo`
- **WHEN** выполняется `openspec status --change demo --json`
- **THEN** первым артефактом стоит `intent` с путём `openspec/changes/demo/intent.md`; каталога `.gigacode/` в проекте нет; инструменты лежат в `.symphysis/tools/`

#### Scenario: Обновление схемы
- **GIVEN** payload с новым `schema.yaml` (артефакт `intent`) и проект со старым `schema.yaml`
- **WHEN** выполняется `install` без `--force`
- **THEN** stdout называет `openspec/schemas/symphysis/schema.yaml` отдельной строкой «пропущен: отличается, нужен --force», `check` даёт `[!!] схема: байты отличаются от payload`, код 2; установка по инструкции с `--force` обновляет файл

#### Scenario: Файл mermaid в проекте
- **GIVEN** проект без установки
- **WHEN** выполняется `install`
- **THEN** в `.symphysis/tools/` лежит файл mermaid закреплённой версии, а страница журнала рисует схему

#### Scenario: Файл mermaid не в git ядра
- **GIVEN** репозиторий ядра после сборки поставки
- **WHEN** выполняется `git ls-files`
- **THEN** файла mermaid в списке нет

#### Scenario: Черновики переживают обновление
- **GIVEN** `.symphysis/viewer/` с черновиком человека
- **WHEN** выполняется `install --force`
- **THEN** черновик байт в байт прежний

#### Scenario: Файла mermaid нет при сборке поставки
- **GIVEN** файла mermaid нет в зависимостях сборки
- **WHEN** идёт `sync-payload.js`
- **THEN** код не ноль и названа причина, поставка не собрана

#### Scenario: Файл mermaid пропал из проекта
- **GIVEN** проект без файла mermaid
- **WHEN** выполняется `symphysis check`
- **THEN** строка-сигнал `[..]`, код прежний: страница работает и с текстом

<!-- проба краёв, журнал `calibration-fixes`: форма=io, stateful, text, исходы: F-50 Specify -->
<!-- проба запретов, журнал `calibration-fixes`: исходы: нет -->
<!-- проба краёв: форма=io, stateful, collection, исходы: F-100 Specify, F-101 Specify; снято: idempotency — сценарий «Повторная установка» и подсказка `--force` -->
<!-- проба запретов: исходы: F-113 Dismiss; канон — F-117 → security.md -->

### Requirement: `check` называет расхождения и версию форка, не чинит
Команда `symphysis check --project <dir>` SHALL проверить версию форка против пина `1.15.0-symphysis.1`, байты схемы, `schema: symphysis`, `SKILL.md` в каталогах скиллов, тела агентов в каталогах агентов, инструменты и Python и прогнать `journal.py check` по каждому `openspec/changes/*/decisions.json`; расхождения — строки `[!!]`, код 2; сигналы сверки — `[..]` без влияния на код; `check` SHALL NOT ничего менять (F-15.A «ГЕЙТ НАЗЫВАЕТ, А НЕ ЧИНИТ», F-15.C).
<!-- проба краёв: форма=text, io, исходы: F-58 открыт, F-59 открыт -->
<!-- проба запретов: исходы: нет -->

#### Scenario: Ванильный OpenSpec вместо форка
- **GIVEN** `SYMPHYSIS_OPENSPEC` указывает на ванильный `openspec` 1.15.0
- **WHEN** выполняется `check`
- **THEN** строка `[!!] openspec: версия 1.15.0, нужна 1.15.0-symphysis.1 (форк symphysis): <источник>`, код 2

#### Scenario: Установка цела
- **GIVEN** проект после `install` и форк по пину
- **WHEN** выполняется `check`
- **THEN** stdout — `check: ok`, код 0; журналы изменений дают строки `[..] <путь>: [ok] улик сверено N из M`

### Requirement: Установка не включает телеметрию форка молча
Телеметрия форка SHALL быть выключена по умолчанию: `init` форка и `symphysis install` SHALL NOT включать её; `check` SHALL давать код 0 и `[..] telemetry: выключена` при выключенной или без конфига и `[!!] telemetry: включена — выключить: <команда>` при включённой; README называет, как выключить (F-21.A, F-51.E, F-57.E; symphysis-schema F-79).
<!-- проба краёв: форма=io, text, исходы: F-51 Specify -->
<!-- проба запретов: исходы: F-57 Specify; канон — F-58 → security.md -->

#### Scenario: Установка в чистом окружении
- **GIVEN** глобальный конфиг OpenSpec без ключа `telemetry`
- **WHEN** выполняется `install --project <dir>`
- **THEN** телеметрия остаётся выключенной: `openspec config list` не показывает включённой телеметрии, `check` даёт `[..] telemetry: выключена`, код 0 — предположение: способ выключения — запись `telemetry.enabled: false` при установке или сборка форка без телеметрии; решить в design

#### Scenario: Конфига OpenSpec нет
- **GIVEN** глобальный конфиг OpenSpec отсутствует (первый запуск)
- **WHEN** выполняется `check --project <dir>`
- **THEN** stdout содержит `[..] telemetry: конфиг OpenSpec не найден — появится после первого openspec init`, код 0

#### Scenario: Телеметрия включена
- **GIVEN** глобальный конфиг с включённой телеметрией и `anonymousId`
- **WHEN** выполняется `check --project <dir>`
- **THEN** stdout содержит `[!!] telemetry: включена — выключить: <команда из README>`; предположение: код 2 как у расхождений установки; решить

### Requirement: `install` обновляет проект так, чтобы появилась `/opsx:continue`
Форк по пину SHALL включать `continue` в профиль `core`. Команда `symphysis install` SHALL обновлять проект так, чтобы в нём появилась `/opsx:continue`, и SHALL NOT менять профиль и список workflow глобального конфига OpenSpec (F-126.A, слово человека к F-123). Требование дополняет «`install` ставит схему, скиллы и инструменты в проект и сливает конфиг» (F-32.A).

#### Scenario: Чистая установка
- **GIVEN** проект после `openspec init --tools claude` и глобальный конфиг с профилем `core`, заданным или по умолчанию
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** появляется `.claude/commands/opsx/continue.md`; профиль и список workflow в конфиге не изменены

#### Scenario: Конфиг с телеметрией без профиля
- **GIVEN** глобальный конфиг с заданной телеметрией и без ключа `profile`, команды `/opsx:continue` в проекте нет
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** `openspec update` не зовётся, конфиг не изменён, строка называет `openspec config profile core` и `openspec update`, код 0 (F-139.A)

#### Scenario: Вызов форка через `openspec.cmd`
- **GIVEN** Windows, форк из PATH как `openspec.cmd` и путь проекта с пробелом
- **WHEN** выполняется `install`
- **THEN** проект обновлён; отказ форка назван своим текстом, а не «openspec не найден»

#### Scenario: Список человека сохраняется
- **GIVEN** глобальный конфиг с `profile: custom` и workflow `propose`, `apply`, `verify`
- **WHEN** выполняется `symphysis install --project <каталог>`
- **THEN** `profile` и `workflows` прежние, умолчания, которые дописал `config set`, в счёт не идут (F-116.A); stdout называет, что `continue` в нём нет и как добавить: `openspec config profile`; `check` даёт `[!!] continue`

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
Команда `symphysis check` SHALL давать строку о `symphysis.yaml`: сигнал `[..]` с текущим составом у годного файла и `[!!]` с кодом 2 у неизвестного ключа или недопустимого значения; строки даёт скрипт настроек, файл `check` сам не разбирает (F-135.B; F-24.A: «строка в `check`»; вариант B отклонён в том числе за то, что опечатку никто не проверит).

#### Scenario: Годный файл
- **GIVEN** `symphysis.yaml`, где допущения выключены
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[..] symphysis.yaml: ветки отказа вкл, допущения выкл, проба краёв вкл, водители: атака вкл, пробы выкл, опись выкл, исследование вкл`, эта строка на код выхода не влияет

#### Scenario: Опечатка в ключе
- **GIVEN** `symphysis.yaml` с неизвестным ключом `edge-probe`
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[!!] symphysis.yaml: неизвестный ключ edge-probe`, код 2

#### Scenario: Файла настроек нет
- **GIVEN** проект без `symphysis.yaml`
- **WHEN** выполняется `check`
- **THEN** `[..] symphysis.yaml: нет файла, действует всё включено; создать: symphysis install`, код не меняется

#### Scenario: У найденного Python нет PyYAML
- **GIVEN** `symphysis.yaml` с выключенной пробой краёв и Python, который находит `check`, без пакета PyYAML (F-110.B)
- **WHEN** выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[..] symphysis.yaml: ветки отказа вкл, допущения вкл, проба краёв вкл, водители: атака вкл, пробы выкл, опись выкл, исследование вкл` и `[!!] symphysis.yaml: нет пакета PyYAML — выполнить: python -m pip install pyyaml`, код 2: показан состав, который получит модель (F-135.B)
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

#### Scenario: Клон в модульной раскладке
<!-- F-60 -->
- **GIVEN** клон в модульной раскладке без каталога `skills/` и прежний `installer/payload`
- **WHEN** из клона выполняется `symphysis check --project <каталог>`
- **THEN** stdout несёт `[!!] payload старее исходников — выполнить: npm --prefix installer ci`, код 2

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

### Requirement: `install` ставит скрипт графа
Команда `symphysis install` SHALL класть скрипт графа и общий модуль запуска форка в `.symphysis/tools/`: файлы SHALL входить в payload и его перечень (F-39, F-138). `symphysis check` SHALL называть их пропажу (F-126).

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

### Requirement: `install` переносит подсказки операций
Кроме `schema` и `rules` слияние `openspec/config.yaml` SHALL переносить ключ `operations` из конфига symphysis, чтобы подсказка заморозки дошла до проекта (F-08, F-49). Списки подсказок SHALL объединяться, как `rules`: чужие подсказки остаются, старые человек удаляет руками (F-110, F-124).

#### Scenario: Конфиг без подсказок
- **GIVEN** `openspec/config.yaml` без ключа `operations`
- **WHEN** выполняется `symphysis install`
- **THEN** для изменения проекта `openspec instructions archive --change <имя> --json` отдаёт подсказку заморозки полем `operationGuidance`

#### Scenario: У проекта своя подсказка
- **GIVEN** `openspec/config.yaml` со своей строкой в `operations.archive.guidance`
- **WHEN** выполняется `symphysis install`
- **THEN** своя строка на месте, подсказка заморозки добавлена

#### Scenario: Повторная установка не дублирует
- **GIVEN** проект после `symphysis install`
- **WHEN** `symphysis install` выполняется снова
- **THEN** подсказка заморозки стоит в списке один раз

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
### Requirement: Local остаётся самостоятельной полной установкой
Проектная установка local SHALL сохранять собственные runtime, ресурсы, схему и клиентские файлы по правилам проектного install/check и SHALL работать без global-установки. Она SHALL NOT объявляться устаревшей или требовать миграции только ради появления global scope; поддержка одновременной смешанной установки этим не вводится (global-user-install/F-13).

#### Scenario: Проект использует только local
- **GIVEN** проект с local-установкой symphysis и без пользовательской global-установки
- **WHEN** человек проверяет установку и выполняет инструменты выбранного проекта
- **THEN** используются проектные runtime и ресурсы; отсутствие global не является расхождением установки и не мешает работе

#### Scenario: Повторная local-установка
- **GIVEN** проект с полной local-установкой и пользовательскими правками настроек и карты корней
- **WHEN** человек повторяет проектный install в local scope
- **THEN** действуют прежние правила повторной установки и сохранения проектных данных; команда не переводит проект в global и не требует такого перехода

### Requirement: Global-инициализация настраивает выбранный store отдельно от runtime
Инициализация store для global SHALL применять схему symphysis и её правила к выбранному planning root, используя runtime и ресурсы пользовательской поставки через общий resolver. Она SHALL NOT создавать проектную копию общего runtime или менять другой store; расположение поставки SHALL NOT становиться корнем артефактов (global-user-install/F-03, global-user-install/F-10).

#### Scenario: Клонированный store использует global
- **GIVEN** клонированный store OpenSpec, выбранный человеком для symphysis, и совместимая global-поставка
- **WHEN** выполняется global-инициализация этого store и создаётся изменение
- **THEN** изменение использует схему symphysis и лежит в выбранном store; инструменты и общие ресурсы берутся из пользовательской поставки, без их копирования внутрь store

#### Scenario: Инициализация из исходного репозитория с указателем store
- **GIVEN** исходный репозиторий с действительным указателем на выбранный store и без собственного planning root
- **WHEN** выполняется global-инициализация для этого store из исходного репозитория
- **THEN** конфигурация планирования относится к выбранному store; второй локальный planning root в исходном репозитории не создаётся, артефакты остаются в store

#### Scenario: Конфликт структуры planning config останавливает global-инициализацию
<!-- global-user-install/F-26 -->
- **GIVEN** существующий planning config имеет `rules` или `operations` неожиданной структуры
- **WHEN** store инициализируется для global
- **THEN** до записи показан конфликт структуры, исходный config сохранён и инициализация не объявлена завершённой

### Requirement: Global-инициализация сохраняет проектное состояние
При global-инициализации выбранного store настройки, карта корней, журналы, ответы и черновики SHALL оставаться данными этого store, а не пользовательской поставки. Существующие пользовательские настройки и карта корней SHALL NOT перезаписываться при повторной инициализации; прежние артефакты, ответы и черновики SHALL сохраняться (global-user-install/F-03, global-user-install/F-12, global-user-install/F-13).

#### Scenario: Повторная инициализация store с данными
- **GIVEN** выбранный store с изменёнными пользователем настройками, картой корней, журналом, ответом и черновиком
- **WHEN** человек повторяет его global-инициализацию
- **THEN** перечисленные файлы сохранены байт в байт в store и не перенесены в пользовательскую поставку

#### Scenario: Второй store не меняется
- **GIVEN** два store с разными настройками, картами корней и черновиками, использующие одну global-поставку
- **WHEN** инициализируется один из них
- **THEN** файлы второго store не меняются, его данные не подставляются вместо данных выбранного store

### Requirement: Проверка global не требует локальной копии runtime
Проверка установки выбранного global-store SHALL использовать runtime и ресурсы, выбранные общим resolver, и проверять настройку и данные этого store. Отсутствие проектной копии runtime SHALL NOT считаться поломкой global-установки; проверка SHALL только называть найденные расхождения и необходимые действия, не менять scope, установку или проектные данные (global-user-install/F-10, global-user-install/F-11, global-user-install/F-13).

#### Scenario: Global-store без локальных инструментов
- **GIVEN** совместимая global-поставка и инициализированный для неё store без local runtime
- **WHEN** человек проверяет установку этого store
- **THEN** отсутствие local runtime не даёт расхождения; схема, ресурсы и клиентская установка проверяются для global scope, а настройки и журналы — для выбранного store

#### Scenario: Проверка не переключает scope
- **GIVEN** global-store с расхождением установки или несовместимостью с выбранной поставкой
- **WHEN** человек выполняет проверку
- **THEN** расхождение названо с необходимым действием, несовместимость даёт отказ по правилу совместимости; проверка не устанавливает local runtime, не мигрирует store и не правит его данные
