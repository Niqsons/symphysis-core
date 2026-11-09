# B-66/B-67: глобальная установка runtime и интеграции агентных клиентов

Сверка 2026-11-08. Область — локальные Claude Code, Codex и OpenCode как агентные клиенты; VS Code/GIGA/OpenCode Desktop как IDE-хосты — отдельная ось. Ничего не установлено глобально, пользовательские конфиги и ключи не читались, модели не вызывались. Ниже документированная механика отделена от непроверенных предположений.

## Что есть локально

`claude --version` → 2.1.319; `codex --version` → codex-cli 0.167.0; `opencode --version` → opencode v2.2.5. Для каждого выполнен `--help`, exit 0. Дополнительно `opencode debug --help` и `codex agents --help`, exit 0. Это проверка установленного клиента, не доказательство того, какие инструкции получила модель.

## Нативные места установки

| Клиент | Skills на пользователя / проект | Агенты на пользователя / проект | Формат агента |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills/<id>/SKILL.md` / `.claude/skills/<id>/SKILL.md` | `~/.claude/agents/*.md` / `.claude/agents/*.md` | YAML frontmatter (`name`, `description`, `tools`, `skills` и др.), тело — system prompt |
| Codex | `~/.agents/skills/<id>/SKILL.md` / `.agents/skills/<id>/SKILL.md` | `~/.codex/agents/*.toml` / `.codex/agents/*.toml` | TOML: обязательны `name`, `description`, `developer_instructions` |
| OpenCode V2 | `~/.config/opencode/skills/<id>/SKILL.md` / `.opencode/skills/<id>/SKILL.md` | `~/.config/opencode/agents/*.md` / `.opencode/agents/*.md` | Markdown: `description`, `mode: subagent`, `permissions`, `request` и др.; тело — `system`. Также agents в JSONC |

Источники: [Claude skills](https://code.claude.com/docs/en/skills), [Claude subagents](https://code.claude.com/docs/en/sub-agents), [Codex skills](https://learn.chatgpt.com/docs/build-skills), [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [OpenCode skills](https://opencode.ai/docs/skills/), [OpenCode agents](https://opencode.ai/docs/agents/). Это нативная discovery, не обязанность symphysis копировать runtime во все эти места.

## Главные различия и коллизии

- **Claude skills:** enterprise > personal > project при одинаковом имени; это прямо показано в таблице Resolve skills that share a name. Значит глобальная копия может перекрыть проектную, а не наоборот. Nested project skills могут оставаться доступными под квалифицированным именем; plugin skills namespaced. Symlinked skills поддерживаются, одинаковая цель загружается один раз. [Источник](https://code.claude.com/docs/en/skills#resolve-skills-that-share-a-name).
- **Claude agents:** managed > CLI `--agents` > project > user > plugin. Из вложенных project-каталогов выигрывает ближайший к cwd. Дубликаты одного name внутри одного дерева agents недетерминированы порядком чтения файлов; уникальность имени обязательна для предсказуемого выбора. [Источник](https://code.claude.com/docs/en/sub-agents#choose-the-subagent-scope).
- **Codex skills:** обход `.agents/skills` от cwd до корня репозитория; одноимённые skills не объединяются, оба могут появиться в selector. Поэтому правило «проектная копия всегда перекрывает user» НЕ подтверждено. Поддерживаются symlinked skill folders; `agents/openai.yaml` — метаданные skill, не файл subagent. [Источник](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills).
- **Codex agents:** `name` в TOML определяет идентичность; пользовательский агент может переопределить built-in. Приоритет одинаковых user/project names официальная страница явно не оговаривает — нельзя обещать без отдельной изолированной проверки/исходника конкретной версии. [Источник](https://learn.chatgpt.com/docs/agent-configuration/subagents).
- **OpenCode skills:** ID задаёт путь, `name` — display label; по одному ID выигрывает позже зарегистрированный источник: built-in → compatibility `.claude` → compatibility `.agents` → native user → native project (ближайший позже) → explicit `skills` config entries. Для `.claude`/`.agents` сначала user, потом project-предки. Дубликаты разных клиентов реально видны одному OpenCode. [Источник](https://opencode.ai/docs/skills/#precedence).
- **OpenCode agents:** definitions merge: более поздние scalar заменяют ранние, request maps объединяются по ключу, permission rules дописываются. Это не атомарное замещение файла агента: при столкновении можно получить смесь. Mode по умолчанию primary, для driver явно нужен subagent. [Источник](https://opencode.ai/docs/agents/#merging).

## Почему текущие drivers нельзя просто скопировать всем

Текущие `attack/agents/symphysis-attack-driver.md:4–5` и `research/agents/symphysis-research-driver.md:4–5` используют Claude `tools:` и `skills:`. Общий текст brief/отчёта пригоден как источник, но оболочки должны быть клиентскими.

- **Claude:** `skills:` действительно предварительно загружает полные тела перечисленных skills (до 32 разных names), не запрещает остальные. При недоступном skill клиент пропускает preload с warning; это не гарантированный stop. [Источник](https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents).
- **Codex:** такого поля preload в схеме нет; skills наследуются от родителя, `skills.config` может их отключать. `developer_instructions` должен явно задавать чтение нужного skill по проверяемому пути/имени. Sandbox/approval/provider/MCP наследуются, custom TOML не создаёт отдельный sandbox через `sandbox_mode` или `approval_policy`. [Источник](https://learn.chatgpt.com/docs/agent-configuration/subagents).
- **OpenCode V2:** `skills` отсутствует в ConfigAgent.Info; `tools` и `permission` — legacy V1, новые агенты используют `permissions`, `system`, `request`. Нельзя трактовать YAML Claude как preload; driver должен явно вызвать `skill` или прочитать тело. Локальное подтверждение: `X:/opencode/packages/schema/src/config/agent.ts:11–26`, schema без skills; `packages/core/src/config/plugin/agent.ts:33–35` различает native/legacy поля. [Документация](https://opencode.ai/docs/agents/).

## Home/config override и Windows/X

- **Claude:** на Windows `~` — `%USERPROFILE%`. `CLAUDE_CONFIG_DIR` меняет config home вместо `~/.claude`; в settings требуется абсолютный путь, project/local settings не могут перенаправить его. Политика установки должна учитывать его или явно сообщать выбранный target; не менять HOME и не переносить auth/state лишь ради symphysis. Фактическую discovery skills/agents после override на этой машине отдельно не прогонял. [Settings](https://code.claude.com/docs/en/settings), [env](https://code.claude.com/docs/en/env-vars#environment-variables).
- **Codex:** `CODEX_HOME` меняет корень state/config (каталог должен существовать); `~/.codex/config.toml` и project `.codex/config.toml` — разные слои, проектные загружаются только при trust. CLI > project closest > profile > user > defaults. `CODEX_HOME` НЕ доказательство переноса `~/.agents/skills`: документация skills задаёт его отдельно через HOME. Для установки нужен отдельный target skills, target agents/state и диагностика найденных копий. [Env](https://learn.chatgpt.com/docs/config-file/environment-variables), [config](https://learn.chatgpt.com/docs/config-file/config-basic).
- **OpenCode 2.2.5:** фактический default config в локальных исходниках — `$XDG_CONFIG_HOME/opencode`, иначе `os.homedir()/.config/opencode`, в том числе Windows; не подставлять автоматически APPDATA. `OPENCODE_CONFIG_DIR` заменяет config root, а `OPENCODE_CONFIG` — explicit config file, это разные ручки. Подтверждение: `X:/opencode/packages/util/src/global-roots.ts:7,15`, `global.ts:79`, `packages/cli/src/index.ts:139`, `server-process.ts:123,132`; clone commit ffe6fed583, core package 2.2.5. [Общая документация](https://opencode.ai/docs/config/).
- Для OpenCode выполнена безопасная проба: с TEMP/TMP и всеми XDG_* в `X:/codex-tmp/oc-path-probe`, `OPENCODE_CONFIG_DIR=X:/codex-tmp/oc-path-probe/custom-config`, команда `opencode debug paths config` вернула этот X-путь, exit 0. [Документация](https://opencode.ai/docs/cli/#paths) говорит, что debug paths не запускает сервер и не открывает БД; пользовательские файлы не читались.
- Compatibility roots OpenCode `.claude`/`.agents` в локальном `packages/core/src/config/discovery.ts:72–74` строятся от `global.home`, отдельно от native config root. Перенос OPENCODE_CONFIG_DIR не отключает чтение совместимых user-каталогов. Не нужно переносить все клиентские config home ради runtime на X.

## Вывод для B-66/B-67

1. **Подтверждено:** локальные user-scope skills и агенты существуют у всех трёх клиентов. Единый runtime symphysis на пользователя технически совместим с такой схемой, но discovery runtime самими клиентами не обеспечивается — это задача resolver/инсталлятора symphysis.
2. **Предложение:** один user runtime с явной версией/манифестом, клиентские адаптеры в нативных каталогах, project только config/данные/локальное переопределение. Причина: избегаем трёх тяжёлых копий, но сохраняем нативную discovery и разные форматы агентов. Конкретные каталоги runtime, команды и приоритет global/local должен решить change B-66/B-67; здесь они не утверждаются.
3. **Миграция должна быть явной:** искать старые symphysis skills/agents и сравнивать происхождение/версию перед записью. Удалять только свои отслеживаемые инсталлятором файлы; пользовательские custom bodies не перезаписывать. Причина — у клиентов несовместимые collision semantics, и «положили global» не означает «везде выбрана новая версия».
4. **Гипотеза, требует прогона до выпуска:** один канонический каталог skill-тел и native symlink/junction adapters. Claude/Codex skills это документированно поддерживают, Windows-права/переносимость установщика и OpenCode agent links этой проверкой не доказаны. Надёжный запасной вариант — небольшие генерируемые клиентские копии с manifest/version.
5. **Не подтверждено:** что уже существующий симфизис driver выполнится одинаково после механической перекладки; что Codex agent collision project/user стабилен; что глобальные пути доступны в sandbox каждого клиента; что user-runtime останется доступен в cloud/remote-сессии. Эти случаи нуждаются в изолированных acceptance-прогонах без пользовательских конфигов и с журналом реально полученного контекста.

Проверки ограничены документацией, локальными исходниками OpenCode и version/help/path командами. Агентные тела, skills, backlog, git и глобальная установка не менялись.
