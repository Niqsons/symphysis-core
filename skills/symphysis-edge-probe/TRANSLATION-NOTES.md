# symphysis-edge-probe — где перевод меняет смысл источника

Источник — GSD Core @ e2cd587 (MIT, Copyright (c) 2026 Open GSD):
`gsd-core/references/edge-probe.md` (копия целиком — `references/`)
и Step 5.5 «Edge-Completeness Probe» в `gsd-core/workflows/spec-phase.md`
(`:191-382`, в копию не взят: это шаг другого workflow, его механика —
в SKILL.md). Перевод — не механический, а инструкция агенту на русском
(F-14.A, слово владельца: «указать, где при переводе произошло изменение
смысла инструкции»). Ниже — каждое место, где изменён смысл, а не только
язык. Строки — по файлам источника.

| Место | В источнике | У нас | Почему смысл изменён |
| --- | --- | --- | --- |
| `edge-probe.md:44-60` Inputs, `:52` «The classifier reads English; `text` does not have to be.»; `spec-phase.md:196-204` «Non-English projects — `text_en` carries the classifier-facing translation; the SPEC is not.» | классификатор — код над английскими cue-словами (`SHAPE_CUES`); русское требование получает `text_en` или авторские `shapes`, иначе формы нет | классификатора-кода нет: форму из пяти называет модель по смыслу русского требования и пишет префиксом `[категория · форма]` в `question`; человек правит префикс | F-08.D — слово владельца «Согласен с рекомендацией» на «A, а C — как поправка человека поверх: форма модели предлагается, человек правит»; следствие F-08: «форма — поле записи, которое человек может переписать»; `CLAUDE.md`: «классификатор GSD — код и читает только английский; тип требования определяет модель» |
| `edge-probe.md:91-99` «Zero-classification surfaces an `unclassified` candidate (#1110)»; `spec-phase.md:353-355`, `:374-378` | требование, не давшее ни одной формы, получает мягкий кандидат `unclassified — review manually`; `--auto` оставляет его `unresolved` | кандидата `unclassified` нет: классификатор — модель, форма называется всегда, случай «ноль форм» не возникает | #1110 чинит слепое пятно cue-классификатора на прозе без cue-слов; у модели, читающей смысл, такого пятна нет, а сигнал «посмотри руками» и так идёт человеку — каждым кандидатом в просмотрщике |
| `edge-probe.md:100-101` «an explicit `shapes: []` opt-out stays silent (the author's deliberate "no edge surface")» | автор может молча снять требование с пробы | молчаливого снятия нет: форма называется, лишних кандидатов человек отводит Dismiss с причиной — след остаётся в журнале | то же правило, что у отказа: «silence is not» (`:90`); в symphysis причина — слово человека через `apply`, видное в `outcome.reason` |
| `spec-phase.md:316-333` «WARNING: edge-probe proposed ZERO applicable edges across all requirements … Do NOT silently write an empty Edge Coverage section», подтверждение через AskUserQuestion | нулевой результат движка — повод спросить автора, не ошибка ли классификации | отдельного гейта нет: форма называется всегда, и каждая форма поднимает хотя бы одну категорию таблицы — нуля кандидатов у требования не бывает | гейт сторожит промах классификатора-кода; промах модели виден человеку в просмотрщике как неверный префикс формы, который он правит |
| `spec-phase.md:336-343` «the deterministic `items[]` are the FLOOR … Union the engine's rows with your own classification … do not narrow to them» | два классификатора: движок даёт пол, модель добавляет пропущенные категории | один классификатор — модель; «пол» и «потолок» совпадают: поднимаются ровно категории таблицы, применимые к названным формам | движка нет — F-08.B отвергнут: «отказ классификатора на кратком тексте признан самим GSD; порт унаследует его»; таблица закрыта (`edge-probe.md:64-65`), расширять её модели нельзя |
| `spec-phase.md:343` «Reuse any edges the Round-4 Failure Analyst already surfaced as pre-resolved.» | край, найденный интервью, входит в пробу уже решённым элементом | край, уже решённый в журнале, второй раз не поднимается; в комментарий spec.md идёт номер той записи | у записи журнала один номер и одно решение; дубль дал бы два решения на один край |
| `spec-phase.md:346-352` «Resolve each with the user (AskUserQuestion; text mode → numbered list)» | исход выбирается в чате, по одному краю, из меню | кандидат — запись журнала с четырьмя фиксированными вариантами A–D; человек решает в просмотрщике, слово вносит `apply`; модель `decision` не пишет | правило владельца (`CLAUDE.md`): «Развилки обсуждаются в просмотрщике, не в чате»; у клиентов контура меню нет |
| `edge-probe.md:103-121` две оси `status` × `verification`, сводка `coverage` (`:134`); `spec-phase.md:347-352` «mark the edge `resolved` with `verification: explicit`» и далее | исход — два поля элемента `items[]` плюс счётчики `coverage` | исход — одно поле записи `outcome {kind: "проба", value, reason}`, `value` из четырёх: Specify = resolved/explicit, Backstop = resolved/backstop, Dismiss = dismissed, Defer = unresolved; сводка — строка `notes[]` «проба краёв: кандидатов N, Specify a, Dismiss b, Backstop c, Defer d» | F-09.C: «две сущности, две лексики; общее у них одно — отказ без причины не принимается»; следствие: «формат журнала получает поле `исход` с двумя закрытыми списками»; слова GSD оставлены по-английски — это и есть «лексика GSD» |
| `edge-probe.md:89-90` «Dismissal requires a reason string … The reason string is the audit trail.»; `edge-probe.md:108` «accompanied by a required, non-empty reason string» | причина — строка в выводе движка, её пишет тот, кто резолвит | причина — слово человека: `decision.word` → `outcome.reason`; `check` красит Dismiss с пустой причиной; B без слова — вопрос человеку и строка `к решению B — «причина»` через `apply` | смысл тот же, носитель другой: причину не пишет модель — иначе след аудита был бы её, а не человека |
| `spec-phase.md:367-372` `--auto`: «auto-`resolved` (verification: explicit) where a defensible acceptance criterion can be written; otherwise auto-`resolved` (verification: backstop) (never auto-dismiss …)» | автоматический режим сам выбирает между Specify и Backstop | автоматического режима нет; «реши сам» — слово человека на рекомендованный вариант через `apply`; на B «реши сам» не ложится — рекомендованный B становится C | модель решений не принимает (instruction схемы: «Решает человек, не ты»); запрет авто-отказа GSD сохранён как правило для «реши сам» |
| `spec-phase.md:357-365` soft gate: «Resolve now / Write SPEC.md anyway — flag unresolved / Keep probing», «⚠ Edge unresolved — planner must treat as assumption» | нерешённые края задерживают запись SPEC.md до слова автора; есть цикл «Keep probing» | гейта и цикла нет: spec.md уже написан, проба его дополняет; Defer — решение человека, записанное в журнал; `consequences` «край не решён — tasks считает его допущением», в комментарии spec.md — `F-NN Defer` | по схеме symphysis проба идёт «после написания» требований (`openspec/schemas/symphysis/schema.yaml:65`), не до; открытый кандидат виден атаке и Open Questions дизайна — блокировать артефакт ему незачем |
| `edge-probe.md:145-155` «an Acceptance Criterion that `plan-phase` lifts into `must_haves.truths`», backstop — «a non-inferable check in `must_haves.truths`»; `spec-phase.md:480-484` раздел «Edge Coverage» SPEC.md | Specify — критерий приёмки SPEC.md, Backstop — пункт `must_haves` для планировщика; покрытие — раздел SPEC.md | Specify — `#### Scenario:` GIVEN/WHEN/THEN под требованием; Backstop — `consequences` записи, тест пишет `tasks`; покрытие — комментарий `<!-- проба краёв: … -->` под требованием (`openspec/schemas/symphysis/templates/spec.md:10`) и строка `notes[]` | в грамматике OpenSpec критерий приёмки — сценарий; раздела Edge Coverage и `must_haves` нет; комментарий под требованием уже заложен шаблоном схемы |
| `edge-probe.md:103-113` (у края нет обратимости); `discuss-phase/templates/context.md:58-70` обратимость — у решений интервью | обратимость — свойство решения дизайна, не края | `reversibility` у кандидата остаётся `null`, хотя у записей журнала поле есть и брейншторм заполняет его у решённых (F-10) | кандидат — не проектное решение: отменить Specify — убрать сценарий; «в одну сторону» ставило бы кандидата первым в `design.md` (`render-design`) |
| `edge-probe.md:1-9` «Walk each requirement against the closed taxonomy below, propose a concrete candidate edge for each applicable category, and resolve each to exactly one state.» | один проход: поднять и резолвить | два прохода: модель поднимает всё и пишет в журнал, затем круг просмотрщика и зеркало исхода | решение и его носитель разнесены (F-01.B: журнал — источник, HTML — рендер); человек видит все кандидаты разом, не по одному |

## Соответствие терминов — смысл тот же

| В источнике | У нас |
| --- | --- |
| requirement / SPEC Requirement | `### Requirement:` в `specs/<capability>/spec.md` |
| author / user | человек |
| verifier | атака (`symphysis-attack`) |
| edge item (`items[]`) | запись `F-NN` с префиксом `[категория · форма]` |
| candidate edge / probe question | кандидат / вопрос таблицы |
| Acceptance Criterion | `#### Scenario:` |
| plan-phase / planner | артефакт `tasks` |
| resolution state | исход |
| coverage | строка `notes[]` «проба краёв: …» |
| Specify / Dismiss / Backstop / Defer | те же слова, по-английски; русская расшифровка — в тексте варианта |

## Перенесено без изменения смысла

Восемь категорий, их QA-имена, формы применимости и вопросы — дословно
(`edge-probe.md:70-79`); пять форм (`:47`); фильтр применимости
(`:85-88`); отказ только с причиной (`:89-90`); закрытость таблицы и её
обоснование (`:64-68`); довод «проба стоит в начале конвейера»
(`:15-25`); конкретный край вместо напоминания (`spec-phase.md:344-345`);
четыре исхода и их значение (`:347-352`); проба по ясным требованиям
(`:193`).

## Не перенесено

Парный справочник `domain-probes.md` — ось технологий (`edge-probe.md:3-6`):
отдельный документ, в плане нет. Схема вывода JSON и `coverage`
(`:123-141`) — у нас носитель журнал. Разобранные примеры (`:157-458`)
остались в копии как примеры; теста на совпадение с фикстурами
(`:216-217`) нет. Ссылки на ADR GSD — контекст источника, не инструкция.
