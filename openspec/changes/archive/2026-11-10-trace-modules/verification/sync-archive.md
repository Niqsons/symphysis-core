# Синхронизация и архивация trace-modules

2026-11-10. По поручению владельца: «Можем приступать к синхронизации и архивации?» Исходная ветка `feat/trace-modules`, коммит реализации `e68646b`.

Перед переносом `openspec list/status --json` подтвердили локальный planning root, 40/40 задач и завершённость обязательных артефактов. Необязательные атаки ранее не вызывались. Пути семи дельт взяты только из `artifactPaths.specs.existingOutputPaths`; правила specs получены одним успешным вызовом instructions specs. Подсказки archive учтены: freeze до sync, якоря после sync, перенос каталога средствами скилла без повторного CLI archive.

Синхронизированы 29 ADDED и 5 MODIFIED требований семи capability: module-discovery, repository-survey, trace-conventions, trace-diagram, trace-graph, trace-signals, trace-snapshot. Первые две master-спеки созданы с Purpose из дельт. У существующих сохранены заголовки, Purpose, незатронутые требования и сценарии. Служебные комментарии проб удалены из перенесённых блоков; самостоятельные следы F-NN сохранены, аннотация symphysis:implements осталась только при требовании «Граф собирается из файлов изменения».

`python -X utf8 anchors/anchor_refs.py trace-modules` переписал 90 ссылок в семи файлах, сохранив унаследованные ссылки по frozen base. [Полный вывод](sync-anchors.txt). Повторный запуск: «Переписывать нечего: голых номеров журнала в блоках изменения нет.» Повторная сборка результата sync+anchor совпала с текущими master-спеками: 7/7 capability, 34/34 блока. [Результат сравнения](sync-comparison-results.json).

`node upstream/openspec/bin/openspec.js validate --specs --json`: **34/34, код 0**. Дополнительный strict: 20/34, код 1; только 32 прежних предупреждения о длине требований в 14 capability. Проверка копии master-спек из исходного HEAD во временном проекте дала 16/32 в strict и 34 предупреждения: sync не добавил предупреждений и устранил два. Новых ошибок нет. [Числа и полный перечень](sync-validation-results.json). Чужие требования ради strict не менялись.

`python3.13 -X utf8 -m pytest trace/tests anchors/tests tests/test_guide.py -q` с xdist: **429 passed, 2 skipped**; оба пропуска — прежние живые тесты заархивированного trace-graph. [Полный вывод](sync-regression.txt). Повторный check сохранённого графа после sync: «сигналов нет». Снимок до sync был свежим, freeze обновил только коммиты корней; graph/report.md не переписывался.

Перенос: `openspec/changes/trace-modules` → `openspec/changes/archive/2026-11-10-trace-modules`. Каталог назначения предварительно отсутствовал, оба абсолютных пути проверены внутри этой рабочей копии; reparse-точек в переносимом дереве нет. После переноса сверяются относительные имена и SHA-256 всех файлов, включая metadata, снимок и отчёт. Master sync, сохранение истории и архив выполнены в своей ветке; merge и push не выполнялись.
