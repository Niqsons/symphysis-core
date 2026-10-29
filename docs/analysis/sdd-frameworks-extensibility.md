# Расширяемость SDD-фреймворков

Разбор 2026-10-29 к плану `docs/plan-flexible-pipeline.md`
(написан во flow-specs, перенесён сюда тогда же);
продолжение `sdd-frameworks-proactive-design.md` — версии, коммиты
и места клонов там же.

Вопросы:

1. Можно ли встроить в конвейер фреймворка свой шаг (скилл
   `playground:playground`, свой скилл исследования кодовой базы),
   убрать шаг или сделать его опциональным — без переписывания
   фреймворка?
2. Если можно — насколько легко и гибко?

Сравнение по исходникам, не по обкатке. OpenSpec и sdd-superpowers
разобраны вручную; GSD и BMAD — агентами, ключевые цитаты сверены
по файлам.

## Короткий ответ

| | Встроить шаг | Заменить встроенный | Убрать шаг | Обязательная проверка | Правки переживают обновление |
| --- | --- | --- | --- | --- | --- |
| OpenSpec | да: артефакт в своей схеме | да: схема своя целиком | да: удалить артефакт | только «файл есть»; содержимое — прозой | да: схема в проекте; правки сгенерированных скиллов затираются |
| sdd-superpowers | только предложением после скилла, с согласия человека | нет | нет | нет | нет: правки тел скиллов — форк |
| GSD | да: capability на точке цикла | нет: «can only *add*» | да: переключатели в конфиге; ядро — нет | да, но только детерминированная и не на всех точках | да |
| BMAD V7 | да: прозой в `on_complete` / `activation_steps_*` | только пункт меню по коду | конвейер — не вызывать; внутри скилла — нет | нет: ревьюеры без вердикта | да |

Главное различие — **где живёт конвейер**:

- **OpenSpec** — в данных: граф артефактов в YAML. Меняется
  целиком и легко, но CLI проверяет только наличие файла.
- **GSD** — в коде ядра с точками расширения. Добавлять гибко,
  убирать — переключателями, заменять нельзя; детерминированные
  гейты есть, но не везде.
- **BMAD** — конвейера нет, есть набор скиллов. Внутрь скилла
  можно только добавлять, и только прозой для модели.
- **sdd-superpowers** — в прозе скиллов. Без форка — одна точка
  расширения, и та с согласия человека.

## OpenSpec 1.13.1

Конвейер — граф артефактов в `schema.yaml`; workflow-скиллы
(`propose`, `continue`, `apply`) читают его через CLI, а не держат
шаги в себе.

- **Где своя схема.** Порядок поиска — «1. Project-local:
  <projectRoot>/openspec/schemas/<name>/schema.yaml 2. User override:
  ${XDG_DATA_HOME}/openspec/schemas/<name>/schema.yaml 3. Package
  built-in» (`dist/core/artifact-graph/resolver.js:113-116`).
  Копия встроенной — `openspec schema fork <source> [name]`, новая —
  `openspec schema init <name> --artifacts …`; выбор —
  `schema:` в `openspec/config.yaml`.
- **Что такое шаг.** Поля артефакта: `id`, `generates`,
  `description`, `template`, `instruction`, `requires`
  (`dist/core/artifact-graph/types.js:24-31`). Схема проверяется:
  повторы id, ссылки на несуществующие артефакты, циклы
  (`artifact-graph/schema.js:46,59,118`).
- **Готовность шага — только наличие файла.** «Detects which
  artifacts are completed by checking file existence»
  (`artifact-graph/state.js:4`). Содержимое CLI не проверяет.
- **`requires` — предупреждение для артефакта, запрет для apply.**
  Для артефакта CLI пишет «This artifact has unmet dependencies.
  Complete them first or proceed with caution.»
  (`dist/commands/workflow/instructions.js:121`). Для apply —
  «Cannot apply this change yet. Missing artifacts: …» (`:425`).
- **Передача работы скиллу.** Workflow-скиллы обязаны: «If the
  `instruction` field delegates creation to a specific skill or
  command, invoke it to produce the artifact instead of writing the
  file yourself, then verify the artifact file exists at
  `resolvedOutputPath`» (`templates/workflows/continue-change.js:79`,
  так же в `propose.js`). Так `store-flow` зовёт `flow-step`.
- **Тонкая настройка без своей схемы.** `openspec/config.yaml`:
  `context` — «injected into all artifact instructions», до 50 КБ;
  `rules` — «Per-artifact rules, keyed by artifact ID», «additive
  to schema's built-in guidance» (`dist/core/project-config.js:31-42,183`);
  `operations.apply|archive.guidance`.
- **Пропуск шага.** В своей схеме — удалить артефакт и поправить
  `requires`. В схеме по умолчанию — `design.md` условный по тексту
  instruction; спеки — `skip_specs: true` в `.openspec.yaml` change'а.
  Набор workflow-команд — профиль: `openspec config profile`.
- **Обновление.** Схема проекта — файл проекта, `openspec update`
  её не трогает. Сгенерированные `SKILL.md` перезаписываются,
  если отличаются: «a user who edited a SKILL.md on purpose is owed
  the reason their edit is about to be overwritten»
  (`dist/core/update.js:447-451`).

Сценарии:

- **playground.** Артефакт `decisions-view` с `generates:
  playground.html`, `requires: [decisions]`, в `instruction` —
  вызов `playground:playground`; следующий артефакт ставит его
  в `requires`. Агент читает готовые артефакты из `dependencies`.
  Ограничение: «шаг пройден» = HTML-файл существует.
- **Своё исследование кодовой базы.** Артефакт `codebase-research`,
  `instruction` вызывает свой скилл. Встроенного шага исследования
  у OpenSpec нет — заменять нечего; `propose` читает код сам
  («Inspect the relevant project before drafting»), это проза
  workflow-скилла, её не отключить.
- **Убрать шаг.** Удалить артефакт из своей схемы.
- **Обязательная проверка.** Артефакт-вердикт в `requires` у apply:
  без файла apply запрещён CLI. Что в файле «пройдено» — только
  прозой instruction, как `store-flow`: «Файл не пиши сам:
  артефакт появляется только после того, как задача исполнена
  и её результат принят человеком»
  (`gigacode-skills/skills/config/openspec/schemas/store-flow/schema.yaml`
  в проекте flow-specs).

## sdd-superpowers 3.2.0

Конвейер — проза в скиллах: следующий шаг назван в разделе
Transition каждого `SKILL.md` и в `sdd-workflow/routing.md`;
запреты держат хуки (`pre-write-plan-gate.sh` — нет `plan.md`
без спеки со статусом Approved).

- **Единственная точка расширения без форка —
  `.claude/integrations.md`.** Таблица «`Trigger Skill` | `Custom
  Skill` | `Purpose`» (`skills/sdd-integrations/SKILL.md`). Хук
  `post-skill-integration-check.sh` на `PostToolUse` по `Skill`
  находит строку и подсказывает модели: «announce and confirm with
  the user before invoking each one, individually»
  (`scripts/hooks/post-skill-integration-check.sh:32`).
- **Срабатывает после вызова скилла, а не после его окончания.**
  ADR авторов: «the injected context lands on the *next* turn
  rather than inline in the same turn the skill produced its own
  output» (`docs/adr/029-custom-skill-integration-architecture.md:26`).
- **Тонкая настройка — steering-файлы** в
  `.claude/memory/steering/*.md` с `loaded-by: <скиллы>`: контекст,
  не шаги.
- **Обновление.** Плагин ставится в кэш целиком; правки тел скиллов
  в кэше — форк плагина.

Сценарии:

- **playground.** Строка `sdd-brainstorm | playground:playground |
  …` — модель предложит запуск, человек подтвердит. Встать между
  шагами нельзя: `sdd-brainstorm` по своему Transition сразу зовёт
  `sdd-specify`.
- **Своё исследование.** Так же — строкой после нужного скилла;
  заменить исследование внутри `sdd-brainstorm` — правка его тела.
- **Убрать шаг или сделать опциональным** — только правка `SKILL.md`
  и `routing.md`. `sdd-brainstorm` опционален уже сейчас; `sdd-review`
  перед слиянием — нет.
- **Обязательная проверка** — свой хук в `.claude/settings.json`
  по образцу `pre-write-plan-gate.sh`. Это настройка Claude Code,
  а не плагина.

## GSD Core

Конвейер — код ядра (discuss → plan → execute → verify → ship)
с переключателями и двенадцатью точками для capability.

- **Переключатели.** `.planning/config.json`: «All workflow toggles
  follow the **absent = enabled** pattern» (`docs/CONFIGURATION.md:537`).
  По умолчанию включены, среди прочих: `research`, `plan_check`,
  `verifier`, `security_enforcement`, `assumption_delta`,
  `specless_probe_fallback`, `context_coverage_gate`; выключены:
  `skip_discuss`, `auto_advance`, `tdd_mode`; `discuss_mode` —
  `discuss` или `assumptions` (по разбору агента, `:541-600`).
- **Что выключить нельзя.** «The planner/checker loop, the verifier,
  the verify-work gap-closure loop, **and the verifier↔predicate
  contract** … remain **core** (not hooks)»
  (`docs/adr/857-capability-system.md:85`).
- **Скиллы во встроенного агента.** `agent_skills.<agent-type>`
  в конфиге; «Any GSD agent type can receive skills»
  (`CONFIGURATION.md:966`). Плагинные скиллы — только в Claude Code,
  и GSD «cannot validate plugin presence» (по разбору агента,
  `docs/how-to/attach-a-plugin-skill-to-a-gsd-agent.md:87`).
- **Capability.** Папка с `capability.json` (`steps`,
  `contributions`, `gates`, `config`, `skills`, `hooks`),
  `fragments/`, `skills/`; ставится `gsd capability install <путь |
  git | npm:…> --scope project|global` (`docs/COMMANDS.md:1560-1561`).
  Точки: `discuss:pre|post`, `plan:pre|post`, `execute:pre`,
  `execute:wave:pre|post`, `execute:post`, `verify:pre|post`,
  `ship:pre|post`.
- **Только добавлять.** «An overlay … can only *add*; it can never
  *override*» (`docs/explanation/capability-overlay-model.md:151`).
  Проектная capability «inert (discovered-but-inactive) until
  a matching record exists in your user-owned consent store» (`:64`).
- **Шаги — совет, не гарантия.** «A `step` is **advisory by
  construction**: it never blocks or redirects the host workflow —
  that is what a `gate` is for. Each dispatch is best-effort»
  (`gsd-core/references/loop-hook-dispatch.md:78-79`); сами точки —
  «best-effort prose dispatch» (`:146-147`).
- **Гейты.** «When `true`, a failed check halts the loop at this
  point» (`docs/reference/capability-manifest.md:109`). Но проверка
  моделью останавливать не может: агентский вердикт — «No (forced
  advisory) … non-deterministic checks may not halt the loop»
  (`:119`). Блокирует только детерминированная проверка — query
  или predicate (`artifact-frontmatter-equals`, `command-exit-zero`).
- **Обновление.** Правленые установленные файлы — бэкап
  в `gsd-local-patches/` и замена; «`--reapply`» сливает правки
  обратно (`docs/how-to/update-gsd.md:136-142`). Capability и конфиг
  живут вне каталогов GSD и не трогаются.

Сценарии:

- **playground.** Capability со `step` на `discuss:post` и
  `contribution` на `plan:pre` в планировщика — «читай
  playground.html». Три оговорки (по разбору агента, первая
  сверена):
  - шаг ссылается только на свой скилл: «ref.skill must be declared
    in this capability's skills array»
    (`gsd-core/bin/lib/capability-validator.cjs:2946`) — нужна
    обёртка, которая зовёт `playground:playground`;
  - список чтения планировщика зашит, путь в его промпт — только
    через `contribution`;
  - хуки discuss срабатывают только в режиме `discuss`: в
    `discuss-phase-assumptions.md` вызовов `render-hooks` нет
    (сверено).
- **Своё исследование.** Рядом — `agent_skills` для
  `gsd-phase-researcher` или `gsd-codebase-mapper`, либо step
  на `plan:pre`. Вместо — нельзя: выключить встроенное
  (`workflow.research=false`) и добавить своё; без `--auto`
  plan-phase всё равно спросит, исследовать ли.
- **Убрать шаг** — переключатель; планировщик, проверку плана
  и верификатор — нельзя.
- **Обязательная проверка перед планом.** «Атака должна пройти»
  выражается только детерминированно — например, `verdict: pass`
  во frontmatter файла атаки. По разбору агента, на `plan:pre`
  обработка гейтов в `plan-phase.md` завязана на результат
  UI-проверки — свой гейт там, скорее всего, не сработает;
  полноценно гейты разбираются на `plan:post`, `verify:pre`,
  `execute:wave:post`, `ship:pre`.

## BMAD-METHOD V7 alpha

Конвейера нет: «These are independent tools, not stages. Pick the
ones the gap calls for, in any order.»
(`docs/plan/choose-a-planning-path.md:51`). Настраиваются отдельные
скиллы.

- **Слои настроек.** `_bmad/custom/<skill>.user.toml` →
  `_bmad/custom/<skill>.toml` → `customize.toml` скилла
  (`docs/customize/customize-bmad.md:66-70`, по разбору агента).
  Поставляемые — «DO NOT EDIT -- overwritten on every update.»
  (`skills/bmad-prd/customize.toml:1`); свои — «Updates do not
  touch your files» (`customize-bmad.md:11`).
- **Слияние.** Скаляры заменяются; массивы дописываются —
  `return list(base) + list(override)`
  (`skills/bmad/scripts/config_utils.py:57-58`); элементы с `code`
  или `id` заменяются по ключу.
- **Убрать нельзя.** «An override cannot delete a base item.
  To suppress a default menu item, override it by `code` with
  a description or prompt that does nothing; to restructure an
  array further, fork the skill.» (`customize-bmad.md:84-86`).
  Переключателей нет по замыслу: «What customization is not:
  boolean toggles (a switch means the author never decided)»
  (`skills/bmod-toolsmith/help/craft-customization.md:11`).
- **Логика шага закрыта.** «It cannot change step logic or any
  field `customize.toml` does not list.»
  (`skills/bmod-core-tools/help/customization.md:31`).
- **Крючки — проза.** `on_complete` — «Executed when the workflow
  completes… Accepts either a string scalar (single instruction)
  or an array of instructions executed in order.»
  (`skills/bmad-prd/customize.toml:35-38`); у всех скиллов —
  `activation_steps_prepend|append`, `persistent_facts`.
- **Ревьюеры не блокируют.** `finalize_reviewers` архитектуры —
  «whenever the gate runs, every entry here runs with it»
  (`skills/bmad-architecture/customize.toml:87`), но по находке —
  «autofix, discuss, defer to Deferred / open items, or ignore»
  (`references/reviewer-gate.md:13`). Сам гейт — «stakes-gated —
  a throwaway spine may run it quietly or skip it»
  (`customize.toml:86`).
- **Свой модуль.** «Do not add to the installed method record;
  the next update overwrites it. Make your own module with your
  own prefix» (`skills/bmod-toolsmith/help/how-to-add-to-module.md:18`).

Сценарии:

- **playground.** `on_complete = "…вызови playground:playground
  на …"` в `_bmad/custom/bmad-prd.toml`, или пункт меню агента
  со `skill`; следующему скиллу файл передаётся через
  `persistent_facts = ["file:…"]`. Исполнение не проверяется:
  PRD лишь самопроверяет «confirm every entry was executed
  in order» (по разбору агента, `bmad-prd/SKILL.md:32`).
- **Своё исследование.** Рядом — пункт меню, `persistent_facts =
  ["skill:…"]` или файл с frontmatter `type: codebase` —
  его подхватывает Build (по разбору агента). Вместо — нельзя:
  исследование кодовой базы зашито прозой в архитектуру и Build
  и выбирается внутри `bmad-deep-recon` по намерению, ключа нет.
- **Убрать шаг.** Скилл — не вызывать. Элемент внутри скилла —
  форк: ревьюера-противника архитектуры не убрать, линзу полировки
  PRD — только косвенно, пустым `instruction` линзы в
  `bmad-review` (вывод агента, не проверен).
- **Обязательная проверка** — свой ревьюер в `finalize_reviewers`:
  запускается всегда, когда идёт гейт, но вердикта «не прошёл»
  у него нет.

## Что это значит для конвейера

- **Playground и свой скилл исследования встраиваются везде,
  кроме sdd-superpowers.** Разница — в гарантии. В OpenSpec шаг
  стоит в графе, и apply без его файла не пустит. В GSD шаг —
  совет; держит только детерминированный гейт. В BMAD — проза
  для модели.
- **Убрать или заменить шаг без форка дают OpenSpec и GSD.**
  OpenSpec — любой: схема своя целиком. GSD — переключателем, кроме
  ядра; заменить встроенный — нет.
- **Проверку содержимого не держит никто.** OpenSpec знает только
  «файл есть». GSD блокирует по frontmatter или коду возврата
  команды. Атаку шага 7 как обязательный проход это превращает
  в две части: агент пишет вердикт, а держит его детерминированная
  проверка — frontmatter или скрипт.
- **Довод за кандидата 1 из `sdd-frameworks-proactive-design.md`**
  (основа — OpenSpec): своя схема даёт и журнал как артефакт,
  и шаг поиска умолчаний, и атаку — без форка. Механики GSD
  (edge probe, prohibition probe) и BMAD (ревьюер-противник)
  переносятся текстом в instruction своих артефактов.
- **Чего OpenSpec не даёт** — проверки содержимого шага. Кандидат:
  артефакт-вердикт с frontmatter и скриптом проверки; кто и когда
  его запускает — решить: хук Claude Code, `validate` или шаг
  instruction.

## Не разобрано

- Ничего не запускалось: `openspec schema fork`, `gsd capability
  install`, override BMAD — только по исходникам и документации.
- GSD: обработка гейтов на `plan:pre` и молчание хуков в режиме
  `assumptions` — вывод агента по тексту workflow, прогоном
  не проверен.
