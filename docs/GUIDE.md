# Руководство по symphysis

symphysis — схема для OpenSpec: задача идёт от намерения человека через журнал решений, спецификации и опись последствий к списку задач, а решает на каждой развилке человек. Руководство ставит всё с нуля и проводит один маленький проект через все шаги настоящими командами.

**Сводка.** Часть 1: клон, форк OpenSpec из тарбола, выключение телеметрии, пакет `pyyaml`, инсталлятор, проект, `check: ok`. Часть 2: учебный проект от `intent.md` до `tasks.md`. Часть 3: реализация, синхронизация спек и архивация. Дальше — остальные команды, обновление, другой клиент, шаг разработчика и сбои.

Как читать блоки вывода: вывод CLI совпадёт с точностью до путей, заменённых на `<каталог>`. То, что пишет модель, помечено «пример, у читателя будет иначе».

## Что понадобится

- Node 20 или новее, Python с `pip`, git, клиент Claude Code.
- Доступ к репозитория symphysis и к реестру npm и индексу pip или их зеркалу. Что делать без них — в разделе «Сбои».

Команды даны отдельно для PowerShell и bash. В PowerShell зови именно `where.exe`: `where` там псевдоним `Where-Object` и ничего не покажет. В Git Bash пути пиши прямыми слешами: `X:\work\p` без кавычек станет `X:workp`, установка молча уйдёт не туда, а `check` там же ответит `ok`.

## Что изменится на машине

Глобальных изменений четыре. У каждого шага ниже то же самое написано ещё раз перед командой.

| Шаг | Что меняется | Откат |
| --- | --- | --- |
| `npm i -g` тарбола | команда `openspec` у всех проектов пользователя; прежний глобальный OpenSpec заменяется | `npm rm -g @fission-ai/openspec` |
| `openspec config set telemetry.enabled false` | глобальный конфиг OpenSpec | `openspec config unset telemetry.enabled` |
| `python -m pip install pyyaml` | пакет в том Python, что первым стоит в `PATH` | `python -m pip uninstall pyyaml` |
| `npm i -g ./installer` | команда `symphysis`, ссылка ведёт в клон | `npm rm -g @niqsons/symphysis` |

## Часть 1. Установка

### 1. Клон

Адрес без токена: токен в адресе остаётся в `.git/config` и в истории оболочки. Доступ к закрытому репозитория держит хранилище учётных данных: на Windows это Git Credential Manager, он идёт с Git for Windows и спросит вход при первом клоне; на macOS и Linux — помощник из `git config --global credential.helper`.

PowerShell:

```powershell
git clone <адрес репозитория> symphysis
Set-Location symphysis
```

bash:

```bash
git clone <адрес репозитория> symphysis
cd symphysis
```

Шаги 2–6 идут из корня клона.

### 2. Форк OpenSpec

**Что меняется.** `npm i -g` ставит пакет `@fission-ai/openspec` в глобальный каталог npm и кладёт команду `openspec` в `PATH`: она действует у всех проектов этого пользователя. Уже стоящий глобально OpenSpec заменяется, поэтому его версию запиши заранее: `openspec --version`. Сборки нет, тарбол лежит в `vendor/`; из сети берутся только зависимости форка.

**Откат.** `npm rm -g @fission-ai/openspec`. Прежний OpenSpec вернёт `npm i -g @fission-ai/openspec@<записанная версия>`.

PowerShell:

```powershell
npm i -g ./vendor/fission-ai-openspec-1.15.0-symphysis.4.tgz
```

bash:

```bash
npm i -g ./vendor/fission-ai-openspec-1.15.0-symphysis.4.tgz
```

Следующая команда форка — только шаг 3: иначе первая же команда запишет идентификатор установки и отправит событие телеметрии.

### 3. Телеметрия

**Что меняется.** В глобальный конфиг OpenSpec записывается `telemetry.enabled: false`. Конфиг один на все проекты пользователя. Вместе с ключом `config set` дописывает умолчания `featureFlags`, `profile` и `delivery`, значений они не меняют. Переменная `OPENSPEC_TELEMETRY=0` действует только на эту команду: с ней форк не пишет идентификатор и не шлёт событие.

**Откат.** `openspec config unset telemetry.enabled`: ключ уходит, телеметрия снова включена по умолчанию.

PowerShell:

```powershell
$env:OPENSPEC_TELEMETRY = "0"
openspec config set telemetry.enabled false
Remove-Item Env:OPENSPEC_TELEMETRY
Get-Content (openspec config path)
openspec --version
```

bash:

```bash
OPENSPEC_TELEMETRY=0 openspec config set telemetry.enabled false
cat "$(openspec config path)"
openspec --version
```

Вывод:

```text
Set telemetry.enabled = false
{
  "featureFlags": {},
  "profile": "core",
  "delivery": "both",
  "telemetry": {
    "enabled": false
  }
}
1.15.0-symphysis.4
```

Ключа `anonymousId` в файле нет. Версия другая — раньше в `PATH` стоит другой `openspec`: `where.exe openspec` в PowerShell, `which openspec` в bash.

### 4. Где лежит глобальный конфиг

Путь показывает `openspec config path`. Задана `XDG_CONFIG_HOME` — конфиг лежит в `<XDG_CONFIG_HOME>/openspec/config.json`, и запись идёт только в этот файл: соседние каталоги с настройками других программ не трогаются. Не задана — `%APPDATA%\openspec\config.json` на Windows и `~/.config/openspec/config.json` на остальных системах.

Переменная, заданная не во всех оболочках, даёт два конфига. `openspec update` приводит проект к тому конфигу, что прочитал, поэтому из другой оболочки `/opsx:continue` может пропасть. `symphysis check` называет оба файла:

```text
[..] openspec: глобальный конфиг <каталог>\openspec\config.json; есть ещё <каталог>\openspec\config.json, он действует без XDG_CONFIG_HOME
```

Команды здесь нет, шаг только для чтения.

### 5. Пакет PyYAML

**Что меняется.** `pip` ставит пакет `pyyaml` в тот Python, что первым стоит в `PATH`: его увидят все программы на этом Python. Если пакет уже стоял, ничего не меняется. Без него настройки считаются включёнными, а `check` даёт `[!!]`.

**Откат.** `python -m pip uninstall pyyaml`. Перед установкой проверь `python -m pip show pyyaml`: если пакет уже был, удалять его не нужно, он нужен кому-то ещё.

PowerShell:

```powershell
python -m pip install pyyaml
```

bash:

```bash
python -m pip install pyyaml
```

### 6. Инсталлятор

**Что меняется.** `npm --prefix installer ci` работает только внутри клона: ставит зависимость и собирает `installer/payload`. `npm i -g ./installer` кладёт в глобальный каталог npm ссылку на клон и команду `symphysis` в `PATH`. Ссылка ведёт в клон: `git pull` обновляет и её, а удаление клона ломает команду.

**Откат.** `npm rm -g @niqsons/symphysis`.

PowerShell:

```powershell
npm --prefix installer ci
npm i -g ./installer
symphysis --help
```

bash:

```bash
npm --prefix installer ci
npm i -g ./installer
symphysis --help
```

Первая строка вывода справки:

```text
symphysis — схема OpenSpec symphysis, скиллы и инструменты журнала в проект
```

### 7. Выбор клиента

Какой клиент есть на машине, покажут эти команды. Инсталлятор сам клиентов не ищет.

PowerShell:

```powershell
where.exe claude
where.exe opencode
```

bash:

```bash
which claude
which opencode
```

Прохождение этого руководства шло только на Claude Code, поэтому дальше команды для него. opencode и другие клиенты — раздел «Другой клиент»; opencode этим прохождением не проверен.

### 8. Проект

Учебный проект лежит в `docs/guide/example/`: файл `reminders.py` с напоминаниями и задача `intent.md`. Он копируется рядом с клоном, глобальных изменений здесь нет. `openspec init` создаёт `.claude/` и `openspec/`, `symphysis install` кладёт в проект схему, скиллы, инструменты журнала и личный `symphysis.yaml`.

Команды идут из каталога проекта. Параметр `--project` им не нужен; если он понадобится, путь относительный и с прямыми слешами.

PowerShell:

```powershell
Copy-Item -Recurse docs/guide/example ../reminders
Set-Location ../reminders
git init
openspec init --tools claude
symphysis install
symphysis check
$LASTEXITCODE
```

bash:

```bash
cp -r docs/guide/example ../reminders
cd ../reminders
git init
openspec init --tools claude
symphysis install
symphysis check
echo $?
```

Вывод `symphysis install`:

```text
записано 47
config.yaml уже был: схема переключена с spec-driven на symphysis, rules добавлены
.gitignore: добавлена строка symphysis.yaml — правка уйдёт в git вместе с работой
openspec: глобальный конфиг <каталог>\openspec\config.json
```

Вывод `symphysis check` и код:

```text
[..] symphysis.yaml: ветки отказа вкл, допущения вкл, проба краёв вкл
[..] openspec: глобальный конфиг <каталог>\openspec\config.json
[..] telemetry: выключена
check: ok
0
```

`[!!]` — расхождение, код выхода 2, и в строке названа команда, которая его снимает. `[..]` — сведения, на код не влияют. Команда `/opsx:continue` теперь есть в проекте, файл `.claude/commands/opsx/continue.md`.

## Часть 2. От намерения до задач

Запусти `claude` в каталоге проекта. Строки вида `/opsx:continue add-overdue` набираются в чате клиента, остальные команды — в терминале.

Все шаги схемы идут одной командой: `/opsx:continue` делает следующий шаг и останавливается. Какой шаг следующий, показывает `openspec status --change add-overdue`.

### Создать изменение и положить намерение

PowerShell:

```powershell
openspec new change add-overdue
Move-Item intent.md openspec/changes/add-overdue/intent.md
openspec status --change add-overdue
```

bash:

```bash
openspec new change add-overdue
mv intent.md openspec/changes/add-overdue/intent.md
openspec status --change add-overdue
```

Вывод статуса:

```text
Change: add-overdue
Schema: symphysis
Change root: <каталог>\openspec\changes\add-overdue
Progress: 1/9 artifacts complete (2 optional, not invoked)

[x] intent
[ ] decisions
[-] research (blocked by: decisions)
[-] attack-decisions (blocked by: research) (optional, not invoked)
[-] proposal (blocked by: research)
[-] specs (blocked by: proposal)
[-] consequences (blocked by: specs)
[-] design (blocked by: proposal, consequences)
[-] security (blocked by: specs)
[-] tasks (blocked by: specs, design)
[-] attack-artifacts (blocked by: specs, design, security, tasks) (optional, not invoked)

Next: openspec instructions decisions --change "add-overdue" --json
```

`intent.md` — намерение словами человека. Файл принят как есть, дальше он не правится.

### Круг просмотрщика

Этот круг повторяется на шагах `decisions`, `specs` и `consequences`: модель записывает в журнал `decisions.json` развилки с вариантами и рекомендацией, решает человек.

1. Открой `openspec/changes/add-overdue/decisions.html` в браузере.
2. У каждой развилки выбери вариант; слово к выбору необязательно. Спорный вопрос можно припарковать.
3. Нажми «Скопировать промпт» и вставь его в чат.
4. Модель сохраняет промпт в `answers/<дата>.md` и вносит его командой `python .symphysis/tools/journal.py apply`.

Короткий путь для учебного проекта: написать в чат `реши сам`. Модель внесёт рекомендованные варианты строками `- F-NN: X — «реши сам»`, и в журнале будет видно, что решение отдано модели.

### Шаг `decisions`: журнал решений

```text
/opsx:continue add-overdue
```

Модель читает `intent.md` и код, записывает критерии готовности фактами, а развилки — записями с вариантами, уликами из кода и рекомендацией. Вопросы, которых нет ни в файлах, ни в вариантах, она задаёт порциями в чате. Затем круг просмотрщика.

### Шаг `research`: исследование и второй круг

```text
/opsx:continue add-overdue
```

На каждую запись, припаркованную к материалам, модель пишет `research/<F-NN>.md`. Парковок нет — один файл `research/none.md`, это законный исход. В конце она спрашивает, нужен ли ещё круг брейншторма; для учебного проекта ответ `нет, круг закончен`.

### Атака журнала, по желанию

```text
/opsx:continue add-overdue attack-decisions
```

Шаг необязательный и зовётся только по имени: модель ищет в журнале утверждения, ничем не подкреплённые, и пишет вердикт `status: passed` или `status: gaps_found` в `attack/decisions.md`. Строки с тяжестью `блокер` закрываются правкой журнала и повтором атаки.

### Шаг `proposal`

```text
/opsx:continue add-overdue
```

Файл `proposal.md`: зачем изменение и какие capabilities оно задевает. Основание — решённые записи журнала со ссылками `F-NN`.

### Шаг `specs`: требования и пробы

```text
/opsx:continue add-overdue
```

Модель пишет `specs/<capability>/spec.md`, затем две пробы. Проба краёв проходит каждое требование по восьми категориям и пишет файл покрытия `edge-probe.md`, по восемь строк на требование. Проба запретов спрашивает, чем требование может тихо стать. Найденное идёт кандидатами в журнал с исходами Specify, Dismiss, Backstop, Defer. Затем круг просмотрщика.

### Шаг `consequences`: опись последствий

Перед запуском можно выбрать, что войдёт в шаг. Выбор лежит в `symphysis.yaml` в корне проекта. Файл личный: `install` вносит его в `.gitignore`, в git он не идёт, каждый решает сам.

```yaml
# Личная настройка symphysis: в git проекта не идёт. Показать состав: symphysis config
consequences:
  failure_branches: true
  assumptions: true
edge_probe:
  enabled: true
```

Выбора три, у всех умолчание «включено», значения `true` или `false`. Нет файла или ключа — считается включённым.

| Ключ | Что включает |
| --- | --- |
| `consequences.failure_branches` | ветки отказа в описи |
| `consequences.assumptions` | допущения в описи |
| `edge_probe.enabled` | проба краёв на шаге `specs` |

Состав показывает `symphysis config`; ту же строку получает модель, человека она о составе не спрашивает.

```text
[..] symphysis.yaml: ветки отказа вкл, допущения вкл, проба краёв вкл
```

```text
/opsx:continue add-overdue
```

Модель берёт места кода из улик решённых развилок командой `journal.py code-sites`, разбирает их и пишет в `consequences.md` опись: что код делает при отказе и что конструкция об этом считает. Ветка без сценария в `specs/` становится кандидатом журнала, причём кандидаты пишутся раньше файла. В конце идут три причины провала всего изменения. Затем круг просмотрщика.

### Шаги `design`, `security`, `tasks`

```text
/opsx:continue add-overdue
```

Команда зовётся по разу на шаг. `design.md` собирается из журнала, модель дописывает контекст и границы. `security.md` — чек-лист канона безопасности по спекам. `tasks.md` — задачи с проверкой в каждой строке.

### Атака артефактов, по желанию

```text
/opsx:continue add-overdue attack-artifacts
```

Как атака журнала, но по `specs/`, `consequences.md`, `design.md`, `security.md` и `tasks.md`. Предупреждения идут человеку списком и в реализации читаются как заметки к задачам.

## Часть 3. После `tasks.md`

```text
/opsx:apply add-overdue
```

Реализация: модель идёт по `tasks.md` и отмечает `- [x]`, задача закрывается проверкой из своей строки. Невызванные атаки названы строкой перед работой. Результат в учебном проекте:

```text
python reminders.py overdue
```

```text
/opsx:sync add-overdue
```

Синхронизация: дельты из `specs/` изменения переходят в общие спеки `openspec/specs/`.

```text
/opsx:archive add-overdue
```

Архивация: изменение переезжает в `openspec/changes/archive/<дата>-add-overdue/`.

## Остальные команды

Установка ставит семь workflow профиля `core`. Три уже прошли выше вместе с `/opsx:continue`: `/opsx:apply`, `/opsx:sync`, `/opsx:archive`. Ещё три:

- `/opsx:explore` — обсудить задачу без артефактов, когда она ещё не ясна.
- `/opsx:update` — переписать готовые артефакты изменения и свести их между собой; код не трогает.
- `/opsx:propose` — создать изменение и все артефакты одним ходом. Для схемы symphysis основной путь — `/opsx:continue`: этим прохождением `/opsx:propose` не проверялся.

Остальные пять (`new`, `ff`, `bulk-archive`, `verify`, `onboard`) есть в форке, добавляет их `openspec config profile`, затем `openspec update` в проекте.

## Обновление

**Что меняется.** Те же глобальные записи, что при установке: новый тарбол заменяет команду `openspec`, ссылка `symphysis` остаётся. `openspec update` и `install --force` меняют только файлы проекта. `symphysis.yaml` и файл корней `.symphysis/tools/journal-roots.json` не трогаются и с `--force`.

**Откат.** Вернуться на прежний коммит клона и повторить этот раздел.

Имя нового тарбола — в `vendor/` и в поле `symphysis.openspecSource` файла `installer/package.json`.

PowerShell, из корня клона:

```powershell
git pull
npm --prefix installer ci
npm i -g ./vendor/<новый тарбол>
Set-Location ../reminders
openspec update
symphysis install --force
symphysis check
```

bash, из корня клона:

```bash
git pull
npm --prefix installer ci
npm i -g ./vendor/<новый тарбол>
cd ../reminders
openspec update
symphysis install --force
symphysis check
```

В конце `check: ok`. Без `npm --prefix installer ci` будет `[!!] payload старее исходников`, а без `--force` файлы схемы, отличные от новых, пропускаются строкой `пропущен: <путь> — отличается, нужен --force`.

## Другой клиент

Каталог скиллов выбранного клиента задаёт `--skills-dir`, параметр повторяемый, путь относительный от проекта. Он нужен и в `install`, и в `check`: без него `check` сверяет `.claude/skills`. Для opencode:

PowerShell:

```powershell
openspec init --tools opencode
symphysis install --skills-dir .opencode/skills
symphysis check --skills-dir .opencode/skills
```

bash:

```bash
openspec init --tools opencode
symphysis install --skills-dir .opencode/skills
symphysis check --skills-dir .opencode/skills
```

Имя команды у клиента своё: у opencode это `/opsx-continue`, файл `.opencode/commands/opsx-continue.md`. Список имён `--tools` показывает `openspec init --help`.

Прохождение этого руководства шло только на Claude Code. Установка для opencode выше проверена до `check: ok`, сам проект на нём не проходился.

## Разработчику

Этот шаг нужен только для запуска тестов инсталлятора и сборки нового тарбола. Пользователю он не нужен: установка выше идёт из тарбола без исходников форка.

Форк лежит вне git ядра, в ветке `openspec-fork`, а `bin/openspec.js` ждёт собранный `dist/`. Нужен `pnpm`: `npm i -g pnpm`, откат `npm rm -g pnpm`.

PowerShell, из корня клона:

```powershell
git fetch origin openspec-fork
git worktree add upstream/openspec FETCH_HEAD
pnpm --dir upstream/openspec install
pnpm --dir upstream/openspec build
npm --prefix installer ci
npm --prefix installer test
```

bash, из корня клона:

```bash
git fetch origin openspec-fork && git worktree add upstream/openspec FETCH_HEAD
pnpm --dir upstream/openspec install
pnpm --dir upstream/openspec build
npm --prefix installer ci
npm --prefix installer test
```

## Сбои

**Реестр npm недоступен.** Шаг форка или инсталлятора падает с `npm error code ECONNREFUSED`, `ENOTFOUND` или `ETIMEDOUT`. Причина — нет реестра или нужно зеркало. Настройка меняет `~/.npmrc` у всех проектов пользователя, откат `npm config delete registry`. После неё повтори упавшую команду, она поставит недостающее.

```text
npm config set registry <адрес зеркала>
```

**Индекс pip недоступен.** Шаг `pyyaml` падает с `ERROR: No matching distribution found for pyyaml`. Настройка меняет файл настроек `pip` пользователя, откат `python -m pip config unset global.index-url`. Затем повтори установку пакета.

```text
python -m pip config set global.index-url <адрес зеркала>
```

**PowerShell не даёт запускать скрипты.** Ошибка о выполнении сценариев на `npm.ps1` или `openspec.ps1`: зови `npm.cmd`, `openspec.cmd` и `symphysis.cmd`.

**`[!!] symphysis.yaml: нет пакета PyYAML`.** Шаг 5 пропущен или `python` в `PATH` другой. Настройки при этом считаются включёнными.

**`[!!] continue: клиент не настроен`.** В проекте не было `openspec init`: выполни команду из строки.

**Известное ограничение.** Префикс npm с пробелом и `&` вместе ломает сам шим npm (`SET dp0=%~dp0`): `install` заканчивается кодом 0 и печатает команду на потом.
