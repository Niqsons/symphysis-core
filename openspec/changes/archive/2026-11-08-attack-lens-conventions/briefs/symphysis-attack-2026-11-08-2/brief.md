---
skill: symphysis-attack
artifact: attack-artifacts
change: attack-lens-conventions
targets:
  - path: decisions.json
    sha256: 09978ff1910257a35393ea604861d45fb25daec31c2e07bb2b1df3759a403804
  - path: specs/artifact-attack/spec.md
    sha256: a0cdcd7162ae658ec4a2dbd30b8af9a8071ed3165943df56bf76d7816c21457a
  - path: specs/decision-viewer/spec.md
    sha256: bb6c431f21ee4b4192065add2f6ef1b6d3e3d9ed7890402ca37d3f945b9ce99a
  - path: specs/plugin-core-contract/spec.md
    sha256: 3f79daeb0b6c875d7b35d9150af01bc58b8261db843b3f1e3b7c2f860d04d015
  - path: consequences.md
    sha256: 1f10527cc0e7e6a1f16d56ce09a8b43559be0dc22c48629899eb8f09d864937c
  - path: design.md
    sha256: c46422b78029888182156dd1d50aced2a152a4440ec41a9b12adb1f87f3b139a
  - path: security.md
    sha256: c8444a77e81bb8846ba61fbe470b821a83034c24d88bb8422405e0f65bf60d37
  - path: tasks.md
    sha256: b11f63d2b48b43c1d728d8252f683ab96f41cdce201f0e48cc50459ec94c1a1f
inputs:
  - openspec/changes/attack-lens-conventions/
  - openspec/schemas/symphysis/schema.yaml
  - openspec/config.yaml
  - openspec/schemas/symphysis/templates/
  - openspec/schemas/symphysis/steps.md
  - openspec/specs/
  - attack/skills/symphysis-attack/SKILL.md
  - attack/skills/symphysis-attack/sources/TRANSLATION-NOTES.md
  - attack/attack-table.md
  - attack/attack_table.py
  - viewer/playground-template.html
  - settings/symphysis_config.py
  - installer/lib/install.js
  - decisions/journal_render.py
  - step-help/step_help.py
  - docs/repo-contract.md
  - docs/GUIDE.md
  - tests/test_skills.py
  - tests/test_repo_contract.py
  - tests/test_guide.py
  - tests/fixtures/settings-cases.json
  - viewer/tests/test_viewer_page.py
  - viewer/tests/test_viewer_prompt.py
  - settings/tests/test_settings.py
  - installer/test/install.test.js
  - decisions/tests/test_journal_render.py
  - decisions/tests/test_journal_view_json.py
  - step-help/tests/test_step_help.py
  - openspec/schemas/symphysis/tests/test_schema.py
  - openspec/schemas/symphysis/tests/test_steps_md.py
  - upstream/openspec/src/core/project-config.ts
  - upstream/openspec/src/core/specs-apply.ts
  - ../symphysis-vscode/src/core/core.ts
  - ../symphysis-vscode/src/journal/attack.ts
report: openspec/changes/attack-lens-conventions/briefs/symphysis-attack-2026-11-08-2/report.md
---

# Brief: повтор атаки артефактов изменения attack-lens-conventions после правок по слову человека

Повтор после правок целей по слову человека (`answers/2026-11-08-5.md`). Исполнить шаги 0–6 тела скилла
`symphysis-attack` для вызова `attack-artifacts`: цели — `targets` выше, журнал первым как опора. Шаг 7 — отчёт
по пути `report`. Корень проекта — `X:\symphysis-attack-lens-conventions` (worktree ядра symphysis; команды из корня
проекта).

Файл атаки `attack/artifacts.md` от прохода 2026-11-08 (`status: gaps_found`, 118 строк, brief
`briefs/symphysis-attack-2026-11-08/`) уже лежит на месте; хеши четырёх целей разошлись (`decisions.json`,
`specs/plugin-core-contract/spec.md`, `design.md`, `tasks.md`) — по шагу 1 тела скилла атака артефактов идёт с начала:
таблица пишется заново, прежние строки не переносятся, frontmatter — свежие хеши.

Состав линз (вторая строка `python .symphysis/tools/symphysis_config.py`, прочитана главной нитью): все линзы
включены, у файла артефактов — `**Состав:** включены scenario-run, claim-extraction, trace-link, rule-compliance;
выключены —`.

Что изменилось с прошлого прохода (для сверки, не для пропуска строк):

- `specs/plugin-core-contract/spec.md`: MODIFIED «`view-json` отдаёт номер контракта» — родитель теперь несёт два первых
  предложения мастер-текста дословно (с `F-24`); смена адресата `материалы` → `агент` ушла в новое дочернее ADDED
  «Смена адресата поднимает номер контракта до 4» с мастер-текстом этого предложения дословно, номером `F-40`
  и своим сценарием «Договор называет смену адресата». Деление — по слову владельца (факт `F-40` журнала): требование
  длиннее 500 знаков делится, а не ужимается.
- `decisions.json`: запись-факт `F-40` (улика — `answers/2026-11-08-5.md`), две строки `notes[]` с итогами проб краёв
  и запретов нового дочернего, прежняя строка итога атаки.
- `edge-probe.md`: восемь строк нового дочернего.
- `design.md`, Context: абзац «Перенесённые сценарии» — механизмы и тесты шести сценариев MODIFIED «Режим «атака»…»,
  перенесённых из мастера без правки; абзац «Деление по пределу».
- `tasks.md`: задача 4.4 (отмечена) — исторический тест номера 4 держит `Needs:` и правило `Why:`, сценарий
  «Договор называет смену адресата».

Особенности этого запуска:

- Сверка журнала — только исходником с корнями изменения, дословно:
  `python -X utf8 cli/journal.py check --write --roots openspec/changes/attack-lens-conventions/probes/journal-roots.json openspec/changes/attack-lens-conventions/decisions.json`.
  Установленная копия `.symphysis/tools/journal.py` раскрывает `<root>` от `.symphysis/` и даёт ложные «файла нет»
  у улик `vscode/`, `context/`, `upstream/`. Главная нить уже выполнила эту команду: `[ok] улик сверено 104 из 109`,
  пять `[!!]` «цитаты нет дословно» у F-05 (две), F-06, F-13, F-15 — эти цитаты переписало само изменение. Хеш
  `decisions.json` в `targets` — после неё.
- Реализация сделана (задачи групп 1–5, 4.4 и 6.2 отмечены в `tasks.md`): механизмы design читаются по коду в `inputs`.
  Код только читается; тесты, сборку и команды цели не запускать.
- Связи для `trace-link`: `python .symphysis/tools/trace_graph.py build attack-lens-conventions`; счёт главной нити по
  команде тела скилла — `satisfies 32, traces 31, verifies 2, всего 65`; узлов `req:` с `"section": "MODIFIED"` — 3.
- Мастер-спеки для `rule-compliance` — `openspec/specs/<capability>/spec.md` на диске; они ещё не синхронизированы
  с дельтами, это мастер-текст до изменения — с ним и сверять.
- Пути `../symphysis-vscode/…` — плагин (соседний репозиторий): только чтение.
- Отчёт: если среда откажет в записи `report.md` — текст отчёта целиком идёт последним сообщением, главная нить
  сохранит его по пути `report`.

Писать: `openspec/changes/attack-lens-conventions/attack/artifacts.md`, строку итога в `notes[]` журнала
`openspec/changes/attack-lens-conventions/decisions.json`, черновики — в каталог этого brief.

Не делать: `apply`, `decision`, `outcome`, правки `specs/`, `design.md`, `security.md`, `tasks.md`, `consequences.md`,
кода проекта и `symphysis.yaml`; вопросы человеку — только строками отчёта; чтение вне `inputs`.
