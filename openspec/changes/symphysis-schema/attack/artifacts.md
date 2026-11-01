---
status: gaps_found
targets:
  - path: decisions.json
    sha256: cf569791a6af418ab2de1188cf93780bdbcbc04293fb5921399284952ad88776
  - path: specs/artifact-attack/spec.md
    sha256: 89534541be903eba519845e979bbb8a5557f5ab9e5d4c9b3cc05cc6349d84143
  - path: specs/artifact-graph/spec.md
    sha256: 65a15ae49910ee295d96c6f832a3c610f3943c535c2ec988eaf9ab82eff1b1e7
  - path: specs/brainstorm-interview/spec.md
    sha256: a1012209f92ca857c250b3b8e6f6cfe98c7da468517a5f789bc918e2e54ede95
  - path: specs/decision-journal/spec.md
    sha256: 246cddb2b44dbd67c12bd2ae93a523a3a4a71f06112ee8b9af450e65c69ad653
  - path: specs/decision-viewer/spec.md
    sha256: c22ea0d2a0c90e80a3c7311ec5fc20bc24ab84069dd687e5e7b22c18c9840c4c
  - path: specs/project-installer/spec.md
    sha256: 5977378f1f3aaf5633b3db389755b1e61e0d37152ae208f7c0bf29ecdecfd8d0
  - path: specs/requirement-probes/spec.md
    sha256: 46128e568a8c59305ac05018b9e79309313c8026276efd6118974195df1d0212
  - path: specs/skill-transfer/spec.md
    sha256: 0f9ebca6731a74d7e950efc0f933eaeb53897d736d63dd557be9b6b62fb672a5
  - path: specs/verdict-readiness/spec.md
    sha256: 6e96668c868fb3e36d055380608d77e01a6a45f830a1bd0e6d1a3ad0a5f84340
  - path: design.md
    sha256: f5c4f6dd0740aca8d74cf4099224ea1e004cbec692338c8d64b4760b96025815
  - path: security.md
    sha256: ea3a77693fd850547211125a416aa2899e366fc53ff1292549dd6e4be40d2e13
  - path: tasks.md
    sha256: 82244542f26907c5cdf2342b18ae4d97e9f6f4fa74472bce4521dbe89a3c99f4
---

# Атака артефактов

Проход 1, 2026-10-30, FORCE stance (`symphysis-attack`), тот же контекст,
что писал цели (второго контекста в прогоне нет). Цели: `decisions.json`
(опора, 83 записи, `check --write` «145 из 145»), 9 файлов `specs/`
(23 требования, 45 сценариев), `design.md`, `security.md` (7 строк),
`tasks.md` (23 задачи в 10 группах). Измерения — чтение и `grep`, команды
в опоре. Разделы: требование со сценариями; раздел и решение design;
строка security; задача tasks.

| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |
| --- | --- | --- | --- | --- | --- | --- |
| журнал — опора: 83 записи, 145 улик `found: true`, атака журнала `passed` (`attack/decisions.md`, хеш `3096773b…` на момент той атаки; с тех пор добавлены 56 кандидатов и 3 заметки — вердикт журнала устарел по хешу) | decisions.json | claim-extraction | опора артефактов существует и сверена | справка | есть: `check --write` «улик сверено 145 из 145»; `attack/decisions.md` `status: passed` | — |
| «Инъекции через содержимое файлов — применимо … требования, закрывающего пункт, в specs нет» | security.md, строка 1 | task-completeness | «применимо» называет требование specs, которое его закрывает | блокер | нет: `grep -rn -i недоверенн specs/` и `grep -rn -i untrusted specs/` — пусто (сама строка это и говорит) | запись журнала |
| «Пути с `../` — применимо … закрывает только выбор корня, не выход из него» | security.md, строка 2 | task-completeness | «применимо» называет закрывающее требование | блокер | нет: `tools/journal_apply.py:48-53` «return roots[prefix] / path[len(prefix):]»; в `specs/decision-journal/spec.md` требования о выходе за корень нет | запись журнала |
| «Бинарные файлы — применимо … требование … этого не оговаривает — пункт закрыт поведением кода, не спекой» | security.md, строка 5 | task-completeness | «применимо» называет закрывающее требование | блокер | нет: `specs/decision-journal/spec.md` слов «бинарн» не содержит; поведение — `journal_apply.py:78` `errors="replace"` без требования | запись журнала |
| «Инъекции в HTML просмотрщика — применимо … требование … экранирование не называет» | security.md, строка 6 | task-completeness | «применимо» называет закрывающее требование | блокер | нет: `specs/decision-viewer/spec.md` слов «экранир» не содержит; `grep "esc("` в шаблоне — есть, полнота не проверена | запись журнала |
| «Данные наружу (телеметрия форка) — применимо … закрывающего требования нет — кандидат-запрет F-79 (открыт)» | security.md, строка 7 | task-completeness | «применимо» называет закрывающее требование | блокер | нет: F-79 `status: открыт`, `decision: null`; в `specs/project-installer/spec.md` телеметрии нет | запись журнала |
| «Токены — неприменимо — конвейер не хранит … токенов» с командой проверки | security.md, строка 3 | task-completeness | «неприменимо» с причиной и проверкой | справка | есть: `grep -rn -i` по словам token, secret, password в `tools/*.py` и `installer/lib/*.js` — пусто | — |
| «Права — применимо … закрывает требование `project-installer` «`install` ставит схему…»: отличающийся файл пропускается без `--force`» | security.md, строка 4 | task-completeness | «применимо» называет закрывающее требование | справка | есть: `specs/project-installer/spec.md:9` «отличающийся файл SHALL пропускаться с подсказкой `--force`, файл корней SHALL NOT перезаписываться»; `installer/lib/install.js` `place()` | — |
| сценарий «Повторный рендер без правок даёт тот же файл»: THEN «совпадают байт в байт» — помечен автором как предположение; из решений не следует | specs/decision-journal/spec.md, «Журнал — JSON-источник…», сценарий 3 | honest-verifier | сценарий выводится из решённой записи или её улик | предупреждение | по спеке не выводится: F-41 (idempotency) открыт, `decision: null` | вопрос человеку |
| «`decisions.md` и `decisions.html` … SHALL NOT редактироваться руками» — запрет на действие человека, не наблюдаемое поведение системы | specs/decision-journal/spec.md, «Журнал — JSON-источник…», текст требования | verification-derivation | требование описывает наблюдаемое поведение системы | предупреждение | нет: наблюдаемо только следствие (рендер перезаписывает правки) — оно в сценариях не названо | правка артефакта |
| сценарий «Отрицание без шаблонов не принимается»: THEN стоит на предположении «атака артефактов по схеме не целит `research/`» | specs/artifact-graph/spec.md, «Исследование — файл на каждую парковку…», сценарий 2 | honest-verifier | сценарий выводится из решения | предупреждение | по спеке не выводится: `schema.yaml` `attack-artifacts.instruction` называет цели `specs/`, `design.md`, `security.md`, `tasks.md` — `research/` нет; записи журнала о целях атаки нет | вопрос человеку |
| сценарий «Блок context при слиянии»: THEN — наблюдение прогона, помечено «предположение … решить» | specs/project-installer/spec.md, «`install` ставит схему…», сценарий 3 | honest-verifier | сценарий выводится из решения | предупреждение | по спеке не выводится: F-15, F-16 о `context` молчат; `installer/lib/install.js` `mergeConfig` переносит `schema` и `rules` | вопрос человеку |
| сценарий «Скилл без источника GSD»: THEN «`references/` отсутствует … предположение» | specs/skill-transfer/spec.md, «Скилл несёт копию источника…», сценарий 2 | honest-verifier | сценарий выводится из решения | предупреждение | по спеке не выводится: F-14 говорит о копиях GSD/BMAD; F-64 (empty) открыт | вопрос человеку |
| сценарий «Новый выпуск upstream»: THEN «строка таблицы … до любого слияния — предположение … решить: нужен ли гейт» | specs/verdict-readiness/spec.md, «Форк пинует upstream…», сценарий 2 | honest-verifier | сценарий выводится из решения | предупреждение | по спеке не выводится: F-03 decision.word «Сначала будет идти его анализ и решение» — порядок есть, механизм проверки не решён | вопрос человеку |
| 9 capabilities proposal ↔ 9 каталогов `specs/`; 23 требования ↔ задачи «сверить сценарии» групп 2–10 tasks.md; у каждого требования ≥ 1 сценарий | specs/**, требования 1–23 | requirement-coverage | capability без proposal и наоборот нет; требование без сценария и без задачи нет | справка | есть: `ls specs` = 9; `grep -c "^### Requirement:"` = 23; `openspec validate symphysis-schema` «is valid»; `tasks.md` группы 2–10 по capability | — |
| команды и пути в требованиях существуют: `render-md`, `render-html --attack`, `check --write/--strict`, `apply --date`, `schema validate/which`, `.claude/skills/openspec-continue-change/SKILL.md`, `symphysis install/check` | specs/**, тексты требований | claim-extraction | названное существует | справка | есть: `journal.py --help` (подкоманды), `openspec --help` ветки, прогон шаги 1–4 (файл скилла continue — 143 строки) | — |
| чисто | specs/decision-journal/spec.md, «Улика сверяется скриптом…» | coverage | — | справка | есть | — |
| чисто | specs/decision-journal/spec.md, «Решение появляется только словом…» | coverage | — | справка | есть | — |
| чисто | specs/decision-journal/spec.md, «Обратимость, адресат парковки и исход…» | coverage | — | справка | есть | — |
| чисто | specs/artifact-graph/spec.md, «Граф схемы начинается журналом…» | coverage | — | справка | есть | — |
| чисто | specs/verdict-readiness/spec.md, «Вердикт-артефакт готов только со status: passed» | coverage | — | справка | есть | — |
| чисто | specs/verdict-readiness/spec.md, «continue при расхождении вердикта…» | coverage | — | справка | есть | — |
| чисто | specs/brainstorm-interview/spec.md, «Вопрос, ответ на который есть в файлах…» | coverage | — | справка | есть | — |
| чисто | specs/brainstorm-interview/spec.md, «Круг кончается счётом…» | coverage | — | справка | есть | — |
| чисто | specs/requirement-probes/spec.md, «Проба краёв поднимает категории…» | coverage | — | справка | есть | — |
| чисто | specs/requirement-probes/spec.md, «Проба запретов отсеивает гигиену…» | coverage | — | справка | есть | — |
| чисто | specs/artifact-attack/spec.md, «Строка атаки валидна…» | coverage | — | справка | есть | — |
| чисто | specs/artifact-attack/spec.md, «Хеши целей обесценивают вердикт…» | coverage | — | справка | есть | — |
| чисто | specs/artifact-attack/spec.md, «Покрытие поимённо…» | coverage | — | справка | есть | — |
| чисто | specs/decision-viewer/spec.md, «Просмотрщик — один HTML…» | coverage | — | справка | есть | — |
| чисто | specs/decision-viewer/spec.md, «Все варианты и рекомендация…» | coverage | — | справка | есть | — |
| чисто | specs/decision-viewer/spec.md, «Режим «атака» группирует…» | coverage | — | справка | есть | — |
| чисто | specs/skill-transfer/spec.md, «Классификатор краёв и движок запретов…» | coverage | — | справка | есть | — |
| чисто | specs/project-installer/spec.md, «check называет расхождения…» | coverage | — | справка | есть | — |
| Goals: «каждое решение дизайна ниже стоит на записи журнала со словом человека и обратимостью» — у F-04, F-09, F-13 слово пустое | design.md, Goals / Non-Goals | context-compliance | утверждение design не противоречит журналу | предупреждение | нет: decisions.json F-04, F-09, F-13 `decision.word: ""` | правка артефакта |
| Decisions: «F-18 … Выбрано: B. Форк плагина playground» показано как действующее решение рядом с F-26 «Свой скилл … Playground — образец, не точка расширения»; пересмотр виден только в строке обратимости | design.md, Decisions, F-18 | context-compliance | design не несёт двух несовместимых решений как действующих | предупреждение (по линзе блокер; снижено: пересмотр записан в F-18 reversibility и F-26) | нет: decisions.json F-26 decision.word «…Playground будет как источник вдохновения, а не точка расширения»; F-18 `status: решён`, `decision.option: B` | вопрос человеку |
| Open Questions: «F-01 → материалы: …» — парковка с `finding` и `research/F-01.md` показана открытой | design.md, Open Questions | context-compliance | Open Question не решён | предупреждение (по линзе блокер; снижено: рендер показывает все парковки, ответ в `finding`) | нет: decisions.json F-01 parking.finding непустой; `research/F-01.md` существует | вопрос человеку |
| Risks / Trade-offs: 46 строк «[Risk] <цитата улики> (F-NN, отвергнут X: путь:строка) → Mitigation: решение Y» — «риск» — цитата улики отвергнутого варианта («rules:», «Specify it», «Single HTML file»), не формулировка риска | design.md, Risks / Trade-offs | context-compliance (ближайшая: линзы для формулировки риска нет) | строка риска называет, что может пойти не так | предупреждение | нет: `tools/journal_render.py` `render_design` — Risks собирается из `evidence.quote` отвергнутых вариантов; поля «риск» в журнале нет | вопрос человеку |
| Context: F-80…F-83 «[канон] …: канон ИБ» перечислены как факты с уликой-заголовком требования | design.md, Context | context-compliance | факт Context — утверждение о состоянии системы | справка | есть: записи `kind: факт`, `status: припаркован` существуют; утверждают лишь применимость канона — шум, не ложь | — |
| Decisions F-01…F-17, F-19, F-25…F-27: «Выбрано» совпадает с `decision.option`, слово дословно, обратимость с причиной, отвергнутые с «маловероятно» | design.md, Decisions (21 решение) | context-compliance | решение design = decision журнала | справка | есть: рендер `render-design` из `decisions.json` (хеш в targets); выборочно сверены F-02, F-25, F-27 | — |
| Migration Plan: шаги 1–4 и откат; имена команд и файлов существуют | design.md, Migration Plan | key-links | у плана выкладки есть «до» и «после» | справка | есть: шаг 1 прогона (команды выполнены); `openspec config set workflows …` — `config --help` | — |
| пути и имена в design: `state.ts`, `frontmatter.ts`, `instruction-loader.ts`, `journal_model`, `apply_answers`, `parse_md4h`, `cmd_check`, `schema which`, `tools/playground-template.html` | design.md, Context · Decisions (reversibility) | claim-extraction | названное существует | справка | есть: `ls upstream/openspec/src/core/artifact-graph/` — state.ts, frontmatter.ts; `grep -n "def apply_answers" tools/journal_apply.py`, `grep -n "def parse_md4h" tools/journal_apply.py`; `grep -n "def cmd_check" tools/journal_cli.py` | — |
| один источник данных (`decisions.json`), три рендера; два парсера слова человека (`apply_answers`, `parse_md4h`) пишут одно поле, исходный промпт сохраняется в `answers/<дата>.md` | design.md, Decisions F-01 · F-17 | data-contracts | одни данные не преобразуются в двух местах несовместимо; исходное сохраняется | справка | есть: `skills/symphysis-viewer/SKILL.md` §Порядок 4 «сохрани как есть в answers/»; `tools/journal_apply.py:351`, `:537` | — |
| задачи 2.2, 3.2, 5.2, 6.2, 7.2, 7.3, 9.2 стоят на открытых записях (F-41, F-36, F-40, F-77, F-30, F-31, F-78) — помечены «допущение … открыт», ждут группу 1 | tasks.md, 2.2 · 3.2 · 5.2 · 6.2 · 7.2 · 7.3 · 9.2 | dependency-correctness | задача не стоит на записи `открыт` | предупреждение (по линзе блокер; снижено: допущения названы в строке, группа 1 первая по порядку) | нет: decisions.json F-30, F-31, F-36, F-40, F-41, F-77, F-78 `decision: null` | вопрос человеку |
| задача 1.1 «показать decisions.html, получить промпт по F-28…F-79, внести apply, зеркала outcome, сценарии Specify, повторить attack/artifacts.md» — 52 кандидата и повтор атаки в одной задаче | tasks.md, 1.1 | scope-sanity | задача укладывается в один сеанс | предупреждение | нет: 52 записи × слово человека + повтор атаки (проход 1 атаки артефактов — 60 строк) | правка артефакта |
| у каждой из 23 задач — файлы, действие и проверка в строке («проверка: …») | tasks.md, 1.1–10.3 | task-completeness | задача называет проверку завершения | справка | есть: `grep -c "проверка:" tasks.md` = 23 = `grep -c "^- \[ \]"` | — |
| проверки — наблюдаемые результаты (pytest зелёный, grep даёт строку, запись F-NN существует), не «сделано» | tasks.md, 1.1–10.3 | verification-derivation | проверка — наблюдаемый результат | справка | есть: строки «проверка: `py -3.13 -X utf8 -m pytest …` зелёный», «`grep -n …` даёт строку» | — |
| «до решения», «по решению человека» в 2.3, 7.2, 10.2 — не сокращение объёма против `decision`: записи-основания открыты, полного объёма никто не требовал | tasks.md, 2.3 · 7.2 · 10.2 | scope-reduction | «пока/позже» нет там, где decision требует полного | справка | есть: F-80, F-30 без `decision`; предположение `context` без записи | — |
| пути в задачах существуют: `tests/test_journal_*.py`, `tests/test_schema.py`, `tests/test_skills.py`, `installer/test`, `upstream/openspec/test/core/artifact-graph`, `test/commands/status-verdict.test.ts` | tasks.md, 2.1–10.1 | claim-extraction | названное существует | справка | есть: `ls tests installer/test upstream/openspec/test/core/artifact-graph upstream/openspec/test/commands` | — |
| чисто | tasks.md, группа 1: 1.2 | coverage | — | справка | есть | — |
| чисто | tasks.md, группа 2: 2.1 · 2.3 | coverage | — | справка | есть | — |
| чисто | tasks.md, группа 3: 3.1 | coverage | — | справка | есть | — |
| чисто | tasks.md, группа 4: 4.1 · 4.2 | coverage | — | справка | есть | — |
| чисто | tasks.md, группа 5: 5.1 | coverage | — | справка | есть | — |
| чисто | tasks.md, группа 6: 6.1 | coverage | — | справка | есть | — |
| чисто | tasks.md, группа 7: 7.1 | coverage | — | справка | есть | — |
| чисто | tasks.md, группа 8: 8.1 · 8.2 | coverage | — | справка | есть | — |
| чисто | tasks.md, группа 9: 9.1 | coverage | — | справка | есть | — |
| чисто | tasks.md, группа 10: 10.1 · 10.2 · 10.3 | coverage | — | справка | есть | — |

Счёт: строк 59 — блокеров 5, предупреждений 12 (из них «по спеке
не выводится» 5), справок 42. Вердикт `gaps_found`. (Строка итога
в `notes[]` журнала записана до таблицы и говорит «строк 60, справок 43» —
счёт руками ошибся на единицу; хеш журнала в `targets` взят после той
строки, поэтому она не правится; расхождение названо здесь.) Пять блокеров
закрываются только записями журнала (канон ИБ → требование — решение
человека); из двенадцати предупреждений без человека закрываются три
(правка артефакта: «не редактируется руками», Goals, задача 1.1) — повторная
атака до `passed` не дойдёт, пока нет слова человека по F-18, F-30, F-31,
F-36, F-40, F-41, F-64, F-77, F-78, F-79 и пяти предположениям specs.

Вердикт: `status: passed` ставится, только когда в таблице нет ни одной строки с тяжестью `блокер` или `предупреждение`; строки `справка` не блокируют.
