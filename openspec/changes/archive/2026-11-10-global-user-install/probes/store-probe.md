# B-66+B-67: store и global/user install — проверка 2026-11-08

Read-only для репозиториев; выполнялась только запись изолированных образцов в `X:/codex-tmp/global-store-p74xxikb`. Форк не менял и не собирал; network, git init/clone/commit, личные корни и настройки не использовал. Реальное клонирование заменено копией подготовленного store для проверки регистрации checkout.
Во всех дочерних процессах XDG_CONFIG_HOME/DATA_HOME, HOME/USERPROFILE, APPDATA/LOCALAPPDATA, CODEX_HOME/CLAUDE_CONFIG_DIR и TEMP/TMP указывают внутрь образца на X. `--no-init-git` исключает git-действия setup. Телеметрия/проверка обновления отключены только в env.
Полные argv/cwd/stdout/stderr/exit — `global-store-p74xxikb/results.json` и `extra-results.json`; скрипты — `global-store-probe.py`, `global-store-probe-extra.py` в `X:/codex-tmp`. Скрипты не являются новыми тестами репозитория.

## Корни, store и конфиг

1. Store — **standalone OpenSpec root**, а не глобальное место установки инструмента. Документы `upstream/openspec/docs/cli.md:275–294`: «Create and register a local store», `setup --path`, `--no-init-git`; `:308–324`: существующий checkout регистрируется через `store register`.
2. Identity хранится в `<store>/.openspec-store/store.yaml`, реестр локальной машины — `<global data>/stores/registry.yaml`: `src/core/store/foundation.ts:28–31`, `:86–92`. В пробе реестр `data/openspec/stores/registry.yaml`; register уже существующего metadata не меняет идентичность store.
3. Корень planning-команд выбирается не по текущему каталогу исходников автоматически: `docs/agent-contract.md:30–37` — explicit `--store` → nearest planning root либо config-only `store:` pointer → global `defaultStore` → ошибка/ограниченный implicit fallback.
4. Без `--store`, из самого store `context` вернул `root.source=nearest`; из постороннего каталога с тестовым defaultStore — `global_default`. Config-only исходный repo с `openspec/config.yaml: store: probe-store` дал `declared`; new change и status адресованы store, не исходному repo.
5. **Существующий planning root побеждает pointer:** обычный `init source-repo` создал локальную структуру; дописанный после него `store:` проигнорирован с warning «this directory is a real OpenSpec root». Поэтому не стоит сначала обычным init заводить второй planning root, а потом считать строку store переключателем.
6. **Но init уже умеет pointer-mode.** Если сначала есть только config-only `store:`, `init pointer-repo --tools claude` ставит интеграции, оставляет context `declared` и не создаёт вторую planning-структуру. Код `src/core/init.ts:199–240`: «externalized planning», «without creating a second local planning root»; `:244`, `:305–306`: planning/config остаются в store. B-67 должен переиспользовать это, а не проектировать заново.
7. `store register cloned-store --id probe-clone` отказал code=1: `store_metadata_id_mismatch`; «One checkout per store id is supported». После unregister исходного `probe-store`, register копии без смены id прошёл code=0, defaultStore затем разрешился в новый путь. Это локальная регистрация checkout, не перенос настроек другим пользователям вместе с git.
8. Schema/default/runtime конфиг должен быть на **выбранном store root**. Pointer имел `schema: cwd-only`, но `new change store-target` без override создал schema `spec-driven` из store-конфига, а не cwd-only. Новому store надо выбрать `symphysis` в его конфиге либо явно `--schema symphysis`; одна глобальная доступность схемы не делает её умолчанием.

## Schema discovery: доступность схемы не равна инициализации проекта

- `docs/customization.md:346–366`: `schema which`, source project/user/package; user-level schemas поддерживаются. Реальная приоритетность `src/core/artifact-graph/resolver.ts:134–143`: project-local выбранного root → user override → bundled package.
- User schemas физически `<XDG_DATA_HOME>/openspec/schemas/<name>`; Windows fallback `%LOCALAPPDATA%/openspec/schemas`, не безусловно Linux-путь из документации. Код `src/core/global-config.ts:82–123`, `resolver.ts:49,58`. XDG precedence на всех платформах: config `global-config.ts:52–64`, data `:103–108`.
- До копирования схемы в изолированный user-dir `schema which symphysis` из store дал code=1. После копирования — code=0/source=user; `new change global-demo --schema symphysis` и `instructions intent --change global-demo --json` прошли code=0 без project-local symphysis-схемы. Выдача JSON инструкции — факт CLI, не свидетельство контекста получившей её модели.
- После добавления store-local `openspec/schemas/symphysis` источник project, user указан как shadow. Глобальная схема даёт обновление пользователю сразу для проектов без локального override; локальная копия по-прежнему перекрывает её.
- **Диагностическая ловушка:** `schema which` использует `process.cwd()` (`src/commands/schema.ts:516`), не resolver store. Из pointer-repo `schema which store-only --json` code=1, но `schemas --store probe-store --json` code=0 видит store-only. Поэтому диагностировать доступность выбранного store следует из store cwd или planning-командой с `--store`, а не одним schema which из исходного repo.

## Init/update клиентов: project vs global

- `init [path] --tools ...` и `update [path]` — адресованы каталогу проекта: `docs/cli.md:88–113`, `:167–183`; глобальные profile/delivery/workflows — **настройки генерации**, а не scope установки всех интеграций (`docs/cli.md:85,165`).
- Для claude, opencode, codex проба init создала файлы внутри `source-repo`: `.claude/skills` + `.claude/commands/opsx`, `.opencode/skills` + `.opencode/commands`, `.agents/skills` (Codex skills-only). Домашние каталоги этих клиентов не заполнялись. Пути документированы `docs/supported-tools.md:70,74` (claude/codex) и таблицей OpenCode; config `src/core/config.ts:56` задаёт Codex `.agents`.
- **Универсального `--global` сейчас нет:** `init --global` и `update --global --dry-run --json` оба code=1 «unknown option '--global'». Перенос OpenSpec на user skills Claude/OpenCode/Codex потребует продуктового решения/изменения, не только использования имеющегося флага.
- Исключение уже существует для **MiniMax Code**: `docs/supported-tools.md:118–122`, `config.ts:81` — `globalSkillsDir: .minimax`. Изолированная проба `init minimax-project --tools minimax-code` code=0 реально создала 7 skills в тестовом `home/.minimax/skills`, не project-local. Не обобщать исключение на остальных клиентов.
- `update source-repo --dry-run --json` code=0 описал проектные интеграции, ничего не записал. Продуктовая глобальная установка должна отдельно определить обновление user skills и предотвращение конкурирующих project/user копий.

## Следствия для B-66+B-67 (выводы, не принятый дизайн)

1. Желаемый путь «пользователь клонирует store → ставит symphysis → change→archive» совместим с уже имеющейся моделью OpenSpec: planning root остаётся store, а tool/runtime/user skills могут жить отдельно. Продуктовая инициализация должна связать эти части и задать schema, а не делать store синонимом global install.
2. Для работы **из store cwd** регистрация не нужна для nearest root; для кода вне store нужны явный `--store`, pointer или осознанно выбранный defaultStore. Registry/defaultStore пользовательские и не приезжают с клоном.
3. Глобальные schema и client skills не решают global runtime symphysis: текущие instruction зовут `python .symphysis/tools/...` (`openspec/schemas/symphysis/schema.yaml:23,93–106,168`), installer кладёт runtime в `<project>/.symphysis` (`installer/lib/paths.js:15–25`), config CLI тоже ищет локальный tools (`installer/bin/symphysis.js:110`). Эти предпосылки должны измениться согласованно в B-66, иначе глобальные инструкции будут обращаться к отсутствующей локальной копии.
4. При pointer cwd относительное `.symphysis/...` дополнительно неоднозначно: cwd исходников и planning store различаются. Нужен явный контракт runtime-path и project/store-root для CLI/skills/плагинов; OpenSpec уже отдаёт `root/changeRoot/artifactPaths`, но автоматического переноса всех сторонних относительных команд из-за этого не происходит.
5. Проектная инициализация B-67 может быть тонкой: сохранить/создать store pointer либо выбрать существующий planning root, настроить schema/rules и клиентские интеграции, не копируя весь runtime в каждый repo. Однако именно это разделение ещё предстоит спроектировать в symphysis; данный аудит ничего не реализовал.

## Реальные команды и коды

Команды ниже вызваны через `node X:/symphysis/upstream/openspec/bin/openspec.js`; все пути — внутри изолированного probe.

| Команда | cwd / результат |
| --- | --- |
| `store setup probe-store --path <probe>/team-store --no-init-git --json` | probe, 0 |
| `context --json` | team-store, 0/nearest |
| `init <probe>/source-repo --tools claude,opencode,codex --no-animation --force` | probe, 0/project-local files |
| `update <probe>/source-repo --dry-run --json` | probe, 0 |
| `init <probe>/source-repo --tools claude --global` | probe, 1/unknown option |
| `update <probe>/source-repo --global --dry-run --json` | probe, 1/unknown option |
| `list --store probe-store --json` | source-repo, 0/store |
| `context --json` после дописанного pointer в real root | source-repo, 0/nearest + warning |
| `context --json`, `new change store-target --json`, `status --change store-target --json` | config-only pointer-repo, все 0/declared, change в store |
| `schema which symphysis --json` | team-store, 1 → 0/user после user-schema → 0/project после локальной |
| `new change global-demo --schema symphysis --json`, `instructions intent --change global-demo --json` | source-repo, оба 0 при user schema |
| `schema which store-only --json`; `schemas --store probe-store --json` | pointer-repo, 1/not found; 0/visible |
| `init <probe>/pointer-repo --tools claude --no-animation --force`, `context --json` | оба 0; root остаётся declared |
| `store register <probe>/cloned-store --id probe-clone --json` | 1/id mismatch |
| `store unregister probe-store --json`, `store register <probe>/cloned-store --json` | оба 0, тот же id в новом checkout |
| `config set defaultStore probe-store`, `context --json` | outside cwd, оба 0/global_default |
| `init <probe>/minimax-project --tools minimax-code --no-animation --force` | 0, 7 skills в изолированном home |

Код форка изучался в текущем рабочем checkout другой сессии, исполнялся существующий dist без rebuild. Это проверка наличного CLI; расхождения source/dist не исключены. Поведение модели, полный модельный флоу и архивирование настоящего проекта здесь не проверялись.
