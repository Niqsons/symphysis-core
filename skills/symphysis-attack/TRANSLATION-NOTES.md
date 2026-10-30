# symphysis-attack — где перевод меняет смысл источника

Источник — GSD Core @ e2cd587 (MIT, Copyright (c) 2026 Open GSD), слой
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
язык. Строки — по файлам источников.

| Место | В источнике | У нас | Почему смысл изменён |
| --- | --- | --- | --- |
| `gsd-plan-checker.md:9`, `:30` «A set of phase plans has been submitted for pre-execution review … Assume every plan set is flawed until evidence proves otherwise … these plans will not deliver the phase goal» | объект — набор планов фазы, цель — phase goal; проверяющий планов читает PLAN.md | объект `attack-decisions` — журнал `decisions.json`; объект `attack-artifacts` — specs, design, security, tasks; цель — изменение OpenSpec: «решения не доведут изменение до цели» | планов и фаз нет: единица работы — изменение `openspec/changes/<имя>/`, место планов занимает журнал (F-01.B, F-04.A); атака журнала стоит до proposal (`schema.yaml:27-43`), атака артефактов — до `apply` (`:107-123`, `:125-126`); источник механики — слой проверки GSD, не гриль store (F-25) |
| `gsd-doc-verifier.md:29` «Assume every factual claim in the doc is wrong until filesystem evidence proves it correct … the documentation has drifted from the code» | документация сверяется с кодом; улика — файловая система | артефакты сверяются с журналом и между собой; улика — `путь:строка «цитата»` или решённая запись `F-NN` | кода на шаге атаки нет; «filesystem evidence» — цитата прочитанного файла или запись журнала, решённая человеком |
| `gsd-plan-checker.md:39-42` «BLOCKER … WARNING … INFO — advisory; every consuming gate counts only BLOCKER + WARNING»; `:897-899` «zero issues of any severity. An INFO-only result is NOT `passed`. … Return `## ISSUES FOUND` even when every issue is INFO» | три степени; статус проверяющего при одних INFO — `issues_found`, оркестратор принимает без ревизии и показывает советы | три тяжести — `блокер`, `предупреждение`, `справка`, определения те же; при одних `справка` — `status: passed` | оркестратора нет: форк читает только `status` (F-02.B, F-13.B), а справки остаются строками таблицы файла атаки и видны без него; правило гейта `:42` перенесено на уровень вердикта |
| `gsd-plan-checker.md:43-46`, `:913-938` находка — YAML `plan · dimension · severity · required_property · description · task · fix_hint`; «`fix_hint` is **one example** of a route to that property — never the only admissible route, never an instruction» | структура находки для оркестратора; `dimension` — `snake_case` имя измерения; `fix_hint` — свободный текст | строка таблицы: `dimension` → «Линза» — слуг из закрытого списка SKILL.md (`requirement-coverage` … `coverage`, латиница через дефис, от имени измерения GSD), `required_property` → «Инвариант», `description` → «Опора: нет: …», `severity` → «Тяжесть», `plan`/`task` → «Раздел», `fix_hint` → «Чем закрыть» из закрытого списка шаблона | носитель — markdown-таблица артефакта OpenSpec (F-13.B), не YAML; слуг в своей колонке — по слову владельца 2026-10-30 (передано контроллером): просмотрщик получит режим «результаты атаки» с группировкой строк по линзе, слуг должен быть греппируемым и устойчивым к переводу; закрытый список закрытий — чтобы «пример пути» не разросся в предписание (F-12.B: «стена вердиктов — наблюдённый отказ») |
| `gsd-plan-checker.md:126-720` измерения над PLAN.md, ROADMAP.md (requirements), CONTEXT.md (locked decisions), RESEARCH.md (open questions), `must_haves.key_links` | вопрос измерения задаётся артефактам GSD | те же вопросы — своим целям: requirements ROADMAP → `### Requirement:` specs; locked decisions CONTEXT.md → `decision` журнала; open questions RESEARCH.md → парковки `материалы` и `research/<F-NN>.md`; tasks PLAN.md → `- [ ] N.M` tasks.md; key_links → связи design.md; таблица — SKILL.md, шаг 4 | артефакты другие, вопрос измерения тот же; тяжесть по умолчанию — как у источника (`:137`, `:446`, `:549`), иная — с причиной в строке |
| `gsd-verifier.md:603-607` три статуса: `passed`, `human_needed` (gaps пусты, но есть human verification items), `gaps_found` | третий статус — для человека | два статуса: `passed \| gaps_found`; `human_needed` → `gaps_found` со строками «по спеке не выводится» | нижняя планка `sdd-review` бинарна: «READY TO PLAN or NEEDS REVISION» (`sdd-superpowers/skills/sdd-review/SKILL.md:34`); форк знает одно значение `verdict.value: passed` (`schema.yaml:31-33`, `:111-113`) — третий статус был бы для него тем же `mismatch` |
| `gsd-verifier.md:616-631` Gap Output: `truth` · `status: failed \| partial` · `reason` · `artifacts[path, issue]` · `missing` | разрыв — YAML frontmatter для `/gsd:plan-phase --gaps` | `truth` → «Утверждение»; `artifacts.path` → «Раздел»; `reason` и `artifacts.issue` → «Опора: нет: на чём держится»; `missing` → «Чем закрыть»; `status: failed \| partial` не перенесён — его место занимает «Тяжесть» | одна таблица на все цели; `partial` — суждение о доле сделанного, тяжесть — о последствии для цели |
| `gsd-verifier.md:26` «until codebase evidence proves it», `:828-839` самопроверка: «read it back through its owner: `gsd_run query verification.status`», «never edit `status` to match it» | проверяющий исполняет код и тесты; статус перечитывается через CLI GSD | цель не исполняется — существование грепом и чтение (`gsd-doc-verifier.md:77`), живое измерение только чтением; самопроверка — счёт строк по тяжестям, сверка `status` с таблицей, затем чтение frontmatter файла заново; `openspec status --json` показывает `verdict` | кода на шаге нет, `gsd_run` нет; «never edit `status` to match it» сохранено: статус — из таблицы, не из того, что показал форк |
| `honest-verifier.md:25-29` «Exogenous, not endogenous. The trigger is the *external tag* (`backstop`), never the verifier's self-judgment» | тег `verification: backstop` ставит edge-probe в `must_haves.truths` | повод воздержания — запись журнала с `outcome.value` Backstop или Defer у требования (зеркало слова человека, F-09.C) и число или факт, которых не измерить | тег GSD — вывод движка; у symphysis исход пробы — поле записи журнала; для атаки он так же внешний |
| `honest-verifier.md:43`, `:47-52` «abstain → ⚠️ `insufficient_spec`, flagged, → `human_needed` — never `passed`»; AFK — флаг `unverified — held-out test recommended` | воздержание — статус `human_needed` с причиной `insufficient_spec`; в автономном режиме — флаг | строка с опорой «по спеке не выводится», тяжесть `предупреждение`, «Чем закрыть» — `вопрос человеку`; `status: gaps_found`; вопрос — в чат порцией, ответ — через `apply` | статусов два (строка выше); режима AFK нет; правило владельца (`CLAUDE.md`): решения человека вносятся в журнал, не в файл атаки |
| `honest-verifier.md:42`, `:45-46` явная улика для non-inferable — «a wired held-out/property-based test that passes, or a directly-observed behavior» | улика — прогон теста | у `attack-artifacts` кода нет: для края Backstop «есть» — задача tasks.md, называющая тест-страховку, и `consequences` записи; поведение на крае остаётся невыводимым — его не выдают за решённое | тест пишет `tasks` (`symphysis-edge-probe`, зеркало исхода C); атака проверяет намерение, не прогон |
| `gsd-doc-verifier.md:40-41` «WARNING — a claim cannot be verified from the filesystem alone … Every extracted claim must resolve to PASS, FAIL (BLOCKER), or UNVERIFIABLE (WARNING with reason)» | три исхода утверждения | три исхода: «есть», «нет», «по спеке не выводится» с причиной в «Утверждении» и тяжестью `предупреждение` | в Task 19 исходов было два — третий звал бы модель судить проверяемость; с D4b третий исход несёт honest-verifier: повод внешний, суждения модели нет |
| `gsd-doc-verifier.md:58-98` пять категорий — пути с расширениями из списка, команды `npm \| node \| yarn \| pnpm \| npx \| git` против `package.json`, API endpoints по `router.(get\|post…)`, функции, зависимости | регулярные выражения и `package.json` npm-проекта | пути — любое расширение (`.py`, `.yaml`, `.json`); команды — `py`, `node`, `openspec`, `git`: существование файла скрипта или подкоманды в `--help`, без запуска; записи `F-NN` — есть в журнале, как опора — `решён`; числа — живое измерение; имена модулей и функций в design — грепом по коду проекта; endpoints и зависимости — только когда артефакт их называет | проект не npm-пакет; запись журнала — свой вид утверждения; «Do NOT execute any commands. Existence check only.» (`:77`) сохранено |
| `gsd-plan-checker.md:711-716` «Measurement confirms plan → WARNING: RESEARCH.md is stale … Measurement contradicts plan → BLOCKER: plan value is wrong; prescribe the measured value … report the discrepancy WITHOUT prescribing which value is correct» | спор плана с RESEARCH.md; измеренное значение предписывается | сошлось — «есть» с командой измерения в «Опоре»; разошлось — `блокер`, измеренное значение в «Опоре»; измерить нельзя — «расхождение: цель X, улика Y» без назначения правого, опора «по спеке не выводится» | RESEARCH.md stale → у нас улика с `found: false` от `check` — та же роль; измеренное значение — опора строки, а не правка цели: «Чем закрыть» остаётся примером |
| `gsd-plan-checker.md:961-1028` `<structured_returns>`, «## VERIFICATION PASSED», «## ISSUES FOUND» со счётом по тяжестям | вердикт — отчёт оркестратору | `status: passed \| gaps_found` во frontmatter `attack/*.md`; счёт по тяжестям — строка `notes[]` журнала и итог в чат; форк читает `status`, `/opsx:continue` при `mismatch` зовёт атаку снова (`upstream/openspec/UPSTREAM.md:21-22`) | F-13.B («вердикт сам становится артефактом»), F-02.B («статус считает сам CLI форка»); урок чужой связки: «Гейт `ship:pre` читает только поле `status`» (`docs/analysis/gsd-openspec-integration.md:285`) |
| `gsd-plan-checker.md:53` «Revision Gate pattern (bounded quality loop with escalation on cap exhaustion)» | предел числа кругов ревизии, эскалация | предела нет: атака повторяется после каждой правки цели, пока не `passed`; цикл останавливает человек | оркестратора с капом нет — исполнитель идёт по `/opsx:continue`; от стены вердиктов защищает порция вопросов человеку (F-12.B), не счётчик кругов |

## Соответствие терминов — смысл тот же

| В источнике | У нас |
| --- | --- |
| plan set / doc (GSD) | цель атаки: `decisions.json` или specs, design, security, tasks |
| evidence / filesystem evidence | опора: `путь:строка «цитата»` или решённая запись `F-NN` |
| plan checker / verifier / doc verifier | атака (`symphysis-attack`) |
| dimension (`:126-720`) | линза — слуг в колонке «Линза» (`requirement-coverage`, `task-completeness`, `dependency-correctness`, `key-links`, `scope-sanity`, `verification-derivation`, `context-compliance`, `scope-reduction`, `data-contracts`, `research-resolution`, `claim-authority`, `claim-extraction`, `honest-verifier`, `coverage`) |
| `required_property` (`:44`) | «Инвариант» |
| BLOCKER / WARNING / INFO (`:40-42`) | `блокер` / `предупреждение` / `справка` |
| `fix_hint` (`:45-46`) | «Чем закрыть» |
| PASS / FAIL (`gsd-doc-verifier.md:41`) | опора «есть» / «нет» |
| UNVERIFIABLE (`:41`); `insufficient_spec` (`honest-verifier.md:43`) | опора «по спеке не выводится» |
| `human_needed` (`gsd-verifier.md:606`) | `gaps_found` со строкой воздержания |
| `gaps[].truth` / `artifacts` / `missing` (`:616-631`) | «Утверждение» / «Раздел» и «Опора» / «Чем закрыть» |
| VERIFICATION PASSED / `passed` (`gsd-verifier.md:605`) | `status: passed` |
| Dimension N: SKIPPED (`gsd-plan-checker.md:473`, `:569`) | строка «не пройдено» с линзой `coverage` (по разделу, не по линзе) |

## Перенесено без изменения смысла

Три предложения каждой строки FORCE — допущение, исходная гипотеза, что
назвать (`force-stance.md`); «do not credit effort or intent, only
verifiable coverage» (`gsd-plan-checker.md:9`); определения трёх тяжестей
(`:40-42`); строка без тяжести, инварианта и улики невалидна (`:43-44`);
инвариант формулируется свойством, не правкой (`:933-934`); `fix_hint` —
пример, не предписание (`:45-46`, `:928-931`); «Do NOT flag» как половина
измерения (`:238-243`) и `<skip_rules>` (`gsd-doc-verifier.md:100-110`);
«Do NOT execute any commands. Existence check only.» (`:77`); живое
измерение — только чтение (`gsd-plan-checker.md:720`); статус не `passed`
при пунктах для человека (`gsd-verifier.md:611`); самопроверка статуса
после записи (`:828`); воздержание не «есть» и не «нет» и защита
от пере-воздержания (`honest-verifier.md:41-43`); исход «вопрос человеку» —
«never silent, never a hard halt» (`:47`).

## store, не GSD

Из гриля store (`store/change-intake/references/grill-form.md`) после D4b
остаются два правила — у GSD эквивалента нет; оба помечены в SKILL.md
как заимствование.

| Правило | В store | У нас | Почему оставлено |
| --- | --- | --- | --- |
| покрытие поимённо | «Раздел пройден, когда у него есть вопросы или «чисто»» (`grill-form.md:69-70`); «Молчание по разделу читалось бы как «претензий нет», поэтому непройденное называется поимённо» (`:81-82`) | у каждого раздела цели строка — находка, «чисто» (`справка`) или «не пройдено» (`блокер`), у строк покрытия линза `coverage`; `passed` при «не пройдено» невозможен | GSD называет пропущенное измерение («Dimension 10: SKIPPED (no CLAUDE.md found)», `gsd-plan-checker.md:569`), но не раздел цели, до которого проверяющий не дошёл; предел выхода модели — наш отказ, не GSD |
| второго такта нет | «модель не перечитывает свою находку и не судит её — судила бы та же модель, что спрашивала» (`grill-form.md:31-32`) | строки после записи не перечитываются и не выбрасываются; самопроверка статуса GSD — счёт, не пересуждение | правила у GSD нет, опасность названа: «does NOT defend against *malicious compliance* (a self-graded review rationalizing away its own findings)» (`honest-verifier.md:93-94`) |

Снято как источник: «не «чего не хватает», а «какое утверждение ничем
не подкреплено»» (`grill-form.md:3-4`) — ту же установку даёт
`gsd-plan-checker.md:9`; пять линз с «чего не репортить»
(`grill-form.md:23-27`, прежний `references/grill-lenses.md`) — линзы
теперь измерения plan-checker, отсев — «Do NOT flag»
(`gsd-plan-checker.md:238`) и `<skip_rules>` (`gsd-doc-verifier.md:100-110`);
«машинные линзы гриль не повторяет» (`grill-form.md:28-29`) — у GSD то же
разделение труда между агентами («DO NOT check
code existence — that's gsd-verifier's job», `gsd-plan-checker.md:1034`),
у нас — между `check`, `openspec validate` и атакой.

## Не перенесено

Из `gsd-plan-checker.md`: Nyquist Compliance (`:519-530`) — блоков
`<automated>` и `<fails_when>` у tasks.md нет, проверка задачи — текст
в её строке (Task Completeness); Pattern Compliance (`:637-680`) —
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
