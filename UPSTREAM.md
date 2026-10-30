# Форк OpenSpec для symphysis

upstream: Fission-AI/OpenSpec @ 6d04a1b5 (1.15.0, 2026-10-24)
ветка форка: `symphysis`

Правило (слово человека 2026-10-29, F-03): «Форк бы отставал, но не каждый
выпуск openspec затягивается в реальную работу. Сначала будет идти его
анализ и решение о необходимости подключения функций.»

Правки форка — две точки (F-02.B, F-03.C): готовность артефакта
по вердикту во frontmatter (`verdict` в схеме, `state.ts`, `status`)
и шаг вердикта в шаблоне `continue`. Остальное — схема, `rules`
и свои скиллы в проекте symphysis.

## Правки форка

| Правка | Коммит |
| --- | --- |
| C1 — verdict в схеме артефакта | 543113cd |
| C2 — frontmatter и готовность по вердикту (`frontmatter.ts`, `state.ts`) | 3af902cf |
| C3 — verdict в статусе артефакта и подсказка в `nextSteps` (`instruction-loader.ts`, `change-status-policy.ts`, `status.ts`) | de8c1f10 |
| C4 — шаг вердикта в шаблоне `continue` (`continue-change.ts`, пины парити, `skills/openspec-continue-change`) | cb801a59, b982f281 |
| C5 — сборка, кросс-проверка пинов, docs (`docs/cli.md`, `docs/agent-contract.md`, `docs/customization.md`), тест `status` через `runCLI` | adced9b4, 4b100b6e |
| C5 — `isGlobPattern` вынесен из `outputs.ts` в `glob-pattern.ts`: проверка verdict в `schema.ts` тянула tinyglobby в чтение схемы (`startup-modules` красный после сборки); `outputs.ts` переэкспортирует имя | d88ca368 |

## Выпуски upstream

| Выпуск | Разобран | Решение |
| --- | --- | --- |
| 1.15.0 `6d04a1b5` | 2026-10-29 (`docs/analysis/step0-sources.md` symphysis) | база форка |

## Прогоны тестов

| Дата | Коммит форка | Результат |
| --- | --- | --- |
| 2026-10-29 | база, без правок (6d04a1b5) | 6560 passed, 154 skipped, **8 failed — все EPERM symlink на Windows без прав разработчика** (`test/core/update.test.ts` ×1, `test/commands/schema.test.ts` ×1, `test/core/artifact-graph/resolver.test.ts` ×6); база: «зелёный» значит без новых красных |
| 2026-10-30 | C1–C5, после сборки `dist/` (4b100b6e) | 6624 passed, 154 skipped, **8 failed — те же восемь EPERM symlink** (`update.test.ts` ×1, `schema.test.ts` ×1, `resolver.test.ts` ×6); первый прогон на свежем `dist/` (b982f281) дал 6622 passed и 9 failed — девятым был `cli-e2e/startup-modules.test.ts`, исправлен в d88ca368; `pnpm regen:parity-hashes`: «already match the build - nothing to update», `pnpm generate:skills`: `git status` чист |
