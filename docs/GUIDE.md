# Руководство по symphysis

symphysis — схема для OpenSpec: задача идёт от намерения человека через журнал решений, спецификации и опись последствий к списку задач, а решает на каждой развилке человек. Руководство ставит всё с нуля и проводит один маленький проект через все шаги настоящими командами.

**Сводка.** Часть 1: клон, форк OpenSpec из тарбола, выключение телеметрии, пакет `pyyaml`, инсталлятор, проект, `check: ok`. Часть 2: учебный проект от `intent.md` до `tasks.md`. Часть 3: реализация, синхронизация спек и архивация. Дальше — граф трассируемости, остальные команды, обновление, другой клиент, шаг разработчика и сбои.

Как читать блоки вывода: вывод CLI совпадёт с точностью до путей, заменённых на `<каталог>`. То, что пишет модель, помечено «пример, у читателя будет иначе». Вывод `npm`, `pip` и `git` не показан: числа и времена в нём меняются от запуска к запуску, поэтому их успех — код 0.

## Что понадобится

- Node 22.14 или новее, Python с `pip`, git и один native клиент: Claude Code, Codex или OpenCode.
- Доступ к репозиторию symphysis и к реестру npm и индексу pip или их зеркалу. Что делать без них — в разделе «Сбои».

Команды даны отдельно для PowerShell и bash. В PowerShell зови именно `where.exe`: `where` там псевдоним `Where-Object` и ничего не покажет. В Git Bash пути пиши прямыми слешами: `..\reminders` без кавычек станет `..reminders`, установка молча уйдёт не туда, а `check` там же ответит `ok`.

## Что изменится на машине

Базовая подготовка меняет четыре компонента. У каждого шага ниже описаны назначение
и откат; установка самого продукта в local/global описана отдельно после CLI.

| Шаг | Что меняется | Откат |
| --- | --- | --- |
| `npm i -g` тарбола | команда `openspec` у всех проектов пользователя; прежний глобальный OpenSpec заменяется | `npm rm -g @fission-ai/openspec` |
| `openspec config set telemetry.enabled false` | глобальный конфиг OpenSpec | `openspec config unset telemetry.enabled` |
| `python -m pip install pyyaml` | пакет в том Python, что первым стоит в `PATH` | `python -m pip uninstall pyyaml` |
| `npm i -g ./installer` | команда `symphysis`, ссылка ведёт в клон | `npm rm -g @niqsons/symphysis` |

## Часть 1. Установка

### 1. Клон

`<адрес репозитория>` — адрес, который дал владелец репозитория. Адрес без токена: токен в адресе остаётся в `.git/config` и в истории оболочки. Доступ к закрытому репозиторию держит хранилище учётных данных: на Windows это Git Credential Manager, он идёт с Git for Windows и спросит вход при первом клоне; на macOS и Linux — помощник из `git config --global credential.helper`.

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

Шаги 2–8 начинаются из корня клона, шаг 8 уводит в каталог проекта.

### 2. Форк OpenSpec

**Что меняется.** `npm i -g` ставит пакет `@fission-ai/openspec` в глобальный каталог npm и кладёт команду `openspec` в `PATH`: она действует у всех проектов этого пользователя. Уже стоящий глобально OpenSpec заменяется, поэтому его версию запиши заранее: `npm ls -g @fission-ai/openspec`. Ответ `(empty)` и код 1 значат, что OpenSpec не стоял и записывать нечего, это не сбой. Сборки нет, тарбол лежит в `vendor/`; из сети берутся только зависимости форка.

**Откат.** `npm rm -g @fission-ai/openspec`. Прежний OpenSpec вернёт `npm i -g @fission-ai/openspec@<записанная версия>`.

PowerShell:

```powershell
npm ls -g @fission-ai/openspec
npm i -g ./vendor/fission-ai-openspec-1.16.1+symphysis.5.tgz
```

bash:

```bash
npm ls -g @fission-ai/openspec
npm i -g ./vendor/fission-ai-openspec-1.16.1+symphysis.5.tgz
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
1.16.1+symphysis.5
```

Ключа `anonymousId` в файле нет. Если версия другая, раньше в `PATH` стоит другой `openspec`: `where.exe openspec` в PowerShell, `which openspec` в bash.

### 4. Где лежит глобальный конфиг

Путь показывает `openspec config path`. Задана `XDG_CONFIG_HOME` — конфиг лежит в `<XDG_CONFIG_HOME>/openspec/config.json`, и запись идёт только в этот файл: соседние каталоги с настройками других программ не трогаются. Не задана — `%APPDATA%\openspec\config.json` на Windows и `~/.config/openspec/config.json` на остальных системах.

Переменная, заданная не во всех оболочках, даёт два конфига. `openspec update` приводит проект к тому конфигу, что прочитал, поэтому из другой оболочки `/opsx:continue` может пропасть. `symphysis check` называет оба файла:

```text
[..] openspec: глобальный конфиг <каталог>\openspec\config.json; есть ещё <каталог>\openspec\config.json, он действует без XDG_CONFIG_HOME
```

Команды здесь нет, шаг только для чтения.

### 5. Пакет PyYAML

**Что меняется.** `pip` ставит пакет `pyyaml` в тот Python, что первым стоит в `PATH`: его увидят все программы на этом Python. Если пакет уже стоял, ничего не меняется. Без него настройки считаются включёнными, а `check` даёт `[!!]`.

**Откат.** `python -m pip uninstall pyyaml`, если пакета не было до этого шага: он мог быть нужен другим программам. Был ли он, покажет `python -m pip show pyyaml` до установки: код 1 и `Package(s) not found` значат, что не было.

PowerShell:

```powershell
python -m pip install pyyaml
```

bash:

```bash
python -m pip install pyyaml
```

### 6. CLI-инсталлятор

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
symphysis — установка и инструменты OpenSpec symphysis
```

`npm i -g ./installer` делает доступной команду, но ещё не устанавливает runtime
и скиллы в пользовательские каталоги. Выбери один из двух самостоятельных режимов:

- **Local:** продукт и native носители находятся в проекте; global-поставка не нужна.
  Продолжай шагом 8 с `symphysis install --scope local --client claude`.
- **Global:** общий runtime и native носители устанавливаются один раз для пользователя;
  клонированному store нужна отдельная инициализация. Используй раздел «Global: установка и store».

Native клиент — агентная среда Claude/Codex/OpenCode. Плагины VS Code, GIGA IDE и
OpenCode IDE — отдельные потребители: наличие native скиллов не устанавливает плагин.

### Global: установка и store

После шагов 1–6 установи продукт для нужного клиента. Повторяемый `--client`
позволяет поставить носители для нескольких клиентов. Эти команды одинаковы в
PowerShell и bash:

```text
symphysis install --scope global --client claude
git clone <адрес store> my-store
symphysis init --project ./my-store
symphysis check --scope global --project ./my-store
symphysis resolve --project ./my-store --json
```

Для Codex замени `claude` на `codex`, для OpenCode — на `opencode`. Global install
не принимает `--project` и `--store`, не создаёт planning root и не мигрирует проекты.
`init` работает с уже существующим корнем OpenSpec: добавляет правила и декларацию
совместимости, сохраняет чужие поля planning config, личные настройки, карту и ответы.
Неверная структура config даёт отказ до записи. Повторный init сохраняет данные.

Store — самостоятельный репозиторий спецификаций OpenSpec. Если открытый репозиторий
содержит OpenSpec pointer, `--project <source>` выбирает связанный store через форк,
а не создаёт второй planning root в source. Явно зарегистрированный store можно
выбрать через `--store <id>`; список показывает `symphysis openspec store list --json`.

Команды инструмента выполняются из выбранного store; `--project` обозначает исходный
каталог для его обнаружения. Например, из любого каталога:

```text
symphysis --project ./my-store openspec new change first-change
symphysis --project ./my-store help --change first-change
symphysis --project ./my-store journal check openspec/changes/first-change/decisions.json
symphysis --project ./my-store trace freeze first-change
```

Пути journal, файла ответов и `--out` разрешаются от исходного каталога `--project`
(без него — от cwd вызова), затем инструмент запускается с cwd выбранного store.
При запуске из pointer-source бери абсолютный `changeRoot` из JSON команды
`symphysis --project <source> openspec status --change <имя> --json`;
в JSON инструкций артефакта тот же каталог называется `changeDir`.
Используй его для входных и выходных файлов, например после создания журнала:

```text
symphysis --project <source> journal check "<changeRoot>/decisions.json"
symphysis --project <source> journal render-md "<changeRoot>/decisions.json" --out "<changeRoot>/decisions.md"
```

Можно открыть терминал в самом store и использовать обычные относительные пути.
Pointer уже выбирает связанный store; дополнительный `--store` для этого не нужен.
Селекторы dispatcher ставь перед именем инструмента, собственные параметры — после него.

Global runtime находится в `SYMPHYSIS_HOME/runtime`, если задан `SYMPHYSIS_HOME`;
иначе в `XDG_DATA_HOME/symphysis/runtime`, а без этих переменных — в
`%LOCALAPPDATA%/symphysis/runtime` на Windows или `~/.local/share/symphysis/runtime`
на остальных системах. Все overrides global-каталогов должны быть полными
абсолютными путями. Native носители имеют независимые назначения:

| Клиент | Global skills | Global agents/commands |
| --- | --- | --- |
| Claude | `~/.claude/skills` (либо `CLAUDE_CONFIG_DIR/skills`) | `agents`, `commands` того же client root |
| Codex | `~/.agents/skills` | `CODEX_HOME/agents` (по умолчанию `~/.codex/agents`) |
| OpenCode | `OPENCODE_CONFIG_DIR/skills`, иначе `XDG_CONFIG_HOME/opencode/skills` или `~/.config/opencode/skills` | `agents`, `commands` того же client root |

`CODEX_HOME` не переносит пользовательские skills Codex. `--skills-dir` и
`--agents-dir` повторяемы; с global это абсолютные назначения одного явно выбранного
клиента. Пользовательская проекция схемы OpenSpec также проверяется по manifest;
проектная схема с тем же именем не должна незаметно её перехватить.

`check` разделяет целостность файлов, наличие workflow каждого клиента и подтверждение
реальной сессии. Скопированные носители ещё не доказывают native discovery.

Установщик поддерживает самостоятельные local/global носители для Claude Code,
Codex и OpenCode. На 2026-11-10 для проверяемых сборок подтверждён следующий объём:

| Среда | Установка | Подтверждённая приёмка и её предел |
| --- | --- | --- |
| Claude Code | local/global | Сохранён прежний учебный пример Claude/local; свежая native-приёмка не проводилась |
| Codex 0.167.0 | local/global | Native discovery skills и workflow подтверждён; модельная приёмка заблокирована недоступным Windows MXC в тестовом окружении |
| OpenCode CLI 2.2.5 | local/global | Модель получила brainstorm skill, research-driver и guard до записи проверены; полный intent→archive не завершён; повторный вход водителя с готовыми выходами также не принят |
| Плагин VS Code | local/global | Пройдена приёмка установленной сборки |
| Плагин GIGA IDE | local/global | Пройдена приёмка установленной сборки |
| OpenCode IDE | Порт отложен | Приёмка установленного IDE-порта не завершена; проверка native CLI её не заменяет |

Ограничение проверки Codex относится к использованному Windows-окружению и не
становится требованием продукта. IDE-плагин не требуется для работы native-клиента;
его установленная приёмка также не подтверждает модельный флоу другого клиента.

Local и global не требуют друг друга. Если установлены оба, resolver выбирает local,
в том числе повреждённый: global не скрывает поломку. Конфликты native обнаружения
при смешанной установке пользователь разбирает явно; автоматическое объединение
не поддерживается.

### Принятие известных прежних файлов

Если OpenSpec уже создал native workflow, обычный install может отказать с
ownership-конфликтом: файл ещё не принадлежит этой поставке. `--force` не разрешает
замену чужого или изменённого файла. Для точных известных версий есть отдельный
просмотр и подтверждение; сходного имени или номера версии недостаточно.

Для global выполни первую команду, затем открой полученный JSON и проверь
назначения `files`, принимаемые `adoptions`, удаляемые `retiredPredecessors` и
`conflicts`. Продолжай второй командой только при `ready: true` и пустом списке
конфликтов. Команды одинаковы в PowerShell и bash:

```text
symphysis install --scope global --client claude --preview --out ./install-global-plan.json
symphysis install --apply-plan ./install-global-plan.json --confirm
```

Без `--out` preview печатает JSON в stdout и ничего не записывает. С `--out`
записывается только сам план; существующий файл плана не перезаписывается.
Для local принятие работает тем же способом:

```text
symphysis install --scope local --project ./my-store --client claude --preview --out ./install-local-plan.json
symphysis install --apply-plan ./install-local-plan.json --confirm
```

`--apply-plan` не принимает новые `--scope`, `--project`, `--client`, overrides
каталогов или `--force`: они уже зафиксированы просмотренным планом. При применении
installer заново проверяет пути, байты, профиль и поколения. Изменение после
просмотра даёт отказ без установки; исправь причину и создай новый preview под
новым именем. Неизвестные и пользовательские изменения остаются конфликтами:
сохрани свою правку отдельно и явно реши, какой файл должен остаться.

### Миграция выбранного store

Install обновляет поставку своего scope, а `migrate` явно переключает один store.
Для local → global сначала нужна исправная совместимая global-поставка с нужными
клиентами. Если её native файлы требуют принятия, пройди предыдущий раздел.
Из каталога, содержащего `my-store`, составь план:

```text
symphysis install --scope global --client claude
symphysis migrate --project ./my-store --to global --out ./to-global-plan.json
```

Открой JSON: проверь `storeRoot`, `from`, `to`, собственные удаляемые копии и
назначения в `files`, а также `conflicts` и `warnings`. Только после просмотра
готового плана подтверди переход и проверь результат:

```text
symphysis migrate --apply-plan ./to-global-plan.json --confirm
symphysis check --scope global --project ./my-store
symphysis resolve --project ./my-store --json
```

Миграция удаляет только подтверждённые собственные файлы прежней поставки.
Журналы, ответы, черновики, личный `symphysis.yaml` и карта корней сохраняются;
данные и несовместимые API автоматически не переводятся. Изменённый собственный
файл, неизвестная прежняя генерация, несовместимый источник или неподтверждённая
схема дают конфликт до переключения. При двух расположениях личной карты у
плоской legacy-установки preview требует явно разрешить неоднозначность, не читая
и не сливая содержимое карт. Остальные store продолжают работать в прежнем режиме.

Если файл, реальный путь или поколение изменились после просмотра, старый план
не применяется. После устранения причины составь и просмотри новый:

```text
symphysis migrate --project ./my-store --to global --out ./to-global-plan-v2.json
symphysis migrate --apply-plan ./to-global-plan-v2.json --confirm
```

Обратный переход создаёт самостоятельную local-поставку:

```text
symphysis migrate --project ./my-store --to local --out ./to-local-plan.json
symphysis migrate --apply-plan ./to-local-plan.json --confirm
symphysis check --scope local --project ./my-store
```

Перед второй командой также просмотри план. Global runtime и пользовательские
проекции не удаляются: ими могут пользоваться другие store. Предупреждение
`native-discovery-mixed` означает, что local и global носители выбранного клиента
сосуществуют. Resolver symphysis выберет local; порядок обнаружения самим native
клиентом нужно проверить отдельно, автоматическая очистка его конфликта не обещается.
Для local-работы открывай сам store: клиентские файлы устанавливаются в него.
Обычная новая local-установка по-прежнему не требует global.

Вместо прямого пути к store можно передать `--project ./app` с OpenSpec pointer
либо выбрать зарегистрированный store через `--store <id>` на команде preview.
Форк определяет единственный planning root. При `--apply-plan` селекторы не
добавляются: подтверждается именно просмотренный store.

### Справка, корни и запуск из IDE

`symphysis help` читает тексты шагов и версию выбранной поставки. Карта
`.symphysis/tools/journal-roots.json`, личный `symphysis.yaml`, журнал и ответы
относятся к store. В карте `<root>` раскрывается от `<store>/.symphysis`, поэтому
прежнее `<root>/..` по-прежнему обозначает store. Без карты доступен сам store;
пользовательские префиксы из соседнего проекта либо runtime не заимствуются.
Негодная существующая карта даёт явную диагностику.

После миграции прежней плоской установки личная карта может остаться в
`<store>/tools/journal-roots.json`: при отсутствии канонической карты используется
она, с прежней базой `<root>` от самого store. Наличие негодной канонической карты
не переключает чтение на эту сохранённую карту. Две разные карты не объединяются.

`symphysis --project <source> help --install-dir <dir>` меняет только дополнительное
место поиска скиллов после самого store. Этот параметр не выбирает runtime,
planning root, тексты шагов или версию. При global-установке найденные тела скиллов
и Mermaid включаются в HTML, поэтому странице не нужны абсолютный путь установки
или доступ к сети. Команда пересборки на панели выполняется из store журнала.

В IDE bootstrap и Python — разные уровни. Настройка `symphysis.commandPath`
указывает абсолютный путь команды symphysis или её JS-entrypoint, а
`symphysis.nodePath` — абсолютный Node для JS-entrypoint. Без явного commandPath
хост ищет symphysis в своём PATH; PATH терминала может отличаться. Наличие npm CLI
не доказывает установку global runtime: это проверяет `symphysis resolve`.
`toolsPath` не заменяет bootstrap и не служит разрешением запускать найденный Python
в обход отказа совместимости. Готовность конкретной сборки IDE-плагина проверяется
её установленной приёмкой; native клиент и IDE host имеют разные настройки.

### 7. Выбор клиента

Какой клиент есть на машине, покажут эти команды. Инсталлятор сам клиентов не ищет. Клиента нет — команда отвечает кодом 1 и текстом, что не нашла: это не сбой, а ответ. Дальше нужен хотя бы один клиент: без него шаг 8 ещё пройдёт, а Часть 2 вести нечем.

PowerShell:

```powershell
where.exe claude
where.exe codex
where.exe opencode
```

bash:

```bash
which claude
which codex
which opencode
```

Ниже сохранён учебный пример с командами Claude Code. У OpenCode имена workflow
отличаются: раздел «Другой клиент». Подтверждённый объём работы каждого клиента и
IDE указан в матрице готовности выше.

### 8. Проект

Учебный проект лежит в `docs/guide/example/`: код `reminders.py`, его данные
`reminders.json`, `README.md` и задача `intent.md`. Он копируется рядом с клоном.
Local install явно создаёт planning config, схему и охраняемые native workflow,
скиллы, тела агентов в `.claude/agents/`, инструменты журнала, общие файлы с
уведомлениями MIT в `.symphysis/docs/` и личный `symphysis.yaml`. Отдельный
`openspec init` перед ним не нужен: уже созданные чужие носители могут конфликтовать
с управляемыми. Если телеметрия не настроена, installer выключает её в глобальном
конфиге OpenSpec; явное значение сохраняет.

Команды идут из каталога проекта. Параметр `--project` им не нужен; если он понадобится, путь относительный и с прямыми слешами. `git init` нужен, чтобы `symphysis.yaml` было от чего отделять: файл личный и в коммит не идёт.

PowerShell:

```powershell
Copy-Item -Recurse docs/guide/example ../reminders
Set-Location ../reminders
git init
symphysis install --scope local --client claude
symphysis check
$LASTEXITCODE
```

bash:

```bash
cp -r docs/guide/example ../reminders
cd ../reminders
git init
symphysis install --scope local --client claude
symphysis check
echo $?
```

Вывод `symphysis install` начинается числом записанных файлов; оно зависит от
выбранных клиентов и версии payload:

```text
записано <N>
```

Строка о `.gitignore` значит: сам `.gitignore` войдёт в коммит вместе с работой, а `symphysis.yaml` в git не пойдёт.

Вывод `symphysis check` и код:

```text
[..] symphysis.yaml: ветки отказа вкл, допущения вкл, проба краёв вкл, водители: атака вкл, пробы выкл, опись выкл, исследование вкл
[..] openspec: глобальный конфиг <каталог>\openspec\config.json
[..] telemetry: выключена
check: ok
0
```

`[!!]` — расхождение, код выхода 2, и в строке названа команда, которая его снимает. `[..]` — сведения, на код не влияют. Команда `/opsx:continue` теперь есть в проекте, файл `.claude/commands/opsx/continue.md`.

## Часть 2. От намерения до задач

Запусти `claude` в каталоге проекта. Строки вида `/opsx:continue add-overdue` набираются в чате клиента, остальные команды — в терминале. На модели Sonnet весь проект с атаками занял около десяти минут её работы.

Все шаги схемы идут одной командой: `/opsx:continue` делает следующий шаг и останавливается. Какой шаг следующий, показывает `openspec status --change add-overdue`.

### Создать изменение и положить намерение

PowerShell:

```powershell
symphysis openspec new change add-overdue
Move-Item intent.md openspec/changes/add-overdue/intent.md
symphysis openspec status --change add-overdue
```

bash:

```bash
symphysis openspec new change add-overdue
mv intent.md openspec/changes/add-overdue/intent.md
symphysis openspec status --change add-overdue
```

Вывод `openspec new change` и статуса:

```text
Created change 'add-overdue' at openspec\changes\add-overdue/
Schema: symphysis
Next: openspec status --change add-overdue
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

1. Открой `openspec/changes/add-overdue/symphysis.html` в браузере.
2. У каждой развилки выбери вариант; слово к выбору необязательно. Спорный вопрос можно припарковать.
3. Нажми «Скопировать промпт» и вставь его в чат.
4. Модель сохраняет промпт в `answers/<дата>.md`, каталог создаёт сама, и вносит его командой `symphysis journal apply`.

Улики и файлы, названные в вопросе, на странице — ссылки: открывается файл, а значок ↗ рядом открывает его в редакторе на нужной строке. Редактор выбирается один раз в шапке страницы и хранится в браузере. Значок работает из внешнего браузера: встроенные браузеры VS Code и GIGA IDE такие ссылки не открывают. Файлы `.ts` браузер в Windows скачивает, их открывай значком. Для IDEA и GIGA IDE в Windows нужен зарегистрированный протокол `jetbrains`: раздел «Сбои».

Короткий путь для учебного проекта: написать в чат `реши сам`. Модель внесёт рекомендованные варианты строками `- F-NN: X — «реши сам»`, и в журнале будет видно, что решение отдано модели. Слово действует только на записи, показанные сейчас: на следующем круге его пишут заново.

Решить можно и без страницы: написать решение в чат, модель внесёт его тем же способом. Если тебе удобнее работать только в чате или только на странице, скажи об этом модели: этого достаточно.

Справка о шагах есть на странице `symphysis.html`: открывается кнопкой «схема · справка», затем вкладка «справка»; считается командой `symphysis help`.

### Шаг `decisions`: журнал решений

```text
/opsx:continue add-overdue
```

Модель читает `intent.md` и код, записывает критерии готовности фактами, а развилки — записями с вариантами, уликами из кода и рекомендацией. Вопросы, которых нет ни в файлах, ни в вариантах, она задаёт порциями в чате. Затем круг просмотрщика.

Развилки в журнале, пример, у читателя будет иначе:

```text
F-5  Что делать с напоминанием, чей срок не разобран (`due: "завтра"`)?
F-6  Просрочено ли напоминание, срок которого сегодня?
F-7  Как напечатать просроченное напоминание?
F-8  Как оформить код выбора просроченных: опереться на `load_reminders` и `parse_due` или читать файл заново?
```

После круга модель спрашивает, начинать ли новый. Для учебного проекта ответ `нет, круг закончен`: он ложится в `notes[]` журнала строкой «брейншторм закончен по решению человека».

### Шаг `research`: исследование и второй круг

```text
/opsx:continue add-overdue
```

На каждую запись, припаркованную к агенту, модель составляет brief: слово человека, что выяснить, область чтения. Исследование одной парковки по умолчанию исполняет субагент-водитель по скиллу `symphysis-research`: brief и его отчёт лежат в `openspec/changes/add-overdue/briefs/symphysis-research-<дата>/`, а файл `research/<F-NN>.md` несёт находки `путь:строка «цитата»` и честное «не найдено» с шаблонами поиска. Парковок нет — один файл `research/none.md`, это законный исход. Если строки «брейншторм закончен» в журнале ещё нет, в конце она снова спросит о новом круге, ответ тот же.

### Атака журнала, по желанию

```text
/opsx:continue add-overdue attack-decisions
```

Шаг необязательный и зовётся только по имени: модель ищет в журнале утверждения, ничем не подкреплённые, и пишет вердикт `status: passed` или `status: gaps_found` в `attack/decisions.md`. Строки с тяжестью `блокер` закрываются правкой журнала и повтором атаки. По умолчанию атаку исполняет субагент-водитель: brief с хешами целей и его отчёт лежат в `openspec/changes/add-overdue/briefs/symphysis-attack-<дата>/`, вопросы водителя главная нить задаёт в чате.

Вердикт привязан к хешу журнала, а следующие шаги журнал дописывают. Поэтому позже статус покажет `attack-decisions (verdict: stale — signal, not a gate)`: это сигнал, идти дальше можно, свежий вердикт даст повтор той же команды. Что именно устарело, называет `symphysis journal check openspec/changes/add-overdue/decisions.json` строкой `[..] атака журнала: после вердикта добавлено N записей: …`; те же строки справка шага отдаёт полем `stale_scope`. Повтор той же командой проходит только названные записи и их стыки (записи, связанные с новыми через `depends_on`, `antipodes` или номера в `consequences`), остальные строки таблицы остаются. Вызванная атака входит в счёт: вместо `1/9` в строке `Progress` будет `/10`, а со второй атакой `/11`.

Предупреждение можно отметить прочитанным на странице `symphysis.html`: у строки `предупреждение` в режиме «атака» стоит переключатель «прочитано», отметка уходит в промпт возврата текстом «предупреждение прочитано: <раздел>» и после `apply` ложится заметкой в `notes[]` журнала; при пересборке страница показывает флаг по этой заметке (подпись «в журнале», до внесения — «не внесено»). Заметка меняет хеш журнала, поэтому вердикт станет `stale` с составом «записей не добавлено: журнал изменён иначе»; повтор той же командой обновит хеш, а в итоге назовёт прочитанные предупреждения с пометкой «(прочитано)». Флаг — свидетельство прочтения, не снятие: тяжесть, счётчики и вердикт он не меняет.

Тяжесть строки человек может сменить сам, и тоже на странице: у строки `блокер` в режиме «атака» стоит кнопка «понизить», у строки `предупреждение` — «повысить»; у строк `справка` и у строк покрытия кнопки нет. Обоснование пишется в собственном свёрнутом поле кнопки, отдельно от поля спора: нажатая кнопка без текста строки не даёт. В промпт возврата уходит строка о тяжести: `- тяжесть: openspec/changes/add-overdue/attack/decisions.md · <раздел> · «<утверждение>» → предупреждение — «<обоснование>»`; путь к файлу атаки считается от корня проекта, как его показывает страница, и `apply` принимает его только в таком виде. `apply` перепишет ячейку тяжести в файле атаки в `предупреждение (<обоснование>)` и пересчитает `status`, так что вердикт `gaps_found` станет `passed` в момент `apply`, а не в момент нажатия, и только если понижен последний блокер; повышение `предупреждение` → `блокер` у `passed` вернёт `gaps_found`. Журнал `add-overdue/decisions.json` при этом не меняется, поэтому вердикт от такой строки не устаревает. Повтор атаки хранит слово человека, пока строка с тем же файлом, разделом и утверждением на месте, а её опора не «есть»; когда строка исчезла или опора стала «есть», слово снимается. Кнопок тяжести в плагине пока нет: на странице `symphysis.html` они работают, в виде атаки плагина будут позже.
<!-- src: F-17, F-18, F-19, F-20, F-47 -->

### Шаг `proposal`

```text
/opsx:continue add-overdue
```

Файл `proposal.md`: зачем изменение и какие capabilities оно задевает. Основание — решённые записи журнала со ссылками `F-NN`.

### Шаг `specs`: требования и пробы

```text
/opsx:continue add-overdue
```

Модель пишет `specs/<capability>/spec.md`, затем две пробы. Проба краёв проходит каждое требование по восьми категориям и пишет файл покрытия `openspec/changes/add-overdue/edge-probe.md`, по восемь строк на требование, а итог — строкой `notes[]` журнала. Проба запретов спрашивает, чем требование может тихо стать. Найденное идёт кандидатами в журнал с исходами Specify, Dismiss, Backstop, Defer. Затем круг просмотрщика. Пробы по умолчанию идут в главной нити; ключ `drivers.probes` в `symphysis.yaml` отдаёт их водителю.

Строки файла покрытия и итог, пример, у читателя будет иначе:

```text
- overdue-reminders/Вывод просроченных напоминаний · empty · кандидат F-10
- overdue-reminders/Вывод просроченных напоминаний · ordering · кандидат F-9
- overdue-reminders/Команда list не меняется · empty · не выбран: пустой или отсутствующий файл; `list` печатает то же, что до изменения
- overdue-reminders/Команда list не меняется · boundary · неприменимо: формы collection, io; boundary только для numeric-range

проба краёв: кандидатов 3, Specify 0, Dismiss 0, Backstop 0, Defer 0; кандидаты без решения F-9, F-10, F-11; не выбран 1: overdue-reminders/Команда list не меняется
```

### Шаг `consequences`: опись последствий

Перед запуском можно выбрать, что войдёт в шаг. Выбор лежит в `symphysis.yaml` в корне проекта. Файл личный: `install` вносит его в `.gitignore`, в git он не идёт, каждый решает сам.

```yaml
# Личная настройка symphysis: в git проекта не идёт. Показать состав: symphysis config
consequences:
  failure_branches: true
  assumptions: true
edge_probe:
  enabled: true
drivers:
  attack: true
  probes: false
  consequences: false
  research: true
```

Значения `true` или `false`. Нет файла или ключа — умолчание ключа: у частей шагов «включено», у водителей — как в примере выше.

| Ключ | Что включает |
| --- | --- |
| `consequences.failure_branches` | ветки отказа в описи |
| `consequences.assumptions` | допущения в описи |
| `edge_probe.enabled` | проба краёв на шаге `specs` |
| `drivers.attack` | атака идёт субагенту-водителю по brief, по умолчанию включено |
| `drivers.probes` | пробы краёв и запретов идут водителю, по умолчанию выключено |
| `drivers.consequences` | опись последствий идёт водителю, по умолчанию выключено |
| `drivers.research` | исследование идёт водителю, по умолчанию включено |

Водитель — субагент, который исполняет шаг по brief и возвращает отчёт файлом; человека он не спрашивает, вопросы пишет в отчёт, а главная нить задаёт их в чате и вносит слово. Тела водителей `symphysis install` кладёт в `.claude/agents/` проекта; каждое грузит тело своего скилла полем `skills:`. Нет тела в каталоге агентов — шаг идёт в главной нити по тому же скиллу, brief не пишется.

Состав показывает `symphysis config`; ту же строку получает модель, человека она о составе не спрашивает.

```text
[..] symphysis.yaml: ветки отказа вкл, допущения вкл, проба краёв вкл, водители: атака вкл, пробы выкл, опись выкл, исследование вкл
```

```text
/opsx:continue add-overdue
```

Модель берёт места кода из улик решённых развилок командой `journal.py code-sites`, разбирает их и пишет в `consequences.md` опись: что код делает при отказе и что конструкция об этом считает. Кандидатом журнала становится ветка, чей исход не назван в THEN ни одного сценария из `specs/`, причём кандидаты пишутся раньше файла. В конце идут три причины провала всего изменения. Затем круг просмотрщика.

Начало файла, пример, у читателя будет иначе. Первая строка описи здесь — ветка `load_reminders`, на которую сценария не было: битый файл выглядит как пустой список.

```markdown
**Состав:** ветки отказа, допущения

## Опись

- **Загрузка напоминаний: битый JSON** — `reminders.py:16` «except json.JSONDecodeError:»
  - при отказе: возвращает пустой список, `overdue` ничего не печатает
  - допущение: конструкция считает, что файл всегда корректен; если он повреждён, `overdue` выглядит как «просроченных нет»
  - кандидат: F-12; ближайший сценарий: Просроченные идут от старых к новым
```

Кандидат той же ветки в журнале, пример, у читателя будет иначе:

```text
F-12 [ветка] Загрузка напоминаний: битый `reminders.json` читается как пустой список — что видит человек у `overdue`?
A. Specify — GIVEN `reminders.json` содержит `{` WHEN выполнена команда `overdue` THEN в stderr сообщение «файл напоминаний не читается», код выхода 1, stdout пуст
B. Dismiss — битый файл даёт пустой вывод; допустимо, пока файл ведёт только `add`
C. Backstop — тест подаёт файл `{` и утверждает, что `overdue` завершается без трассировки
D. Defer — что делать с нечитаемым файлом, остаётся открытым до решения о восстановлении данных
```

Выбранный Specify становится новым сценарием в `spec.md`.

### Шаги `design`, `security`, `tasks`

```text
/opsx:continue add-overdue
```

Команда зовётся по разу на шаг, порядок показывает `openspec status`. `design.md` собирается из журнала, модель дописывает контекст и границы; повторная сборка эти разделы стирает, поэтому после правки журнала модель вписывает их заново. `security.md` — чек-лист канона безопасности по спекам. `tasks.md` — задачи с проверкой в каждой строке.

### Атака артефактов, по желанию

```text
/opsx:continue add-overdue attack-artifacts
```

Как атака журнала, но по `specs/`, `consequences.md`, `design.md`, `security.md` и `tasks.md`. Предупреждения идут человеку списком и в реализации читаются как заметки к задачам; на странице их можно отметить прочитанными так же, как у атаки журнала; кнопки тяжести работают там так же.

Вызванная атака становится воротами: пока у неё `gaps_found`, `/opsx:apply` не начнётся. Блокер закрывается правкой файла, а если не хватает решения — новой развилкой журнала, её решает человек. Затем та же команда ещё раз. Атаку, которую не вызывали, `/opsx:apply` только называет строкой `атаки не вызывались`.

Ожидай этот круг: на учебном проекте первый вызов дал `gaps_found` с тремя блокерами оба раза, второй — `passed`. Статус, когда атака прошла:

```text
Change: add-overdue
Schema: symphysis
Change root: <каталог>\openspec\changes\add-overdue
Progress: 11/11 artifacts complete

[x] intent
[x] decisions
[x] research
[x] attack-decisions (verdict: stale — signal, not a gate)
[x] proposal
[x] specs
[x] consequences
[x] design
[x] security
[x] tasks
[x] attack-artifacts (verdict: ok)

All planning artifacts complete!
Next: openspec instructions apply --change "add-overdue" --json
```

## Часть 3. После `tasks.md`

```text
/opsx:apply add-overdue
```

Реализация: модель идёт по `tasks.md` и отмечает `- [x]`, задача закрывается проверкой из своей строки. Перед первой задачей и после последней она зовёт заморозку графа и отдаёт тебе ссылку на отчёт `graph/report.md`: раздел «Граф трассируемости». Результат в учебном проекте, код писала модель, пример, у читателя будет иначе:

```text
python reminders.py overdue
2020-01-15 вернуть книгу
2020-03-01 продлить домен
```

```text
/opsx:sync add-overdue
```

Синхронизация: дельты из `specs/` изменения переходят в общие спеки `openspec/specs/`.

```text
/opsx:archive add-overdue
```

Архивация: до вопроса о синхронизации модель проверяет `graph/` и при нужде замораживает граф заново. Изменение переезжает в `openspec/changes/archive/<дата>-add-overdue/`. Спеки уже синхронизированы, поэтому команда спросит: `Archive now`, `Sync anyway` или `Cancel`. Выбирай `Archive now`. Без шага синхронизации она предложит сделать его сама.

## Граф трассируемости

Граф показывает, чем держится каждое требование изменения: какая запись журнала за ним стоит, какой сценарий его проверяет, какая задача сценарий закрывает. Нужен он затем, что человек прочитал требование и решил, что оно будет в реализации, а оно тихо выпало: граф называет такие зазоры списком. Скрипт `trace_graph.py` собирает граф из файлов изменения: `intent.md`, `decisions.json`, `specs/`, `consequences.md`, `security.md`, `tasks.md`. Напрямую граф не правится: правится файл изменения, граф пересобирается. Живого файла графа у изменения нет, он считается при каждом вызове; на диск граф ложится только заморозкой.

Порядок шагов граф не меняет. Он добавляет три точки, где модель зовёт скрипт (подраздел «Где появляется `graph/`»), и сигналы, которые решает человек. Сигнал не останавливает ни шаг, ни `/opsx:apply`, ни архивацию: код выхода команд при сигналах остаётся нулевым.

### Команды

Команды идут из каталога проекта; `add-overdue` — имя изменения.

| Команда | Что даёт |
| --- | --- |
| `symphysis trace build add-overdue` | граф в JSON в stdout: узлы, связи, кандидаты связей между требованиями (запись со статусом `припаркован` кандидатов не даёт, связь `traces` к ней остаётся) |
| `symphysis trace build add-overdue --out graph.json` | тот же граф в файле; каталоги пути создаются, файлы изменения не меняются |
| `symphysis trace build add-overdue --format mermaid` | текст `requirementDiagram` для Mermaid, предел 50 000 знаков без выбора и с `--capability`; у `--requirement` предела нет, а превышение даёт отказ с кодом 1 и подсказкой, чем выбрать меньше |
| `symphysis trace report add-overdue` | отчёт Markdown: находки `openspec validate` и сигналы графа группами тяжести — «Связь не разрешена», «Опоры нет», «Реализация не закрывает» — подзаголовком со счётом строк, внутри группы по месту в файле |
| `symphysis trace check add-overdue graph.json` | сверка сохранённого файла графа с изменением: не устарел ли и не правили ли его руками; файл другой версии формата отвергается строкой с обеими версиями («формат 1, а скрипт читает 2») |
| `symphysis trace freeze add-overdue` | заморозка: снимок `req-graph.json` и отчёт `report.md` в `graph/` изменения |
| `symphysis trace archive-gaps` | какие изменения в архиве остались без снимка |

Диаграмма берёт часть графа: `--capability <имя>` оставляет одну capability, `--requirement <имя>` одно требование; если имя есть у двух capability, пиши `capability/имя`. Скрипт печатает только текст: картинку по нему строишь ты или модель, файла с рисунком скрипт не создаёт. Весь граф одной картинкой в symphysis не входит, поэтому на большом изменении бери часть. Коды выхода у всех команд: 0 — выполнено, 1 — отказ с текстом в stderr (нет изменения, негодный журнал, путь не записать), 2 — вызов неверен. Справка по каждой подкоманде — `--help`.

В Mermaid задача подписана номером и явным названием: `- [ ] 1.2 **Сохранить отчёт** — полное тело; проверка: …` даёт `TASK_1.2 Сохранить отчёт`. Без начальной формы `**Название** — тело` остаётся `TASK_1.2`. Название новых задач — обычный текст до 80 знаков, вся подпись ограничена 90. Полное тело, checkbox и ссылки сохраняются в tasks.md и JSON графа; Mermaid указывает исходную строку в docref. Старые задачи и снимки format 2 не требуют миграции.

### Граф и `openspec validate`

Отчёт сам запускает `openspec validate --json` форка и ставит находки рядом с сигналами графа: один файл вместо двух проверок. Голый `openspec validate` сигналов графа не покажет, а `report` его не заменяет. Форк берётся из переменной `SYMPHYSIS_OPENSPEC`, затем из `PATH`; если `validate` не запустился, в отчёте строка `validate не запустился` с причиной, а сигналы графа остаются.

### Где появляется `graph/`

Каталог `graph/` лежит внутри каталога изменения. В нём два файла: `req-graph.json` — замороженный граф с хешами исходников, коммитами корней и базой мастер-спеки, и `report.md` — отчёт, абсолютных путей в нём нет. Новый снимок имеет `format: 3`, читатель поддерживает форматы 2 и 3: база мастер-спеки хранит ссылки строками той формы, в какой они стоят в тексте. Пригодная base формата 2 сохраняет прежний смысл MODIFIED после sync; старый формат не получает нынешнюю структуру модулей задним числом. Архивы автоматически не переписываются. Заморозка активного изменения поверх формата 1 собирает граф заново и называет поддерживаемые версии; база при этом снимается с живого мастера. Команда одна, `freeze`, и звать её модель умеет сама:

1. Перед первой задачей `/opsx:apply`: снимок и отчёт появляются до реализации. Снимок тогда мало что значит, но уже несёт базу мастер-спеки по требованиям MODIFIED.
2. Когда отмечена последняя задача `/opsx:apply`: `freeze` повторяется. Это раньше `/opsx:sync`: после синхронизации новый сценарий MODIFIED уже лежит в мастере, и сигнал о нём замолчал бы.
3. В `/opsx:archive` до вопроса о синхронизации: `freeze` собирает граф заново, если каталога, снимка или отчёта нет либо файлы изменения разошлись со снимком; свежий снимок только обновляет коммиты корней, граф и отчёт остаются прежними.

Архивирует изменение только скилл `/opsx:archive`: он дожидается выбранного sync и его якоризации, проверяет результат, затем переносит каталог сам. Уже завершённую привязку повторять не требуется. При `Archive without syncing` мастер не меняется. CLI `symphysis openspec archive` к общей спеке с якорями не применяется: он сверяет блоки по равенству текста, блок с якорями считает не применённым и перепишет его дельтой с голыми номерами.

Результат переноса можно проверить отдельно: `symphysis sync-check <имя> --json`, при частичном sync — с повторяемым `--capability <имя>`. Проверщик ничего не пишет: `match` означает совпадение проверенных частей, `mismatch` называет явное расхождение, `review` требует суждения по тексту или происхождению ссылки. Голый номер и якорь одного числа не обязательно ссылаются на один журнал. Поздний снимок уже заякоренного мастера прежнего происхождения не доказывает. После запрошенного sync неразрешённая проверка оставляет изменение активным; отдельный выбор архива без sync сохраняется и при ошибке графа.

Когда граф собран заново, вывод `freeze` называет путь к `graph/report.md`; на ветке «Снимок свежий: обновлены только коммиты корней, граф и отчёт прежние.» ссылки в выводе нет, отчёт лежит там же. Модель отдаёт тебе ссылку на него без пересказа и без отбора строк: читай отчёт сам. Сигнал отчёта не повод править спеки и задачи без твоего слова. Дочернее требование, вынесенное из длинного родителя, без своего номера записи получает сигнал «требование без записи»: ему нужен номер решения, по которому требование делили (F-76, F-150). Ручной `openspec archive` мимо скилла заморозку не вызывает: для этого есть `archive-gaps`.

### Соглашения в артефактах

Граф читает связи из текста, поэтому модель держит несколько привычек в самих файлах. Знать их нужно, чтобы понять сигнал и поправить файл, если модель отступила.

- Требование называет решения журнала номером в скобках: `(F-NN)` в его тексте. Запись другого изменения называется якорем `(<изменение>/F-NN)`: имя — каталог изменения, без даты архива.
- В общей спеке `openspec/specs/` ссылки на записи синхронизированного изменения стоят якорем всегда: после переноса блоков шаг sync зовёт `symphysis anchors <имя>` (при частичном переносе — с повторяемым `--capability <имя>` только для выбранных capabilities), завершённая привязка при архиве повторно не требуется; `rules.specs` задаёт форму ссылок; скрипт переписывает голые номера журнала в блоках этого изменения, маркеры и комментарии блока тоже, и печатает каждую замену. Сверь `git diff` общих спек с его выводом: других правок ссылок быть не должно, руками их не переписывают. Голый номер, который стоял в блоке до синхронизации, принадлежит прежнему журналу и остаётся голым: скрипт узнаёт его по базе снимка.
- Задача называет сценарий в форме `` `capability`: «имя сценария» `` у каждого названного имени. Задача без сценария, например полный прогон тестов, заканчивается словом `` `служебная` `` в обратных кавычках: сигнал «задача ни к чему» её не считает.
- Длинное требование делится: часть уходит в дочернее требование, и оно называет родителя фразой `Часть требования «имя».` (у другой capability — вместе с её именем).
- Под заголовком сценария, появившегося по исходу Specify, стоит комментарий `<!-- F-NN -->` с номером записи.
- Запись журнала, которая снимает прежнее решение, называет его в `depends_on`: сигнал показывает рядом «снято F-NN?».

### Как скрипт разрешает связи

Правила простые, и по ним можно предсказать, что скрипт увидит.

- Ссылка на запись пишется в трёх формах: голая `F-NN` с буквой варианта или без неё (`F-07.A`), якорь `<изменение>/F-NN` и список с именем журнала перед ним (``журнал `имя`: F-NN, F-MM``). Номер ищется по границе слова: после буквы, цифры, дефиса или косой черты он номером не считается, так `UTF-8` номера не даёт; точка со строчной буквой после числа (`research/F-01.md`) — не ссылка. Ссылка без имени или с именем этого изменения — своя и ведёт к записи `F-NN`; с именем другого изменения проекта — чужая: ни связи, ни сигнала; с именем, которого нет ни в `openspec/changes/`, ни в архиве, — сигнал «неизвестное имя или номер» с этим именем. Имя после списка без двоеточия именем не считается: ссылка голая.
- Если после «ёлочки» подходят несколько известных имён, берётся самое длинное, что стоит в строке целиком вместе с закрывающей `»`.
- Задача к сценарию ведёт связью `satisfies`, ветка описи к сценарию — `verifies`, пункт `security.md` к требованию — `refines`. Ветка называет сценарий подстрокой `сценарий: <имя>`, а слова «ближайший сценарий» связи не дают. Пункт `security.md` называет требование в любой из двух форм, `` `capability` «имя» `` и `` `capability`: «имя» ``, в любой колонке строки.
- Имя, которое нашлось только в мастер-спеке, молчит: ни связи, ни сигнала, потому что узла в графе изменения у него нет. Имя, которого нет нигде, даёт сигнал «неизвестное имя или номер».
- Образец формы в двойных обратных кавычках, как в описании самой формы, не ссылка: связи и сигнала не даёт.
- У требования MODIFIED ссылки мастер-текста отсекаются по полному ключу — число, буква варианта, имя изменения: голое `(F-20)` против голого `(F-20)` отсекается и остаётся сигналом «требование без записи», а `(F-26)` рядом с `F-26.B` или со ``журнал `другое`: F-26.B`` мастера связь даёт. Так же для следов из мастера: комментарии проб и номера сценария, перенесённые без изменения, с журналом изменения не сверяются, ложного «след отстал» нет.
- Номер в следе пробы (`<!-- проба краёв: … исходы: F-NN … -->`, то же для проб запретов) в конце блока требования даёт связь `traces` со строкой следа при любом исходе. Если номер стоит и в тексте, и в следе, связей две с разным местом, это не повтор. След, перенесённый из мастера в MODIFIED, связи не даёт. Номер вне журнала даёт сигнал «неизвестное имя или номер», как в тексте.
- Ссылки в тексте дочернего требования, которые стоят в мастер-тексте его родителя, связей не дают — тем же ключом: число, буква, имя.
- Сигнал «требование без записи» гасит только номер в тексте требования: связь из следа пробы и связь к записи со статусом `припаркован` его не гасят (F-158), и номер, отсечённый как чужой, тоже.
- Повторный id узла и неразрешённая ссылка не пропадают молча: дубль идёт сигналом «неоднозначное имя» с обоими местами, в графе остаётся первый узел; ссылка без разрешения связи не даёт и идёт сигналом «неизвестное имя или номер».
- Строка описи без места `путь:строка` узла в графе не даёт: допущение без цитаты в граф не попадает.

### Ответ на сигнал

Сигнал в отчёте — строка вида `[!!] <вид>: <ключ> — <место>`. Пример, у читателя будет иначе:

```text
[!!] требование без задачи: overdue-reminders/Вывод просроченных напоминаний — specs/overdue-reminders/spec.md:3
```

В отчёте строки стоят группами тяжести под подзаголовками «Связь не разрешена», «Опоры нет», «Реализация не закрывает», у каждого счёт строк: сначала то, что сломано сильнее — ссылка никуда не ведёт, — потом то, чему нет опоры в журнале, потом то, что реализация не закрывает. Имена групп — не слова тяжести: строка любой группы, и нижней тоже, ждёт твоего ответа или записи `[сигнал]`, как без групп; сама строка от группы не зависит, вид и ключ копируются из неё так же.

Чтобы записать решение по сигналу, скажи его модели: она заведёт запись журнала, чей вопрос начинается так: `[сигнал] <вид> · <ключ>`. Вид и ключ копируются из строки отчёта: ключ — ровно то, что стоит между `вид: ` и ` — место`. Для сигнала выше:

```text
[сигнал] требование без задачи · overdue-reminders/Вывод просроченных напоминаний
```

У сигнала «решение без требования и задачи» ключ несёт номер записи и усечённый текст вопроса, как он напечатан в строке: копируй его целиком, с многоточием. У записи те же исходы Specify, Dismiss, Backstop, Defer и тот же круг просмотрщика. Сигнал снимает только запись с решением: пока вариант не выбран, отчёт поднимает сигнал снова.

### Изменения без снимка

Снимок появляется заморозкой, а заморозку зовёт модель по подсказке, которую она может пропустить; ручной `openspec archive` подсказки не читает вовсе. Изменения в архиве без снимка находит скрипт:

```text
symphysis trace archive-gaps
```

Без аргумента он читает `openspec/changes/archive`, с аргументом — любой каталог архива. Изменения без `graph/req-graph.json` он называет строками `Без снимка: <имя>`; изменения старше первого снимка идут одной строкой со счётом, поимённо только более новые. Скрипт только читает: снимок не собирает и файлов не прибавляет. `symphysis check` его не зовёт и таких изменений сам не ищет, поэтому запускай `archive-gaps` сам, например после ручного `openspec archive`.

### Линзы `trace-link`, `rule-compliance` и настройки атаки

Атака артефактов проверяет связи графа линзой `trace-link`: модель берёт связи из вывода `trace_graph.py build` и судит, закрывает ли задача названный сценарий и задета ли сценарием названная ветка отказа. Включение линзы личное и лежит в `symphysis.yaml` в группе `attack`: ключ равен слугу линзы.

```yaml
attack:
  trace-link: false
```

Линза `rule-compliance` («правила составления») сверяет артефакт с правилами составления его шага и требование `MODIFIED` — с текстом мастер-спеки: при делении и ужатии не должны пропасть условия. Пропавшее условие мастер-текста в её строке идёт с тяжестью `блокер`, прочие нарушения правил — с причиной `предупреждение (правило составления)`. Выключается ключом `attack.rule-compliance: false`.

Остальные линзы настраиваются так же: `attack.rule-compliance`, `attack.context-compliance`, `attack.claim-authority`, `attack.claim-extraction`, `attack.coverage`, `attack.scenario-run`. Нет файла или ключа — линза включена. Состав показывает `symphysis config`.

## Остальные команды

Установка ставит workflow профиля `core` и обязательный `new`: восемь охраняемых
носителей при стандартном профиле. Три уже прошли выше вместе с `/opsx:continue`:
`/opsx:apply`, `/opsx:sync`, `/opsx:archive`. Ещё три:

- `/opsx:explore` — обсудить задачу без артефактов, когда она ещё не ясна.
- `/opsx:update` — переписать готовые артефакты изменения и свести их между собой; код не трогает.
- `/opsx:propose` — создать изменение и все артефакты одним ходом. Для схемы symphysis основной путь — `/opsx:continue`: этим прохождением `/opsx:propose` не проверялся.

`/opsx:new` создаёт изменение. Дополнительные `ff`, `bulk-archive`, `verify`,
`onboard` доступны в профилях форка. После явного выбора профиля повтори
`symphysis install` своего scope для сборки охраняемых носителей.

## Обновление

**Что меняется.** Новый тарбол заменяет команду `openspec`; обновление npm-пакета
не обновляет установленный payload само по себе. Повтори install выбранного scope.
Global install обновляет общий runtime и собственные native проекции для всех
совместимых store; он не обходит store и не меняет их журналы, карты и ответы.
Local install обновляет выбранный проект независимо от global.

**Откат.** Вернуться на прежний коммит клона и повторить этот раздел.

Имя нового тарбола — в `vendor/` и в поле `symphysis.openspecSource` файла `installer/package.json`.

PowerShell, из корня клона:

```powershell
git pull
npm --prefix installer ci
npm i -g ./vendor/<новый тарбол>
Set-Location ../reminders
symphysis install --scope local --client claude
symphysis check
```

bash, из корня клона:

```bash
git pull
npm --prefix installer ci
npm i -g ./vendor/<новый тарбол>
cd ../reminders
symphysis install --scope local --client claude
symphysis check
```

Для global после обновления пакета выполни `symphysis install --scope global`,
затем `symphysis check --scope global --project <store>`. Если store несовместим,
команда называет причину и действие; автоматической миграции и перехода к local нет.

Installer сравнивает файлы с ownership manifest. Изменённый пользователем или чужой
файл остаётся на месте, установка сообщает конфликт. `--force` сохраняется как
совместимый флаг и эту защиту не отключает. Повторный install без новых overrides
сохраняет прежние client targets. Перед обновлением дождись завершения активных
инструментов: reader lease блокирует замену используемого поколения.

При обрыве не удаляй lock/backup по возрасту. Явное восстановление проверяет
незавершённую транзакцию, владельца и байты её файлов:

```text
symphysis install --recover --scope global
symphysis install --recover --scope local --project <project>
symphysis init --recover --project <store>
symphysis migrate --recover --project <source>
```

Живой либо неподтверждённый владелец, изменённые пользователем файлы и неизвестные
остатки дают отказ. После успешного recovery повтори исходную install/init и check.
Для миграции используй тот же source и при необходимости тот же `--store <id>`,
что при preview. Результат `rolled-back` означает возврат прежнего режима: составь
новый preview перед повтором. При `completed` переключение уже завершено — выполни
check целевого scope. Не удаляй личные данные или lock-файлы для обхода отказа.
Системные Node/Python/форк installer не ставит автоматически.

Для охраняемого обновления носителей используй dispatcher. Он строит общий план
установки и проверяет ownership до записи; прямой native генератор не запускается:

```text
symphysis --project <store> openspec update --dry-run --json
symphysis --project <store> openspec update
symphysis --project <store> openspec init --tools claude,codex,opencode
```

Профиль берётся из конфига OpenSpec. `init --profile core` либо `init --profile custom`
задаёт профиль только для этой операции и не переписывает глобальный конфиг.
Обязательные workflow добавляются к выбранному набору, ссылки на отключённые
workflow не остаются в носителях. Без `--tools` сохраняются прежние client targets.
Позиционный путь, если задан, должен обозначать тот же выбранный store.

Внешний `openspec init/update` может перегенерировать носители без guard. Последующий
`check` назовёт расхождение; обычный install и `--force` не заменяют изменённые файлы
автоматически. Для принятия известной прежней генерации нужен явный просмотр
конфликтов и подтверждение плана.

## Другой клиент

Идентификатор клиента задаёт `--client`, а не имя каталога. `--skills-dir` и
`--agents-dir` — независимые overrides; local пути считаются от проекта, global —
полные абсолютные. Для local OpenCode:

PowerShell:

```powershell
symphysis install --scope local --client opencode
symphysis check --scope local --client opencode
```

bash:

```bash
symphysis install --scope local --client opencode
symphysis check --scope local --client opencode
```

Имя команды у клиента своё: у OpenCode это `/opsx-continue`, файл
`.opencode/commands/opsx-continue.md` при local-установке. Остальные обязательные
команды — `/opsx-new`, `/opsx-apply`, `/opsx-sync`, `/opsx-archive`.
Список имён `--tools` показывает `symphysis openspec init --help`.

Для Codex укажи `--client codex`: local skills идут в `.agents/skills`, агенты — в
`.codex/agents`; `.agents/agents` не используется. Для Claude ставится родное тело
с preload, для Codex — TOML, для OpenCode — Markdown subagent. Два последних тела
явно получают нужный skill через resource API. Установка не меняет модель и права
родительской сессии. После установки проверь обнаружение в своём клиенте.

OpenCode CLI проверен реальными модельными сессиями в local/global для получения
скилла и работы исследовательского водителя. Текущий объём приёмки полного флоу
указан в матрице готовности; он не распространяется автоматически на OpenCode IDE.

## Разработчику

Этот шаг нужен только для запуска тестов инсталлятора и сборки нового тарбола. Пользователю он не нужен: установка выше идёт из тарбола без исходников форка.

Форк лежит вне git ядра, в ветке `openspec-fork`, а `bin/openspec.js` ждёт собранный `dist/`. Нужен `pnpm`: `npm i -g pnpm`, откат `npm rm -g pnpm`.

Тела скиллов и агентов пишутся по канону `docs/skills-canon.md`: общие файлы — у модулей (`skill-shared/`, `cli/`, `settings/`, `decisions/`, `attack/`; в проект они ложатся в `.symphysis/docs/`), выписки доноров и заметки перевода — `<модуль>/skills/<имя>/sources/` (в продукт не идут), тела водителей — `<модуль>/agents/`. Форму проверяют `tests/test_skills.py` и `tests/test_agents.py`; переписанное тело проверяется двумя прогонами субагентом с одним brief, не чтением.

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

**Нет ожидаемой native-команды или скилла.** Проверь выбранную поставку через
`symphysis resolve --project <source> --json` и `symphysis check` с выбранными scope
и client. `filesystem ready` не подтверждает обнаружение в работающем клиенте:
проверь его собственный список skills/commands и выбранный client root.
Используй диагностику управляемого install/init; внешний `openspec init/update`
может перегенерировать носители без guard.

**`declaration-missing` в global-store.** Выполни явный
`symphysis init --project <source>` для нужного существующего store, затем повтори
check/preflight. Global install сам store не инициализирует.

**`selector-conflict` у journal из pointer-source.** Проверь абсолютные пути журнала,
ответов и `--out` по `changeRoot`/`changeDir` выбранного изменения. Относительный
путь от store не становится таким путём от открытого source автоматически.

**Значок ↗ не открывает IDEA или GIGA IDE.** В Windows не зарегистрирован протокол `jetbrains`. Регистрация только для твоего пользователя, путь — к своей IDE:

```powershell
$ide = 'C:\путь\к\IDE\bin\idea64.exe'
$key = 'HKCU:\Software\Classes\jetbrains'
New-Item -Path "$key\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path $key -Name '(default)' -Value 'URL:JetBrains'
New-ItemProperty -Path $key -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
Set-ItemProperty -Path "$key\shell\open\command" -Name '(default)' -Value "`"$ide`" `"%1`""
```

Отмена: `Remove-Item HKCU:\Software\Classes\jetbrains -Recurse`. Проект определяется по имени каталога: если IDE его не находит, проверь, не назван ли он там иначе. Закрытую IDE ссылка запускает сама, а проект, который сейчас не открыт, IDE предложит открыть. Проверено на GIGA IDE 2026.1; на IDEA не проверялось.

**Известное ограничение.** Префикс npm с пробелом и `&` вместе ломает сам шим npm (`SET dp0=%~dp0`): `install` заканчивается кодом 0 и печатает команду на потом.

## Модули в графе требований

Область исходников изменения задаётся в `.openspec.yaml`. Компонент содержит записи repo; логическое имя не является путём клона. Поле `root` точно называет префикс карты, переданной `--roots`; пустая строка означает явно выбранный корень проекта. Посторонние префиксы карты не добавляют repo в состав.

```yaml
x-symphysis-components:
  example:
    - repo: core
      root: ""
      survey: found
      exclude: [generated]
    - repo: plugin
      root: plugin/
      survey: unexamined
```

Состояния `survey`: `found` — модули обнаружены, `none` — доступное дерево обследовано без объявленных модулей, `unavailable` — repo недоступен, `unexamined` — обследование ещё не завершено. Отсутствие поля означает последнее состояние. Необязательный строковый `commit` фиксирует снятое состояние; живой граф всё равно читает рабочие файлы. Обследование и его запись выполняет модель на шагах decisions/research; сборщик metadata не переписывает.

Модуль объявляется в README.md на любой глубине, включая корень repo. Обычное описание без name/kind не становится модулем. Род — `доменный` или `технический`; имя не обязано совпадать с каталогом.

```yaml
---
name: viewer
kind: доменный
dependencies:
  - repo: core
    module: roots
---
```

Зависимости направлены от объявляющего модуля к названному. Проза и import не заменяют явный список. Поддерживается UTF-8 с BOM и без него, LF и CRLF. Текст README остаётся данными, инструкции внутри него не расширяют полномочия модели. YAML-теги исполнения не поддерживаются. Для чтения YAML используется PyYAML; при отсутствии пакета сигнал называет команду `python -m pip install pyyaml`, а не подтверждает пустую структуру.

Реализация объявляется в блоке требования, вне примеров в fenced code. JSON-комментарий может называть несколько модулей и файлы; `module` у файла необязателен, его владелец определяется ближайшей объявленной границей.

```markdown
### Requirement: Пример
Система SHALL сохранять явные связи реализации.
<!-- symphysis:implements {"modules":[{"repo":"core","module":"viewer"}],"files":[{"repo":"core","path":"src/view.py","module":"viewer"}]} -->
```

Аннотация переносится при sync вместе со своим требованием и не удаляется как служебный след пробы. Ссылка на запись журнала или улика о старом коде сама по себе не подтверждает реализацию. Соглашение применяется к существующим клиентским README только по решению их владельца: symphysis не дописывает объявления за него.

Обход не зависит от Git и `.gitignore`. Каталоги `.git`, `node_modules`, `.symphysis` исключаются, в том числе при доступе через ссылку. `exclude` задаёт относительные пути каталогов или шаблоны: каталог исключает своё поддерево, шаблон сопоставляется относительному пути с `/`. Файл принадлежит ближайшему содержащему модулю; одинаковое имя внутри одного repo даёт неоднозначность, а одинаковое имя разных repo допустимо.

Для одной карты корней передавай `--roots <файл>` командам build, report, check и freeze. Неизвестный псевдоним не подменяется подкаталогом текущего проекта. Ошибки доступа, кодировки и объявлений дают сигналы с местом и причиной; доступная корректная часть остаётся в графе. Отчёт отдельно показывает сохранённый `survey`, результат нового чтения и доступность repo. Отсутствующий раздел структуры не доказывает, что модулей нет.

Снимок хранит нормализованные поля и хеши прочитанных байтов, состав README и происхождение связей, без полных README и исходного кода. Check замечает добавление и перенос объявления, не перезаписывая историю; исчезнувший клон означает предел проверки, а не исчезновение исторического модуля. Поля/хеш и структурные утверждения снимка/отчёта относятся к одному прочитанному состоянию. Глобальная блокировка рабочего дерева не обещается.

Текстовый requirementDiagram содержит новые виды и связи. Выбор требования/capability сохраняет реализацию, прямые зависимости и нужных предков repo/компонента; весь транзитивный граф зависимостей не втягивается. Встроенного рендера этого экспорта в HTML нет. Модуль без локальной аннотации остаётся структурным узлом и не получает глобальную оценку отсутствия реализации или требований.
