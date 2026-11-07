---
skill: symphysis-attack
artifact: attack-artifacts
change: attack-stale-scope
targets:
  - path: decisions.json
    sha256: 26600aa48422f24d1b504c68536d4f061f2d8343f961bb94c5320c7f7684b047
  - path: specs/artifact-attack/spec.md
    sha256: d4b72253f56abb39fc900c68f901d00e946afb31491081825956187408839e51
  - path: specs/decision-journal/spec.md
    sha256: 673cd7f6371090f8ab8a75d9966bdc7f7e75c3aa2ef9f61576afaf6e1ac2341d
  - path: specs/stale-verdict-scope/spec.md
    sha256: 362523cd620c41505b2f83b1c71b9860640c276e576e5dc79908fefa5baec407
  - path: specs/step-help/spec.md
    sha256: f220aaea67ba6c2e6c809b3c4b7e1ef8b0bcfe46bba22be6ccba03922845721f
  - path: consequences.md
    sha256: a0359d50bd8bef058c37b47d27a16b6e0afdc28249c0716dae5fe26b06984e18
  - path: design.md
    sha256: 77672cfd1a2b6e450c80b81d0d8de4faa78191a6baf0f85eb99264640208093d
  - path: security.md
    sha256: b63e8e993572d84beafa6c4ce21193999d880259d4d766b8556fb14782b6716b
  - path: tasks.md
    sha256: a8af915db1f8628960f96d89fbb28717eb07a59629efe37cf7c6e41bf3bce52a
inputs:
  - openspec/changes/attack-stale-scope/
  - attack/attack_scope.py
  - attack/attack_table.py
  - cli/journal_cli.py
  - cli/journal.py
  - step-help/step_help.py
  - attack/skills/symphysis-attack/SKILL.md
  - attack/agents/symphysis-attack-driver.md
  - attack/attack-table.md
  - skill-shared/terms.md
  - cli/journal-cli.md
  - openspec/schemas/symphysis/templates/attack-decisions.md
  - openspec/schemas/symphysis/steps.md
  - docs/GUIDE.md
  - docs/repo-contract.md
  - installer/scripts/sync-payload.js
  - installer/lib/install.js
  - installer/lib/check.js
  - installer/test/install.test.js
  - attack/tests/test_attack_scope.py
  - cli/tests/test_cli_check.py
  - step-help/tests/test_step_help.py
  - tests/test_skills.py
  - upstream/openspec/src/core/artifact-graph/state.ts
  - openspec/specs/
report: openspec/changes/attack-stale-scope/briefs/symphysis-attack-2026-11-07-2/report.md
---

# Brief: повтор атаки артефактов изменения attack-stale-scope

Повтор после правок артефактов по спору человека (`answers/2026-11-07-5.md`, `notes[]` журнала).
Исполнить шаги 0–6 тела скилла `symphysis-attack` для вызова `attack-artifacts`: цели — `targets`
выше, журнал первым как опора. Шаг 7 — отчёт по пути `report`. Каталог изменения и корень
проекта — `X:\symphysis-attack-stale-scope` (worktree ядра symphysis; команды из корня проекта).

Файл атаки `attack/artifacts.md` от прохода 2026-11-07 (`status: gaps_found`, 235 строк) уже
лежит на месте; хеши пяти целей разошлись (`decisions.json`, `specs/artifact-attack/spec.md`,
`consequences.md`, `tasks.md` правлены после вердикта) — по шагу 1 тела скилла атака артефактов
идёт с начала: таблица пишется заново, прежние строки не переносятся, frontmatter — свежие хеши.

Состав линз (вторая строка `python .symphysis/tools/symphysis_config.py`, прочитана главной
нитью): все три линзы файла включены: `**Состав:** включены scenario-run, claim-extraction,
trace-link; выключены —`.

Что изменилось с прошлого прохода (для сверки, не для пропуска строк):

- улики F-16 и F-21 на `attack/skills/symphysis-attack/SKILL.md` заменены текущей строкой
  правила (`check`: 89 из 89);
- задача 1.5 больше не называет сценарий «Два читателя», задача 2.2 называет отдельный тест
  `install.test.js` о `attack_scope.py`;
- комментарий следа в `specs/artifact-attack/spec.md` не несёт номеров чужого журнала;
- опись `consequences.md`: строки о `cli/journal_cli.py:162` (файла нет — ветка из `check`
  недостижима), `state.ts:195` (`verdict: missing` → сценарий «Хеш цели не задан»),
  `state.ts:131` (окно только гейтует → сценарий «Вердикт не прошёл при изменённом журнале»).

Особенности этого запуска:

- Сверка журнала — только исходником с корнями изменения, дословно:
  `python -X utf8 cli/journal.py check --write --roots openspec/changes/attack-stale-scope/probes/journal-roots.json openspec/changes/attack-stale-scope/decisions.json`.
  Установленная копия `.symphysis/tools/journal.py` раскрывает `<root>` от `.symphysis/`
  и даёт ложные «файла нет» у улик `upstream/`, `vscode/`.
- Реализация изменения сделана (27 задач отмечены): механизмы design читаются по коду
  в `inputs` — `attack/attack_scope.py` (`scope_lines`), `cli/journal_cli.py` (`_scope_report`),
  `step-help/step_help.py` (`_stale_scope`, `_artifact_page`), правило повтора —
  `attack/skills/symphysis-attack/SKILL.md`, шаг 1. Код только читается; тесты, сборку
  и команды цели не запускать.
- Ветки форка из описи — файл `upstream/openspec/src/core/artifact-graph/state.ts` в `inputs`:
  опора «есть» у строк по этим веткам — цитатой из файла, не результатом сверки `check`.
- Связи для `trace-link`: `python .symphysis/tools/trace_graph.py build attack-stale-scope`;
  счёт главной нити по команде тела скилла — `satisfies 51, traces 32, verifies 12, всего 95`.
- Мастер-спеки для требований MODIFIED — `openspec/specs/<capability>/spec.md`.
- Отчёт: среда субагента отказывает в записи `report.md` — текст отчёта целиком идёт последним
  сообщением, главная нить сохраняет его по пути `report`; попытка записи не нужна.

Писать: `openspec/changes/attack-stale-scope/attack/artifacts.md`, строку итога в `notes[]`
журнала `openspec/changes/attack-stale-scope/decisions.json`, черновики — в каталог этого brief.

Не делать: `apply`, `decision`, `outcome`, правки `specs/`, `design.md`, `security.md`,
`tasks.md`, `consequences.md`, кода проекта и `symphysis.yaml`; вопросы человеку — только
строками отчёта; чтение вне `inputs`.
