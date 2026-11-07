---
skill: symphysis-attack
artifact: attack-artifacts
change: attack-stale-scope
targets:
  - path: decisions.json
    sha256: 864170b9bf5e38b3c585873ae8751adbc7842fa197f8c162fa60829077fd692c
  - path: specs/artifact-attack/spec.md
    sha256: 0215af9868505df7992d1fdd562b857eed1ac0192b167492caf298ac7e0153d0
  - path: specs/decision-journal/spec.md
    sha256: 673cd7f6371090f8ab8a75d9966bdc7f7e75c3aa2ef9f61576afaf6e1ac2341d
  - path: specs/stale-verdict-scope/spec.md
    sha256: 362523cd620c41505b2f83b1c71b9860640c276e576e5dc79908fefa5baec407
  - path: specs/step-help/spec.md
    sha256: f220aaea67ba6c2e6c809b3c4b7e1ef8b0bcfe46bba22be6ccba03922845721f
  - path: consequences.md
    sha256: 3e15d347e03e4f66a2446fbef3e79c5a787da459cbfd43f0ae2f6b5c92f5c6cf
  - path: design.md
    sha256: 77672cfd1a2b6e450c80b81d0d8de4faa78191a6baf0f85eb99264640208093d
  - path: security.md
    sha256: b63e8e993572d84beafa6c4ce21193999d880259d4d766b8556fb14782b6716b
  - path: tasks.md
    sha256: d40790805bf9c166f99508ab2313d12e638d0c170189b070de7fad711b10e08e
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
  - attack/tests/test_attack_scope.py
  - cli/tests/test_cli_check.py
  - step-help/tests/test_step_help.py
  - tests/test_skills.py
  - openspec/specs/
report: openspec/changes/attack-stale-scope/briefs/symphysis-attack-2026-11-07/report.md
---

# Brief: атака артефактов изменения attack-stale-scope

Исполнить шаги 0–6 тела скилла `symphysis-attack` для вызова `attack-artifacts`: цели —
`targets` выше, журнал первым как опора. Шаг 7 — отчёт по пути `report`. Каталог изменения
и корень проекта — `X:\symphysis-attack-stale-scope` (worktree ядра symphysis; команды
из корня проекта).

Состав линз (вторая строка `python .symphysis/tools/symphysis_config.py`, прочитана главной
нитью): `context-compliance вкл, claim-authority вкл, claim-extraction вкл, coverage вкл,
scenario-run вкл, trace-link вкл` — у артефактов включены все три линзы файла:
`**Состав:** включены scenario-run, claim-extraction, trace-link; выключены —`.

Особенности этого запуска:

- Сверка журнала — только исходником с корнями изменения, дословно:
  `python -X utf8 cli/journal.py check --write --roots openspec/changes/attack-stale-scope/probes/journal-roots.json openspec/changes/attack-stale-scope/decisions.json`.
  Установленная копия `.symphysis/tools/journal.py` раскрывает `<root>` от `.symphysis/`
  и даёт ложные «файла нет» у улик `upstream/`, `vscode/`.
- Два `[!!]` у улик F-16 и F-21 (`attack/skills/symphysis-attack/SKILL.md`, цитата «Если хеши
  разошлись … с начала») — дрейф улик: правило скилла заменено этим изменением; строки о них
  идут как «нет» по `found: false`, как велит тело скилла, без дополнительных выводов.
- Реализация изменения уже сделана (все 27 задач `tasks.md` отмечены): механизмы design
  читаются по коду в `inputs` — `attack/attack_scope.py` (`scope_lines`), `cli/journal_cli.py`
  (`_scope_report`), `step-help/step_help.py` (`_stale_scope`, `_artifact_page`), правило
  повтора — `attack/skills/symphysis-attack/SKILL.md`, шаг 1. Код только читается; тесты,
  сборку и команды цели не запускать.
- Связи для `trace-link`: `python .symphysis/tools/trace_graph.py build attack-stale-scope`;
  счёт главной нити по команде тела скилла — `satisfies 52, traces 34, verifies 12, всего 98`.
- Мастер-спеки для требований MODIFIED — `openspec/specs/<capability>/spec.md`.

Писать: `openspec/changes/attack-stale-scope/attack/artifacts.md`, строку итога в `notes[]`
журнала `openspec/changes/attack-stale-scope/decisions.json`, отчёт
`openspec/changes/attack-stale-scope/briefs/symphysis-attack-2026-11-07/report.md`, черновики —
в каталог этого brief.

Не делать: `apply`, `decision`, `outcome`, правки `specs/`, `design.md`, `security.md`,
`tasks.md`, `consequences.md`, кода проекта и `symphysis.yaml`; вопросы человеку — только
строками отчёта; чтение вне `inputs`.
