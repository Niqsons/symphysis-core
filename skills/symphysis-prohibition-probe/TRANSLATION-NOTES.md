# symphysis-prohibition-probe — где перевод меняет смысл источника

Источник — GSD Core @ e2cd587 (MIT, Copyright (c) 2026 Open GSD):
`gsd-core/references/prohibition-probe.md` (копия целиком — `references/`)
и Step 5.6 «Prohibition-Completeness Probe (must-NOT)»
в `gsd-core/workflows/spec-phase.md` (`:384-470`, в копию не взят: это шаг
другого workflow, его механика — в SKILL.md). Перевод — не механический,
а инструкция агенту на русском (F-14.A, слово владельца: «указать, где
при переводе произошло изменение смысла инструкции»). Ниже — каждое
место, где изменён смысл, а не только язык. Строки — по файлам источника.

| Место | В источнике | У нас | Почему смысл изменён |
| --- | --- | --- | --- |
| `prohibition-probe.md:76-91` canon-referral, `:82-83` «→ breadcrumb to `/gsd:secure-phase` and `eslint` (security plugins), not a minted prohibition»; `spec-phase.md:407-411` «emit a one-line breadcrumb … and DROP it» | канон — строка-отсылка к другому инструменту (`/gsd:secure-phase`, eslint) и сброс: следа в выходе пробы нет | канон — запись-факт `[канон] <требование>: канон ИБ` со статусом `припаркован` и парковкой адресату `ИБ` на каждый пункт; текст парковки называет `security.md`; след остаётся в журнале; строка в `security.md` не пишется, файл не создаётся | F-11.D (слово владельца «Написал сам ранее: только материалы, человек, ИБ.») и F-24 («отсылает в чек-лист ИБ — это и есть адресат «ИБ» из F-11»); `security.md` на шаге `specs` ещё нет (`schema.yaml:65`, `:81-91`): ванильный CLI считает артефакт готовым по существованию файла (`CLAUDE.md`), созданный раньше времени он закрыл бы шаг `security`; парковки шаг `security` превращает в строки чек-листа |
| `spec-phase.md:412` «Resolve each surfaced (non-canon) prohibition (AskUserQuestion; text mode → numbered list)», `:468-470` PROB-09 | исход выбирается в чате, по одному запрету, из меню или нумерованного списка | кандидат — запись журнала с четырьмя фиксированными вариантами A–D; человек решает в просмотрщике, слово вносит `apply`; модель `decision` не пишет | правило владельца (`CLAUDE.md`): «Развилки обсуждаются в просмотрщике, не в чате»; текстовый режим PROB-09 не нужен — просмотрщик один для всех клиентов |
| `prohibition-probe.md:93-111` две оси: `status` `resolved \| dismissed \| unresolved` × `verification` `test \| judgment`; `:105-106` «this REPLACES the edge-probe's `explicit \| backstop`» | исход — два поля элемента; ярус проверки — значение второй оси | исход — одно поле `outcome {kind: "проба", value, reason}`, `value` из трёх: Specify = resolved (A и B), Dismiss = dismissed, Defer = unresolved; ярус — строка `consequences` «проверка: test — …» или «проверка: judgment — …»; варианты A/B различают ярус до слова человека | F-09.C: одна лексика «проба» на обе пробы, список `journal_model.PROBE_OUTCOMES` закрыт и не расширяется; `Backstop` у запретов не бывает — ярус GSD его заменил; ярус — не исход, а способ проверки требования, и живёт рядом с текстом требования |
| `spec-phase.md:413-416` «Keep it → write a NEGATIVE acceptance criterion (a must-NOT line) into Acceptance Criteria AND mark the prohibition `resolved` with a verification tier»; `prohibition-probe.md:225` «a SPEC acceptance criterion (marked prohibition) that `plan-phase` lifts into `must_haves.prohibitions`» | Specify — строка must-NOT в критериях приёмки; планировщик поднимает её в `must_haves.prohibitions` | Specify — новое `### Requirement:` с MUST NOT и `#### Scenario:` GIVEN/WHEN/THEN под той же capability; у яруса test THEN проверяет тест, у judgment THEN называет суждение и судью; `must_haves` нет — тест пишет `tasks`, судит атака | грамматика OpenSpec: требование с SHALL/MUST и сценарий (`schema.yaml:62`); отдельной секции Prohibitions и `must_haves` в symphysis нет; проверяющий — атака (F-02.B, F-13) |
| `prohibition-probe.md:101-103` «accompanied by a required, non-empty reason string … The reason string is the audit trail»; `spec-phase.md:444-445` PROB-05 | причина — строка в выходе, пишет её тот, кто резолвит | причина — слово человека: `decision.word` → `outcome.reason`; `check` красит Dismiss с пустой причиной; C без слова — вопрос человеку и строка «к решению C — «причина»» через `apply` | смысл тот же, носитель другой: причину не пишет модель — иначе след аудита был бы её, а не человека |
| `spec-phase.md:459-466` `--auto`: «auto-`resolved` where a defensible negative acceptance criterion can be written … `--auto` NEVER auto-dismisses a prohibition» | автоматический режим сам резолвит и никогда не отклоняет | автоматического режима нет; «реши сам» — слово человека на рекомендованный вариант через `apply`, букву скилл не подменяет; рекомендованный C при «реши сам» получает причиной `why` рекомендации с пометкой «по слову „реши сам“» | модель решений не принимает (instruction схемы: «Решает человек, не ты»); запрет авто-отказа GSD сохранён в его сути — отказа без причины нет: причина берётся из рекомендации, которую человек делегировал, и видна в `outcome.reason` |
| `spec-phase.md:448-457` soft gate PROB-06: «Any `unresolved` → AskUserQuestion … "Resolve now" (loop back) / "Write SPEC.md anyway — flag unresolved" / "Keep probing"», «⚠ Prohibition unresolved — planner must treat as assumption» | нерешённые запреты задерживают запись SPEC.md до слова автора; есть цикл «Keep probing» | гейта и цикла нет: spec.md уже написан, проба его дополняет; Defer — решение человека в журнале, `consequences` «запрет не решён — tasks считает его допущением»; открытый кандидат остаётся открытой записью — его видят атака и Open Questions `design.md` | по схеме проба идёт «после написания» требований (`schema.yaml:65`), не до; слово человека и так решает каждый кандидат в просмотрщике — второй вопрос «что делать с нерешёнными» дублировал бы круг |
| `prohibition-probe.md:154-192` wired-check descriptor (`check_kind`, `check_target`, `check_rule`, `check_violation_fixture`, `check_clean_fixture`), `:113-146` `check prohibition-enforcement` и machine-proven fail-first; `spec-phase.md:417-443` | у яруса test — дескриптор механической проверки, которую verify-phase находит и доказывает fail-first | дескриптора нет: `consequences` ← «проверка: test — <какой тест>» как намерение; тест пишет `tasks`, проверяет атака | движка нет (F-24; `spec-phase.md:391` «no compiled engine»); `check prohibition-enforcement`, eslint и `node --test` — код verify-phase GSD, у symphysis проверяющий — атака, исполнение — `tasks` |
| `prohibition-probe.md:194-219` выходная схема: `items[]` с `category`, `statement`, `check_*`; `coverage {applicable, resolved, unresolved, byVerification}` | выход — JSON по контракту, сводка — счётчики по осям | выход — записи журнала; сводка — строка `notes[]` «проба запретов: требований R, оставлено K, канон → ИБ M, Specify a, Dismiss b, Defer d»; поля `category` нет — класс (values, fairness, privacy…) служит отсеву такта 2, а не записи | носитель — журнал (F-01.B: журнал — источник, HTML — рендер); класс нужен был проекции и `coverage`, человеку в просмотрщике яснее сам текст запрета |
| `prohibition-probe.md:9-11` «Walk each requirement through the two-stage recall→precision protocol below and resolve each surfaced prohibition to exactly one state.» | один проход: поднять и резолвить | два прохода: модель поднимает всё и пишет в журнал, затем круг просмотрщика и зеркало исхода | решение и его носитель разнесены (F-01.B); человек видит все кандидаты разом, не по одному |
| `prohibition-probe.md:147-148` «A **judgment**-tier prohibition routes to a never-silent / never-hard-halt soft gate (autonomous emits an `unverified-prohibition — human review recommended` flag)» | ярус judgment — флаг на этапе проверки | ярус judgment — THEN сценария называет суждение и судью (ревью, атака `symphysis-attack`), `consequences` «проверка: judgment — <кто и как судит>» | этапа verify с флагами в symphysis нет; судью называет спека, читает его атака |
| `prohibition-probe.md:93-111` (у запрета нет обратимости); `discuss-phase/templates/context.md:58-70` обратимость — у решений интервью | обратимость — свойство решения дизайна, не запрета | `reversibility` у кандидата остаётся `null`, хотя у записей журнала поле есть и брейншторм заполняет его у решённых (F-10) | кандидат — не проектное решение: `render-design` не ставит его в Decisions; «в одну сторону» ставило бы кандидата первым |

## Соответствие терминов — смысл тот же

| В источнике | У нас |
| --- | --- |
| requirement / SPEC Requirement | `### Requirement:` в `specs/<capability>/spec.md` |
| author / user | человек |
| verifier | атака (`symphysis-attack`) |
| prohibition item (`items[]`), `statement` (must-NOT sentence) | запись `F-NN` с префиксом `[запрет]`; `question` — «<требование>: не должен …» |
| canon breadcrumb → `/gsd:secure-phase` + `eslint` | парковка адресату `ИБ` с текстом про `security.md` (запись `[канон]`) |
| NEGATIVE acceptance criterion (must-NOT line) | `### Requirement:` с MUST NOT и `#### Scenario:` |
| plan-phase / `must_haves.prohibitions` | артефакт `tasks` |
| `resolved` / `test` | Specify (вариант A), `consequences` «проверка: test — …» |
| `resolved` / `judgment` | Specify (вариант B), `consequences` «проверка: judgment — …» |
| `dismissed` (reason) | Dismiss (вариант C) с причиной |
| `unresolved` | Defer (вариант D) |
| coverage | строка `notes[]` «проба запретов: …» |
| Specify / Dismiss / Defer | те же слова, по-английски; русская расшифровка — в тексте варианта |

## Перенесено без изменения смысла

Два такта «широко, затем узко» (`prohibition-probe.md:46-48`); вопрос
такта 1 дословно (`:53-54`) — в SKILL.md по-английски и в переводе рядом;
избыточность ~10 сырых и «recall first» (`:57-58`); развилка DROP / KEEP
с её примерами (`:63-70`); ~2–3 оставленных и ноль как правильный исход
чистой утилиты (`:72-74`); перечень канона — OWASP, prototype-pollution,
path-traversal, injection, GDPR, data-retention, consent, generic fairness
(`:82-85`); цена чеканки канона (`:90-91`); довод «проба стоит в начале
конвейера» (`:17-28`); смысл ярусов test и judgment (`:107-111`);
отсутствие движка и классификатора (`:30-35`; `spec-phase.md:391-396`) —
у нас его тоже нет; проба после пробы краёв по тому же списку требований
(`:41-42`); сырой список такта 1 не сохраняется — и в источнике выход
содержит только оставленные (`:196-200`).

## Не перенесено

Дескриптор механической проверки, machine-proven fail-first, фикстуры
нарушения и контроля, `GSD_PROHIB_SUBJECT` (`prohibition-probe.md:113-192`;
`spec-phase.md:417-443`) — код verify-phase GSD, движка у нас нет (F-24).
Выходная схема JSON и `coverage` (`:194-219`) — носитель журнал. Таблица
соответствий хостам (`:221-234`) — контекст источника. Разобранные примеры
(`:236-332`) остались в копии как примеры; теста на совпадение
с фикстурами (`:329-332`) нет. Мягкий гейт PROB-06 и режим `--auto`
(`spec-phase.md:448-466`), текстовый режим PROB-09 (`:468-470`) — у нас
просмотрщик и слово человека. Раздел «Prohibitions» в SPEC.md (`:485`) —
у нас комментарий под требованием (`templates/spec.md:11`) и требование
MUST NOT. Ссылки на ADR GSD — контекст источника, не инструкция.
