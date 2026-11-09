# F-27 · Отчёт водителя

## Итог

жанр: устройство
находок: 24
строк «не найдено»: 3
проба: да

## Файлы

- `openspec/changes/trace-modules/research/F-27.md`
- `openspec/changes/trace-modules/research/F-27-probe/run_probe.py`
- `openspec/changes/trace-modules/research/F-27-probe/results.txt`
- `openspec/changes/trace-modules/research/F-27-probe/write_report.py`

## Вопросы человеку

- Фактические потребители и списки поставки плагинов: `X:/symphysis-vscode/test/core-files.mjs`, соответствующие файлы GIGA/OpenCode — вне inputs.
- Стенды модульных тестов: `decisions/tests/test_journal_check.py`, `viewer/tests/test_viewer_page.py`, `settings/tests/test_settings.py`, `step-help/tests/test_step_help.py` — вне inputs, указатели не проверены.
- Полная проводка dogfood: `cli/journal_cli.py`, `viewer/playground-template.html` — вне inputs.
- Какие данные и идентичность сохранять при dirty README, перемещении и пропаже внешнего клона — открытая проектная развилка после пробы, здесь не решена.
- Отсутствующих inputs нет.

## Сигналы

Проба закончилась кодом 0. Ожидаемые сигналы искусственно испорченного снимка дословно в обезличенном следе:

- `new_kind_format2: {"capability_kinds": ["cap", "req", "scn"], "check": ["[!!] <TEMP>\\project\\openspec\\changes\\demo\\graph\\req-graph.json: узел поправлен: в файле лишний узел module:demo", "[!!] <TEMP>\\project\\openspec\\changes\\demo\\graph\\req-graph.json: узел поправлен: в `edges` файла лишнее или поправленное: req:demo/Requirement -implements-> module:demo"], "full_diagram": "KeyError: 'module'", "requirement_kinds": ["req", "scn"], "shape": []}`
- `format1_current_check: ["[!!] <TEMP>\\project\\openspec\\changes\\demo\\graph\\req-graph.json: форма не та: формат 1, а скрипт читает 2"]`

Критериев шагов 4–8, не выполненных в пределах brief, не выявлено. Чужие файлы, журнал и продуктовый код не правились. Файл отчёта в briefs разрешён самим brief.

## Не сделано

Не запускались install, prepare, sync-payload, сборка форка, общий pytest или настоящий OpenSpec validate. Проба подменяет только validate_findings в памяти; это не полная интеграционная проверка freeze с форком. Реальные архивы не переписывались. Полный CLI/DOM dogfood и соседние плагины не проверены. Проектные решения, новый формат/синтаксис объявлений и связи реализации в JSON не созданы; журнал не менялся, коммитов нет.
