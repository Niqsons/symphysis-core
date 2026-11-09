# global-user-install: карта runtime перед проектированием

Сверка 2026-11-08; read-only код ядра и трёх плагинов. Прочитаны актуальные B-66/B-67, AGENTS/CLAUDE, контекст 05; личные настройки/карты корней не читались. Все артефакты пробы — `X:/codex-tmp`.
Целевая граница от контроллера: общий runtime/skills/поддерживаемые agents/справка — на пользователя; store хранит состояние и нужную инициализацию; сценарий clone store → install symphysis → change → archive.

## Что установлено сейчас

| Ресурс | Текущий путь | Привязка в коде |
| --- | --- | --- |
| Команда npm | глобальная ссылка CLI на клон/пакет | GUIDE:142–146; сама по себе payload не глобализирует |
| Runtime + journal schema + HTML template + mermaid | PROJECT/.symphysis/tools/* | installer/lib/paths.js:15–25; install.js:176–189 |
| Общая справка/термины/формы/MIT | PROJECT/.symphysis/docs/* | install.js:186–188; sync-payload.js:56–68,182 |
| Личные корни улик | PROJECT/.symphysis/tools/journal-roots.json | install.js:17,189; создаётся `{"":"<root>/.."}`, существующий сохраняется |
| Метка поставленного runtime | PROJECT/.symphysis/tools/symphysis-version.txt | install.js:85–90,184–185; версия пакета + хеш совпадающих исходников |
| Skills | PROJECT/.claude/skills либо переданные --skills-dir | paths.js:3,15–23; install.js:160–167 |
| Agents | agents рядом со skills либо --agents-dir | paths.js:5–7,19; install.js:168–174 |
| Схема, тексты шагов и шаблоны | PROJECT/openspec/schemas/symphysis | paths.js:21; это тоже общий ресурс, сейчас проектная копия |
| Конфигурация проекта | PROJECT/openspec/config.yaml | paths.js:22; install.js:191–209 объединяет schema/rules/operations |
| Личный состав | PROJECT/symphysis.yaml | install.js:211–212; сохраняется даже --force, добавляется в gitignore |
| Состояние | PROJECT/openspec/changes, specs; .symphysis/viewer; answers | X:/symphysis-vscode/src/core/project.ts:18–20,53 и функции черновиков; runtime туда не должен переносить состояние |

## Разрешение путей: что переживёт перенос, что нет

- `roots/roots.py:22–23`: ROOT = родитель каталога кода, ROOTS_PATH = ROOT/tools/journal-roots.json. `_expand_value` :29–36 раскрывает `<root>` от runtime ROOT, **не от переданного файла корней и не от рабочего проекта**.
- `default_roots(..., journal_path)` :70–80 умеет вывести проект из пути журнала `openspec/changes/[archive/]...` (`change_of`:39–45). Когда инструменты вне проекта, fallback — проект; однако `_roots_around` :59–67 берёт внешний файл корней, если его пустой префикс охватывает журнал.
- `project_roots(project)` :82–93 аналогично поддерживает инструменты вне проекта, но общий файл с чрезмерно широким `""` победит fallback. Нельзя класть старый ROOTS_CONTENT в пользовательский runtime без пересмотра семантики.
- `settings/symphysis_config.py:153–160`: без --project берёт default_roots() без журнала. После переноса в user scope это будет каталог runtime/его родитель, а не cwd проекта. Явный --project уже есть (:178–190).
- `step-help/step_help.py:397–399`, `trace/trace_graph.py:328–330`, `anchors/anchor_refs.py:215`: рабочий проект — ближайший родитель cwd с openspec/. Это совместимо с отдельным runtime при правильном cwd; вложенный store/worktree должен не унаследовать чужой openspec выше границы.
- `cli/journal_cli.py:75,142,266,299`: операции с журналом передают его путь в default_roots; CLI уже имеет --roots. Для явной карты проекта нужно определить совместимость `<root>` отдельно — смена только пути файла не исправляет его базу.
- `decisions/journal_model.py:22` находит journal.schema.json рядом с кодом; `viewer/viewer_render.py:19` так же находит шаблон. Эти файлы переносятся вместе с runtime без изменения внешнего JSON.
- `viewer/viewer_render.py:63–69` ищет mermaid, поднимаясь от HTML и находя .symphysis/tools. Без проектного каталога рисунок исчезнет, останется текст. Нужен ресурсный resolver/встраивание/доставка ассета, а не глобальная абсолютная file-ссылка в отслеживаемом HTML.
- `step_help:130–138` читает steps.md только из проектной схемы. При глобальной схеме нужен общий schema/resource resolver; простое удаление проектной схемы лишает справку текстов.
- `_symphysis_version` step_help:140–145 читает метку рядом с реально исполняемым кодом. Это хорошая база для user runtime; источник версии должен совпадать с исполнителем и schema/resources.
- Поиск skills step_help:309–339 — три фиксированных проектных каталога и те же/модульные каталоги --install-dir. Сам по себе не ищет глобальные каталоги всех клиентов и не отражает факт обнаружения моделью.
- Тела skills и общая справка жёстко ссылаются на .symphysis/tools и .symphysis/docs (например viewer/skills/symphysis-viewer/SKILL.md:22–26,57,99–117; decisions/.../SKILL.md:23,34). Перемещение SKILL.md без адаптации оставляет все эти ссылки нерабочими.
- `openspec-run/openspec_run.py:70–85`: форк — SYMPHYSIS_OPENSPEC, затем PATH; cwd проекта передаётся запуску. Здесь нет согласованного выбора версии runtime/форка/схемы. Нужна явная политика совместимости, иначе обновление user runtime меняет старые проекты молча.

## Плагины: уже есть часть нужной развязки

- VS Code `src/core/project.ts:26–39`: сначала PROJECT/.symphysis/tools, затем PROJECT/tools; только при отсутствии локальных — явная абсолютная настройка symphysis.toolsPath. Автоматического поиска user runtime нет. Старая локальная копия маскирует новый глобальный runtime даже при настройке.
- `CoreEnv` (`src/core/core.ts:12–17`) уже разделяет tools и cwd проекта. Python вызывается с cwd проекта, аргументы журнала/ответа считаются от него (:36,55–65). Можно сохранить argv/JSON view-json/apply/check и заменить только lookup/источник tools.
- `src/step-help/stepHelp.ts:58–71`: исполняет tools/step_help.py, передаёт --install-dir при внешнем runtime и не пускает запрос без openspec в cwd. Сохранять эти гарантии; --install-dir не означает смену проекта.
- OpenCode содержит тот же lookup (`src/core/project.ts:26–50`) и поле toolsPath (`src/gui/host.ts:54,77,343`). Watcher :164–189 следит только за проектными tools; обновления общего runtime он не увидит автоматически.
- GIGA IDE пока проба: `src/main/kotlin/symphysis/probe/Scenario.kt:162` зовёт ровно PROJECT/.symphysis/tools/journal.py; общей discovery-границы в проверенном Kotlin нет. Порту всё равно предстоит production host, B-64.
- Во всех вариантах оставить `.symphysis/viewer` и answers в выбранном проекте: общие tools не означают общие drafts/events. Не перенаправлять cwd в user runtime.
- `docs/repo-contract.md` держит грамматику/JSON/коды/пути артефактов/skills-links; расположение runtime и lookup нужно явно обновить в договоре. Сохранение значений/смысла старых полей позволяет не объявлять смену номера автоматически; решение о номере — по фактическому diff контракта, не по названию задачи.

## Минимальные адаптации

1. Разделить ResourceRoot (общий код/ассеты/доки) и ProjectContext (cwd/root/state/settings/roots map); явно передавать ProjectContext всем входам. Не выводить проект от __file__ глобального кода.
2. Спроектировать user install и project/store init как разные действия с понятным совместным entrypoint для «clone → install → change». Одна команда может их оркестрировать; общий runtime не копировать в каждый store.
3. Сохранить проектный/личный файл корней вне глобального runtime; зафиксировать базу `<root>` и миграцию старой карты без чтения/перезаписи чужих значений. Два проекта/одинаковое имя change — обязательная изоляционная приёмка.
4. Дать skills/agents справочник ресурсов без проектных .symphysis/docs ссылок; клиентские глобальные каталоги — тонкие зарегистрированные носители, runtime/docs общие. Формат agents и способ подключения проверять для каждого клиента, не копировать Claude frontmatter вслепую.
5. Выбирать schema/steps/template/schema-json/mermaid из той же версии ресурсов, что исполняется; разрешение schema у форка отдельно подтвердить документацией и реальным запуском. Сохранить проектные rules/context/operations как настройку, а не копию всех общих тел.
6. Единый resolver для CLI и трёх плагинов: global default, явный dev override и объявленная политика legacy local. Удалять/игнорировать старые локальные копии только управляемой миграцией, не `--force` по чужому дереву.
7. Перестроить check: user runtime цел/версия совместима; клиент обнаружил skills/agents; проект инициализирован; roots/settings читаются из проекта; без смешения findings. `installer/lib/check.js:133–157` сейчас считает отсутствие каждого проектного инструмента ошибкой и зовёт локальный config.py.
8. Update/uninstall: версия/manifest только своих файлов; атомарная замена выбранного runtime; явное влияние на существующие проекты; не трогать проектные журналы/черновики/настройки.

## Альтернативы входа в runtime

| Вариант | Цена и выбор |
| --- | --- |
| Единый `symphysis <tool>` dispatcher | Рекомендуемая основа: один resolver проекта/версии/ресурсов и короткие команды в skills; меняет вызовы skills и требует адаптации хостов. Можно сохранять прежние Python entrypoints как API для плагинов в global runtime. |
| Проектные Python/JS stubs → user runtime | Меньше миграции старых путей, но на каждом проекте остаются исполняемые файлы, обновление stubs и валидация адреса; не решает docs/mermaid/schema само. Только как временная совместимость, если она нужна владельцу. |
| Копии всего payload в проект | Наименьший diff сегодня и независимые версии, но противоречит цели общего runtime и повторяет нынешнюю проблему дублирования; не считать реализацией global-user-install. |

## Проверка ловушки корней

Команда `python -X utf8 X:/codex-tmp/global-runtime-root-probe.py`, код 0, без личных файлов: скопирован roots.py в синтетический user-runtime/tools, задан старый installer default `{"":"<root>/.."}`, журнал — соседний project-a/openspec/changes/demo/decisions.json.
Результат: все три `default_roots(journal_path=...)`, `default_roots(project_map, journal)`, `project_roots(project)` вернули общий `X:/codex-tmp/global-runtime-root-probe`, а не project-a. Это расширяет область чтения улик на соседние проекты. Логика доказана кодом и запуском, не прогнозом поведения модели.
Остальная карта подтверждена чтением текущего кода; реализация глобальной установки, клиентские discovery-прогоны, обновление и полный цикл на двух проектах здесь не выполнялись.
