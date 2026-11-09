# Зависимость IDE-плагинов от обнаружения symphysis

Сверка исходников 2026-11-09; только чтение. Проверены рабочие копии VS Code (`main`, HEAD `3838163`), OpenCode (`master`, `33b8f91`), GIGA IDE (`main`, `a483d62`). Код плагинов, установки и настройки не менялись; IDE/модели и межрепозиторные тесты в этой сверке не запускались.

| Плагин | Текущий lookup | Текущий вызов |
| --- | --- | --- |
| VS Code | `src/core/project.ts:26–39`: `.symphysis/tools` → `tools` → явный абсолютный toolsPath; без local и настройки — `no-tools` | `src/activation/extension.ts:32–39` собирает CoreEnv, `src/core/core.ts:17,36` вызывает найденный journal.py через Python |
| OpenCode | `src/core/project.ts:26–39`: тот же поиск local/manual toolsPath | `src/gui/host.ts:76–77` вызывает findTools; `src/core/core.ts` использует прямой Python path; watcher host ориентирован на проектные tools |
| GIGA IDE | `src/main/kotlin/symphysis/giga/Core.kt:44–58`: local tools либо абсолютный toolsPath, иначе `no-tools` | CoreEnv содержит python/tools/root; операции Core исполняют journal.py; `Settings.kt` пока предлагает python/toolsPath |

Из этих веток следует: при global-only store без проектного journal.py и без ручной настройки текущий lookup не обнаружит user runtime автоматически. Это вывод по коду, не результат наблюдённой IDE-сессии. Возможность задать внешний toolsPath решает прежний ручной lookup, но не вводит новые resolver/preflight/lease гарантии.

В design до этой сверки были описаны общий resolver, необходимость обновить все три host и вызов через dispatcher, но не было явно раскрыто первое звено — обнаружение bootstrap самой IDE. Добавлены launcher/handshake, обработка IDE PATH и явных путей, перечень зависимых consumer-изменений и матрица приёмки. Это конкретизация принятого F-10 и дельты plugin-core-contract; новых решений владельца и результатов приёмки она не создаёт.

Зависимость на плагины подтверждена как работа по интеграции, а не как готовая функциональность. Глобальный CLI/skills-флоу может работать без IDE-плагина; заявленная global-поддержка каждой IDE требует её обновлённой установленной сборки и фактической проверки цепочки discovery → resolve → view/help/apply/rebuild. Порты ведутся отдельными сессиями, их готовность не выводится из статуса файлов change ядра.
