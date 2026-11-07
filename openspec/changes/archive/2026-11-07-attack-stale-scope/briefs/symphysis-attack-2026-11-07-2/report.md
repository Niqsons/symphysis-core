# Отчёт водителя атаки: attack-artifacts, изменение attack-stale-scope (brief symphysis-attack-2026-11-07-2)

## Итог

Вердикт: `status: gaps_found`. Строк 183: блокеров 4, предупреждений 0, справок 179, не выводится 0. Проход второй, с начала (хеши четырёх целей разошлись с прошлым вердиктом); состав линз по brief — включены scenario-run, claim-extraction, trace-link; выключены —.

- scenario-run — 44 строки на 39 сценариев четырёх дельт (все 39 покрыты, сверено скриптом по заголовкам `#### Scenario`), исход по коду совпал у всех; пять сценариев получили вторую строку по второму механизму (правило скилла × `attack_scope.py`, `_scope_report` × `attack_table.py`, `_artifact_page` × `state.ts`).
- claim-extraction — 44 строки по specs, design, security, tasks, consequences; 1 блокер.
- trace-link — 95 строк, по одной на каждую связь `build` (satisfies 51, traces 32, verifies 12; счёт командой тела скилла — `51 32 12 95`); 3 блокера, все в `verifies`.

Блокеры:

1. `tasks.md:28`, задача 4.3 (claim-extraction): задача называет `test_project_tree_stays_the_same` («проходит и с файлом атаки при устаревшем вердикте») и `test_no_project_directory_in_output` («проверяет и строки `stale_scope`») — названные тесты существуют (`step-help/tests/test_step_help.py:931`, `:834`), но этих проверок в них нет: они в соседних `test_project_tree_stays_the_same_with_a_stale_verdict` (`:816`) и `test_stale_scope_has_no_project_directory` (`:809`). Чем закрыть — правка артефакта (имена тестов в задаче).
2. `branch:cli/journal_cli.py:162` → сценарий `decision-journal` «Файла атаки нет» (trace-link, consequences.md:31-34): ветка `return None, f"{path}: файла нет"` из `check` недостижима — `_scope_report` (`:111-112`) пропускает отсутствующий файл до `_read_attack`; это пишет и сама опись («ветка из `check` недостижима»). Сценарий ветку не задевает; ветка достижима только из `render-html --attack` (`:243-247`), сценария о нём нет. Чем закрыть — запись журнала (кандидат) или исключение с доводом.
3. `branch:state.ts:195` → сценарий `stale-verdict-scope` «Хеш цели не задан» (trace-link, consequences.md:51-54): `:195` — ветка `missing` «файла нет»; ветку «файл без значения `status`», которую описывает опись, даёт `:202-203`. Сценарий с пустым `target_sha256` при существующем файле и `status` идёт в форке в `malformed` (`:227-233`, `:263` — связь 91, «есть»), ветки `missing` не задевает. У `verdict: missing` в дельте `step-help` сценария нет (`:6` называет значение, `:8-38` не проверяют); ветку `:195` задевает `step-help` «Атака не вызвана», опись его не называет. Чем закрыть — правка артефакта.
4. `branch:state.ts:131` → сценарий `step-help` «Вердикт не прошёл при изменённом журнале» (trace-link, consequences.md:75-78): `hasCheckedTask` зовётся только для `stale` (`:97`, `:81` «Only `stale` has a window: `mismatch` and `missing` always gate») и только у артефакта без зависимых (`:101-114`; у `attack-decisions` зависимый `proposal`). Сценарий с `gaps_found` даёт `mismatch` и до `:131` не доходит; допущение описи «при открытом и закрытом окне одни строки» проверил бы сценарий со `stale` у `attack-artifacts` и нечитаемым `tasks.md` — его в дельтах нет. Чем закрыть — правка артефакта.

Блокеры 2–4 — повторение по существу прошлых спорных строк (`answers/2026-11-07-5.md`: `journal_cli.py:134`, `state.ts:1…` ×2): правка описи переназвала сценарии, но по коду ветки этими сценариями по-прежнему не задеваются. Если человек считает связь «ветка → ближайший сценарий» достаточной, путь — слово человека с понижением тяжести или кандидаты журнала (Dismiss), не правка кода.

Прочее по итогам (не строки): номера строк веток в описи сдвинуты правками изменения (`attack_table.py:28/106/121/42/37` → `:36/114/129/50/45`, `journal_cli.py:60` → `:61`, `step_help.py:76/364/103` → `:78/390/105`); цитаты дословны, `check` сверяет цитату, а не номер — записано строкой-справкой, не находкой. `security.md:3` «Реализации ещё нет» писалось до `tasks`; тесты столбца «Чем проверено» теперь существуют — справка.

## Файлы

- `openspec/changes/attack-stale-scope/attack/artifacts.md` — переписан с начала, CRLF, frontmatter со свежими хешами девяти целей (`decisions.json` — `81a36990fdabed72b366dc4342c773b47c3194f52d7789e87b3544fa56846c5f`, после `notes[]` и `check --write`; остальные восемь равны brief). `view-json --attack` — код 0, отказа у файла атаки нет, невалидных строк 0.
- `openspec/changes/attack-stale-scope/decisions.json` — строка `notes[]` `{date: 2026-11-07, text: «атака артефактов: строк 183, блокеров 4, предупреждений 0, справок 179, не выводится 0 — gaps_found»}`; затем `check --write --roots …` код 0, 89 из 89; `check` после обновления хеша строк `[..] атака артефактов` не печатает. LF, без CR.
- Черновики в каталоге запуска `openspec/changes/attack-stale-scope/briefs/symphysis-attack-2026-11-07-2/`: `build.json` (вывод `trace_graph.py build`), `part-2-claims.md`, `part-3-satisfies.md`, `part-4-traces-verifies.md` (части таблицы, дописывались в файл по ходу), `view.json`.
- `report.md` не записан (по brief): текст отчёта — это сообщение.

## Вопросы человеку

нет

## Сигналы

- `openspec status --change attack-stale-scope --json`: `attack-artifacts` → `verdict: mismatch` (`status: gaps_found`), `nextSteps`: «run its instruction again» — ожидаемо при блокерах.
- Страница не собрана (критерий «Страница собрана» — за главной нитью по телу скилла): `python .symphysis/tools/journal.py render-html openspec/changes/attack-stale-scope/decisions.json --out openspec/changes/attack-stale-scope/symphysis.html --attack openspec/changes/attack-stale-scope/attack/artifacts.md` (файла `attack/decisions.md` нет — второй `--attack` не нужен); у исходника — с `--roots openspec/changes/attack-stale-scope/probes/journal-roots.json`.
- Хеш `.claude/skills/symphysis-attack/SKILL.md` (установленная копия) не равен `attack/skills/symphysis-attack/SKILL.md` (исходник из `inputs`): разница — только комментарии `<!-- src: -->`; цитаты и номера строк в таблице — по исходнику.
- Строк `[!!]` скриптов не было.

## Не сделано

- Существование имён вне `inputs` (`tests/conftest.py`, `tests/test_agents.py`, `installer/test/payload.test.js`, `installer/test/check.test.js`, `decisions/journal_render.py`, `openspec-run/openspec_run.py`, мастер-спеки) проверялось только грепом имени и `ls`, без чтения файлов — помечено в опоре «греп существования».
- Тесты, сборка, `openspec validate`, команды цели (`journal.py check` на архиве `trace-graph`, `step_help.py`) не запускались; исходы — чтением кода и рассуждением (задача 7.2 — по F-08, F-09 и `attack_scope.py:46, :58`).
