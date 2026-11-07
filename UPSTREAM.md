# Форк OpenSpec для symphysis

upstream: Fission-AI/OpenSpec @ 0fa4a970 (1.16.1, 2026-11-07); база форка — 6d04a1b5
(1.15.0, 2026-10-24), выпуски upstream втягиваются мержем в ветку `symphysis` (C15)
ветка форка: `symphysis`

Правило (слово человека 2026-10-29, F-03): «Форк бы отставал, но не каждый
выпуск openspec затягивается в реальную работу. Сначала будет идти его
анализ и решение о необходимости подключения функций.»

Правки форка — две точки (F-02.B, F-03.C): готовность артефакта
по вердикту во frontmatter (`verdict` в схеме, `state.ts`, `status`)
и шаг вердикта в шаблоне `continue`. Остальное — схема, `rules`
и свои скиллы в проекте symphysis.
Решение 2026-10-31 (F-06.A, F-26.E) добавило признак `optional`, вердикт `stale`
и вызов артефакта по имени (`continue <change> <artifact-id>`).
Решение 2026-11-01 (F-64.B) добавило окно устаревания: `stale` гейтует, пока
не начался следующий шаг, дальше — сигнал.
Решение 2026-11-01 (F-126.A): `continue` входит в профиль `core`, `symphysis install`
только обновляет проект, а глобальный конфиг не трогает.

## Правки форка

| Правка | Коммит |
| --- | --- |
| C1 — verdict в схеме артефакта | 543113cd |
| C2 — frontmatter и готовность по вердикту (`frontmatter.ts`, `state.ts`) | 3af902cf |
| C3 — verdict в статусе артефакта и подсказка в `nextSteps` (`instruction-loader.ts`, `change-status-policy.ts`, `status.ts`) | de8c1f10 |
| C4 — шаг вердикта в шаблоне `continue` (`continue-change.ts`, пины парити, `skills/openspec-continue-change`) | cb801a59, b982f281 |
| C5 — сборка, кросс-проверка пинов, docs (`docs/cli.md`, `docs/agent-contract.md`, `docs/customization.md`), тест `status` через `runCLI` | adced9b4, 4b100b6e |
| C5 — `isGlobPattern` вынесен из `outputs.ts` в `glob-pattern.ts`: проверка verdict в `schema.ts` тянула tinyglobby в чтение схемы (`startup-modules` красный после сборки); `outputs.ts` переэкспортирует имя | d88ca368 |
| C6 — версия форка 1.15.0-symphysis.1, чтобы гейт инсталлятора отличал форк от ванильного OpenSpec (package.json) | 3a6a8265 |
| C7 — `optional` и вердикт `stale` (схема, `state.ts`, `instruction-loader.ts`, гейт apply, `status`, `instructions`; документы `docs/agent-contract.md`, `docs/cli.md`, `docs/customization.md`) | 378cdfe4, b29b8b15, 18d49d7f |
| C8 — `continue` по имени артефакта: четыре правила `NAMED_ARTIFACT` и `stale` в `VERDICT_CHECK` (`continue-change.ts`, пины парити, `skills/openspec-continue-change`) | 27048f12 |
| C9 — `apply` о невызванных атаках (`UNINVOKED_OPTIONAL`) и о блоке только по вердикту (`apply-change.ts`, `skills/openspec-apply-change`) | 27048f12 |
| C10 — версия форка 1.15.0-symphysis.2; регэксп теста `generatedBy` принимает prerelease-суффикс (package.json, `test/core/update.test.ts`) | 1385c85b |
| C11 — окно устаревания вердикта (F-64.B): `stale` гейтует, пока у зависимого артефакта нет файла, а у артефакта без зависимых в `apply.requires` — пока в `apply.tracks` нет отмеченной задачи; дальше артефакт `done` с `verdict: "stale"` и строкой-сигналом в `nextSteps`; окно — из графа и `apply.tracks`, без имён схемы (`state.ts` `detectStaleSignals`, `instruction-loader.ts`, `change-status-policy.ts`, `status.ts`; документы `docs/agent-contract.md`, `docs/cli.md`; противоречие §4.4 и §4.6 о `missingArtifacts` снято) | 9b2acf6f |
| C12 — `continue` выбирает тот же следующий артефакт, что CLI (`NEXT_ARTIFACT`: пропускается только optional без файла), по имени `done` без вердикта или `skipped` — STOP; `apply` называет сигнал stale (`STALE_SIGNAL`) (`continue-change.ts`, `apply-change.ts`, пины парити, два SKILL.md) | e0d02a2b |
| C13 — версия форка 1.15.0-symphysis.3 (package.json) | 18ae8ba1 |
| C14 — `continue` в `CORE_WORKFLOWS` (F-126.A, `profiles.ts`): развилки `optionalWorkflow` сами дают `/opsx:continue` на core, запасной путь CLI остаётся для custom без него; тесты паритета под семь workflow. Состав core поправлен в `docs-lab/customize/profiles.md` (его читает тест), `docs-lab/reference/skills.md`, `docs/glossary.md`. В `README.md`, `docs/supported-tools.md`, `faq.md`, `how-commands-work.md`, `opsx.md` прежний состав: в тарбол они не входят, а правка поднимала гейт имён на чужих адресах всего файла. Версия форка 1.15.0-symphysis.4 (package.json) | 2a64d727 |
| C15 — мерж upstream v1.16.1 (`0fa4a970`, 26 коммитов от базы): конфликт один — строка `version` в package.json; область C1–C14 upstream не трогал (`artifact-graph`, шаблоны workflow, `status`, `instructions`, `profiles`); версия форка 1.16.1-symphysis.5 (package.json), engines upstream `node >=22.12.0`. Разбор — symphysis `docs/analysis/upstream-openspec-1.16.1-2026-11-07.md` | ecad6db2 |
| C16 — форма версии `1.16.1+symphysis.5`: build metadata вместо prerelease. С `-symphysis.N` версия по SemVer ниже релиза, и `openspec version --check` на установленном форке печатал «Update available: 1.16.1» с командой поставить ваниль; с `+symphysis.N` `compareVersions` (`src/core/version-check.ts`, `split('+', 1)`) отбрасывает build-часть, пакет отвечает «up to date». Регэксп теста `generatedBy` (C10, `test/core/update.test.ts`) принимает `[-+]`. Четыре standalone-теста `version-check.test.ts` остаются красными при любом суффиксе — регэксп ленты релизов берёт только `vX.Y.Z`. Решение владельца 2026-11-07 (symphysis `docs/plan-flexible-pipeline.md`, «Сверка с upstream — 2026-11-07») | 8c0a8c0c |

## Выпуски upstream

| Выпуск | Разобран | Решение |
| --- | --- | --- |
| 1.15.0 `6d04a1b5` | 2026-10-29 (`docs/analysis/step0-sources.md` symphysis) | база форка |
| 1.16.0 `27c05157` | 2026-11-07 (symphysis `docs/analysis/upstream-openspec-1.16.1-2026-11-07.md`) | втянут мержем вместе с 1.16.1 (C15); слово владельца о порядке и Node 22.14 — symphysis `docs/plan-flexible-pipeline.md`, «Сверка с upstream — 2026-11-07» |
| 1.16.1 `0fa4a970` | 2026-11-07 (там же) | втянут мержем (C15): исправления валидатора и парсеров, Node ≥ 22.12 → порог инсталлятора и GUIDE symphysis поднят до 22.14; `validate --strict` в `trace_graph.py` теперь красный на сценарии без WHEN/GIVEN или THEN (в корпусе symphysis нарушений нет) |

## Прогоны тестов

| Дата | Коммит форка | Результат |
| --- | --- | --- |
| 2026-10-29 | база, без правок (6d04a1b5) | 6560 passed, 154 skipped, **8 failed — все EPERM symlink на Windows без прав разработчика** (`test/core/update.test.ts` ×1, `test/commands/schema.test.ts` ×1, `test/core/artifact-graph/resolver.test.ts` ×6); база: «зелёный» значит без новых красных |
| 2026-10-30 | C1–C5, после сборки `dist/` (4b100b6e) | 6624 passed, 154 skipped, **8 failed — те же восемь EPERM symlink** (`update.test.ts` ×1, `schema.test.ts` ×1, `resolver.test.ts` ×6); первый прогон на свежем `dist/` (b982f281) дал 6622 passed и 9 failed — девятым был `cli-e2e/startup-modules.test.ts`, исправлен в d88ca368; `pnpm regen:parity-hashes`: «already match the build - nothing to update», `pnpm generate:skills`: `git status` чист |
| 2026-10-31 | C1–C10, после сборки `dist/` (версия 1.15.0-symphysis.2) | 6698 passed, 154 skipped, **8 failed — те же восемь EPERM symlink** (`update.test.ts` ×1, `schema.test.ts` ×1, `resolver.test.ts` ×6); девятое падение (`update.test.ts` «should embed generatedBy», регэксп не принимал `-symphysis.N` после C6) снято правкой регэкспа в C10; `pnpm regen:parity-hashes` после сборки сдвинул пины `continue`/`apply`, `pnpm generate:skills` обновил два SKILL.md |
| 2026-11-01 | C1–C13, после сборки `dist/` (версия 1.15.0-symphysis.3) | с `XDG_CONFIG_HOME` во временном каталоге: 6719 passed, 154 skipped, **8 failed — те же восемь EPERM symlink** (`update.test.ts` ×1, `schema.test.ts` ×1, `resolver.test.ts` ×6). Без изоляции ещё 11 красных в `test/core/version-check.test.ts`: глобальный конфиг машины несёт `telemetry.enabled: false`, и проверка обновлений отключена (`isCheckEnabled`) — среда, не правка; в изоляции 67/67. `pnpm regen:parity-hashes` сдвинул пины `continue`/`apply`, `pnpm generate:skills` обновил два SKILL.md |
| 2026-11-02 | C1–C14, после сборки `dist/` (версия 1.15.0-symphysis.4) | с `XDG_CONFIG_HOME` во временном каталоге: 6719 passed, 154 skipped, **8 failed — те же восемь EPERM symlink** (`update.test.ts` ×1, `schema.test.ts` ×1, `resolver.test.ts` ×6). До правки тестов под новый состав core падало 46, из них 38 — ожидания прежних шести workflow. `pnpm regen:parity-hashes`: «already match the build», `pnpm generate:skills`: `git status` без новых файлов |
| 2026-11-07 | C1–C15, после мержа v1.16.1 и сборки `dist/` (версия 1.16.1-symphysis.5; vitest 5, vite 8) | с `XDG_CONFIG_HOME` во временном каталоге: 6855 passed, 157 skipped, **12 failed — те же восемь EPERM symlink** (`update.test.ts` ×1, `schema.test.ts` ×1, `resolver.test.ts` ×6) **и четыре новых в `version-check.test.ts` «standalone update check»** (`:1567`, `:1597`, `:1611`, `:1663`): тест строит ленту релизов GitHub из собственной версии пакета и ждёт `current`, а проверка standalone пропускает prerelease-теги — `1.16.1-symphysis.5` по SemVer prerelease, лента пуста, `checkForCliUpdate` отдаёт `offline` (`version-check.ts:410`). Это форма версии форка, не правка; standalone-бинарник форк не поставляет. Снимется формой `+symphysis.N` (build metadata — не prerelease) или правкой четырёх тестов — решение открыто. `pnpm regen:parity-hashes`: «already match», `pnpm generate:skills`: `git status` чист |
| 2026-11-07 | C1–C16, после сборки `dist/` (версия 1.16.1+symphysis.5) | с `XDG_CONFIG_HOME` во временном каталоге: 6855 passed, 157 skipped, **12 failed — те же, что в прогоне C1–C15**: восемь EPERM symlink и четыре «standalone update check» (`version-check.test.ts`), форма версии их не меняет. Тест `generatedBy` (`update.test.ts`, C10/C16) с `+` зелёный. `pnpm regen:parity-hashes`: «already match», `pnpm generate:skills`: `git status` чист. Установленный тарбол на `openspec version --check` (реестр npm): «OpenSpec is up to date» |
