# Разбор выпуска upstream OpenSpec 1.16.0 и 1.16.1

- База форка: `6d04a1b5` (1.15.0, 2026-10-24), ветка `symphysis` в `upstream/openspec`, версия `1.15.0-symphysis.4`, правки C1–C14 по `upstream/openspec/UPSTREAM.md:25-39`.
- Цель: `origin/main` = `0fa4a970` (v1.16.1, 2026-11-07); между базой и целью 26 коммитов, два выпуска.
- Дата разбора: 2026-11-07.
- Кто разбирал: агент, по файлам `upstream/openspec` (ревизии `origin/main` и `symphysis`, через `git show`/`git diff`; ветки и рабочий каталог не трогались). Строки без пометки — из `origin/main`.
- Чего не делалось: тесты форка на `origin/main` не запускались, `pnpm install` с vitest 5 не выполнялся, `openspec update` на машине владельца не запускался. Утверждения о поведении — по коду, не по прогону.

## Сводка

| Класс | Коммитов | Какие |
| --- | --- | --- |
| (а) задевает точку соприкосновения symphysis | 7 | `33c6f93e` Node 22.12; `dc376098` сценарий без WHEN/THEN; `83053dd8` нераспознанная секция; `ae7ad750` битый config.yaml; `a6cd3bc9` code-fence; `cb1adee5` `###Requirement:`; `c887ab07` закрывающие `#` |
| (б) риск правкам форка C1–C14 | 4 | `0fa4a970`, `27c05157` — строка `version` в `package.json` (единственный конфликт merge-tree); `3e4d5f07`, `6368683d` — vitest 4 → 5, vite 7 → 8 (тестовая база форка) |
| (в) не задевает | 15 | остальные: version-check ×2, zsh, store-suggest, website ×3, deps ×3, CI, docs ×2, архив изменений upstream, таймаут тестов store |

По смыслу ни один из 26 коммитов не трогает область C1–C14: `src/core/artifact-graph/*`, `src/commands/workflow/*`, `src/core/templates/*`, `src/core/profiles.ts`, `src/core/change-status-policy.ts`, `skills/` upstream не менял (`git diff --name-only 6d04a1b5..origin/main` по этим путям пуст). Из семи коммитов класса (а) ни один не меняет поведение на текущих файлах symphysis: формы, которые они чинят или запрещают, в `openspec/` не встречаются (проверка ниже). Задевают они правила на будущее и документацию (Node 22.12).

## Таблица коммитов

Порядок — как в `git log`, от новых к старым. Класс: (а) точка соприкосновения, (б) риск форку, (в) не задевает.

| # | Коммит | Что меняет | Улика | Класс |
| --- | --- | --- | --- | --- |
| 1 | `0fa4a970` Version Packages (1.16.1) | версия пакета, CHANGELOG, снятие `.changeset/*` | `package.json:3` `"version": "1.16.1"` | (б) конфликт со строкой версии форка `1.15.0-symphysis.4` (`symphysis:package.json:3`) |
| 2 | `a1ae5366` version: standalone updates only released | `version --check` у standalone-бинарника спрашивает GitHub releases, не npm; один HTTP-клиент `httpsGet` | `src/core/version-check.ts:342` `const RELEASES_URL = 'https://github.com/Fission-AI/OpenSpec/releases';`, `:409` `const latest = standalone ? await fetchLatestStandaloneRelease() : await fetchLatestVersion();` | (в) форк ставится из тарбола через npm, standalone-ветка не его |
| 3 | `83053dd8` validate: reject unrecognized requirement sections | требование под `## <что угодно> Requirements`, кроме четырёх дельт, — ERROR в `validate` и отказ `archive`; требование внутри HTML-комментария больше не «сирота» | `src/core/parsers/requirement-blocks.ts:312` `export function isUnrecognizedDeltaSection(section: string \| null): boolean {` (регэксп `/\brequirements?$/i`); `src/core/validation/validator.ts:265` `level: isUnrecognizedDeltaSection(orphan.section) ? 'ERROR' : 'WARNING',`; `src/core/specs-apply.ts:248-252` `const misplaced = plan.orphanedRequirements.find((o) => isUnrecognizedDeltaSection(o.section)); … "which is not a delta section, so it would not be applied."` | (а) `validate --json` в `trace_graph.py`, `archive` в `step_help.py`; в дельтах symphysis только ADDED/MODIFIED — эффекта сегодня нет |
| 4 | `c887ab07` parser: closing `#` runs on section headings | `## Purpose ##`, `## ADDED Requirements ##` читаются как без закрывающего прогона; один помощник `stripClosingSequence` в трёх парсерах | `src/core/parsers/requirement-blocks.ts:23` `export function stripClosingSequence(title: string): string {`; `src/core/parsers/spec-structure.ts:9` `const REQUIREMENT_HEADER = /^###\s*Requirement:\s*(.+)\s*$/i;`; `src/core/parsers/markdown-parser.ts` (diff `@@ -93,7 +93,8 @@`) `const title = stripClosingSequence(headerMatch[2]);` | (а) парсер `show --json`/`validate`; в symphysis таких заголовков нет — эффекта нет |
| 5 | `ef170faa` version: explicit `--check` even when telemetry is off | явный `version --check` игнорирует `OPENSPEC_TELEMETRY`, `DO_NOT_TRACK`, `telemetry.enabled: false` и CI; пассивная проверка в `update` — как была | `src/core/version-check.ts:71-80` `function isCheckEnabled(requested: boolean): boolean { if (process.env.OPENSPEC_NO_UPDATE_CHECK !== undefined) return false; if (process.env.NODE_ENV === 'test') return false; if (requested) return true; if (isCiEnvironment()) return false; if (isTelemetryOptedOutByEnv()) return false; … if (getGlobalConfig().telemetry?.enabled === false) return false;`; `src/cli/index.ts:169` `const update = options.check ? await checkForCliUpdate({ requested: true }) : undefined;` | (в) symphysis зовёт `--version` (`step-help/step_help.py:347`), не `version --check`; см. «version-check и память о телеметрии» |
| 6 | `631c911a` deps: website group | только `website/` | stat коммита | (в) |
| 7 | `3e4d5f07` deps: root bumps, `@types/node` 22 | devDependencies: `@types/node ^22.12.0`, `@vitest/ui ^5.0.3`, `vite ^8.3.5`, `vitest ^5.0.3`; `flake.nix` | `package.json:65` `"@types/node": "^22.12.0",`, `:73` `"vitest": "^5.0.3"` | (б) вся тестовая база форка (19 файлов тестов C1–C14) переезжает на vitest 5; ханки `package.json` вне строки `version` merge-tree слил сам |
| 8 | `2bd5bc3b` deps: force minimatch ≥ 11.0.1 | override в `pnpm-workspace.yaml`, dev-only (eslint) | `pnpm-workspace.yaml` (diff) `minimatch@<11.0.1: '>=11.0.1'` с комментарием «never in the published CLI» | (в) |
| 9 | `27c05157` Version Packages (1.16.0) | версия 1.16.0, CHANGELOG | как № 1 | (б) как № 1 |
| 10 | `4abbb373` deps: website group | только `website/` | stat | (в) |
| 11 | `e55e5337` deps-dev: typescript-eslint 8.72.0 | dev | stat | (в) |
| 12 | `05cc75f2` completion: zsh block to `$ZDOTDIR/.zshrc` | zsh-инсталлятор автодополнения читает `ZDOTDIR` (только абсолютный), uninstall чистит оба файла | `src/core/completions/installers/zsh-installer.ts:13` `function zshrcDir(homeDir: string): string {` | (в) Windows, PowerShell; `openspec completion` symphysis не зовёт |
| 13 | `33c6f93e` build!: drop Node.js 20, require 22.12.0 | `engines.node`, CI-матрица, install-скрипты, docs | `package.json:60` `"node": ">=22.12.0"` (было `">=20.19.0"`); `.github/workflows/ci.yml` (diff) `node: '22.12.0'` ×3 | (а) `installer/package.json` `engines.node >=20`, `docs/GUIDE.md:11` «Node 20 или новее»; корпоративная установка — см. ниже |
| 14 | `ebdd9a53` openspec: archive 19 shipped changes | только `openspec/` самого репозитория upstream | stat: 170+ файлов под `openspec/changes/archive/`, `openspec/specs/` | (в) форк этот каталог не трогал, merge-tree чист |
| 15 | `c4990101` test(store): 30s on Windows | таймаут двух тестов с настоящим git | stat: `test/commands/store-git.test.ts` +6, `store-remote.test.ts` +6 | (в) полезно прогону на Windows |
| 16 | `dc376098` validate: warn when scenario has no WHEN/GIVEN or THEN | WARNING на `#### Scenario:` без шага-триггера или без THEN, в дельтах и мастер-спеках; `--strict` на нём красный; строка в инструкции `specs` схемы spec-driven | `src/core/validation/validator.ts:1134` `private findScenarioStepIssues(blockRaw: string, label: string, issuePath: string): ValidationIssue[] {`, `:1149` `level: 'WARNING',`, `:1151` ``message: `${label}: scenario "${scenario.name}" is missing ${missing}. A scenario needs a trigger and an outcome, …` ``; `src/core/parsers/requirement-text.ts:122-125` `const BOLD_TRIGGER_STEP = /(?:\*\*\|__)(?:WHEN\|GIVEN):?(?:\*\*\|__)/i; const BARE_TRIGGER_STEP = /\b(?:WHEN\|GIVEN)\b/; const BOLD_OUTCOME_STEP = /(?:\*\*\|__)THEN:?(?:\*\*\|__)/i; const BARE_OUTCOME_STEP = /\bTHEN\b/;`; `schemas/spec-driven/schema.yaml:108` `- Every scenario MUST have a WHEN/GIVEN step (its trigger) and a THEN step (its outcome). …` | (а) `trace_graph.py` зовёт `validate … --strict` (`trace/trace_graph.py:1240`), WARNING там = `valid: false`; в корпусе symphysis таких сценариев 0 из 1730 |
| 17 | `18a75a5d` store: suggest store matching repo origin name | в ошибке «no root» называется зарегистрированный store по имени репозитория из `origin`; git спаунится только на этом пути отказа; `toKebabCase` в `id.ts` | `src/core/root-selection.ts:400` `async function suggestStoreFromGitRemote(`, `:471` `const suggested = await suggestStoreFromGitRemote(startPath, registeredIds);`; `src/core/store/git.ts:243` `export const GIT_REPO_LOCATION_ENV_VARS = [` | (в) symphysis всегда зовёт форк с `cwd` корня проекта, корень находится; форк импортирует из `root-selection` только `isRootSelectionError` (`symphysis:src/commands/workflow/shared.ts:17`), класс не менялся |
| 18 | `625834c8` docs: epic-driven schema entry | строка в таблице community schemas | `docs/customization.md` diff `@@ -424,6 +424,7 @@` | (в) форк правит тот же файл в `@@ -265,11 +265,32 @@`; merge-tree: `Auto-merging docs/customization.md`, без конфликта |
| 19 | `ae7ad750` validate: fail when config.yaml is not valid YAML | `validate` — код 1 и конверт `{status:[…]}` при нечитаемом или невалидном `openspec/config.yaml`; остальные команды — как были (предупреждение) | `src/commands/validate.ts:123` `const configError = readConfigParseError(root.path);`, `:132` `const code = unreadable ? 'unreadable_config' : 'unparseable_config';`, `:134` `console.log(JSON.stringify({ status: [{ severity: 'error', code, message, fix }] }, null, 2));`, `:139` `process.exitCode = 1;`; `src/core/project-config.ts` diff `@@ -452,6 +452,34 @@` `export function readConfigParseError(` | (а) `validate --json` в `trace_graph.py`; наш `config.yaml` — валидный YAML (PyYAML `safe_load`: ключи `schema`, `rules`, `operations`) |
| 20 | `0c3d1c6c` website: logo/favicons under /docs | `website/` | stat | (в) |
| 21 | `50949cde` deps: website group | `website/` | stat | (в) |
| 22 | `d924004d` ci: github-actions group | `.github/workflows` | stat | (в) |
| 23 | `6368683d` deps: vite 8.3.5, eslint 10.13.0, @inquirer/core 12.0.5 | dev и `@inquirer/core` | stat, итог в `package.json:73` | (б) с № 7 — vitest/vite major |
| 24 | `cb1adee5` validate: unspaced `###Requirement:` in main-spec structure check | регэксп структурной проверки мастер-спеки принимает заголовок без пробела, как уже делал archive | `src/core/parsers/spec-structure.ts:9` `const REQUIREMENT_HEADER = /^###\s*Requirement:\s*(.+)\s*$/i;` (было `\s+`) | (а) парсер; в symphysis таких заголовков нет; свой парсер `trace_graph.py` эту форму уже принимает (`tests/fixtures/trace/odd-headers/specs/omega/spec.md:36` `###Requirement: Без пробела после решёток`) |
| 25 | `a6cd3bc9` parser: don't open a fence on backtick lines with backticks in info string | строка вида ```` ```npm test``` ```` — не открытие fence; конец строки не заякорен ради CRLF | `src/core/parsers/code-fence.ts:19` ``const fenceMatch = line.match(/^\s*(`{3,}\|~{3,})(.*)/);``, `:27` ``if (fenceMatch[1][0] === '`' && fenceMatch[2].includes('`')) {`` | (а) парсер всех чтений спек; в `openspec/` symphysis строк с тройным бэктиком и ещё бэктиком нет, `~~~` нет |
| 26 | `d68fc512` docs(install): simplify install page, ship archives | install-скрипты бинарника, `.tar.gz`/`.zip` в релизах, тест инсталлятора бинарника | stat: `scripts/binary/install.*`, `test/binary-installer.test.ts` +32 | (в) бинарники форк не собирает |

## Что задевает symphysis

### Node 22.12 (№ 13)

Факт: `package.json:60` `"node": ">=22.12.0"`; changelog 1.16.0: «Only npm installs on Node 20 are affected: the standalone binary … doesn't use Node». В `src`-диффе base..main добавленных вызовов API только Node 22 не найдено (grep по `import.meta.dirname`, `fs.glob`, `Array.fromAsync`, `Promise.withResolvers`, `Set.union`, `Object.groupBy`, `toSorted` и др. — пусто): поднятие `engines` в этих 26 коммитах декларативное, «unblocks vitest 5 … and commander 15» (текст коммита `33c6f93e`). На Node 20 `npm i -g` тарбола с таким `engines` даст предупреждение EBADENGINE и поставит (npm по умолчанию не `engine-strict`; это общее поведение npm, в репозитории не проверялось), а сам CLI, судя по диффу, запустится, но поддержки у этого нет.

На машине владельца Node 24.11.1 — не задето.

Что править, если форк переезжает на 1.16.x:

- `installer/package.json` — `engines.node` с `>=20` на `>=22.12.0`, чтобы `npm i -g ./installer` предупреждал там же, где предупредит тарбол форка; иначе инсталлятор встанет, а `symphysis check` на Node 20 упрётся в форк с неясным сообщением (`installer/lib/check.js:35` проверяет только версию `openspec`, версию Node — нет).
- `docs/GUIDE.md:11` «Node 20 или новее» → «Node 22.12 или новее».
- Корпоративная установка: Node 20 EOL с 2026-04-30 (changelog); если корпоративный стандарт — ещё 20, запасной путь upstream (standalone-бинарник из GitHub releases, `.github/workflows/binaries.yml`) форку недоступен — форк релизы не публикует. Тогда варианты: остаться на `1.15.0-symphysis.4`, или cherry-pick без `33c6f93e` (вариант 3 ниже), или собирать бинарник самим (workflow есть в репозитории, но это отдельная работа, здесь не оценивалась).

### Отказ `validate`/`archive` на нераспознанных секциях `## … Requirements` (№ 3)

Правило: `isUnrecognizedDeltaSection` (`requirement-blocks.ts:312`) — заголовок `##`, чей текст кончается словом `requirement(s)` в любом регистре и не входит в `DELTA_SECTION_TITLES` (ADDED/MODIFIED/REMOVED/RENAMED Requirements). Под таким заголовком `### Requirement:` — ERROR в `validate` (`validator.ts:265`) и отказ `archive` (`specs-apply.ts:248-252`). Раньше было WARNING и требование молча выпадало. Заголовок `## Requirements` в дельте тоже попадает под правило. Заголовки без слова Requirements (`## Notes`) — по-прежнему WARNING.

Проверка symphysis (`grep` по `X:\symphysis\openspec\`):

- В дельтах (активные и архив): `## ADDED Requirements` ×62, `## MODIFIED Requirements` ×27, других заголовков со словом Requirements нет; `## Requirements` ×28 — все в мастер-спеках `openspec/specs/`, в дельтах 0.
- Инструкция `specs`: `openspec/schemas/symphysis/schema.yaml:78` «Дельты — секции `## ADDED|MODIFIED|REMOVED Requirements`; MODIFIED несёт требование целиком» — три из четырёх признаваемых, чужих не называет. Шаблон `openspec/schemas/symphysis/templates/spec.md:6` `## ADDED Requirements`, `:20-21` называет `## MODIFIED Requirements`, `## REMOVED Requirements`, `## RENAMED Requirements`.
- Свои скиллы: `probes/skills/symphysis-edge-probe/SKILL.md:91-93` «В счёт идут `### Requirement:` из секций `## ADDED Requirements` и `## MODIFIED …` (`## REMOVED Requirements`, `## RENAMED Requirements`) строк и кандидатов не получают»; `probes/skills/symphysis-prohibition-probe/SKILL.md:65` — то же для ADDED/MODIFIED. Других имён секций ни один `SKILL.md` symphysis не предлагает.
- `docs/GUIDE.md` имён секций не задаёт (grep по `Requirements` в GUIDE пуст).

Вывод: указаний писать иные секции нет; на текущих файлах ERROR не возникнет. Риск на будущее — модель сама придумает `## DEPRECATED Requirements`: теперь это стоп на `validate --strict` в графе и на `archive`, а не тихая потеря требования. Для symphysis это плюс, не минус.

### Предупреждение о сценарии без WHEN/GIVEN или THEN (№ 16)

Как считается: только блоки с меткой `#### Scenario:` (`isScenarioLabeledHeader`), только непустые, строки вне fence; триггер — `**WHEN**`/`**GIVEN**` (жирный, любой регистр, с двоеточием внутри или без, `**` или `__`) либо голое `WHEN`/`GIVEN` в верхнем регистре; исход — так же `THEN` (`requirement-text.ts:122-125`). Заголовок сценария не считается (`:141` и далее). Уровень — WARNING; `--strict` делает его красным.

Как это ляжет на symphysis:

- `trace/trace_graph.py:1240` `VALIDATE_ARGS = ("--type", "change", "--json", "--strict", "--no-interactive")` — со `--strict` WARNING даёт `valid: false` и код 1 (`validate.ts:367` `process.exitCode = report.valid ? 0 : 1;`), `trace_graph.py:1271-1275` выведет строку `[!!] openspec validate: WARNING …` в раздел находок. Это сигнал, не стоп (F-12).
- Корпус: 1730 сценариев в 101 файле `openspec/specs/**` и `openspec/changes/**/specs/**`, без триггера или без THEN — 0 (проверка скриптом по тем же правилам: жирный или голый верхний регистр, fence вырезан; проверка грубее upstream-овской, но строже — считала только начало строки, так что 0 у неё означает 0 и у upstream).
- Правило `openspec/config.yaml:9` «у каждого требования хотя бы один сценарий GIVEN/WHEN/THEN» и шаблон `templates/spec.md:11-14` (`- **GIVEN** … - **WHEN** … - **THEN** …`) — согласуются: шаблон пишет жирный верхний регистр, который попадает и под BOLD, и под BARE. Инструкция `schema.yaml:77` «сценарий … в виде GIVEN / WHEN / THEN» — то же. Строку, которую upstream добавил в свою схему (`schemas/spec-driven/schema.yaml:108`), в схему symphysis переносить не обязательно: своя инструкция уже требует форму; при желании можно добавить одну фразу о том, что `validate --strict` на этом красный.
- Исход `Specify/judgment` пробы запретов (`symphysis-prohibition-probe/SKILL.md:170` «у `B` THEN называет суждение и судью») — THEN есть, под правило не попадает.

### Выход 1 при невалидном `config.yaml` (№ 19)

`X:\symphysis\openspec\config.yaml` разбирается PyYAML `safe_load` без ошибки (ключи `schema`, `rules`, `operations`); форк на `origin/main` разбирает тем же классом грамматики (`parseYaml` в `readConfigParseError`). Сегодня эффекта нет.

Форма ответа при ошибке — `{ status: [{ severity, code, message, fix }] }` без `items` (`validate.ts:134`). `trace_graph.py:1265-1267` на ответ без `items` даёт одну строку «validate не запустился: ответ без находок `items`, код 1» — сбой назван, но причину (битый config.yaml) не покажет. `step_help.py:63-68` (`_reason`) такой конверт читать умеет (`data["status"][0]["message"]`), но `validate` не зовёт. Если захочется точной причины — в `validate_findings` добавить чтение `status[0].message` по образцу `_reason`; это улучшение, не починка.

### Парсеры (№ 4, 24, 25)

`grep` по `X:\symphysis\openspec\`: заголовков `###Requirement:` без пробела — 0; заголовков `##`–`####` с закрывающим прогоном `#` — 0; строк, начинающихся с тройного бэктика и содержащих ещё бэктик — 0; `~~~` — 0. Эффекта нет.

Свой парсер `trace/trace_graph.py` эти формы уже принимает: фикстура `tests/fixtures/trace/odd-headers/specs/omega/spec.md:36` `###Requirement: Без пробела после решёток`, `:39` `#### Scenario: Закрывающие решётки ####`, `:45` `### Requirement: Имя с закрывающими решётками ###`. После 1.16.1 оба парсера сходятся — расхождений между `trace_graph` и `validate` на этих формах станет меньше, править ничего не нужно.

Побочное от № 3: `findOrphanedRequirements` теперь маскирует HTML-комментарии (`maskHtmlComments`), поэтому `### Requirement:` внутри `<!-- … -->` больше не WARNING «сирота». В symphysis комментарии проб (`<!-- проба краёв … -->`) заголовков не несут — безразлично.

### version-check и память о телеметрии (№ 2, 5)

Скрипты symphysis: `openspec-run/openspec_run.py:144` `env.update(OPENSPEC_TELEMETRY="0", …)` — у каждого вызова форка пассивная проверка обновлений отключена через `isTelemetryOptedOutByEnv()` (`version-check.ts:76`); это не изменилось. `step_help.py:347` зовёт `openspec --version`, не `version --check` — явный путь (`index.ts:169`, `requested: true`) symphysis не трогает. В сеть из скриптов форк, как и раньше, не ходит.

Тестовая база: `test/core/version-check.test.ts` на `origin/main` — 1400+ строк (+351 к базе), тесты пассивного пути чистят `ENV_KEYS` = `NODE_ENV, CI, OPENSPEC_NO_UPDATE_CHECK, DO_NOT_TRACK, OPENSPEC_TELEMETRY, npm_config_registry` (`:97-104`) — `XDG_CONFIG_HOME` в списке нет, значит глобальный `config.json` машины они читают по-прежнему; изоляцию `withGlobalConfig` (`:410-429`) получают только тесты явного пути. Вывод: расклад из `UPSTREAM.md:54` (без `XDG_CONFIG_HOME` во временном каталоге падают тесты version-check при `telemetry.enabled: false`) после ребейза сохраняется; память «телеметрия включена нарочно» остаётся в силе, число падений без изоляции может отличаться от 11 — по прогону.

Побочная находка, не из этого выпуска: суффикс `-symphysis.N` — prerelease по SemVer, `compareVersions` ставит его ниже релиза (`version-check.ts:127-131`, `:185`), так что `1.15.0-symphysis.4` «старше» любого ванильного `1.15.0`+. На машине владельца телеметрия включена, и интерактивный `openspec update` (`index.ts:384` `await getAvailableCliUpdate()`, `:401-402` `displayCliUpdateNote(…); const outcome = await offerCliUpgrade(latestVersion);`) может предложить поставить ванильный `@fission-ai/openspec@latest` поверх форка — условие `shouldOfferUpgrade` (npm-глобальная установка, TTY) у владельца, похоже, выполняется. Не проверялось запуском; ребейз на 1.16.1 этого не меняет (после него `1.16.1-symphysis.N` ниже `1.16.1`). Стоит отдельного взгляда: либо `OPENSPEC_NO_UPDATE_CHECK` в окружении, либо версия форка вида `1.16.1+symphysis.N` (build metadata — `compareVersions` её отбрасывает, `:169`; но тогда гейт инсталлятора `check.js:35` и регэксп `generatedBy` в `update.test.ts` (C10) надо перепроверить).

## Риск ребейза

`git merge-tree --write-tree --name-only origin/main symphysis` (git 2.46.0.windows.1):

```
2bcdba32c290ce065d05c2197f438166fe7c3ae3
package.json

Auto-merging docs/customization.md
Auto-merging package.json
CONFLICT (content): Merge conflict in package.json
```

Конфликт один — `package.json`, строка 3 `version`: форк `"1.15.0-symphysis.4"` (`symphysis:package.json:3`), upstream `"1.16.1"` (`origin/main:package.json:3`). Ханки `engines` и `devDependencies` того же файла слились сами. `docs/customization.md` слился сам (ханки в разных местах, см. № 18). `pnpm-lock.yaml` форк не трогал — конфликта нет.

Пересечение по файлам `src/`, `schemas/`, `skills/`, `test/` между base..origin/main и base..symphysis — пусто (`comm -12` по `git diff --name-only`). Связь через импорты:

- `symphysis:src/core/artifact-graph/instruction-loader.ts:33` `import { readProjectConfig, validateConfigRules, type ProjectConfig } from '../project-config.js';` — upstream в `project-config.ts` только добавил `readConfigParseError` (diff `@@ -452,6 +452,34 @@`), эти два имени не менял.
- `symphysis:src/commands/workflow/shared.ts:17` `import { isRootSelectionError } from '../../core/root-selection.js';` — upstream добавил путь подсказки store, класс и `isRootSelectionError` не менял.
- Обратно: `origin/main:src/commands/validate.ts:20` `import { getAvailableChanges } from './workflow/shared.js';` — форк в `shared.ts` добавил только поле интерфейса `artifactsWithoutPassingVerdict` (`symphysis:shared.ts:63-69`); `origin/main:src/core/validation/validator.ts:50` `import { getPackageSchemasDir, getSchemaDir } from '../artifact-graph/index.js';` — форк в `index.ts` (+12) эти экспорты сохранил.

Семантического пересечения с C1–C14 нет. Вывод `status --json`, `instructions --json`, `show --json` в части, которую читают `step_help.py:189-205, 264-265` (`artifacts[].status/optional/requires/missingDeps`, `applyRequires`, `artifactPaths`, `state`, `progress`) формируется кодом форка и upstream не тронут; `validate --json` в части `items[].valid/issues[].level/path/message` (`validate.ts:380`) — не изменился, добавились только новые issue того же вида и новый конверт `status` при битом config.yaml.

Ребейз или мерж — отдельная развилка:

- Ребейз: 26 коммитов форка переписываются; четыре из них (C6 `3a6a8265`, C10 `1385c85b`, C13 `18ae8ba1`, C14 `2a64d727`) правят ту же строку `version`, каждый даст конфликт на этой строке — четыре тривиальных разрешения. Хеши C1–C14 в `UPSTREAM.md:25-39` устареют все; ветка `openspec-fork` в `symphysis-core` (`installer/scripts/build-vendor.js`, `forkMissingMessage`) потребует force-push.
- Мерж `origin/main` в `symphysis`: один конфликт (`version`), хеши C1–C14 и таблица `UPSTREAM.md` остаются верными, push обычный; цена — история не линейная, и «версия upstream» в `UPSTREAM.md:3` станет мерж-коммитом, а не базой.

## Тесты

Upstream: добавил 8 файлов — `test/cli-e2e/unrecognized-delta-section.test.ts` (+79, e2e, нужен собранный `dist/`), `test/commands/validate-unparseable-config.test.ts` (+109), `test/core/parsers/closed-section-heading.test.ts` (+157), `test/core/parsers/code-fence.test.ts` (+69), `test/core/parsers/spec-structure-unspaced-header.test.ts` (+41), `test/core/store/git-repo-name.test.ts` (+43), `test/core/validation.scenario-steps.test.ts` (+305), `test/core/parsers/orphaned-requirements.test.ts` (+150, изменён); переписал или дополнил 10 — `version-check.test.ts` (+351), `root-selection.test.ts` (+219, спаунит git), `zsh-installer.test.ts` (+170), `archive.test.ts` (+82), `markdown-parser.test.ts`, `closed-requirement-heading.test.ts`, `binary-installer.test.ts`, `store-git.test.ts`, `store-remote.test.ts`, `zsh-installer.round-trip.test.ts`. Ни один не совпадает с 19 тестовыми файлами форка (`comm -12` пуст).

Что может покраснеть у форка после ребейза и почему:

1. Вся база под vitest 5 / vite 8 (`package.json:73`). Тесты форка (`status-verdict`, `optional-artifact`, `frontmatter`, `instruction-loader`, `state`, `apply-optional`, `continue-verdict`, правки `update.test.ts` и др.) написаны на vitest 4. Upstream свою базу на 5 перевёл, идиомы те же (`describe/it/expect`, `vi.spyOn`), поэтому вероятность низкая, но без прогона не утверждается. Это главный неизвестный ребейза.
2. `test/core/version-check.test.ts` — без `XDG_CONFIG_HOME` во временном каталоге часть тестов пассивного пути читает глобальный конфиг (`:97-104`), как и до ребейза; с изоляцией, как в `UPSTREAM.md:54`, ожидается зелёный.
3. Восемь известных EPERM symlink (`update.test.ts` ×1, `schema.test.ts` ×1, `resolver.test.ts` ×6, `UPSTREAM.md:51-55`) — upstream эти тесты не трогал, останутся.
4. `test/core/update.test.ts` «should embed generatedBy» — регэксп C10 принимает `-symphysis.N`; версия `1.16.1-symphysis.N` под него попадает, upstream файл не менял.
5. `test/core/templates/skill-templates-parity.test.ts` — пины парити: upstream шаблоны `src/core/templates/workflows/*` не менял, `pnpm regen:parity-hashes` после сборки ожидаемо скажет «already match».
6. Новые upstream-тесты с настоящим git на Windows (`root-selection.test.ts`, `git-repo-name.test.ts`) — upstream сам поднял таймаут store-тестов до 30 с на Windows (№ 15), значит медленные места видел; возможны таймауты на загруженной машине, не ошибки логики.
7. `test/cli-e2e/unrecognized-delta-section.test.ts` — как `startup-modules` (C5): красный на несвежем `dist/`, прогон только после `pnpm build`.

Symphysis: pytest форк не спаунит — `tests/conftest.py` и тесты `step-help`, `openspec-run`, `trace` ставят `SYMPHYSIS_OPENSPEC` на подставной скрипт (`openspec-run/tests/test_openspec_run.py:25-27`, `step-help/tests/test_step_help.py:145-201`). Задеты только тесты инсталлятора: `installer/test/check.test.js:19` `const PIN = "1.15.0-symphysis.4";` и `:215` — при смене пина править; `installer/test/npx.test.js:139` `assert.equal(v.stdout.trim(), pkg.symphysis.openspecPin);` — сравнивает `--version` настоящего форка с пином, нужен новый тарбол; `installer/test/vendor.test.js:125` — имя тарбола из пина.

## Варианты порядка

Что придётся править при любом переезде форка на новую версию (общий список, «пин-файлы»): `upstream/openspec/package.json:3` (версия), `upstream/openspec/UPSTREAM.md` (`:3` пин, таблица выпусков, строка C15, прогон), `installer/package.json` (`symphysis.openspecPin`, `symphysis.openspecSource`, при Node 22 — `engines.node`), `vendor/fission-ai-openspec-<версия>.tgz` через `installer/scripts/build-vendor.js` (старый тарбол удаляется), `installer/test/check.test.js:19`, `docs/GUIDE.md:59,66,107,651,663` (имя тарбола и вывод `--version`; `:11` — только при Node 22), `CLAUDE.md:102`, `.context/02-glossary.md:33`, семь `.claude/skills/openspec-*/SKILL.md` (`generatedBy`, перегенерирует `openspec update`).

### Вариант 1 — мерж или ребейз на v1.16.1 сейчас, до выпуска

За: три дыры валидатора закрываются до того, как ими воспользуется модель (DEPRECATED-секция, тройной бэктик в строке, опечатка в `config.yaml`, из-за которой все `rules` молча выключаются — для symphysis `rules` несут FORCE stance атак и правило F-NN); один тарбол и одна правка GUIDE вместо двух выпусков подряд; merge-tree чист кроме строки версии, по смыслу C1–C14 не задеты; `trace_graph` и `validate` сходятся на формах заголовков.

Против: вся тестовая база форка (6719 passed на 2026-11-02) переезжает на vitest 5 — полный прогон обязателен и может принести новые красные, которых на бумаге не видно; `engines >=22.12.0` сужает корпоративную установку без запасного пути бинарника; к пин-файлам добавляются `GUIDE.md:11` и `installer/package.json` `engines`; версия вида `1.16.1-symphysis.5` оставляет побочную находку про `openspec update` как есть.

Внутри варианта — мерж против ребейза (раздел «Риск ребейза»): мерж сохраняет хеши C1–C14 и не требует force-push ветки `openspec-fork`; ребейз даёт линейную историю ценой четырёх конфликтов на строке версии и переписывания таблицы `UPSTREAM.md`.

### Вариант 2 — выпуск на `1.15.0-symphysis.4`, переезд после

За: выпуск не ждёт прогона 6.7 тысяч тестов на новом vitest; известная тестовая база (`UPSTREAM.md:55`); GUIDE «Node 20 или новее» остаётся верным; корпоративная установка на Node 20 возможна.

Против: выпуск несёт известные дыры валидатора — на текущих файлах они не стреляют (проверено), но инструкция `schema.yaml:78` и шаблон `spec.md:20-21` разрешают REMOVED/RENAMED, а модель может написать иное имя секции, и 1.15.0 потеряет требование с предупреждением, не стопом; второй выпуск после переезда повторит всю правку пин-файлов и GUIDE; разрыв с upstream растёт, следующий разбор будет на два выпуска.

### Вариант 3 — cherry-pick исправлений валидатора без Node 22 и зависимостей

Набор: `a6cd3bc9`, `cb1adee5`, `ae7ad750`, `dc376098`, `c887ab07`, `83053dd8` — в порядке upstream (они правят одни и те же `requirement-blocks.ts`, `validator.ts`, `specs-apply.ts`, `spec-structure.ts` друг за другом; `83053dd8` ложится на `validator.ts` после `dc376098` и `c887ab07`), с их тестами. Все шесть трогают только файлы, которых форк не касался — конфликтов не ожидается. Версия — `1.15.0-symphysis.5`.

За: `engines` остаётся `>=20.19.0`, vitest остаётся 4 — тестовая база не меняется, прогон короткий; корпоративная установка на Node 20 не ломается; закрываются те же три дыры и предупреждение о сценариях; GUIDE `:11` не меняется, правятся только пин-файлы.

Против: ещё один слой учёта — `UPSTREAM.md` должен перечислять cherry-pick'и отдельно от C-правок (правило F-03 «по перечню правок» это допускает, но перечень растёт); при будущем мерже/ребейзе на 1.16.1+ git опознает дубли по patch-id, но при соседних правках в тех же файлах может дать конфликты, которых не было бы без cherry-pick; версия `1.15.0-symphysis.5` несёт код 1.16.1 — читателю `UPSTREAM.md` это надо объяснять; `version-check` (`ef170faa`, `a1ae5366`) и zsh остаются старыми — для symphysis безразлично.

### Вариант 4 (маловероятный) — не трогать до следующего выпуска upstream

За: правило F-03 (`UPSTREAM.md:6-8`) — не каждый выпуск затягивается; сегодня ни один из 26 коммитов не ломает symphysis.

Против: причина не брать отсутствует — пересечения нет, конфликт один; дыры валидатора остаются; Node 20 EOL, и следующий выпуск upstream точно будет на `>=22.12.0`, то есть вопрос Node вернётся с бо́льшим разрывом.

### Что ещё решить вместе с выбором

- Форма версии форка: `1.16.1-symphysis.N` (продолжить счёт с 5 или начать с 1) — prerelease ниже релиза, побочная находка про `openspec update` остаётся; `+symphysis.N` снимает её, но трогает гейт `check.js:35` и регэксп `update.test.ts` (C10) — проверять.
- `installer/package.json` `engines.node` — поднимать до `>=22.12.0` вместе с форком или оставить `>=20` и ловить Node-версию в `symphysis check` (сейчас не ловит).
- Нужен ли в `trace_graph.validate_findings` разбор конверта `status[0].message` для битого `config.yaml` — улучшение сообщения, не починка.
