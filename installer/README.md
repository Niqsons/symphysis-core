---
name: installer
kind: технический
---

# @niqsons/symphysis

CLI и установщик symphysis для OpenSpec: самостоятельные local/global поставки,
проверка выбранного store и запуск инструментов через dispatcher. Полный учебный
путь — [GUIDE](../docs/GUIDE.md), контракт IDE host —
[runtime-contract.md](../docs/runtime-contract.md).

## Два режима установки

Установка npm-пакета делает доступной команду symphysis. Сам runtime, схему и
native носители устанавливает отдельная команда:

    symphysis install --scope local --client claude --project <project>
    symphysis check --scope local --project <project>

Local — режим по умолчанию. Он не требует пользовательской поставки. Runtime
находится в .symphysis/tools и .symphysis/docs, схема — в openspec/schemas/symphysis.
Явный local install может подготовить новый проект; при pointer нужно выбирать
сам store, а не создавать второй planning root в исходном репозитории.

Global устанавливается без выбора проекта и не инициализирует cwd:

    symphysis install --scope global --client claude --client codex
    symphysis init --project <cloned-store>
    symphysis check --scope global --project <cloned-store>
    symphysis resolve --project <cloned-store> --json

Пользовательский runtime — SYMPHYSIS_HOME/runtime; без override используется
XDG_DATA_HOME/symphysis/runtime, затем системный каталог пользовательских данных.
Global overrides должны быть полными абсолютными путями. Store сохраняет
спецификации, декларацию совместимости, настройки, карту корней, ответы и черновики;
проектная копия общего runtime не требуется.

При одновременных установках resolver выбирает local, включая повреждённую.
Ресурсы global не скрывают поломку local. Нативные коллизии одноимённых скиллов и
агентов пользователь разрешает явно; смешанный режим не является условием работы.
Смена режима store требует отдельного preview/confirm миграции.

## Native клиенты

Поддерживаемые идентификаторы: claude, codex, opencode. Повторяемый --client выбирает
клиентов явно; их имена не выводятся из каталогов. --skills-dir и --agents-dir
задают независимые назначения одного клиента. Local относительные пути считаются
от проекта; global принимает абсолютные. Повторный install без overrides сохраняет
прежние назначения.

Codex skills находятся в .agents/skills, агенты — в .codex/agents; CODEX_HOME не
переносит пользовательские skills. Claude получает родное Markdown-тело с preload,
Codex — TOML, OpenCode — Markdown subagent с явным чтением skill через resource.
Модель и права родителя установщик не меняет.

Workflow собираются из закреплённого vendor artifact с guard перед первой записью.
Профиль и custom-набор учитываются вместе с обязательными new/continue/apply/sync/archive.
Наличие файлов проверяется отдельно для каждого клиента и не подтверждает
фактическое обнаружение или модельную сессию.

## Инструменты и управление

    symphysis --project <source> journal check <journal>
    symphysis --project <source> trace freeze <change>
    symphysis --project <source> help --change <change>
    symphysis --project <source> resource doc journal-cli.md
    symphysis --project <source> openspec update --dry-run --json

Селекторы --project/--store стоят перед именем вложенного инструмента. Planning
root определяет закреплённый OpenSpec context, включая pointer; cwd инструмента —
выбранный store. Dispatcher повторно проверяет совместимость и удерживает reader
lease до завершения child. Resolve/preflight не разрешают поздний прямой запуск Python.

Установка использует собственный manifest, точные хеши и staging. Пользовательский
либо чужой файл не заменяется даже с --force. Личные symphysis.yaml и
.symphysis/tools/journal-roots.json не входят в реестр заменяемого payload.
При незавершённой операции используются явные install --recover или init --recover;
неизвестные остатки и неподтверждённые владельцы автоматически не удаляются.

check ничего не ремонтирует и не переключает scope. Маркер [!!] — расхождение,
[..] — сведения; код 0 означает отсутствие расхождений, код 2 — отказ/usage/конфликт.
Подробные исходы вложенных инструментов сохраняются; их справка доступна через --help.

## Зависимости и конфиг

Нужны Node не ниже 22.14 и закреплённый форк OpenSpec из vendor/ основного репозитория.
Пин и имя тарбола — symphysis.openspecPin/openspecSource в package.json.
SYMPHYSIS_OPENSPEC задаёт абсолютный executable/JS/shim; относительное значение
отвергается. Интерпретатор Python ищется по безопасным абсолютным PATH candidates.
Журнал требует только стандартную библиотеку; PyYAML нужен для личных настроек.

Глобальный конфиг OpenSpec берётся из XDG_CONFIG_HOME/openspec/config.json, иначе
из системного config-home. Install выключает телеметрию только если человек не
задавал явного значения; остальные настройки профиля не переписывает.

## Разработка

    npm --prefix installer ci
    npm --prefix installer test

prepare/pretest собирают trusted workflow catalog из pinned vendor archive и
синхронизируют payload из модулей. Runtime не импортирует native генераторы.
Known legacy inventory — фиксированные хеши прежних продуктовых файлов;
scripts/build-legacy-inventory.js проверяет их по whitelisted git blobs без checkout.
Сами личные карты и настройки в inventory не входят.

Node-набор инсталлятора запускается отдельно командой `npm --prefix installer test`.
Перед запуском активируй ту же среду Python, из которой запускаешь pytest ядра.
`python` в PATH этой сессии должен указывать на выбранный интерпретатор.
Проверка — `python -c "import sys, yaml; print(sys.executable)"`.
Реальные native/IDE сессии принимаются отдельно от parser/unit tests.
Тестовые profiles, cache и logs задаются изолированными каталогами.

## Каталоги пакета

- [bin/](bin/) — bootstrap CLI
- [lib/](lib/) — resolver, dispatcher, планировщики, транзакции и trusted legacy data
- [scripts/](scripts/) — сборка vendor/catalog/payload и проверка inventory
- [generated/](generated/) — воспроизводимый trusted workflow/legacy catalog
- [test/](test/) — тесты пакета; в поставку не идут
- [test-support/](test-support/) — изолированные fixture builders
