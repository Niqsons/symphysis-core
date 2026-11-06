---
status: passed
target: decisions.json
target_sha256: 7fb4849971637b8034b3703e3b97ec8f6a64249aecf362c9a98487ee757d3e0f
---

# Атака журнала решений

Проход 5, 2026-11-05, FORCE stance (`symphysis-attack`). Цель: `decisions.json` изменения `trace-graph`, 79 записей (59 развилок, 20 фактов), 209 улик, `check --write` дал «улик сверено 209 из 209». Строки, снятые словом человека, находками не считаются.

Отступление от правила «атака с начала, прежние строки не переносятся». Между проходами 4 и 5 добавлена запись F-79 и следствия F-51, F-64, F-78: их проход 5 проверил заново вместе со стыками, а остальные строки взял из прохода 4. Проходы 2–4 так же судили только новые записи и их стыки, а по прочим записям опирались на чтение журнала в проходе 1 в этом же контексте.

Атаку вёл тот же контекст, что писал записи F-74–F-79 и новые следствия. Перед первым проходом контекст был сжат, остальной журнал читался заново.

Измерения только чтением: файлы, поиск, разовые счётные скрипты по файлам данных. Цель, код образца, тесты, пробы и `openspec validate` не запускались. Вердикты улик взяты из `check`. Счётные замеры первого прохода взяты повторно: файлы, по которым они сняты, не менялись. Где опора это чтение кода вместо заявленного запуска, так и написано.

| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |
| --- | --- | --- | --- | --- | --- | --- |
| «Архив зовёт тот же проверщик сам», причина F-32: «архив сохраняет свой стоп» | F-07, consequences · F-32, consequences | claim-authority | «уже есть» сходится с замером на обычном пути архивации | справка | есть: следствия обеих записей теперь говорят, что проверщик зовёт только `openspec archive`, а `/opsx:archive` переносит каталог сам: `.claude/skills/openspec-archive-change/SKILL.md:183` основного клона `mv "<changeRoot>" "<planningHome.changesDir>/archive/<target-name>"` | — |
| «Снимок есть при любом запуске», причина: «B даёт настоящую гарантию» | F-75, consequences | claim-authority | польза варианта сходится с кодом | справка | есть: поправка в следствиях F-75: правка `openspec archive` на `/opsx:archive` не действует, полной гарантии нет ни у одного варианта (`.claude/skills/openspec-archive-change/SKILL.md:183` основного клона) | — |
| «в MODIFIED только новые сценарии» и второй отчёт «перед архивацией» | F-64, options.A · F-48, consequences · F-78, decision | context-compliance | сигнал отвечает одинаково до и после `/opsx:sync` | справка | есть: F-78.A ставит заморозку в конец `/opsx:apply`, до синхронизации; пересборка в `/opsx:archive` бывает редко, и следствие F-78 говорит, что сигнал тогда молчит | — |
| «На эталонах это 23, 10 и 12 строк» | F-64, options.A | claim-authority | число описывает отчёт по выбранным правилам | предупреждение | по спеке не выводится: расхождение: цель 23, 10, 12; улика: `openspec/changes/trace-graph/research/F-57-probe/prototype.py:204` считает Specify по совпадению слов (F-45.B, не выбран), а на эталонах исходов Specify 0, 11, 42 и комментария F-45.A нет (F-69: «сигнал сработал бы на каждом Specify»); пометки `служебная` там тоже нет. Измерить можно только готовым скриптом. Слово владельца в следствиях F-64: «оно как бы есть, пока не попробуем не узнаем» | вопрос человеку |
| Строки первого прохода, снятые словом человека | F-25 · F-26 · F-27 · F-28 · F-38 · F-39 · F-42 · F-47 · F-55 · F-56 · F-64 · F-66 · F-72 | context-compliance | решённое человеком с причиной не считается находкой | справка | есть: `openspec/changes/trace-graph/answers/2026-11-05-5.md`, заметка `notes[]` с этими словами и следствия F-38, F-47, F-56, F-66, F-72 | — |
| «Цена пропуска невысока: снимок можно собрать позже из архивного каталога.» | F-49, consequences · F-74, decision | context-compliance | вычисление после архивации входит в названные исключения | справка | есть: следствие F-49 снимает этот довод, слово F-74 «сборка и заморозка графа перед архивацией происходят автоматически» | — |
| `/opsx:archive` и есть обычный путь архивации | F-75, recommendation | claim-authority | «уже есть» сходится с замером | справка | есть: `openspec/schemas/symphysis/steps.md:430`, `docs/GUIDE.md:513` | — |
| Слова F-74 и F-76 внесены дословно | F-74 · F-76, decision | context-compliance | `decision.word` не расходится с вариантом | справка | есть: `openspec/changes/trace-graph/answers/2026-11-05-6.md`, перенос из `answers/2026-11-05-5.md` | — |
| «Отдельного скилла составления требований нет: это инструкция шага `specs`» | F-76, consequences | claim-extraction | названное существует | справка | есть: `openspec/schemas/symphysis/schema.yaml:74`; в `skills/` такого скилла нет | — |
| «mermaid 12.2.0 её знает, на 11.17.2 проба не запускалась» | F-77, consequences | claim-authority | «уже есть» сходится с замером | справка | есть: поиск `derives` в `vscode/node_modules/mermaid/dist/chunks/mermaid.core/requirementDiagram-EQYSW5RA.mjs` даёт 2 совпадения, версия 12.2.0. Про 11.17.2 запись говорит честно | — |
| 188 требований из 188 с номером; задач 251, сценарий у 131, запись у 118, требование у 3, ни с чем 75 | F-06 · F-42 · F-43 · F-44, evidence | claim-authority | число сходится с замером | справка | есть: разовый счёт по `openspec/changes/archive/*/`: 188 и 188; 251, 131, 118, 3, 75 | — |
| Замер при атаке: 540 номеров на 188 требований, медиана 2, максимум 10, 20 длиннее 500 | F-44, consequences · F-76, question | claim-authority | число сходится с замером | справка | есть: разовый счёт по `openspec/changes/archive/*/specs/`; предел `upstream/openspec/src/core/validation/constants.ts:11` | — |
| «27 из 590 в мастер-спеках» | F-42, options.B | claim-authority | число сходится с замером | справка | есть: разовый счёт по `openspec/specs/*/spec.md`: 623 сценария, 590 разных имён, 27 повторяются | — |
| Исходов Specify 159, у 72 связь только в комментарии, у 10 из 77 сценария нет | F-45, options.B · options.C | claim-authority | число сходится с замером | справка | есть: разовый счёт по журналам архива: 159, в тексте 82, только в комментарии 72, нигде 5, то есть 77. Число 10 не перемерено, опора `docs/analysis/requirements-traceability-graph-of-symphysis.md:250` | — |
| Сценарий по исходу Specify пишут три скилла | F-45, consequences | claim-authority | число сходится с замером | справка | есть: `skills/symphysis-edge-probe/SKILL.md:347`, `skills/symphysis-prohibition-probe/SKILL.md:227`, `skills/symphysis-consequences/SKILL.md:454` | — |
| «Проверено запуском: `validate --strict` проходит, при архивации комментарий доходит до мастер-спеки.» | F-45, options.A | claim-authority | заявленный запуск подтверждается | справка | есть чтением: `upstream/openspec/src/core/parsers/requirement-blocks.ts:6` «raw: string; // full block including headerLine and following content». Следа запуска в каталоге изменения нет, повтор не запускался | — |
| F-65 и F-129 это номера журнала `implementation-consequences` | F-46, consequences | claim-extraction | номер в тексте называет чужой журнал | справка | есть: следствие записи; `docs/analysis/requirements-traceability-graph-of-symphysis.md:251` | — |
| «а в схеме symphysis этой команды нет» | F-07, question | claim-authority | число сходится с замером | справка | есть: поиск `validate` по `openspec/schemas/symphysis/schema.yaml` даёт 0 | — |
| «проверено запуском на копии»: подсказка доходит полем `operationGuidance` | F-08, question | claim-authority | заявленный запуск подтверждается | справка | есть чтением: `upstream/openspec/src/commands/workflow/instructions.ts:1008` «if (inputs.operationGuidance && inputs.operationGuidance.length > 0) {», скилл читает её: `.claude/skills/openspec-archive-change/SKILL.md:50` основного клона | — |
| Правило перевода путей есть только в пакете контекста | F-09, question | claim-authority | «уже есть» сходится с замером | справка | есть: поиск «переводят», «переводится», «переводить» по `docs/GUIDE.md` и `openspec/schemas/symphysis/steps.md` дал 0 | — |
| «до реализации совпадают 66 улик из 66, перед архивацией 45» | F-10, question · F-51, recommendation | claim-authority | число сходится с замером | справка | есть: `openspec/changes/trace-graph/research/F-57-probe/summary.txt:3` «[ok] улик сверено 45 из 66»; коммит `940caf7` в клоне есть, `git cat-file -t` даёт commit. 66 из 66 на этом коммите не перемерено, опора `docs/analysis/requirements-traceability-graph-of-symphysis.md:361` | — |
| «у узлов устойчивые id» | F-15, question | claim-extraction | у утверждения факта есть опора | справка | есть: `docs/analysis/requirements-traceability-graph-of-symphysis.md:622` «да: группа в SVG называется», среди улик записи этой строки нет | — |
| Размеры эталонов | F-16, evidence | claim-authority | число сходится с замером | справка | есть: `openspec/changes/trace-graph/research/F-57-probe/summary.txt:3`, `:4`, `:5`; улик 66, 160, 329 посчитаны по журналам клонов | — |
| «строка в `FILES` у `sync-payload.js` и в фильтре имён инсталлятора» | F-39, options.A | claim-extraction | названное существует | справка | есть: `installer/scripts/sync-payload.js:10` «const FILES = [», `installer/lib/install.js:128` фильтр с именем `step_help` | — |
| Живой граф не лежит на диске при слове «надо создавать его граф и постепенно наполнять» | F-41, options.A · F-18, decision | context-compliance | решение не расходится со словом человека | справка | есть: `docs/analysis/requirements-traceability-graph-of-symphysis.md:42` «Форму уточняет Т9: создавать файл не нужно, граф вычисляется.»; `graph/` уточняет F-74 | — |
| «Механизм уже есть: те же четыре исхода, просмотрщик и `apply`» | F-47, recommendation | claim-authority | «уже есть» сходится с замером | справка | есть: `tools/journal_model.py:416`, `tools/journal_render.py:486`, `vscode/src/shared/check.ts:8` читают `outcome.kind` без префикса вопроса | — |
| «Заморозка не гейт, как и просит Т3» | F-49, recommendation | context-compliance | ссылка на решение подтверждается | справка | есть: `docs/analysis/requirements-traceability-graph-of-symphysis.md:366` «Это совпадает с Т3 и не требует правки форка.» Сам Т3 говорит о проверке связей; что совет можно пропустить, названо в F-49.A и принято в F-62 и F-75 | — |
| «правка разрешения путей в `journal_apply.py`» | F-50, options.A | claim-authority | место правки одно, как сказано | справка | есть: `_resolve` определена в `tools/journal_apply.py:110`, `tools/journal_sites.py:10` её импортирует, ссылки плагина идут через `file_links` там же | — |
| Слово «вид пишется в id (SEC-3)» и выбранная форма | F-54, decision · F-67, options.B · F-73, options.A | context-compliance | `decision.word` не расходится с вариантом или отступление названо | справка | есть: F-67.B «у `element` признак вида лежит не в поле, а в имени»; F-73.A «небольшое отступление от формы `SEC-3` из слова к F-54» | — |
| Места правки: `src/shared/attack.ts`, `EXPECTED_CONTRACT`, `test/e2e/scenario.ts`, `tools/playground-template.html`, `CONTRACT` | F-55, consequences | claim-extraction | названное существует | справка | есть: все названы верно, `vscode/src/host/core.ts:9`, `vscode/test/e2e/scenario.ts:300`, `tools/journal_render.py:28`. Список не полон, на шаг `tasks`: линзы называют ещё `openspec/schemas/symphysis/templates/attack-artifacts.md:21`, `openspec/schemas/symphysis/steps.md:337`, `skills/symphysis-viewer/SKILL.md:138`, спека `decision-viewer`, `tests/test_schema.py:371`, `tests/test_skills.py:303`, а номер контракта `vscode/test/unit/core.test.ts:155` | — |
| Вид «улика разошлась» включает строки сверки описи | F-57, consequences | claim-authority | число сходится с замером | справка | есть: следствие записи; `openspec/changes/trace-graph/research/F-57-probe/signals-recommendation-why.txt` несёт 6 таких строк, `openspec/changes/trace-graph/research/F-57-probe/signals-step-help.txt` 4 | — |
| `docs/repo-contract.md:3` действует для двух проектов; бэклог вне git | F-60, parking | claim-extraction | названное существует | справка | есть: `docs/repo-contract.md:3` «Действует для двух проектов»; `git check-ignore .context/backlog.md` в плагине подтверждает | — |
| Сценарий «Цели нет» пишет `coverage` для артефактов; шаблон настроек в инсталляторе | F-61, consequences · options.D | claim-extraction | названное существует | справка | есть: `openspec/specs/artifact-attack/spec.md:76`, `installer/lib/install.js:23` | — |
| «F-119 изменения `implementation-consequences`» | F-63, recommendation | claim-extraction | `F-NN` существует | справка | есть: запись F-119 в журнале этого архива, решение A | — |
| «На эталонах их 4 на три изменения» | F-65, options.A | claim-authority | число сходится с замером | справка | есть: `openspec/changes/trace-graph/research/F-57-probe/summary.txt:15`: 1+1+2 | — |
| «Хук стоит только в репозитории symphysis» | F-73, consequences | claim-authority | «уже есть» сходится с замером | справка | есть: `gate_hook` не найден в `installer/lib`, `installer/scripts`, `installer/package.json` | — |
| Антиподов 5 пар, выбранных пар нет | F-31 · F-32 · F-39 · F-49 · F-64 · F-75 · F-78, antipodes | context-compliance | оба антипода не выбраны вместе | справка | есть: выбраны F-31.A, F-32.D, F-39.A, F-49.A, F-64.A, F-75.A, F-78.A; антиподы F-64.B, F-39.C, F-49.C, F-75.B, F-78.D не выбраны | — |
| Отступления от постановки: выбранных нет | все записи, options.deviation | context-compliance | выбранный вариант, противоречащий факту `постановка`, несёт `deviation` | справка | есть: поле стоит только у F-56.C, он не выбран; выбранные варианты F-01–F-05 не противоречат | — |
| Решённые записи не на `открыт`, обратимость у всех решений | все записи, status · reversibility | context-compliance | статус и обратимость соответствуют решению | справка | есть: разовый счёт: 59 развилок `решён`, открытых 0, обратимость у 59 из 59 | — |
| Пути и номера в текстах записей | все записи, тексты | claim-extraction | названное существует | справка | есть: не найденные пути это будущие файлы или обороты: `trace_graph.py`, `security.md`, `tasks.md`, `consequences.md`, `symphysis.yaml`, `schema.yaml`, `репозиторий/модуль`, `tools/journal`, `openspec/changes/<имя>/…`, `openspec/changes/<change>/graph`, `req:capability/имя`, `scn:capability/требование/имя`, `graph/` | — |
| Строки кругов и строки о развилках из атаки | notes | claim-authority | число сходится с замером | справка | есть: круг 1 и круг 2 как в первом проходе; F-74–F-77 дают 4 решения и антипод F-75.B; F-78 даёт 1 решение и антипод F-78.D; F-79 даёт 1 решение без антипода | — |
| Заморозка в конце `/opsx:apply` (F-78.A) и «Снимок называет только коммиты заморозки» (F-51.A) | F-78, consequences · F-51, consequences · F-79, decision | context-compliance | коммит в снимке содержит то, что снято | справка | есть: F-79.A: `/opsx:archive` обновляет в снимке только коммиты корней. Обе записи ссылаются на это решение | — |
| Подсказка принимается только у `apply` и `archive`, синхронизация файлов изменения не трогает | F-78, options.A | claim-authority | «уже есть» сходится с замером | справка | есть: `upstream/openspec/src/core/project-config.ts:8`, `openspec/schemas/symphysis/schema.yaml:158`, `openspec/schemas/symphysis/steps.md:392`; поиск `operationGuidance` в `upstream/openspec/src/core/templates/workflows/sync-specs.ts` даёт 0 | — |
| Слово F-78 внесено дословно | F-78, decision | context-compliance | `decision.word` не расходится с вариантом | справка | есть: `openspec/changes/trace-graph/answers/2026-11-05-8.md` | — |
| «снимок правится после сборки» при «Нет: только через файлы изменения, файл графа производный» | F-79, options.A · F-30, options.A | context-compliance | решение не расходится со словом человека | справка | есть: следствие F-79: коммиты не входят в хеши исходников и берутся не из файлов изменения, запись делает скрипт. Правит не рука, а слово Т14 говорит о правке мимо файлов изменения | — |
| «Имплементация задач не порождает новых артефактов» | F-79, decision | claim-extraction | названное подтверждается схемой | справка | есть: `openspec/schemas/symphysis/schema.yaml:155` шаг `apply` ничего не объявляет в `generates`. Файл `rulings.md` у `step-help` создан рукой вне схемы и графом не читается | — |
| Слово F-79 внесено дословно | F-79, decision | context-compliance | `decision.word` не расходится с вариантом | справка | есть: `openspec/changes/trace-graph/answers/2026-11-05-9.md` | — |
| чисто | F-01, все поля | coverage | — | справка | есть | — |
| чисто | F-02, все поля | coverage | — | справка | есть | — |
| чисто | F-03, все поля | coverage | — | справка | есть | — |
| чисто | F-04, все поля | coverage | — | справка | есть | — |
| чисто | F-05, все поля | coverage | — | справка | есть | — |
| чисто | F-06, остальные поля | coverage | — | справка | есть | — |
| чисто | F-07, остальные поля | coverage | — | справка | есть | — |
| чисто | F-08, остальные поля | coverage | — | справка | есть | — |
| чисто | F-09, остальные поля | coverage | — | справка | есть | — |
| чисто | F-10, остальные поля | coverage | — | справка | есть | — |
| чисто | F-11, все поля | coverage | — | справка | есть | — |
| чисто | F-12, все поля | coverage | — | справка | есть | — |
| чисто | F-13, все поля | coverage | — | справка | есть | — |
| чисто | F-14, все поля | coverage | — | справка | есть | — |
| чисто | F-15, остальные поля | coverage | — | справка | есть | — |
| чисто | F-16, остальные поля | coverage | — | справка | есть | — |
| чисто | F-17, все поля | coverage | — | справка | есть | — |
| чисто | F-18, остальные поля | coverage | — | справка | есть | — |
| чисто | F-19, все поля | coverage | — | справка | есть | — |
| чисто | F-20, все поля | coverage | — | справка | есть | — |
| чисто | F-21, все поля | coverage | — | справка | есть | — |
| чисто | F-22, все поля | coverage | — | справка | есть | — |
| чисто | F-23, все поля | coverage | — | справка | есть | — |
| чисто | F-24, все поля | coverage | — | справка | есть | — |
| чисто | F-25, остальные поля | coverage | — | справка | есть | — |
| чисто | F-26, остальные поля | coverage | — | справка | есть | — |
| чисто | F-27, остальные поля | coverage | — | справка | есть | — |
| чисто | F-28, остальные поля | coverage | — | справка | есть | — |
| чисто | F-29, все поля | coverage | — | справка | есть | — |
| чисто | F-30, остальные поля | coverage | — | справка | есть | — |
| чисто | F-31, остальные поля | coverage | — | справка | есть | — |
| чисто | F-32, остальные поля | coverage | — | справка | есть | — |
| чисто | F-33, все поля | coverage | — | справка | есть | — |
| чисто | F-34, все поля | coverage | — | справка | есть | — |
| чисто | F-35, все поля | coverage | — | справка | есть | — |
| чисто | F-36, все поля | coverage | — | справка | есть | — |
| чисто | F-37, все поля | coverage | — | справка | есть | — |
| чисто | F-38, остальные поля | coverage | — | справка | есть | — |
| чисто | F-39, остальные поля | coverage | — | справка | есть | — |
| чисто | F-40, все поля | coverage | — | справка | есть | — |
| чисто | F-41, остальные поля | coverage | — | справка | есть | — |
| чисто | F-42, остальные поля | coverage | — | справка | есть | — |
| чисто | F-43, остальные поля | coverage | — | справка | есть | — |
| чисто | F-44, остальные поля | coverage | — | справка | есть | — |
| чисто | F-45, остальные поля | coverage | — | справка | есть | — |
| чисто | F-46, остальные поля | coverage | — | справка | есть | — |
| чисто | F-47, остальные поля | coverage | — | справка | есть | — |
| чисто | F-48, остальные поля | coverage | — | справка | есть | — |
| чисто | F-49, остальные поля | coverage | — | справка | есть | — |
| чисто | F-50, остальные поля | coverage | — | справка | есть | — |
| чисто | F-51, остальные поля | coverage | — | справка | есть | — |
| чисто | F-52, все поля | coverage | — | справка | есть | — |
| чисто | F-53, все поля | coverage | — | справка | есть | — |
| чисто | F-54, остальные поля | coverage | — | справка | есть | — |
| чисто | F-55, остальные поля | coverage | — | справка | есть | — |
| чисто | F-56, остальные поля | coverage | — | справка | есть | — |
| чисто | F-57, остальные поля | coverage | — | справка | есть | — |
| чисто | F-58, все поля | coverage | — | справка | есть | — |
| чисто | F-59, все поля | coverage | — | справка | есть | — |
| чисто | F-60, остальные поля | coverage | — | справка | есть | — |
| чисто | F-61, остальные поля | coverage | — | справка | есть | — |
| чисто | F-62, остальные поля | coverage | — | справка | есть | — |
| чисто | F-63, остальные поля | coverage | — | справка | есть | — |
| чисто | F-64, остальные поля | coverage | — | справка | есть | — |
| чисто | F-65, остальные поля | coverage | — | справка | есть | — |
| чисто | F-66, остальные поля | coverage | — | справка | есть | — |
| чисто | F-67, остальные поля | coverage | — | справка | есть | — |
| чисто | F-68, все поля | coverage | — | справка | есть | — |
| чисто | F-69, все поля | coverage | — | справка | есть | — |
| чисто | F-70, все поля | coverage | — | справка | есть | — |
| чисто | F-71, все поля | coverage | — | справка | есть | — |
| чисто | F-72, остальные поля | coverage | — | справка | есть | — |
| чисто | F-73, остальные поля | coverage | — | справка | есть | — |
| чисто | F-74, остальные поля | coverage | — | справка | есть | — |
| чисто | F-75, остальные поля | coverage | — | справка | есть | — |
| чисто | F-76, остальные поля | coverage | — | справка | есть | — |
| чисто | F-77, остальные поля | coverage | — | справка | есть | — |
| чисто | F-78, остальные поля | coverage | — | справка | есть | — |
| чисто | F-79, остальные поля | coverage | — | справка | есть | — |
| чисто | title · source · intro | coverage | — | справка | есть | — |

Вердикт: `status: passed` ставится, только когда в таблице нет ни одной строки с тяжестью `блокер`; строки `предупреждение` идут человеку списком и `apply` не держат, строки `справка` не блокируют.
