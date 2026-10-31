# @niqsons/symphysis

Установщик схемы OpenSpec `symphysis`: кладёт в проект схему, четыре скилла
и инструменты журнала решений; командой `check` называет расхождения
установки. Форк OpenSpec не ставит — только проверяет его версию.

## Что и куда ставится

| Что | Куда | Заметка |
| --- | --- | --- |
| схема `symphysis` | `<проект>/openspec/schemas/symphysis/` | в проект, не в глобальный каталог (F-16.B) |
| `openspec/config.yaml` | `<проект>/openspec/config.yaml` | сливается, см. ниже |
| четыре скилла `symphysis-*` | `<skills-dir>/<имя>/SKILL.md` | в каждый `--skills-dir`; без параметра — `.claude/skills` |
| инструменты журнала | `<проект>/.symphysis/` (`tools/`, `docs/`) | `journal.py`, модули, схема JSON, файл корней |

Клиент не привязан: каталог скиллов задаётся явно через `--skills-dir`,
единственное умолчание — `.claude/skills`. Относительный путь считается
от `--project`.

## Требование: форк OpenSpec

`check` ждёт `openspec` версии `1.15.0-symphysis.2` (пин — поле
`symphysis.openspecPin` в `package.json`). Источник форка —
`symphysis.openspecSource` там же; сейчас это плейсхолдер.

Бинарь берётся из переменной `SYMPHYSIS_OPENSPEC` либо из `PATH`.
Переменная указывает на `openspec.js`, `.cmd`/`.bat` или `.exe`.

## Установка пакета

Из tarball (после `npm pack`):

```
npx --yes ./symphysis-0.1.0.tgz install --project <каталог проекта>
```

Из клона репозитория:

```
node installer/bin/symphysis.js install --project <каталог проекта>
```

Абсолютный путь Windows (`C:\...`) `npx` принимает за имя команды и молча
выходит с кодом 0, ничего не поставив. Рабочие формы — `./файл.tgz`
из его каталога или `file:C:/путь/файл.tgz`.

## Команды

Параметры обеих: `--project <dir>` (по умолчанию текущий каталог),
`--skills-dir <dir>` (повторяемый). Только у `install`: `--force`.

### install

```
symphysis install --project . --skills-dir .claude/skills --skills-dir .agents/skills
```

- Идемпотентна: повторный запуск ничего не меняет.
- Файл, отличающийся от поставляемого, пропускается и называется
  в stderr с подсказкой `--force`; с `--force` перезаписывается.
  Каждый пропущенный файл схемы дополнительно называется отдельной строкой
  stdout: `пропущен: <путь> — отличается, нужен --force`. Так обновление
  схемы (в payload новый `schema.yaml`, в проекте старый) не проходит молча.
- `openspec/config.yaml` сливается: `schema` переключается на `symphysis`,
  `rules` объединяются, комментарии и прочие ключи пользователя
  сохраняются. Запись — LF без BOM; длинные скаляры разворачиваются
  в одну строку.
- Файл корней `.symphysis/tools/journal-roots.json` создаётся один раз
  (`{"": "<корень>/.."}`) и никогда не перезаписывается, в том числе
  с `--force`.
- Телеметрия форка выключается, если ключ не задан (см. «Телеметрия форка»).

### check

```
symphysis check --project .
```

Называет расхождения, не чинит. Проверяет: версию форка, байты каждого
файла схемы (расхождение — `[!!] схема: байты отличаются от payload: <путь>`),
`config.yaml` (`schema: symphysis`), `SKILL.md` в каждом `--skills-dir`,
инструменты, доступность Python, телеметрию форка и каждый
`openspec/changes/*/decisions.json` через `journal.py check`.

Строки `[!!]` — расхождения, `[..]` — сигналы. Сигнал — результат сверки
улик журналов (F-12): он сообщает, но не останавливает, на код выхода
не влияет.

Коды выхода: `0` — расхождений нет; `2` — расхождения либо ошибка
в аргументах; `1` — внутренняя ошибка (исключение).

Если `journal.py check` сам не отработал (не JSON, нет Python-модуля),
расхождение читается «journal.py check не отработал (…)», а не
«журнал негоден по схеме».

## Вход изменения

Вход изменения — намерение человека, файл `openspec/changes/<имя>/intent.md`
(первый артефакт схемы `intent`, шаблон `templates/intent.md`). Каталог
`.gigacode/` установщик не создаёт и не читает. Инструменты журнала
лежат в `.symphysis/` (`tools/`, `docs/`).

## Телеметрия форка

Форк наследует от OpenSpec анонимную телеметрию: имя команды и версия,
без аргументов, путей и содержимого; в CI она отключена автоматически.
В upstream при незаданном ключе телеметрия включена, поэтому здесь она
выключена по умолчанию:

- `install` пишет `telemetry.enabled: false` в глобальный конфиг OpenSpec
  (через `openspec config set`), если ключ `telemetry.enabled` не задан.
  Значение, которое поставил человек (в том числе `true`), `install`
  не меняет. Если `openspec` не найден, `install` печатает команду
  и продолжает установку.
- `check` показывает состояние: `[..] telemetry: выключена` (код 0);
  `[..] telemetry: конфиг OpenSpec не найден — появится после первого
  openspec init` (код 0); `[!!] telemetry: включена — выключить: ...`
  (код 2). Переменные окружения `OPENSPEC_TELEMETRY`, `DO_NOT_TRACK`,
  `CI` `check` не учитывает — он читает только конфиг.
- Выключить вручную: `openspec config set telemetry.enabled false`.
- `telemetry.anonymousId` в том же конфиге — случайный идентификатор
  установки (UUID без связи с пользователем); `install` его не создаёт
  и не меняет.
- Политика upstream — раздел Telemetry в
  [README OpenSpec](../upstream/openspec/README.md) (в репозитории
  [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec#readme));
  настройки и переменные окружения — в
  [docs/cli.md](../upstream/openspec/docs/cli.md) форка.

Глобальный конфиг лежит в `$XDG_CONFIG_HOME/openspec/config.json`,
иначе `%APPDATA%\openspec\config.json` (Windows) или
`~/.config/openspec/config.json`.

## Python

На Windows ищется `py -3.13`. Поиск вне Windows (`python3.13`, затем
`python3`) написан, но не проверялся.

## Разработка

```
cd installer
npm install
npm test
npm pack
```

- `payload/` генерируется из корня репозитория скриптом
  `scripts/sync-payload.js` и находится в `.gitignore`; `prepare` и
  `pretest` пересобирают его.
- `npm test` включает `test/npx.test.js`: он пакует tarball и ставит его
  через `npx` в пустой каталог. Тесту нужны сеть (зависимость `yaml`
  тянется из реестра) и `upstream/openspec` для зелёного случая `check`.
  Длительность — от нескольких секунд до полутора-двух минут, зависит
  от скорости реестра; без `npm` в `PATH` файл пропускается.
- Остальные тесты: `node --test`, около 10 секунд.
- Тесты, вызывающие `install`/`check`, задают `XDG_CONFIG_HOME` во
  временный каталог: настоящий глобальный конфиг OpenSpec они не трогают.
