# symphysis-brainstorm — где перевод меняет смысл источника

Источник — GSD Core @ e2cd587 (MIT, Copyright (c) 2026 Open GSD):
`gsd-core/workflows/spec-phase.md`, `gsd-core/workflows/discuss-phase.md`,
`gsd-core/workflows/discuss-phase/templates/context.md`. Копии взятых
разделов — `references/`. Перевод — не механический, а инструкция
агенту на русском (F-14.A, слово владельца: «указать, где при переводе
произошло изменение смысла инструкции»). Ниже — каждое место, где
изменён смысл, а не только язык. Строки — по файлам источника.

| Место | В источнике | У нас | Почему смысл изменён |
| --- | --- | --- | --- |
| `spec-phase.md:8-23` `<ambiguity_model>`, `:20` «Gate», `:117-132` Step 3, `:145-157` «After each round» | четыре измерения ясности с весами и минимумами; «**Gate:** ambiguity ≤ 0.20 AND all dimensions ≥ their minimums → ready to write SPEC.md»; пересчёт и показ баллов после каждого раунда | числового гейта нет; круг кончается счётом новых решений и фактов (`notes[]`: «круг N закончен: решений K, фактов M, открытых развилок D, парковок материалам P, антиподов A»), новый круг — по слову человека | F-07.B, слово владельца: «Не зачем гонять круги, если человек не запустил брейншторм или всё было решено на первом круге … количество шагов брейншторма стоит спрашивать у человека»; следствие F-07: «числовой гейт не вводится». Рекомендация C (число как след в файле) отклонена человеком |
| `spec-phase.md:136` «**Max 6 rounds.** Each round: 2–3 questions max.» | раунд — одна порция из 2–3 вопросов; раундов до шести | «круг» — проход по всем пяти перспективам; порция 2–3 вопроса — внутри круга; кругов не больше двух | единица счёта у владельца — проход, не порция: F-07.B с уликами «второй круг брейншторма» (`plan-flexible-pipeline.md`) и «Кругов не больше двух» (`change-intake`); схема зовёт второй круг в конце шага `research`, после отчётов. Две порции не вместили бы пять перспектив |
| `spec-phase.md:139-143` «Round selection by perspective» | перспектива назначена номеру раунда: 1 Researcher, 2 Researcher + Simplifier, 3 Boundary Keeper, 4 Failure Analyst, 5–6 Seed Closer | перспективы — порядок внутри круга; Researcher один раз, в начале; второй круг снова с Researcher — по открытым записям и находкам исследования | номеров раундов нет; чтение материалов (Researcher) вынесено в шаг 1 «до первого вопроса» и повторяется на каждом круге |
| `spec-phase.md:49-50` Seed Closer: «We have [dimension] at [score] — what would make it completely clear?», «The remaining ambiguity is in [area]…» | вопросы опираются на баллы измерений | вопросы опираются на открытые записи журнала по id («запись F-NN открыта — можно решить сейчас?») | измерений и баллов нет; остаток виден как записи со `status: открыт` |
| `spec-phase.md:159-171` «If gate passes … Proceed? / One more round / Done talking» | вопрос о продолжении — только когда гейт пройден | «Начать новый круг?» задаётся после круга с новыми решениями или фактами и после круга, давшего только открытые развилки без решения; **не задаётся**, когда круг оставил парковки `материалы` — тогда его задаёт instruction артефакта `research` в конце шага `research`, после отчётов (`openspec/schemas/symphysis/schema.yaml:34-36`); «нет» пишется в журнал строкой `notes[]` «брейншторм закончен по решению человека» с датой | F-07, слово владельца: «хочет ли начать новый круг? Если нет, то запись, что брейншторм закончен по решению человека»; парковки `материалы` ждут артефакта `research`, и второй круг по схеме идёт в конце шага `research`, после отчётов, а не до исследования |
| `spec-phase.md:173-183` «If max rounds reached (6) and gate not passed … Keep talking → Continue (no round limit from here) / Abandon → Exit without writing» | после предела разговор может идти без предела; есть выход без записи | после второго круга брейншторм закончен без вопроса; открытое остаётся в журнале открытым; выхода «без записи» нет | F-07.B «не больше двух»; план: «Остаток — в Open Questions»; журнал — артефакт графа, «Abandon» оставил бы `research` и `proposal` без входа |
| `spec-phase.md:185` «`--auto` … Replace all AskUserQuestion calls above with Claude's recommended choice» | автоматический режим: модель выбирает сама | автоматического режима нет; модель не пишет `decision`; «реши сам» вносится как слово человека через `apply` на рекомендованный вариант | instruction схемы: «Решает человек, не ты»; F-12 — проверка сигнал, решение не автоматизируется; делегирование должно быть видно в журнале, не растворено в режиме |
| `spec-phase.md:2-5` «Produces a SPEC.md with falsifiable requirements … This workflow handles "what" and "why" — discuss-phase handles "how"» | выход — SPEC.md; «что/зачем» и «как» — два разных workflow | выход — записи `decisions.json`; один скилл берёт перспективы spec-phase и серые зоны discuss-phase; требования пишет позже артефакт `specs` | схема symphysis: журнал — первый артефакт, specs стоят на решениях (F-04.A); два интервью подряд не воспроизводятся |
| `spec-phase.md:110-115` «Synthesize current state … Do not present it to the user yet» | сводка состояния держится внутри до вопросов | найденное пишется в журнал фактом с уликой сразу; человек видит его в рендере | журнал — файл, не память модели; факт с цитатой — след, по которому атака проверяет (F-12) |
| `spec-phase.md:187` text mode, `discuss-phase.md:101-108` `<answer_validation>` | меню AskUserQuestion, текстовый режим как замена, повтор при пустом ответе | вопросы — текстом в чате; развилки — в просмотрщике HTML, возврат промптом через `apply` | у клиентов контура меню нет; правило владельца (`CLAUDE.md`): «Развилки обсуждаются в просмотрщике, не в чате» |
| `discuss-phase.md:57` «The user doesn't know (and shouldn't be asked): codebase patterns … technical risks … implementation approach (planner figures this out), success metrics» | о подходе к реализации человека не спрашивают — его выбирает планировщик | устройство кода и риски — факт сейчас или парковка `материалы`; развилка реализации, меняющая результат, — запись для человека | в symphysis человек решает и реализацию (журнал плана F-01…F-19 — решения о реализации); модель решений не принимает |
| `discuss-phase.md:98` «Claude handles these (don't ask): technical implementation details, architecture patterns, performance optimization, scope» | часть решений модель принимает сама | деталь без развилки, меняющей результат, — не запись: решится в `design`/`tasks`; деталь с развилкой — запись человеку | то же: модель не принимает решений; у детали без выбора записи не нужно |
| `discuss-phase.md:72-79` «Want me to note it for the roadmap backlog? … Capture the idea in a "Deferred Ideas" section», `context.md:133-136` | отложенная идея — раздел CONTEXT.md, адрес — roadmap backlog | парковка с адресатом `человек` на записи, где идея всплыла: «новая возможность: …»; roadmap нет | F-11.D: адресаты парковки — `материалы | человек | ИБ`; идея вне объёма — вопрос человеку, не раздел документа |
| `context.md:79-80` «Claude's Discretion — Areas where user said "you decide"» | отдельный раздел свободы модели | раздела нет: делегирование — решение со словом «реши сам» через `apply` | свобода модели в журнале не записывается; решение остаётся за человеком и видно как его слово |
| `context.md:64-65` «Omit the field entirely for decisions that are plainly reversible; an unrated decision is treated as `reversible`» | обратимость — необязательное поле, по умолчанию «reversible» | у каждой решённой записи `reversibility` с уровнем и причиной | F-10.A: «причина обязательна при оценке»; слово владельца: «тут без вариантов» |
| `context.md:65-66` «`gsd-planner` carries a `one-way` rating forward into a `checkpoint:decision`» | «в одну сторону» рождает контрольную точку в плане | «в одну сторону» ставит решение первым в `design.md` (`render-design`) | следствие F-10; контрольных точек плана в symphysis нет |
| `discuss-phase.md:63` «The phase boundary comes from ROADMAP.md and is FIXED» | граница — фаза roadmap | граница — изменение OpenSpec (`openspec/changes/<имя>/`) и запрос человека | в symphysis нет roadmap и фаз; единица работы — изменение |
| `spec-phase.md:45` «What would cause a verifier to reject the output?» | verifier — проверяющие агенты GSD | «за что атака отвергнет артефакт» — `symphysis-attack` с вердиктом во frontmatter | проверяющий у нас — атака (F-02.B, F-13) |
| `spec-phase.md:29` «What exists in the codebase today related to this phase?» и остальные вопросы Researcher | вопросы задаются человеку | ответ ищется в файлах; человеку вопрос не задаётся, если ответ лежит в материалах | правило `change-intake`: «У человека спрашивается только то, чего нельзя проверить по файлам»; `discuss-phase.md:57` сам говорит, что код читает исследователь |

## Соответствие терминов — смысл тот же

| В источнике | У нас |
| --- | --- |
| phase | изменение (change OpenSpec) |
| round (2–3 questions) | порция |
| codebase | материалы: код, документы, запрос |
| decision `D-NN` | запись `F-NN` |
| gray area | развилка; «серая зона» — пока не оформлена вариантами |
| Deferred Ideas | парковка `человек` |
| Reversibility: reversible / costly / one-way | обратимость: обратимо / дорого / в одну сторону |
| user / Claude | человек / модель |
| Researcher, Simplifier, Boundary Keeper, Failure Analyst, Seed Closer | Исследователь, Упрощатель, Хранитель границ, Аналитик отказов, Закрывающий — английское имя в скобках при первом упоминании |

## Перенесено без изменения смысла

Пять перспектив и их вопросы (`spec-phase.md:28-51`); порция 2–3
вопроса и конец порции ответом человека (`:136`); чтение материалов
до первого вопроса (`:542`); «User = founder/visionary. Claude =
builder.» (`discuss-phase.md:53`); конкретные серые зоны вместо
категорий (`:89`); эвристика ограды объёма (`:69`); причина обратимости
называет миграцию, контракт или систему, не «трудно менять»
(`context.md:62-64`).
