---
skill: symphysis-attack
artifact: attack-artifacts
change: attack-lens-conventions
targets:
  - path: decisions.json
    sha256: ad6e1e2e428c6ca54344a738b74e2d14a4137ce4933b6e144a45cc37685be5d7
  - path: specs/artifact-attack/spec.md
    sha256: a0cdcd7162ae658ec4a2dbd30b8af9a8071ed3165943df56bf76d7816c21457a
  - path: specs/decision-viewer/spec.md
    sha256: bb6c431f21ee4b4192065add2f6ef1b6d3e3d9ed7890402ca37d3f945b9ce99a
  - path: specs/plugin-core-contract/spec.md
    sha256: 9b4a19d8f9fa23bb9cdc2890db537061a3e9440498285c31d34d6f65a0470b7b
  - path: consequences.md
    sha256: 1f10527cc0e7e6a1f16d56ce09a8b43559be0dc22c48629899eb8f09d864937c
  - path: design.md
    sha256: c6e290e1a911740b923ee21a5c7746a25ba0ba46b313a654eeeaeb08896e4f67
  - path: security.md
    sha256: c8444a77e81bb8846ba61fbe470b821a83034c24d88bb8422405e0f65bf60d37
  - path: tasks.md
    sha256: 300839ed6aa1ae3dac71150b80750a075164153e9a2902778f560ac636d18712
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
report: openspec/changes/attack-lens-conventions/briefs/symphysis-attack-2026-11-08/report.md
---

# Brief: атака артефактов изменения attack-lens-conventions — первый проход, пробный проход линзы `rule-compliance`

Исполнить шаги 0–6 тела скилла `symphysis-attack` для вызова `attack-artifacts`: цели — `targets` выше, журнал
первым как опора. Шаг 7 — отчёт по пути `report`. Корень проекта — `X:\symphysis-attack-lens-conventions` (worktree
ядра symphysis; команды из корня проекта). Файла атаки ещё нет — атака первая, таблица пишется с нуля.

Это изменение само вводит линзу `rule-compliance` (задача 6.1 `tasks.md`): реализация сделана и выложена
в установленные копии этого worktree — тело скилла в контексте водителя уже с разделом `#### rule-compliance`.
Пробный проход — её первая работа на живом изменении, с тремя требованиями MODIFIED, из которых одно ужато
до предела и два разделены на родителя и дочерние. Линзу проходить по телу скилла полностью; человек будет читать
её строки о MODIFIED.

Состав линз (вторая строка `python .symphysis/tools/symphysis_config.py`, прочитана главной нитью): все линзы
включены, у файла артефактов — `**Состав:** включены scenario-run, claim-extraction, trace-link, rule-compliance;
выключены —`.

Особенности этого запуска:

- Сверка журнала — только исходником с корнями изменения, дословно:
  `python -X utf8 cli/journal.py check --write --roots openspec/changes/attack-lens-conventions/probes/journal-roots.json openspec/changes/attack-lens-conventions/decisions.json`.
  Установленная копия `.symphysis/tools/journal.py` раскрывает `<root>` от `.symphysis/` и даёт ложные «файла нет»
  у улик `vscode/`, `context/`, `upstream/`. Главная нить уже выполнила эту команду: `[ok] улик сверено 103 из 108`,
  пять `[!!]` «цитаты нет дословно» у F-05 (две), F-06, F-13, F-15 — эти цитаты переписало само изменение
  (списки линз, `CONTRACT = 4` → 5, «шесть» → «семь», строка «Не репортится»). Хеш `decisions.json` в `targets` —
  после неё; повторный `check --write` с теми же корнями хеш не меняет.
- Реализация сделана (задачи групп 1–5 и 6.2 отмечены в `tasks.md`): механизмы design читаются по коду
  в `inputs`. Код только читается; тесты, сборку и команды цели не запускать.
- Связи для `trace-link`: `python .symphysis/tools/trace_graph.py build attack-lens-conventions`; счёт главной нити
  по команде тела скилла — `satisfies 31, traces 30, verifies 2, всего 63`; узлов `req:` с `"section": "MODIFIED"` — 3.
- Мастер-спеки для `rule-compliance` — `openspec/specs/<capability>/spec.md` на диске (`artifact-attack`,
  `decision-viewer`, `plugin-core-contract`): они ещё не синхронизированы с дельтами этого изменения, это мастер-текст
  до изменения — с ним и сверять.
- Пути `../symphysis-vscode/…` — плагин (соседний репозиторий), на него ссылаются опись и журнал: только чтение.
- Отчёт: если среда откажет в записи `report.md` — текст отчёта целиком идёт последним сообщением, главная нить
  сохранит его по пути `report`.

Писать: `openspec/changes/attack-lens-conventions/attack/artifacts.md`, строку итога в `notes[]` журнала
`openspec/changes/attack-lens-conventions/decisions.json`, черновики — в каталог этого brief.

Не делать: `apply`, `decision`, `outcome`, правки `specs/`, `design.md`, `security.md`, `tasks.md`, `consequences.md`,
кода проекта и `symphysis.yaml`; вопросы человеку — только строками отчёта; чтение вне `inputs`.
