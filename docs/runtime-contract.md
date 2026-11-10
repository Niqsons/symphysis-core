# Контракт bootstrap, resolver и запуска

Контракт для CLI symphysis и его потребителей VS Code, GIGA IDE и OpenCode.
Основание — `global-user-install/design.md`, F-10–F-13, F-15, F-20–F-24.
Этот документ и conformance fixtures задают поверхность реализации. Их наличие
само по себе не подтверждает готовность resolver, плагинов или native discovery.

## Обнаружение bootstrap

Хост сначала получает абсолютную команду bootstrap: явный абсолютный
`symphysis.commandPath` либо поиск `symphysis` в PATH процесса, исполняющего
инструмент. Неверная явная настройка — ошибка, без перехода к PATH. Не искать
в cwd, workspace, `node_modules/.bin`, соседнем проекте или по npm prefix.
Относительный либо пустой элемент PATH не служит источником executable.

JS-entrypoint запускается реальным Node из абсолютного `symphysis.nodePath`
либо того же host PATH. Исполняемый файл IDE/Electron не считается Node.
Windows npm shim требует адаптера с проверенным экранированием и отключённым
неявным поиском executable в cwd; все аргументы на границе хоста остаются
массивом строк. Нельзя соединять пользовательские значения в командную строку.

Первый handshake:

```text
<launcher> resolve --project <source> --json
```

`source` — абсолютный корень открытого проекта или его подкаталог. Resolver
получает planning root через закреплённый OpenSpec context, включая pointer и
явный `--store`. Наличие CLI в PATH или успешный `--version` не подтверждает
наличие установленного продукта. Хост проверяет таймаут, exit code, JSON,
format, status, store, generation и фактический journal contract.

## Resolve format 1

Машинная схема —
[`resolve.schema.json`](../installer/test/fixtures/runtime-contract/resolve.schema.json).
JSON локальный: абсолютные пути допустимы для процессов этой машины; этот
ответ не включается в HTML или публикуемый отчёт.

| Поле | Смысл |
| --- | --- |
| `format` | Версия resolver JSON, сейчас `1` |
| `status` | `ready` либо `blocked`; найденный runtime не означает ready |
| `store` | `{root, sourceCwd, id}`: выбранный planning root, исходный cwd, registry id либо null; null при отказе до выбора store |
| `scope` | `local`, `global` либо null, если поставка не выбрана |
| `runtime` | Выбранные пути, поколение и API; null до выбора поставки |
| `resources` | Именованные инструменты/документы/скиллы/шаблоны и схема; null до их разрешения |
| `compatibility` | `{status, declarationPath}`; статусы `compatible`, `incompatible`, `unconfirmed` |
| `clients` | Результат каждого управляемого клиента, отдельно файлы, workflow и discovery |
| `diagnostics` | Массив `{code, message, action}`; code для программы, текст и действие для человека |

`runtime` содержит `root`, `toolsRoot`, `docsRoot`, `schemaRoot`, `manifestPath`,
`generation`, `sourceVersion`, `legacy`, `bootstrapApi`, `runtimeApi`,
`schemaApi`, `journalContract`. В управляемой поставке manifestPath абсолютный,
legacy false. У прежней local-поставки manifestPath null, legacy true,
generation `legacy-local`; это идентификатор режима, не обещание неизменяемого
снимка старых файлов. SourceVersion может быть null, если старый формат её не
сообщает. В blocked-ответе journalContract может быть null, если повреждённая
поставка не позволяет прочитать его; ready требует положительное целое.
При негодном manifest runtime остаётся null, а обнаруженный scope сохраняется.
Неизвестные положительные API могут присутствовать в blocked для диагностики.

Локальный install-manifest — отдельный формат: `format`, `scope`, `generation`,
`sourceVersion`, API и `files[]` с абсолютным `path`, `sha256`, относительным
payload `source` и `purpose`, плюс `clients[]`. Его файловый реестр не копируется
целиком в handshake; личная карта корней и черновики в него не входят.

Bootstrap API, runtime API, schema API и journal contract — разные числа.
Первый контракт этой поверхности использует bootstrapApi/runtimeApi/schemaApi
`1`. Journal contract читается из фактического ядра; новый номер не резервируется
в этих fixtures. Согласование плагина с ним — по [repo-contract.md](repo-contract.md).

`resources.tools` — карта поддерживаемых входов `journal`, `trace`, `anchors`,
`sync-check`, `help`, `config`. Старые поставки могут не содержать `sync-check`:
это не меняет их общий статус готовности; запрос отсутствующего инструмента получает
`resource-missing`, без поиска в другой установке. Повреждённый объявленный файл
по-прежнему нарушает целостность manifest. Остальные карты — `docs`, `skills`, `templates` с именованными
идентификаторами manifest. `resources.schema` — `{name, path}`. Все пути
принадлежат выбранной поставке либо её управляемой проекции. Ресурс другой
установки не заполняет пропуск. `resource <kind> <id>` принимает идентификатор,
а не произвольный путь. Local-копия, в том числе повреждённая или legacy,
имеет приоритет. Одна карта корней в `.symphysis/tools` не является runtime.

У `clients[]`: `id`, `files`, `workflow`, `discovery`. Первые два состояния —
`ready`, `missing`, `conflict`; discovery — `confirmed` либо `unconfirmed`.
Скопированный файл не доказывает получение skill агентом. Эти поля не заменяют
совместимость runtime/store и не смешивают native агентный клиент с IDE host.

Хост может игнорировать новые поля, но не неизвестный format и не отсутствие
обязательных полей. Он отвергает ready без store/runtime/resources/generation,
относительные пути, несовпадающий явный store, неподдерживаемые API и неверный
journal contract. `blocked` сохраняет выбранные scope/runtime, если они известны;
это полезная диагностика и не разрешение запуска. Ошибка декодирования не
становится пустым журналом. Refresh повторяет discovery после изменения
настроек, установки или поколения; отрицательный кэш не бессрочен.

## Коды и отсутствие записи

| Исход | Exit code | Действие хоста |
| --- | --- | --- |
| Resolve/preflight ready | 0 | Показать discovery; запускать инструмент отдельно через dispatcher |
| Ожидаемый отказ/usage/несовместимость | 2 | Показать diagnostics, не запускать инструмент и не чинить store |
| Внутренняя ошибка bootstrap | 1 | Показать ошибку запуска, сохранить данные пользователя |
| Успешный preflight, инструмент завершён | Код инструмента | Сохранить грамматику/семантику exit code инструмента |

`resolve` и `preflight` не создают store, не вызывают init/миграцию и не выдают
lease для будущего прямого Python-вызова. Отсутствующая декларация global-store
требует явного init либо миграции. Local не требует global-декларации.
Конфликт источника схемы, несовместимый контракт и повреждение выбранной
поставки не дают fallback в другую установку.

Conformance cases используют устойчивые диагностические коды. Текст сообщения
и действия может уточняться; неизвестный code хост показывает как отказ,
сохраняя message/action. Launcher-коды относятся к хосту, а resolver-коды —
к ответу bootstrap. Они не переименовывают существующие ошибки journal.py.

## Запуск и lifetime

После discovery хост запускает инструмент тем же launcher:

```text
<launcher> --project <source> [--store <id>] journal <journal argv...>
<launcher> --project <source> [--store <id>] openspec <native argv...>
```

Для новых dispatcher-команд selectors стоят перед именем инструмента.
Их значения не смешиваются с вложенной грамматикой. Путь адресуемого журнала
разрешается относительно документированной исходной базы до смены cwd.
Dispatcher запускает child с cwd выбранного store, повторно проверяет
совместимость/поколение и удерживает reader lease до завершения child.
Read-only resolve не заменяет эту проверку. При отмене хост завершает dispatcher
с его child и дожидается освобождения lease; не обходит отказ прямым Python.

Внутренний Python-контекст содержит reader lease и описание выбранного launcher;
это не поля публичного resolve. Обычно владельцем lease является непосредственный
родитель Python. Для Windows venv допускается только заявленный redirector:
проверяются живые процессы, фактические executable, цепочка родительства и время
создания. Произвольный предок или один совпавший PID не разрешают запуск.

JSON внутреннего launch-плана содержит `format: 1`, `command` (абсолютный),
`args` (массив строк), `cwd` (store root), `execution: "dispatcher"` и
`lease: "child-lifetime"`. Это структура launcher adapter для тестов и хостов,
не отдельная публичная команда, разрешающая исполнить найденные tools напрямую.
Windows quoting живёт внутри launcher adapter; аргументы с пробелом, `&`, `%`,
кавычками и переводом строки остаются отдельными значениями argv.

Поздний `--store`, путь журнала другого store или неизвестный `--schema`
не должны обойти preflight. Все адресующие selectors проверяются до child;
эффективная схема учитывает metadata change, planning config и native argv.
При конфликте — отказ без записи, а не проверка одного store с запуском в другом.

## Общие conformance fixtures

Каталог [`runtime-contract`](../installer/test/fixtures/runtime-contract) содержит
`resolve.schema.json`, `cases.json`, `launch-cases.json`. Пути `/fixture/...`
синтетические, файлы по ним не создаются. В `cases.json` `input` описывает
раскладку, а `expected` — исход resolver/операции. `responseExamples` дают
`responseTemplate` для проверки парсеров; `$journalContract` в нём заменяется
фактическим числом проверяемого ядра. `invalidResponses` задают отвергаемые
изменения этого ответа. Launch
fixtures проверяют исходный argv и диагностические исходы bootstrap discovery.

Тест `node --test installer/test/runtime-contract.test.js` проверяет целостность
формата и противоречия матрицы. Он ещё не проверяет реализацию resolver или
реальный IDE host. Каждый потребитель применяет эти же cases к своему adapter
и выполняет установленную приёмку по tasks; копирование fixtures не равно порту.

## Управляемая отмена dispatcher

IDE host создаёт собственный файл управления до запуска и передаёт абсолютный
путь через `SYMPHYSIS_CANCEL_FILE`. Это внутренний lifecycle-канал, отдельный от
stdin дочернего инструмента и его JSON stdout. Файл — UTF-8 JSON
`{format: 1, id: <уникальная строка>, token: <случайный hex>, cancel: false}`.
Token содержит 16–64 случайных байта в hex, рекомендуемый размер — 32 байта.
Хост хранит id/token для данного запуска и при отмене атомарно заменяет файл
записью с теми же id/token и `cancel: true`.

Dispatcher проверяет начальную запись и путь без reparse/символических ссылок,
затем наблюдает только этот явный файл. Запрос отмены завершает дочернее дерево;
dispatcher дожидается завершения и освобождает reader lease. Изменение id/token,
исчезновение либо повреждение управляющего файла во время выполнения также
завершает child с диагностикой отказа управления, а не оставляет инструмент
без канала отмены. Dispatcher не создаёт и не удаляет этот файл; очисткой после
закрытия dispatcher владеет хост. Без переменной канал не включён.

На Windows принудительный `child.kill()` может завершить сам dispatcher без
выполнения finally. Поэтому хост сначала использует файл отмены и ждёт закрытия
dispatcher; принудительное завершение остаётся аварийным выходом. Сохранившаяся
после такого выхода lease считается неподтверждённой и требует явного recovery,
автоматического удаления по одному PID или возрасту нет.

## Необязательные ресурсы

Resolver может добавить `warnings[]`: элементы `{code, message, action, source,
path}` называют canonical payload source и абсолютный путь затронутого ресурса.
Warnings не входят в блокирующие `diagnostics` и сами не меняют `status=ready`.
Хост показывает их как примечания. Неизвестные поля остаются добавочными;
старый потребитель не обязан знать предупреждения.

Необязательная карта `resources.assets` содержит доступные пути `mermaid`,
`mermaidLicense`, `version`, `steps`. При наличии manifest карта исключает
ресурс с неподтверждёнными байтами. Отсутствующий ключ означает отсутствие
разрешённого ресурса; содержимое другой установки не подставляется. Старый
контекст без `assets` сохраняет прежний способ поиска legacy ресурсов.

Для local отсутствие/повреждение Mermaid допускает текстовый показ схемы;
недоступный или непроверенный `step_help.py` исключается из `resources.tools`:
явный вызов help отказывает, journal/check продолжают работу. Local-файл версии
информационный и не порождает integrity finding. Global сохраняет строгую
проверку зарегистрированных helpers/версии/ассетов. В обоих scope отсутствующий
`steps.md` допускает пустые тексты; существующий файл с неверными байтами —
блокирующее расхождение. Проверки остальных путей и хешей сохраняются.

### Management-only migration preview

`resolveMigrationContext({project,store,to,env,run,schemaRemovalProof})` resolves one native planning root and returns `{managementOnly:true,planningRoot,sourceContext,candidateContext,diagnostics,operationReady}`. The planning root contains `root`, `id` and `sourceCwd`. Both contexts remain `blocked`; the target candidate's compatibility remains `unconfirmed`. This result never authorizes tool launch. Diagnostics from the authoritative source block migration; changing scope does not repair incompatible data or a damaged runtime.

For `to: "global"`, the installed global candidate is checked through the same resource/API/schema validation as discovery. A project schema may shadow its user projection only for this preview, after trusted internal `schemaRemovalProof(sourceContext)` synchronously returns `{root,manifestPath,generation,files:[{path,sha256,snapshot}]}`. Every actual project schema file must match the source ownership manifest, hash and snapshot. Missing owned files need no removal; unknown or changed files block preview. The user projection and canonical global schema still require their own valid ownership and bytes. JSON plans never supply executable callbacks. The planner reconstructs this proof at apply time.

For a manifest-less source, that callback may instead return an opaque capability minted by `createLegacySourceProof(sourceContext,options)`. Recognition requires the shipped critical journal/journal-cli/schema hashes and every present public common resource to match one known generation. Explicit client targets require exact shipped product/native predecessor bytes. The scanner excludes private settings/maps and unrelated skills; unknown public candidates remain conflicts. `legacySourceEvidence(proof,sourceContext)` binds the capability to the selected store/runtime/schema roots and revalidates file snapshots, including inode identity. A serialized lookalike cannot authorize removal. Both flat and `.symphysis` legacy layouts use this same capability; unknown copies retain unconfirmed ownership.

For `to: "local"`, `candidateContext` is null: the installation planner validates the new candidate's package bytes and targets. `operationReady` confirms only the checked source and planning context, not the future installation or native session discovery.

### Guarded native init/update and profiles

`symphysis openspec init/update` uses the installation planner and ownership transaction before acquiring any tool reader lease. It never invokes the native generator directly. Global init first validates the selected store's initialization plan, updates the global installation, then initializes the store with a fresh context. Update requires a compatible initialized store; it does not initialize one implicitly. Local init keeps local scope. A positional native path must identify the already selected store; common project/store selectors belong before `openspec`. `update --dry-run [--json]` plans without file, telemetry or config writes. `--force` grants no additional ownership.

Native init accepts explicit supported `--tools claude,codex,opencode` or `all` (these three supported clients). Omitting tools preserves existing targets. `--tools none` is refused with an explicit `symphysis init` action for configuring a global store without updating carriers. Native `--profile core|custom` is an operation-scoped override; otherwise the planner reads the native config profile and custom workflows. It never rewrites that profile silently. Every selection includes required new/continue/apply/sync/archive workflows and pinned native dependencies.

The trusted build artifact contains profile metadata, a guarded carrier catalog and a separate read-only `legacyCatalog`. Each catalog entry has a complete set of prebuilt variants for only the optional-workflow conditions actually used by that native template. `selectWorkflowCarriers` selects exact prebuilt content without importing runtime generators. `workflowVariantContent(entry,variant)` reconstructs UTF-8 content from readable line fragments and bounded gzip-compressed little-endian uint16 indices encoded as hex; each variant has its own SHA-256. Validation checks canonical hex, decoded length, index ranges, content size, complete condition combinations and hashes. Legacy variants are exact unguarded native predecessor bytes for preview/adoption classification, never install output. Neither catalog nor file presence confirms native session discovery.

Existing change directories may contain Unicode and spaces. Journal addressing accepts only one safe directory segment, verifies real paths inside the selected store, and still asks the pinned native status command for the effective schema. New change names keep the native slug grammar.

### Durable scope migration

`applyMigrationPlan(preview,{confirm:true,...})` reconstructs the preview and its typed capabilities before any publication. It holds a reader on the already installed global generation and a writer on the selected store's `.symphysis` management root. Global runtime/projections remain available to other stores; migration never replaces them. Adjacent stages/backups stay on each target's volume. Backups copy verified original bytes; atomic replacement keeps planning config present during publication and rollback.

The store records `.migration-transaction.json` and `.migration-recovery.json`; atomic updates use `.migration-record-*.tmp` and `.migration-recovery-*.tmp`. All these states block discovery, launches and another writer until cleanup. Every source registry entry is bound to a removal, an absent unchanged file or a verified shared global target. Every new local manifest entry is bound to a publication or an unchanged snapshot. The final `.symphysis/migration.json` receipt records `{format:1,from,to,runtimeApi:1,schemaApi:1}`. Retirement removes the proved local manifest; it never publishes an empty local manifest.

`symphysis migrate --recover [--project <source>] [--store <id>]` resolves one native planning root. It resumes only a fully validated transaction/recovery claim whose former owner is proved dead; live, reused or unconfirmed PIDs remain busy. Recovery itself is repeatable across resource cleanup, reader release, writer release and journal removal. A durable final snapshot precedes that cleanup. Only the transaction's exact reader/lock bytes and file identities can be removed; unrelated leases, changed/deleted user files, reparse points and unknown partial records are preserved with refusal. An already released global reader does not prevent finishing a verified store cleanup after a later global update.

