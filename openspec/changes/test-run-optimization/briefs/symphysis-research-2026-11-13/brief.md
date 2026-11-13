---
skill: symphysis-research
artifact: research
change: test-run-optimization
question: F-11
inputs:
  - pytest.ini
  - viewer/tests/test_viewer_browser.py
  - tests/fixtures/viewer-browser.mjs
  - tests/conftest.py
  - installer/node_modules/mermaid/dist/mermaid.min.js
  - openspec/changes/test-run-optimization/intent.md
  - backlog/symphysis-backlog.md
report: openspec/changes/test-run-optimization/briefs/symphysis-research-2026-11-13/report.md
---

Запись: Как выполнить исключение для браузерных тестов и учесть сценарий очистки профилей под нагрузкой?
Слово человека: «В research определить одинаковый состав браузерных тестов для сравнения, проверить доступность Chrome, Node и Mermaid, сверить очистку драйверов и профилей. Подготовить сравнение текущих 12 воркеров, последовательного режима и малых лимитов. Любые тяжёлые прогоны запускать последовательно, отдельно учитывать тест с шестью драйверами. Если замер не выполнен, явно указать причину и оставить вывод о числе воркеров открытым.»
Выяснить: какие версии и состав реально запущены; как различаются длительность, проходы, пропуски, падения и таймауты между режимами; прошёл ли сценарий с шестью драйверами и остались ли процессы или профили пробного прогона; насколько устойчив результат при повторении.
Область: pytest.ini, viewer/tests/test_viewer_browser.py, tests/fixtures/viewer-browser.mjs, tests/conftest.py, installer/node_modules/mermaid/dist/mermaid.min.js, openspec/changes/test-run-optimization/intent.md, backlog/symphysis-backlog.md. Псевдоним backlog/ указывает на X:/symphysis/.context/backlog.

Жанр: проверка.
Писать: research/F-11.md, research/F-11-probe/.
Команды запускать из X:/symphysis-test-run-optimization. Рабочая ревизия 3db11dfd. Для пробы используй временный каталог на X:/codex-tmp и отдельный TEMP, TMP, TMPDIR и --basetemp на каждый запуск. Отключи pytest cache provider и запись pyc, чтобы исключить запись в проект. Уже доступны Python 3.13 по пути $env:LOCALAPPDATA/Microsoft/WindowsApps/python3.13.exe, pytest 9.2.0, Node v24.11.1, Chrome 157.0.8103.52 и Mermaid. Обычные тесты проекта продолжают использовать xdist. -n 0 разрешён для браузерной группы в этой сравнительной пробе. Запусти весь viewer/tests/test_viewer_browser.py с -n 0, -n 2 и -n 12 строго последовательно. Сделай по возможности по два измерения на режим в прямом и обратном порядке, без прогонов сторонних наборов. Нагрузка — число логических CPU 12 и доступная память около 27 GiB при предполётной проверке. Сохрани вывод, длительность, коды, состав и факт прохождения сценария очистки. При мониторинге фильтруй Chrome, Node и профили по путям этой пробы. Пользовательские процессы не останавливай. Если режим завис, сохрани след, прекрати только дерево пробного запуска и продолжи сравнение. Кратко сообщай главной нити о завершении каждого прогона. В переносимых артефактах убирай посторонние личные абсолютные пути, сохраняя диагностические строки и достаточную воспроизводимость. Сохрани компактную сводку и команды, подробный вывод при наличии ошибок. Самостоятельно не выбирай вариант или постоянный лимит.
Не делать: decisions.json, specs/, код проекта, вопросы человеку, чтение вне области. Не коммитить.
