# Отчёт водителя: атака артефактов `attack-stale-scope`, 2026-11-07

Brief: `openspec/changes/attack-stale-scope/briefs/symphysis-attack-2026-11-07/brief.md`. Хеши всех девяти целей совпали с brief до начала шагов; проход первый (файла атаки не было); состав линз — из brief: все три включены. Файл `report.md` средой не записан (отказ Write: «Subagents should return findings as text»); текст ниже — для сохранения главной нитью по пути `report` дословно, как `.md` с CRLF.

## Итог

- Вердикт: `status: gaps_found`.
- Счёт: строк 235, блокеров 9, предупреждений 1, справок 225, «по спеке не выводится» 0. По линзам: scenario-run 40 (39 сценариев четырёх дельт, у «Готовый шаг атаки» вторая строка — показ на странице), claim-extraction 97, trace-link 98 (satisfies 52, traces 34, verifies 12 — равно счёту по выводу `build`).
- Покрытие: все 39 сценариев в строках scenario-run; строк «не пройдено» нет.
- Блокеры (9):
  1. claim-extraction, design.md:56 — улика F-16 «Если хеши разошлись (у `attack-artifacts` — и хеш журнала) — атака MUST идти с начала,» в `attack/skills/symphysis-attack/SKILL.md` не найдена (`found: false`): правило заменено этим изменением (задача 5.1), улика описывает прежний текст.
  2. claim-extraction, design.md:135 — та же улика у выбранного варианта F-21 (`found: false`).
  3. claim-extraction, tasks.md:15 (задача 2.2) — «утверждение … рядом с проверкой `attack_table.py`» в `installer/test/install.test.js`: такой проверки в файле нет (grep -c `attack_table` = 0); утверждение об `attack_scope.py` в файле есть (:783-788).
  4. trace-link, task:1.5 → «Два читателя» (tasks.md:9): `test_scope_lines_carry_no_cell_text` судит содержимое строк `scope_lines`, читателей не сравнивает — другое поведение; сценарий закрывает задача 4.2.
  5. trace-link, req «Хеши целей обесценивают вердикт после правки» → F-31 (specs/artifact-attack/spec.md:18): место связи — комментарий «прежний проход symphysis-schema: F-31 открыт, F-32 открыт», номера чужого журнала; на F-31 этого журнала требование не опирается.
  6. trace-link, та же связь → F-32 (specs/artifact-attack/spec.md:18): то же.
  7. trace-link, branch `cli/journal_cli.py:134` → «Файла атаки нет» (consequences.md:34): `_scope_report` отсекает отсутствующий файл по `is_file()` (cli/journal_cli.py:111-112) до вызова `_read_attack`; ветка «файла нет» из `check` недостижима, допущение описи (consequences.md:33) неверно.
  8. trace-link, branch `state.ts:195` → «Атака не вызвана» (consequences.md:54): ветка даёт `verdict: missing` (по описи), сценарий — ответ `status` без ключа `verdict`; живой `openspec status --json` у `attack-decisions` без файла ключа `verdict` не несёт; допущение описи («справка отдаёт `verdict: missing`») расходится с THEN сценария.
  9. trace-link, branch `state.ts:131` → «Вердикт устарел после proposal» (consequences.md:78): сценарий нечитаемого `tasks.md` не задаёт и ветку не задевает; опись называет его сценарием, а не «ближайшим сценарием».
- Предупреждение (1): scenario-run «specs/step-help/spec.md, Справка не выдаёт наличие файла за сделанную работу / Готовый шаг атаки — показ на странице» — THEN «показаны вердикт `stale` и строки состава», design относит показ к Non-Goals (design.md:85, F-41); тяжесть `предупреждение (решено человеком в F-41)`, закрыть — `вопрос человеку`.
- Решения атаки, которые стоит знать: строки «есть» у веток `attack_table.py:106` и `:121` → «Файл атаки не разбирается» приняты по общему THEN `<причина>` (сценарий — семейство отказов разбора, задача 3.2 перечисляет все четыре); у сценариев MODIFIED-требования step-help «Пустой файл шага», «Формулировка текущего шага» механизм — прежний код (`file_note`, `_current_text`), design этого изменения его не меняет; связи req → F-33, F-34 (парковки ИБ) — «есть» как отсылка к канону security.md (исключение скилла для парковки ИБ); строки по 18 веткам описи — «есть» с действительными номерами строк кода (в описи номера сдвинуты правками изменения, `check` цитаты находит).

## Файлы

- `openspec/changes/attack-stale-scope/attack/artifacts.md` — файл атаки (CRLF): frontmatter `status: gaps_found`, девять целей; хеш журнала после `notes[]` и `check --write` — `d69709f2c4f7bb52658d0cf622dcdca531fb9599e5205b63f9a0251e366c45d7`; прочие хеши равны brief. Разбор `view-json --attack` без отказа, 235 строк.
- `openspec/changes/attack-stale-scope/decisions.json` (LF) — строка `notes[]`: `{"date": "2026-11-07", "text": "атака артефактов: строк 235, блокеров 9, предупреждений 1, справок 225, не выводится 0 — gaps_found"}`; затем `check --write --roots …` код 0 (поля `line/found/verdict` улик). Повторный `check` без `--write` строки `[..] атака артефактов` не даёт, хеш стабилен.
- Каталог запуска `openspec/changes/attack-stale-scope/briefs/symphysis-attack-2026-11-07/`: `graph-build.json` (вывод `trace_graph.py build`), `instructions.json` (шаблон `attack-artifacts`), `rows-claim.md`, `rows-trace.md` (порции строк, дописанные в файл атаки), `view-check-*.json` (проверки разбора). `report.md` — не записан, см. «Не сделано».

## Вопросы человеку

1. Строка-предупреждение «Готовый шаг атаки — показ на странице» (F-41): THEN сценария требует показа вердикта и состава на странице шага, design оставляет показ панели плагина и шаблона «позже». Оставить сценарий как есть (показ — вне изменения) или сузить THEN до полей вывода `step_help.py`?
2. Улики F-16 и F-21 в design.md (блокеры 1–2): дрейф из-за правки самого изменения (задача 5.1 заменила цитируемое правило). Оставить как есть с пометкой в журнале или заменить цитату на текущую строку SKILL.md:135 «Если у `attack-decisions` разошёлся хеш журнала — повтор MUST идти по составу, не с начала.»?
3. Комментарий specs/artifact-attack/spec.md:18 «прежний проход symphysis-schema: F-31 открыт, F-32 открыт» (блокеры 5–6) даёт графу связи на F-31/F-32 этого журнала по совпадению номеров. Убрать номера чужого журнала из комментария или считать связи законными?
4. Опись consequences.md:31-33 (блокер 7: `check` до `_read_attack` не доходит) и :51-53 (блокер 8: `verdict: missing` против ответа без ключа `verdict`): править допущения описи или принять расхождение как есть?
5. Задача 2.2 (блокер 3): в `installer/test/install.test.js` проверки `attack_table.py` нет. Поправить формулировку задачи или считать место «рядом с проверкой attack_table.py» несущественным?
6. Ветка `state.ts:131` (блокер 9) и ветки «нет таблицы», «битая строка» (`attack_table.py:106`, `:121`, приняты «есть»): считать ли сценарий «Файл атаки не разбирается» семейством для всех отказов разбора, а «ближайший сценарий» описи — достаточной связью? Если нет — две строки «есть» пересмотреть новым brief.

## Сигналы

- `[!!] F-16: attack/skills/symphysis-attack/SKILL.md «Если хеши разошлись (у `attack-artifacts` — и хеш журнала) — атака MUST идти с начала,» — цитаты нет дословно`
- `[!!] F-21: attack/skills/symphysis-attack/SKILL.md «Если хеши разошлись (у `attack-artifacts` — и хеш журнала) — атака MUST идти с начала,» — цитаты нет дословно`
- `[..] атака артефактов: decisions.json: журнал изменён, записей сейчас 42` — строка `check --write` в момент, когда frontmatter файла атаки ещё нёс прежний хеш журнала; после записи свежего хеша повторный `check` строки не даёт.
- `openspec status`: у `attack-artifacts` — `verdict: mismatch`, `nextSteps`: «Artifact "attack-artifacts" has verdict status=gaps_found but passed is required — run its instruction again».
- критерий не выполнен: `Опора — не пересказ: у «есть» — путь:строка «цитата»` — у семи строк claim-extraction по веткам `upstream/openspec/src/core/artifact-graph/state.ts` (consequences.md:51–75) и у шести строк trace-link `verifies` на те же ветки опора по стороне кода — результат сверки `journal.py check` (две проверки описи, без `[!!]`), не цитата из прочитанного файла: файл вне `inputs` brief, чтение вне `inputs` запрещено.
- критерий не выполнен: `Состав линз: вторая строка symphysis_config.py прочитана в начале` — скрипт не звался: состав взят из текста brief, как велит `.symphysis/docs/driver.md`; все три линзы включены, строка `**Состав:**` в файле, `symphysis.yaml` не тронут.
- Разделов «не пройдено» нет.
- Существование имён вне `inputs` (тесты `tests/`, `installer/test/`, журналы архивов) сверялось только `test -f` и `grep -c`, без чтения содержимого; команды цели, тесты и сборка не запускались.

## Не сделано

- `report.md` по пути `report` не записан: среда субагента отказала в записи файла отчёта («Subagents should return findings as text, not write report files»); текст отчёта — это сообщение целиком, главная нить сохраняет его по пути `openspec/changes/attack-stale-scope/briefs/symphysis-attack-2026-11-07/report.md` дословно (CRLF).
