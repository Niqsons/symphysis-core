---
status: passed
target: decisions.json
target_sha256: 3096773bf64974d885d61b97fd1da56fa211c0c53f5bf79f233b3810afb5b87a
---

# Атака журнала решений

Проход 2, 2026-10-30, FORCE stance (`symphysis-attack`), тот же контекст
исполнителя, что и проход 1 (второго контекста в прогоне нет). Цель —
`decisions.json` изменения `symphysis-schema`: 27 записей (22 развилки,
5 фактов), 89 улик, 3 строки `notes[]`; `check --write` — «улик сверено 89
из 89». Хеш цели разошёлся с проходом 1 (`4cf42da4…` → `3096773b…`): атака
с начала, прежние строки не перенесены. Проход 1 (`gaps_found`,
10 предупреждений) — в `docs/dry-run-journal.md`, шаг 4. Измерения — только
чтение; команды названы в опоре.

| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |
| --- | --- | --- | --- | --- | --- | --- |
| «пересмотрено F-26.B (2026-10-30): форк плагина снят, П7 — свой скилл `symphysis-viewer`…» — следствия F-18 согласованы с решением F-26 | F-18, consequences | context-compliance | две решённые записи не противоречат друг другу; пересмотр виден на пересмотренной записи | справка | есть: decisions.json F-26 decision.word «нам стоит сделать свой скилл и шаблон…», F-26 consequences «форк плагина снят (F-18.B пересмотрено)»; `skills/symphysis-viewer/SKILL.md` существует | — |
| рекомендация A с `why` «поле дешёвое — слово и причина…» | F-10, recommendation | research-resolution | у рекомендации есть `why` | справка | есть: decisions.json F-10 recommendation.why непустой | — |
| рекомендация A с `why` «клиент обкатки, человек и весь набор store — на русском…» | F-14, recommendation | research-resolution | у рекомендации есть `why` | справка | есть: decisions.json F-14 recommendation.why непустой | — |
| «шаблон `decisions.json` (F-01.B) и instruction с механиками брейншторма — в П1» | F-04, consequences | claim-extraction | имя артефакта в следствиях существует в схеме | справка | есть: `ls openspec/schemas/symphysis/templates` — `decisions.json`; `schema.yaml` артефакт `decisions` → `generates: decisions.json` | — |
| «шаблоны `attack-decisions.md` и `attack-artifacts.md` с frontmatter: status, хеш…» | F-13, consequences | claim-extraction | имена шаблонов существуют в схеме | справка | есть: `ls openspec/schemas/symphysis/templates` — `attack-decisions.md`, `attack-artifacts.md`; frontmatter `status`, `target_sha256` / `targets[].sha256` | — |
| «этап Э6 (сухой прогон) стоит до обкатки; Э5 — npm-пакет», `delivery: Э6` | F-19, delivery · consequences | claim-extraction | номер этапа совпадает с планом | справка | есть: `docs/plan-implementation.md:94` «**Э5** … П6: npm-пакет форка», `:95` «**Э6** … Сухой прогон» (ячейки таблицы плана) | — |
| «лексика проб закрыта кодом (`PROBE_OUTCOMES`), лексика «вопрос» в коде не закрыта — её закроет скилл, который её пишет» | F-09, consequences | claim-authority | заявленное о коде сходится с кодом | справка | есть: `tools/journal_model.py:42` «PROBE_OUTCOMES = ("Specify", "Dismiss", "Backstop", "Defer")»; `grep -n` по трём словам лексики intake («подтверждён», «не узнать по файлам», «несущественен») в `tools/*.py`, `docs/journal.schema.json`, `skills/*/SKILL.md` — пусто, как и заявлено | — |
| «(коммит `ceae4dc`)» вместо идентификатора леджера | F-25, consequences | claim-extraction | ссылка разрешается в репозитории | справка | есть: `git log --oneline -1 ceae4dc` — «feat(skills): symphysis-attack на слое проверки GSD» | — |
| «(коммит `dd1a7eb`)» вместо идентификатора леджера | F-26, consequences | claim-extraction | ссылка разрешается в репозитории | справка | есть: `git log --oneline` — `dd1a7eb feat(schema): правило «сначала запись» и атака вместо гриля на схеме` | — |
| у всех 22 решённых развилок `reversibility` с `level` из трёх и `why`, называющим контракт или систему (F-10.A) | F-01…F-27, reversibility | context-compliance (ближайшая: инвариант журнала, не design) | у решённой записи оценена обратимость с причиной | справка | есть: decisions.json — `reversibility` непустой у F-01…F-19 (внесено вторым кругом), F-25, F-26, F-27; `why` — имена `journal_model`, `state.ts`, `schema.yaml`, `apply_answers` и т. д.; `check` — ok | — |
| `decision.word` пустое у F-04, F-09, F-13 — выбор зафиксирован буквой и датой 2026-10-29 без слова | F-04 · F-09 · F-13, decision | context-compliance | слово человека, если есть, не противоречит варианту | справка | есть: `docs/journal.schema.json` «"word": {"type": "string"}» — пустая строка допустима; дата решения на месте | — |
| решение D условное («Если будет нерелевантно, то здесь А»); релевантность находки F-01 оценила модель в consequences — делегирование в самом слове | F-17, decision | context-compliance | consequences следуют из решения | справка | есть: decisions.json F-17 decision.word «Стоит учесть информацию из решения F-01. Если будет нерелевантно, то здесь А» | — |
| «пять выпусков OpenSpec за месяц» (unlikely варианта C) | F-03, options | claim-authority | число измеримо и сходится | справка | есть: `git -C upstream/openspec log --tags --simplify-by-decoration --format='%as %d'` — v1.14.0 2026-09-30, v1.14.1 10-05, v1.14.2 10-15, v1.14.3 10-17, v1.15.0 10-24: пять за 25 дней | — |
| «П3 — четыре скилла» | F-06, consequences | claim-authority | число сходится с измерением | справка | есть: `ls skills` — 5 каталогов; пятый `symphysis-viewer` — П7 (F-26), не П3 | — |
| «таблицу восьми категорий дословно, с copyright notice» | F-08, consequences | claim-extraction | таблица и notice существуют | справка | есть: `skills/symphysis-edge-probe/SKILL.md` — таблица из 8 строк (boundary … concurrency); notice — в копии `skills/symphysis-edge-probe/references/edge-probe.md` (`grep -ci copyright` = 1), в самом SKILL.md слова «copyright» нет | — |
| «архитектор» снят и из просмотрщика | F-11, consequences | claim-extraction | удалённого имени в коде нет | справка | есть: `grep -n -i архитектор tools/playground-template.html tools/journal_render.py` — пусто | — |
| «локальный выбор схемы пользователем — конфиг пользователя поверх» | F-16, consequences | claim-extraction | заявленный механизм существует | справка | есть: `upstream/openspec/src/core/artifact-graph/resolver.ts:308` «source: 'project' … 'user' … 'package'» (три источника через вертикальную черту) — пользовательский каталог схем есть; порядок разрешения — project (:335), затем user (:360): выбор пользователя — по имени схемы (`new change --schema`), не поверх одноимённой схемы проекта | — |
| «HTML на диск не пишет»; «два канала возврата … применяет агент» | F-17, consequences | claim-extraction | заявленных механизмов нет / есть по grep | справка | есть: `grep -n showSaveFilePicker tools/playground-template.html` и `grep -n showOpenFilePicker …` — пусто; `tools/journal_apply.py:351` «def apply_answers», `:537` «def apply_md4h» | — |
| «`openspec status` показывает «есть файл, нет вердикта» как не готово» | F-02, consequences | claim-extraction | подсказка существует в форке | справка | есть: `upstream/openspec/src/core/artifact-graph/instruction-loader.ts:523` «exists but has no verdict»; прогон: `status --json` после прохода 1 — `verdict: mismatch`, `proposal` blocked | — |
| «пин версии upstream в форке» | F-03, consequences | claim-extraction | пин существует | справка | есть: `upstream/openspec/UPSTREAM.md:3` «upstream: Fission-AI/OpenSpec @ 6d04a1b5 (1.15.0, 2026-10-24)» | — |
| «`--check` остаётся глаголом пакета» — глагол есть, пишется `check` | F-15, consequences | claim-extraction | команда существует | справка | есть: `installer/bin/symphysis.js:69` «} else if (cmd === "check") {» | — |
| «`references/grill-lenses.md` удалён» | F-25, consequences | claim-extraction | удалённого файла нет | справка | есть: `ls skills/symphysis-attack/references` — без него; `git log --diff-filter=D -- skills/symphysis-attack/references/grill-lenses.md` → `ceae4dc` | — |
| «три режима — решения, проверка, атака»; «правило «сначала запись» — в rules proposal, design, tasks» | F-26, consequences | claim-extraction | заявленное существует | справка | есть: `tools/playground-template.html:113` «режимы: решения · проверка · атака»; `openspec/config.yaml` rules proposal/design/tasks — строка «утверждение о механике, цели или ограничении без записи F-NN — предположение…» | — |
| «ни один скрипт symphysis не судит смысл — check / apply / форк / render_design» | F-27, recommendation | claim-extraction | названные функции существуют и делают заявленное | справка | есть: `tools/journal_apply.py:89` «def check_evidence», `:351` «def apply_answers»; `tools/journal_render.py:371` «def render_design»; `instruction-loader.ts:526` «readFrontmatter(outputPath)?.[verdict.frontmatter]» | — |
| улики 89 из 89 найдены по `путь:цитата`; intro «27 записей, 89 улик» | F-01…F-27, evidence · intro | research-resolution | у каждой улики `found: true`; числа intro сходятся | справка | есть: `check --write` «улик сверено 89 из 89»; `verdict: сверено` ×88, «сверено через перенос» ×1; записей 27 | — |
| парковка «материалы» с `finding`; исследование есть | F-01, parking | research-resolution | парковка «материалы» закрыта находкой при `research/<F-NN>.md` | справка | есть: `research/F-01.md` (14 находок, 2 отрицания с «искал»); parking.finding непустой | — |
| шесть антиподов объявлены, ни у одного обе стороны не решены | F-02 · F-03 · F-04 · F-13 · F-15, antipodes | context-compliance | антиподы не решены оба | справка | есть: F-02=B/F-03=C; F-03=C/F-15=C (F-03.A не выбран); F-04=A/F-05=C; F-13=B/F-02=B (F-13.A не выбран) | — |
| пять фактов с уликами, спор человека отвечен | F-20 · F-21 · F-22 · F-23 · F-24, evidence · dispute | research-resolution | у факта есть улика; спор получил ответ | справка | есть: по две улики у F-20, F-21, F-23, F-24, одна у F-22 (все `found: true`); `dispute` с ответом после «—» или отсылкой («Отвечено в F-08.») | — |
| чисто | F-01, остальные поля (question · options · evidence · recommendation · decision · consequences) | coverage | — | справка | есть | — |
| чисто | F-02, остальные поля | coverage | — | справка | есть | — |
| чисто | F-03, остальные поля | coverage | — | справка | есть | — |
| чисто | F-04, остальные поля | coverage | — | справка | есть | — |
| чисто | F-05, все поля | coverage | — | справка | есть | — |
| чисто | F-06, остальные поля | coverage | — | справка | есть | — |
| чисто | F-07, все поля | coverage | — | справка | есть | — |
| чисто | F-08, остальные поля | coverage | — | справка | есть | — |
| чисто | F-09, остальные поля | coverage | — | справка | есть | — |
| чисто | F-10, остальные поля | coverage | — | справка | есть | — |
| чисто | F-11, остальные поля | coverage | — | справка | есть | — |
| чисто | F-12, все поля | coverage | — | справка | есть | — |
| чисто | F-13, остальные поля | coverage | — | справка | есть | — |
| чисто | F-14, остальные поля | coverage | — | справка | есть | — |
| чисто | F-15, остальные поля | coverage | — | справка | есть | — |
| чисто | F-16, остальные поля | coverage | — | справка | есть | — |
| чисто | F-17, остальные поля | coverage | — | справка | есть | — |
| чисто | F-18, остальные поля | coverage | — | справка | есть | — |
| чисто | F-19, остальные поля | coverage | — | справка | есть | — |
| чисто | F-20, остальные поля | coverage | — | справка | есть | — |
| чисто | F-21, остальные поля | coverage | — | справка | есть | — |
| чисто | F-22, остальные поля | coverage | — | справка | есть | — |
| чисто | F-23, остальные поля | coverage | — | справка | есть | — |
| чисто | F-24, остальные поля | coverage | — | справка | есть | — |
| чисто | F-25, остальные поля | coverage | — | справка | есть | — |
| чисто | F-26, остальные поля | coverage | — | справка | есть | — |
| чисто | F-27, все поля | coverage | — | справка | есть | — |

Счёт: строк 54 — блокеров 0, предупреждений 0, справок 54, «по спеке
не выводится» 0. Вердикт `passed`. Открытое в журнале: новый круг
брейншторма не начат — нужен человек (строка `notes[]`); два вопроса
из `research/F-01.md` (версия формата md4h, детерминизм рендера) записями
не стали — их поднимут пробы `specs`.

Вердикт: `status: passed` ставится, только когда в таблице нет ни одной строки с тяжестью `блокер` или `предупреждение`; строки `справка` не блокируют.
