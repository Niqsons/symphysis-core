# Проверка осуществимости design

Дата: 2026-11-09. Ядро до правок реализации: `a76432e`; проверенный fork checkout/dist — `cf45eb2a`, `1.16.1+symphysis.5`. Никакая установленная пользовательская поставка не менялась. Содержимое личных конфигов и карт корней не читалось.

`design-probe.mjs` импортировал чистые функции существующего dist закреплённого форка, получил пять выбранных workflow (`new`, `continue`, `apply`, `sync`, `archive`) и проверил identity callback `generateSkillContent`. Путь continue у Claude — `.claude/commands/opsx/continue.md`, у OpenCode — `.opencode/commands/opsx-continue.md`. Проба подтверждает доступность конкретных внутренних функций этого pin, не публичное API пакета и не поддержку `--global`. Результаты — `design-results.json`; native carriers не устанавливались.

Дополнительно без распаковки/исполнения проверен `vendor/fission-ai-openspec-1.16.1+symphysis.5.tgz`: версия package совпадает с installer pin, четыре используемых dist-модуля генерации присутствуют. Это проверка состава артефакта; её не следует путать с исполнением будущего сборочного адаптера из тарбола.

Также проверен base64 round-trip существующих байтов mermaid и отсутствие буквального закрывающего HTML-script тега в закодированном поле. Это обосновывает безопасный транспорт библиотеки как данных; исполнение будущего loader под CSP и доступ к скиллу с другого диска этим не доказаны.

Нативный формат Codex сверён поиском и чтением актуальных [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Build skills](https://learn.chatgpt.com/docs/build-skills), [Environment variables](https://learn.chatgpt.com/docs/config-file/environment-variables). Design сохраняет раздельные native skill/agent roots, TOML-оболочку и наследование полномочий; факт загрузки агентом должен быть подтверждён после реализации отдельным безопасным прогоном.

Выполнен базовый pytest существующих защит:

```powershell
python -X utf8 -m pytest roots/tests/test_roots_evidence.py roots/tests/test_roots_links.py viewer/tests/test_viewer_page.py::test_render_html_escapes_script_close_tag viewer/tests/test_viewer_page.py::test_render_html_embeds_hostile_text_as_data_only viewer/tests/test_viewer_page.py::test_viewer_escapes_journal_and_attack_text_in_every_mode viewer/tests/test_viewer_page.py::test_binary_scheme_is_a_file_without_a_block viewer/tests/test_viewer_page.py::test_page_carries_the_csp_and_no_embedded_plan_scheme --basetemp=X:/codex-tmp/global-design-security-pytest -q
```

Результат: **32 passed in 1.60s**, xdist включён (`-n 12`). Браузерные тесты и native model sessions не запускались; весь набор ядра и инсталлятора не выдаётся за выполненный. Продуктовые модули и tests не изменены.

Независимое чтение security не выявило новой продуктовой развилки. Проверка платформенной схемы нашла два разрыва описания: lifetime lease при раздельном host/direct Python запуске и проверку default-схемы вместо эффективной metadata/argv схемы. Design уточнён: исполнение идёт через dispatcher с lease до завершения child, а guard сравнивает именно эффективную схему. Это исправления механизма под принятые F-10/F-11/F-24, новые решения владельца не записывались.
