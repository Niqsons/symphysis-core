# symphysis-attack — где перевод меняет смысл источника

Источник — GSD Core @ v1.20.1 (MIT, Copyright (c) 2026 Open GSD), слой
проверки артефактов: `agents/gsd-plan-checker.md` (установка, классификация
находок, измерения), `agents/gsd-verifier.md` (форма разрыва, статус,
самопроверка), `agents/gsd-doc-verifier.md` (извлечение утверждений),
`gsd-core/references/honest-verifier.md` (воздержание). Выписки с шапкой —
`references/`; строки «FORCE stance» трёх агентов — `references/force-stance.md`.
Нижняя планка — бинарный исход `sdd-review` плагина sdd-superpowers; файл лежит
в кэше плагинов (`~/.claude/plugins/synced/…/skills/sdd-review/SKILL.md`),
в цитатах — `sdd-superpowers/skills/sdd-review/SKILL.md`. Гриль store
(`store/change-intake/references/grill-form.md`) с D4b не источник (F-25,
слово владельца 2026-10-30: «Ведь изначальная задача была "взять openspec как
рамку, и добавить в неё механики gsd-сore"»); что от него осталось — раздел
«store, не GSD». Перевод — не механический, а инструкция агенту на русском
(F-14.A, слово владельца: «указать, где при переводе произошло изменение
смысла инструкции»). Ниже — каждое место, где изменён смысл, а не только
язык. Строки — по файлам источников. Линза `scenario-run` — не из GSD:
измерение SELF; измерения plan-checker, бывшие линзами присутствия, сняты
решением F-07.A — обе строки в конце таблицы.

| Место | В источнике | У нас | Почему смысл изменён |
| --- | --- | --- | --- |
| `gsd-plan-checker.md:9`, `:30` «A set of phase plans has been submitted for pre-execution review … Assume every plan set is flawed until evidence proves otherwise … these plans will not deliver the phase goal» | объект — набор планов фазы, цель — phase goal; проверяющий планов читает PLAN.md | объект `attack-decisions` — журнал `decisions.json`; объект `attack-artifacts` — specs, design, security, tasks; цель — изменение OpenSpec: «решения не доведут изменение до цели» | планов и фаз нет: единица работы — изменение `openspec/changes/<имя>/`, место планов занимает журнал (F-01.B, F-04.A); атака журнала стоит до proposal (`schema.yaml:27-43`), атака артефактов — до `apply` (`:107-123`, `:125-126`); источник механики — слой проверки GSD, не гриль store (F-25) |
| `gsd-doc-verifier.md:29` «Assume every factual claim in the doc is wrong until filesystem evidence proves it correct … the documentation has drifted from the code» | документация сверяется с кодом; улика — файловая система | артефакты сверяются с журналом, между собой и с кодом образца, на который design ставит механизм (`scenario-run`); улика — `путь:строка «цитата»` или решённая запись `F-NN` | кода изменения на шаге атаки ещё нет — есть код образца; «filesystem evidence» — цитата прочитанного файла или запись журнала, решённая человеком |
| `gsd-plan-checker.md:39-42` «BLOCKER … WARNING … INFO — advisory; every consuming gate counts only BLOCKER + WARNING»; `:897-899` «zero issues of any severity. An INFO-only result is NOT `passed`. … Return `## ISSUES FOUND` even when every issue is INFO» | три степени; статус проверяющего при одних INFO — `issues_found`, оркестратор принимает без ревизии и показывает советы | три тяжести — `блокер`, `предупреждение`, `справка`, определения те же; `status: passed` при нуле строк `блокер`, строки `предупреждение` идут человеку списком и `apply` не держат | оркестратора нет: форк читает только `status` (F-02.B, F-13.B). **Отступление от GSD:** гейт источника считает BLOCKER + WARNING, у нас только блокеры. Причина — F-131.A: правило нуля предупреждений заставляло повторять круги, блокеры закрывались за круг, а предупреждения сходились к всё более узким краям. Понижение теперь снимало бы гейт, поэтому оно только по слову человека: причина — решённая запись журнала (F-136.B); правило держится текстом, форк таблицу не читает |
| `gsd-plan-checker.md:43-46`, `:913-938` находка — YAML `plan · dimension · severity · required_property · description · task · fix_hint`; «`fix_hint` is **one example** of a route to that property — never the only admissible route, never an instruction» | структура находки для оркестратора; `dimension` — `snake_case` имя измерения; `fix_hint` — свободный текст | строка таблицы: `dimension` → «Линза» — слуг из закрытого списка своего файла атаки (SKILL.md, шаг 3: журнал — `context-compliance` … `coverage`, артефакты — `scenario-run`, `claim-extraction`; латиница через дефис, от имени измерения GSD), `required_property` → «Инвариант», `description` → «Опора: нет: …», `severity` → «Тяжесть», `plan`/`task` → «Раздел», `fix_hint` → «Чем закрыть» из закрытого списка шаблона | носитель — markdown-таблица артефакта OpenSpec (F-13.B), не YAML; слуг в своей колонке — слово владельца 2026-10-30: «раз атакующих перспектив несколько, то можно сгруппировать по ним их "претензии" к содержимому» — просмотрщик группирует строки по линзе, слуг греппируем и устойчив к переводу; закрытый список закрытий — чтобы «пример пути» не разросся в предписание (F-12.B: «стена вердиктов — наблюдённый отказ») |
| `gsd-plan-checker.md:376`, `:705-720` Context Compliance над CONTEXT.md (locked decisions), Numeric/Factual Claim Authority над числами плана; `:77` «LOCKED — plans MUST implement these exactly. Flag if contradicted.» | вопрос измерения задаётся артефактам GSD; противоречие замкнутому решению — находка всегда | те же вопросы — журналу: locked decisions CONTEXT.md → `decision` журнала и факты `addressee: постановка`; решение против такого факта без пометки «отступление от постановки» — `блокер`, с полем `deviation` у выбранного варианта — `справка`, слово человека не требуется; число записи — измерение командой чтения; таблицы — SKILL.md, шаг 3 | артефакты другие, вопрос измерения тот же; замка нет — видимость без замка (F-08.A, F-55.E; замок GSD, F-08.B, отвергнут человеком); тяжесть «нет» — блокер, иная — только с причиной в скобках той же ячейки (F-54.E), причина — решённая запись журнала (F-136.B) |
| `gsd-verifier.md:603-607` три статуса: `passed`, `human_needed` (gaps пусты, но есть human verification items), `gaps_found` | третий статус — для человека | два статуса: `passed \| gaps_found`; `human_needed` → строки «по спеке не выводится», тяжесть `предупреждение`; они идут человеку вопросом и `status` не держат (F-131.A); `gsd-verifier.md:611` «confirm that status is not `passed` when human verification items exist» не действует | нижняя планка `sdd-review` бинарна: «READY TO PLAN or NEEDS REVISION» (`sdd-superpowers/skills/sdd-review/SKILL.md:34`); форк знает одно значение `verdict.value: passed` (`schema.yaml:31-33`, `:111-113`) — третий статус был бы для него тем же `mismatch` |
| `gsd-verifier.md:616-631` Gap Output: `truth` · `status: failed \| partial` · `reason` · `artifacts[path, issue]` · `missing` | разрыв — YAML frontmatter для `/gsd:plan-phase --gaps` | `truth` → «Утверждение»; `artifacts.path` → «Раздел»; `reason` и `artifacts.issue` → «Опора: нет: на чём держится»; `missing` → «Чем закрыть»; `status: failed \| partial` не перенесён — его место занимает «Тяжесть» | одна таблица на все цели; `partial` — суждение о доле сделанного, тяжесть — о последствии для цели |
| `gsd-verifier.md:26` «until codebase evidence proves it», `:828-839` самопроверка: «read it back through its owner: `gsd_run query verification.status`», «never edit `status` to match it» | проверяющий исполняет код и тесты; статус перечитывается через CLI GSD | цель и код образца не исполняются: исход сценария — чтением кода и рассуждением, существование — грепом (`gsd-doc-verifier.md:77`), живое измерение только чтением; самопроверка — счёт строк по тяжестям, сверка `status` с таблицей, затем чтение frontmatter файла заново; `openspec status --json` показывает `verdict` | атака — чтение: «безопасность и граница F-27: атака — чтение» (F-53.E), проверка правила — ревью транскрипта, не тест; `gsd_run` нет; «never edit `status` to match it» сохранено: статус — из таблицы, не из того, что показал форк |
| `honest-verifier.md:25-29` «Exogenous, not endogenous. The trigger is the *external tag* (`backstop`), never the verifier's self-judgment» | тег `verification: backstop` ставит edge-probe в `must_haves.truths` | повод воздержания — у `scenario-run` край с `outcome.value` Defer, на котором стоит сценарий (зеркало слова человека, F-09.C); у `claim-authority` — число, которого не измерить; механизм, который design не называет, — не повод: «нет», `блокер` (F-32.E) | тег GSD — вывод движка; у symphysis исход пробы — поле записи журнала; для атаки он так же внешний; у края Backstop строки в spec.md нет — сценария для `scenario-run` у него нет |
| `honest-verifier.md:43`, `:47-52` «abstain → ⚠️ `insufficient_spec`, flagged, → `human_needed` — never `passed`»; AFK — флаг `unverified — held-out test recommended` | воздержание — статус `human_needed` с причиной `insufficient_spec`; в автономном режиме — флаг | строка с опорой «по спеке не выводится», тяжесть `предупреждение`, «Чем закрыть» — `вопрос человеку`; `status` она не держит; вопрос — в чат порцией, ответ — через `apply` | статусов два (строка выше); режима AFK нет; «never `passed`» снято вместе с остальным гейтом предупреждений (F-131.A): воздержание остаётся видимым вопросом человеку, но `apply` не держит; правило владельца (`CLAUDE.md`): решения человека вносятся в журнал, не в файл атаки |
| `honest-verifier.md:42`, `:45-46` явная улика для non-inferable — «a wired held-out/property-based test that passes, or a directly-observed behavior» | улика — прогон теста | не перенесено вместе с линзой `honest-verifier` (снята, F-07.A): тест-страховку края Backstop называет задача tasks.md; сценарий на крае Defer — воздержание строки `scenario-run` | тест пишет `tasks` (`symphysis-edge-probe`, зеркало исхода C); прогона у атаки нет — она читает, не исполняет (F-53.E) |
| `gsd-doc-verifier.md:40-41` «WARNING — a claim cannot be verified from the filesystem alone … Every extracted claim must resolve to PASS, FAIL (BLOCKER), or UNVERIFIABLE (WARNING with reason)» | три исхода утверждения | три исхода: «есть», «нет», «по спеке не выводится» с причиной в «Утверждении» и тяжестью `предупреждение` | в Task 19 исходов было два — третий звал бы модель судить проверяемость; с D4b третий исход несёт honest-verifier: повод внешний, суждения модели нет |
| `gsd-doc-verifier.md:58-98` пять категорий — пути с расширениями из списка, команды `npm \| node \| yarn \| pnpm \| npx \| git` против `package.json`, API endpoints по `router.(get\|post…)`, функции, зависимости | регулярные выражения и `package.json` npm-проекта | пути — любое расширение (`.py`, `.yaml`, `.json`); команды — `py`, `node`, `openspec`, `git`: существование файла скрипта или подкоманды в `--help`, без запуска; записи `F-NN` — есть в журнале, как опора — `решён`; числа — живое измерение; имена модулей и функций в design — грепом по коду проекта; endpoints и зависимости — только когда артефакт их называет | проект не npm-пакет; запись журнала — свой вид утверждения; «Do NOT execute any commands. Existence check only.» (`:77`) сохранено |
| `gsd-plan-checker.md:711-716` «Measurement confirms plan → WARNING: RESEARCH.md is stale … Measurement contradicts plan → BLOCKER: plan value is wrong; prescribe the measured value … report the discrepancy WITHOUT prescribing which value is correct» | спор плана с RESEARCH.md; измеренное значение предписывается | сошлось — «есть» с командой измерения в «Опоре»; разошлось — `блокер`, измеренное значение в «Опоре»; измерить нельзя — «расхождение: цель X, улика Y» без назначения правого, опора «по спеке не выводится» | RESEARCH.md stale → у нас улика с `found: false` от `check` — та же роль; измеренное значение — опора строки, а не правка цели: «Чем закрыть» остаётся примером |
| `gsd-plan-checker.md:961-1028` `<structured_returns>`, «## VERIFICATION PASSED», «## ISSUES FOUND» со счётом по тяжестям | вердикт — отчёт оркестратору | `status: passed \| gaps_found` во frontmatter `attack/*.md`; счёт по тяжестям — строка `notes[]` журнала и итог в чат; форк читает `status`, `/opsx:continue` при `mismatch` зовёт атаку снова (`upstream/openspec/UPSTREAM.md:21-22`) | F-13.B («вердикт сам становится артефактом»), F-02.B («статус считает сам CLI форка»); урок чужой связки: «Гейт `ship:pre` читает только поле `status`» (`docs/analysis/gsd-openspec-integration.md:285`) |
| `gsd-plan-checker.md:53` «Revision Gate pattern (bounded quality loop with escalation on cap exhaustion)» | предел числа кругов ревизии, эскалация | предела нет: атака повторяется после каждой правки цели, пока не `passed`; цикл останавливает человек | оркестратора с капом нет — исполнитель идёт по `/opsx:continue`; от стены вердиктов защищает порция вопросов человеку (F-12.B), не счётчик кругов |
| `gsd-doc-verifier.md:58-98` извлекает проверяемые утверждения о файлах | линза ищет существование названного | та же линза `claim-extraction` читает раздел исключений `consequences.md` и строки описи: исключение без довода о конкретном файле и строка ветки без цитаты — строки атаки, `блокер`; новой линзы нет; `consequences.md` входит в `targets[]`, если файл есть | F-91.B, F-90.A, F-128.A: форму описи скрипт не разбирает, судит человек или атака; вопрос тот же — на чём стоит утверждение; своя линза потребовала бы правки закрытых списков и просмотрщика ради двух проверок |
| — (SELF; `docs/analysis/silent-mechanics-review-2026-10-31.md:34`) | у GSD нет измерения «даёт ли механизм исход сценария»: plan-checker проверяет планы, «**DO NOT** check code existence — that's gsd-verifier's job» (`gsd-plan-checker.md:1034`), verifier — исполненный код после фазы | линза `scenario-run` атаки артефактов: по паре «сценарий spec × механизм design» — код образца `путь:строка`, исход по коду, сравнение с THEN; расхождение и механизм не назван — `блокер` (F-32.E); строка на пару (F-33.E); читает, не исполняет (F-53.E) | измерение SELF — калибровка camunda-bid: атака по линзам присутствия дала 84 справки и 0 находок и пропустила сценарий «переменной нет — инцидент» против кода образца `case NULL -> Optional.empty()` (F-03, F-04); решение F-07.A |
| `gsd-plan-checker.md:126`, `:155`, `:189`, `:262`, `:297`, `:346`, `:423`, `:532`, `:597`; `honest-verifier.md:35-43` | Requirement Coverage, Task Completeness, Dependency Correctness, Key Links Planned, Scope Sanity, Verification Derivation, Scope Reduction Detection, Cross-Plan Data Contracts, Research Resolution — измерения проверяющего планов; воздержание Honest Verifier | сняты как линзы: `requirement-coverage`, `task-completeness`, `dependency-correctness`, `key-links`, `scope-sanity`, `verification-derivation`, `scope-reduction`, `data-contracts`, `research-resolution`, `honest-verifier`; детерминируемое ловят `journal.py check` (факт без улики, пустое `why`, парковка «материалы» без `finding`, буква решения вне вариантов — F-12.A) и `openspec validate --strict` (требование без сценария); воздержание осталось правилом строки, не линзой | вопросы о присутствии и происхождении, не о следовании: 84 справки, 0 находок за 13,5 мин (F-03); F-07.A: «Линзы присутствия, которые детерминируемы (покрытие по именам, задача без файлов, парковка без находки), уходят в `journal.py check` и `openspec validate --strict`; остальные снимаются» |

## Соответствие терминов — смысл тот же

| В источнике | У нас |
| --- | --- |
| plan set / doc (GSD) | цель атаки: `decisions.json` или specs, design, security, tasks |
| evidence / filesystem evidence | опора: `путь:строка «цитата»` или решённая запись `F-NN` |
| plan checker / verifier / doc verifier | атака (`symphysis-attack`) |
| dimension (`:376`, `:705`) | линза — слуг в колонке «Линза»: журнал — `context-compliance`, `claim-authority`, `claim-extraction`, `coverage`; артефакты — `scenario-run`, `claim-extraction` |
| `required_property` (`:44`) | «Инвариант» |
| BLOCKER / WARNING / INFO (`:40-42`) | `блокер` / `предупреждение` / `справка` |
| `fix_hint` (`:45-46`) | «Чем закрыть» |
| PASS / FAIL (`gsd-doc-verifier.md:41`) | опора «есть» / «нет» |
| UNVERIFIABLE (`:41`); `insufficient_spec` (`honest-verifier.md:43`) | опора «по спеке не выводится» |
| `human_needed` (`gsd-verifier.md:606`) | строка воздержания, тяжесть `предупреждение`, вопрос человеку |
| `gaps[].truth` / `artifacts` / `missing` (`:616-631`) | «Утверждение» / «Раздел» и «Опора» / «Чем закрыть» |
| VERIFICATION PASSED / `passed` (`gsd-verifier.md:605`) | `status: passed` |
| Dimension N: SKIPPED (`gsd-plan-checker.md:473`, `:569`) | строка «не пройдено» (по разделу, не по линзе): у журнала — линза `coverage`, у артефактов — `scenario-run` с опорой «нет: не пройдено» |

## Перенесено без изменения смысла

Три предложения каждой строки FORCE — допущение, исходная гипотеза, что
назвать (`force-stance.md`); «do not credit effort or intent, only
verifiable coverage» (`gsd-plan-checker.md:9`); определения трёх тяжестей
(`:40-42`); строка без тяжести, инварианта и улики невалидна (`:43-44`);
инвариант формулируется свойством, не правкой (`:933-934`); `fix_hint` —
пример, не предписание (`:45-46`, `:928-931`); «Do NOT flag» как половина
измерения (`:238-243`) и `<skip_rules>` (`gsd-doc-verifier.md:100-110`);
«Do NOT execute any commands. Existence check only.» (`:77`); живое
измерение — только чтение (`gsd-plan-checker.md:720`); самопроверка статуса
после записи (`gsd-verifier.md:828`); воздержание не «есть» и не «нет» и защита
от пере-воздержания (`honest-verifier.md:41-43`); исход «вопрос человеку» —
«never silent, never a hard halt» (`:47`).

## store, не GSD

Из гриля store (`store/change-intake/references/grill-form.md`) после D4b
остаются два правила — у GSD эквивалента нет; оба помечены в SKILL.md
как заимствование.

| Правило | В store | У нас | Почему оставлено |
| --- | --- | --- | --- |
| покрытие поимённо | «Раздел пройден, когда у него есть вопросы или «чисто»» (`grill-form.md:69-70`); «Молчание по разделу читалось бы как «претензий нет», поэтому непройденное называется поимённо» (`:81-82`) | у журнала — у каждого раздела строка: находка, «чисто» (`справка`) или «не пройдено» (`блокер`), линза `coverage`; у артефактов — каждый сценарий спек в строке `scenario-run`, непройденный — «нет: не пройдено» (`блокер`); `passed` при «не пройдено» невозможен | GSD называет пропущенное измерение («Dimension 10: SKIPPED (no CLAUDE.md found)», `gsd-plan-checker.md:569`), но не раздел цели, до которого проверяющий не дошёл; предел выхода модели — наш отказ, не GSD |
| второго такта нет | «модель не перечитывает свою находку и не судит её — судила бы та же модель, что спрашивала» (`grill-form.md:31-32`) | строки после записи не перечитываются и не выбрасываются; самопроверка статуса GSD — счёт, не пересуждение | правила у GSD нет, опасность названа: «does NOT defend against *malicious compliance* (a self-graded review rationalizing away its own findings)» (`honest-verifier.md:93-94`) |

Снято как источник: «не «чего не хватает», а «какое утверждение ничем
не подкреплено»» (`grill-form.md:3-4`) — ту же установку даёт
`gsd-plan-checker.md:9`; пять линз с «чего не репортить»
(`grill-form.md:23-27`, прежний `references/grill-lenses.md`) — линзы
теперь два измерения plan-checker, извлечение утверждений doc-verifier
и своя `scenario-run`, отсев — «Do NOT flag»
(`gsd-plan-checker.md:238`) и `<skip_rules>` (`gsd-doc-verifier.md:100-110`);
«машинные линзы гриль не повторяет» (`grill-form.md:28-29`) — у GSD то же
разделение труда между агентами («DO NOT check
code existence — that's gsd-verifier's job», `gsd-plan-checker.md:1034`),
у нас — между `check`, `openspec validate` и атакой.

## Не перенесено

Из `gsd-plan-checker.md`: Nyquist Compliance (`:519-530`) — блоков
`<automated>` и `<fails_when>` у tasks.md нет, проверка задачи — текст
в её строке; Pattern Compliance (`:637-680`) —
PATTERNS.md нет; Verify Command Format Sanity и Path Resolvability
(`:682-703`) — `<verify>` команд и пробы `{VERIFY_PATHS}` нет, команда
в tasks.md — утверждение claim-extraction; Architectural Tier Compliance
(`:469-517`) — Responsibility Map нет; CLAUDE.md Compliance (`:551-595`) —
правила проекта приходят исполнителю `rules` конфигурации
(`openspec/config.symphysis.yaml`) и CLAUDE.md, атака их не дублирует, как
не дублирует `check`; Undeclared / Temporal Coupling (`:220-260`) —
tasks.md один список по порядку, параллельных планов нет; Review
Incorporation (`:86-93`) — REVIEWS.md нет; smart-zone estimate
(`:305-317`) — бюджета токенов на задачу нет; списки «how plan checkers
go soft» (`:32-37`) — калибровка от мягкости держится установкой
и покрытием поимённо; `<project_context>` (`:55-70`) — скиллы проекта
загружает клиент. Из `gsd-verifier.md`: MVP mode (`:648-660`) — user
story нет; deferred items (`:633-642`) — фаз нет, «отложено» — Defer
журнала, он даёт строку воздержания, а не исключение из счёта; «Group
related gaps by concern» (`:644`) — группировка — пересуждение строк.
Из `honest-verifier.md`: deterministic engine surface (`:58-69`)
и capable-tier requirement (`:71-80`) — код и замеры probe-core.
Из `grill-form.md`: скрипт формы, ключ, `ask/`, дедупликация вопросов,
отзыв approve (`:9-19`, `:84-110`) — чек-листа intake и approve
у symphysis нет.
