# Отчёт водителя: symphysis-research, F-21

(Файл `openspec/changes/trace-numbers-signals/briefs/symphysis-research-2026-11-07/report.md` среда записать отказала — «Subagents should return findings as text, not write report files»; сохрани этот текст по пути `report` дословно.)

## Итог

- жанр: проверка
- находок: 77
- строк «не найдено»: 5
- проба: да

## Файлы

- `openspec/changes/trace-numbers-signals/research/F-21.md`
- `openspec/changes/trace-numbers-signals/research/F-21-probe/` — скрипты и след: `setup.sh`, `setup.txt`, `setup-step-help.sh`, `setup-step-help.txt`, `refparse.py`, `count-refs.py`, `count-refs.txt`, `basecheck.py`, `basecheck-module-structure.txt`, `basecheck-trace-graph.txt`, `layout.py`, `layout-module-structure.txt`, `layout-trace-graph.txt`, `signals.py`, `before-signals-{module-structure,trace-graph,step-help}.txt`, `compare.py`, `before-vs-snapshot-{module-structure,trace-graph}.txt`, `patch-rule-A.py`, `patch-rule-A.diff`, `patch-rule-A.txt`, `run-after.sh`, `after-signals-{module-structure,trace-graph,step-help}.txt`, `after-vs-before-{module-structure,trace-graph,step-help}.txt`, `signals-diff-{module-structure,trace-graph,step-help}.txt`, `check-quotes.py`, `check-quotes.txt` (77 цитат сверены, расхождений 0)
- `openspec/changes/trace-numbers-signals/briefs/symphysis-research-2026-11-07/report.md` — не записан средой, текст здесь.
- Рядом в `research/` лежат `F-24.md` и `F-24-probe/` — след другого запуска, этим водителем не трогались.

Короткий ответ по пунктам brief (подробности и цитаты — в `research/F-21.md`):

1. Мастер `openspec/specs/*/spec.md`, тела 241 требований: ссылок 683, голых 664 (из них 172 с буквой варианта), с именем журнала перед списком 19 — все в `decision-viewer` (9), `project-installer` (5), `artifact-graph` (4), `brainstorm-interview` (1). Требований, где одно число стоит и голым, и с именем журнала, — 4 (`decision-viewer` ×3: F-26 и F-46; `artifact-graph` ×1: `F-26.E` и `F-26.B @step-help`).
2. «Требование без записи»: `module-structure` — 6 (родитель `decision-viewer` «Просмотрщик…» + 3 дочерних, `plugin-core-contract`, `skill-transfer`), `trace-graph` — 0. У четырёх `decision-viewer` совпадение дельты с базой в мастере стоит с буквой и именем чужого журнала (`F-26.B @symphysis-schema`, `F-46.E @calibration-fixes`) — правило A закрывает; у двух — голое против голого (`F-20`, `F-14.A`) — остаются. База снимков равна мастеру на `roots[0].commit` (расхождений 0).
3. Проба: сборка до патча воспроизводит снимки (42 и 212 связей, разницы 0). После патча `module-structure`: +4 связи (`F-26` у родителя, `F-46` у трёх дочерних), −4 сигнала, 2 остались; пропавших связей 0; `trace-graph`: 212 → 212, сигналы без изменений. Ложных связей (по номеру, стоявшему в дельте как чужой) нет: чужие `F-26.B`, `F-17.D`, `F-23.A`, `F-45.E`, `F-46.E`, `F-35` связей не дали, хотя записи с такими номерами в журнале `module-structure` есть; «неизвестного номера» ни до, ни после.
4. `step-help`: снимка нет, MODIFIED с номерами есть (`decision-viewer` с ``журнал `step-help`: F-35`` — своим именем, `decision-journal` с `F-01.B`). Базу заменяет живой мастер на `37841d0^` (дельты влиты коммитом архива `37841d0`): прогнан дополнительно — 76 → 76 связей, один сигнал (`decision-journal`, голое `F-01.B` против голого) остаётся.

## Вопросы человеку

Строки «Вопросы, которые открылись» из `research/F-21.md` (решает второй круг, не водитель):

- Своё имя в своей дельте (``журнал `step-help`: F-35`` в дельте самого `step-help`): проба считала имя, равное имени изменения, своим — так ли читать правило A?
- База снимка хранит только числа; ключ правила A — число, буква, имя. Проба брала ключи из мастера на коммите снимка, у живого изменения после `/opsx:sync` так нельзя: нужна ли смена формата записи базы и что с прежними снимками?
- Буква в ключе: голое `F-26` дельты против голого `F-26.E` мастера при правиле A даст связь (172 голых ссылок с буквой в мастере) — ожидаемо или дыра?
- Имя журнала после списка без двоеточия (``F-12.A; слово владельца, журнал `trace-graph` ``, `decision-journal` ×3) под правило A не попадает — считать ли именованной?
- Голые чужие номера без своей записи (`F-74`, `F-114.A` в дельтах `module-structure`) сегодня прячет только база; без базы — «неизвестный номер». Нужна ли отдельная запись?
- Остаток после правила A: два сигнала `module-structure` (`F-20`, `F-14.A`) — по вопросам записей могут быть верными сигналами; кто это проверяет?
- Следы проб с именем журнала идут через `_TRACE_PAIR` и хеш следа (F-147), не через `known`/`cut` — вне brief, отдельный вопрос.

Путей области, которых нет на диске, — нет.

## Сигналы

- Строки `[!!]` в следе (`before-signals-*.txt`, `after-signals-*.txt`) — предмет пробы: сигналы графа архивных изменений до и после патча, не сигналы о прогоне; все коды выхода сборок и скриптов — 0, строк «validate не запустился» и «дубль id» не было (сигналы брались `graph_signals` без форка).
- Первый запуск `setup.sh` упал (`FileNotFoundError: … journal.schema.json` — модуль `journal_model` читает схему рядом с собой); скрипт поправлен (копируется и схема), перезапущен, `setup.txt` — от второго запуска; след первого падения не сохранён.
- Среда отказала в записи `report.md` по пути `report` («Subagents should return findings as text, not write report files»); текст отчёта — в этом сообщении.
- Критерии «Приёмка» скилла для шагов 4–8 выполнены: файл по шаблону, `question` = F-21, brief дословно (сверено), 77/77 цитат совпали, 5/5 «не найдено» с «искал», раздел «Проба» со следом, `none.md` нет, слов «рекомендую»/«выбрать вариант» нет, `decisions.json` байт в байт прежний (`git diff` пуст), `git status --short` — только `?? …/research/` и `?? …/briefs/`.

## Не сделано

нет
