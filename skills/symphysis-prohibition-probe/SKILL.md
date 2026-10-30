---
name: symphysis-prohibition-probe
description: >-
  Проба запретов требований spec.md по оси «чем система не должна молча
  стать»: продукт, ценности, безопасность, этика — ось, которую проба
  краёв не достаёт. Модель задаёт каждому требованию вопрос GSD «чем это
  может тихо стать, чего автор не хотел бы, а спека не запрещает»,
  отсеивает инженерную гигиену, канон ИБ паркует адресату `ИБ` под
  чек-лист `security.md`, оставшиеся запреты пишет кандидатами в журнал
  `decisions.json`; решает человек в просмотрщике, его слово вносит
  `journal.py apply`, скилл зеркалит его в `outcome`. Применяй, когда
  instruction артефакта `specs` схемы symphysis зовёт скилл по имени
  после пробы краёв, когда человек просит «прогони пробу запретов»,
  «чем это может тихо стать», «что спека не запрещает». Не применяй для
  краёв данных и поведения — это `symphysis-edge-probe`; для атаки
  артефактов — `symphysis-attack`; для развилок замысла —
  `symphysis-brainstorm`.
---

# symphysis-prohibition-probe

Проба запретов шага `specs` схемы symphysis: по каждому требованию —
то, чем система могла бы тихо стать против воли автора, пока спека этого
не запрещает. Механика — из GSD Core: два такта «широко, затем узко»
(`upstream/gsd-core/gsd-core/references/prohibition-probe.md:46-48`),
отсев гигиены (`:60-74`), канон не чеканится (`:76-91`), ярус проверки
`test | judgment` (`:93-111`; Step 5.6 `workflows/spec-phase.md:384-470`).
Движка нет и в источнике: «no compiled `prohibition-probe.cjs` engine —
the recall stage is an LLM prose pass» (`:32-33`; F-24) — переносится
текст. Оригинал — `references/prohibition-probe.md`; где
смысл инструкции изменён против источника — `TRANSLATION-NOTES.md`.

## Главное правило

**Решает человек, не модель.** Модель спрашивает, отсеивает и пишет
кандидата с четырьмя вариантами — исход появляется только из слова
человека: `decision` пишет `apply`, `outcome` — его зеркало. **Отказ без
причины не принимается**: «accompanied by a required, non-empty reason
string … silence is not. The reason string is the audit trail»
(`prohibition-probe.md:101-103`); `check` красит Dismiss без причины.

**Запрет — про намерение, не про гигиену.** «Не должен падать на пустом
списке» — край или код-ревью; «напоминание не должно стыдить» — запрет.
Без отсева такта 2 гигиена утопит настоящие запреты.

**Зачем проба стоит до кода.** «a `✅ done` that means "the code matches
the words in the spec" can still ship a feature that does what the author
explicitly would *not* want» (`:22-24`). Лечится полнотой спеки: запрет
становится требованием до кода.

## Файлы и команды

`<каталог изменения>` — `openspec/changes/<имя>/`. Требования —
`<каталог изменения>/specs/<capability>/spec.md`, журнал —
`<каталог изменения>/decisions.json` (тот же, что у брейншторма и пробы
краёв; номера F-NN продолжаются). CLI —
`py -3.13 .symphysis/tools/journal.py`:

```bash
# после каждой записи: схема и правила (код 1 — журнал негоден, чини), улики (сигнал)
py -3.13 .symphysis/tools/journal.py check <каталог изменения>/decisions.json
py -3.13 .symphysis/tools/journal.py render-md <каталог изменения>/decisions.json --out <каталог изменения>/decisions.md

# круг просмотрщика: человек решает в HTML, промпт возврата вносит apply
py -3.13 .symphysis/tools/journal.py render-html <каталог изменения>/decisions.json --out <каталог изменения>/decisions.html
py -3.13 .symphysis/tools/journal.py apply <каталог изменения>/decisions.json <каталог изменения>/answers/<дата>.md
```

JSON правят только модель (кандидаты, парковки канона, `outcome`,
`consequences`, `notes`) и `apply` (слово человека). `spec.md` модель
правит только по решённому исходу; `security.md` не создаёт.
`decisions.md` и `decisions.html` — рендер, в них не пишут.

## Порядок пробы

### 1. Вход

Все `### Requirement:` файлов `specs/**/spec.md` изменения — тот же
список, что у пробы краёв, после неё («The probe runs **after** the
edge-probe in the spec phase, over the same requirement list»,
`prohibition-probe.md:41-42`). Запрет, уже стоящий в журнале, — запись
с префиксом `[запрет]`, называющая то же требование, — второй раз не
поднимается: в комментарий spec.md идёт её номер.

### 2. Такт 1 — вопрос (recall)

Каждому требованию — один вопрос, дословно и в переводе (`:53-54`):

> *What could this feature silently become that the author would NOT want, but the spec does not forbid?*
>
> Чем эта возможность может тихо стать — таким, чего автор НЕ хотел бы,
> но спека не запрещает?

Отвечай широко: ~10 сырых кандидатов на требование, включая инженерные —
«That over-production is intentional — recall first» (`:57-58`). Сырой
список в журнал не пишется: это материал такта 2, не кандидаты.

### 3. Такт 2 — отсев (precision)

Один проход по сырому списку, правило — «выбросить / оставить»
(`:62-70`):

- **DROP** — «routine-engineering items — anything that is a normal
  correctness or hygiene concern rather than an intent constraint»:
  «не должен менять вход», «не должен падать на пустом» — это проба
  краёв и код-ревью;
- **KEEP** — «values / safety / ethics items — anything that, if
  violated, makes the feature do something the author would object to
  on product, fairness, privacy, transparency, or safety grounds»:
  стыдящая формулировка, прокси защищённого признака, PII открытым
  текстом.

Остаётся ~2–3 на требование. **Ноль оставленных — правильный исход для
чистой утилиты, не отказ пробы** («the correct precision outcome for
a pure utility, not a failure», `:73-74`).

### 4. Канон — адресату ИБ, не в запрет

Часть оставленных — не особенные для задачи, а канон, которым владеет
чек-лист: OWASP, инъекции, пути с `../`, прототипное загрязнение, GDPR
и сроки хранения, общая справедливость. «Do NOT mint a prohibition for
them. Instead emit a one-line breadcrumb and stop» (`:79-80`): чеканка
канона «duplicates other tooling and drowns the bespoke signal» (`:90-91`).

Отсылка — не строка в `security.md`: шаг `specs` идёт раньше шага
`security` (`openspec/schemas/symphysis/schema.yaml:65`, `:81-91`),
файла ещё нет, а созданный раньше времени он закрыл бы шаг — ванильный
CLI считает артефакт готовым по существованию файла. Отсылка — парковка
адресату `ИБ` (F-11.D; F-24: «отсылает в чек-лист ИБ — это и есть адресат
«ИБ» из F-11»): на требование, давшее канон, одна запись `decisions.json`:

- `kind: факт`, `status: припаркован`, `addressee: ИБ`,
  `question: [канон] <требование>: канон ИБ`;
- `evidence[]` — путь spec.md и дословная строка требования;
- `parking[]` — по записи на пункт: `{addressee: "ИБ", text: "<пункт> —
  канон, покрывается чек-листом security.md; запрет не чеканится"}`.

Строки чек-листа из парковок делает шаг `security`.

### 5. Запиши кандидата

На каждый оставленный особенный запрет — одна запись `decisions.json`
по `journal.schema.json`:

- `kind: развилка`, `status: открыт`, `addressee: человек`,
  `reversibility: null` — кандидат не проектное решение;
- `question` — `[запрет] <требование>: не должен <чем стать>`: требование
  названо по имени, запрет один, на данных этого требования, по-русски
  («must not» источника — «не должен»);
- `evidence[]` — путь spec.md и дословная строка требования
  (`### Requirement: <имя>` или строка с SHALL), чтобы `check` нашёл её;
- `options[]` — ровно четыре, тексты дословно:
  - `A. Specify/test — запрет становится требованием spec.md; проверка — тест`
  - `B. Specify/judgment — запрет становится требованием spec.md; проверка — суждение, не тест`
  - `C. Dismiss — не относится; причина обязательна`
  - `D. Defer — отложено; остаётся открытым`
- `recommendation` — одна, после вариантов, с ярусом: A, когда запрет
  проверяется механически — «a negative test, a lint rule, an assertion
  that the audit log contains no raw SSN» (`:107-108`), и назван
  черновик теста; B, когда запрет настоящий, но «cannot be reduced to
  a mechanical test» (`:109-111`), и назван судья; C — только с готовой
  причиной в `why`; D не рекомендуется;
- `depends_on` — записи, на которых стоит требование;
  `decision: null`, `outcome: null` — их заполнят `apply` и шаг 7.

После каждой записи — `check`, затем `render-md`.

### 6. Круг просмотрщика

Когда кандидаты и парковки по всем требованиям записаны —
`render-html`, назови человеку путь к `decisions.html`. Человек выбирает
исход и пишет слово: у C — причина; у A — какой тест, у B — кто и как
судит, если задаёт это сам. Промпт возврата сохрани в
`<каталог изменения>/answers/<дата>.md` как есть и внеси `apply`; отказ
называет запись — исправь строку промпта, не JSON. «Реши сам» — тоже
слово человека: внеси рекомендованный вариант строкой
`- F-NN: X — «реши сам»`, букву не подменяй; у рекомендованного C
причиной становится `why` рекомендации с пометкой «по слову „реши сам“»
— отказа без причины нет (`spec-phase.md:460-461` «a wrong dismissal is
the exact silent failure this probe eliminates»).

### 7. Зеркало исхода

После `apply` у каждой записи пробы с `decision`:

- `outcome` ← `{kind: "проба", value: <A и B → Specify, C → Dismiss,
  D → Defer>, reason: <decision.word дословно; у C по «реши сам» — `why`
  с пометкой>}`. `Backstop` у запретов не бывает,
  `journal_model.PROBE_OUTCOMES` не расширяется: ярус живёт
  в `consequences`, не в `value`;
- A и B: в spec.md под той же capability, в `## ADDED Requirements`, —
  новое `### Requirement:` с MUST NOT и `#### Scenario:` GIVEN/WHEN/THEN;
  меняется существующее — `## MODIFIED Requirements`, требование целиком
  (`templates/spec.md:6,18`); у A THEN проверяет тест, у B THEN называет
  суждение и судью (ревью, атака `symphysis-attack`).
  `consequences` ← `проверка: test — <какой тест>`
  или `проверка: judgment — <кто и как судит>`, затем «в spec.md:
  <имя требования>»; тест пишет `tasks`, здесь только намерение;
- D: `consequences` ← «запрет не решён — tasks считает его допущением»
  («an explicit assumption the downstream planner must surface, not
  silently drop», `prohibition-probe.md:233-234`);
- C: `consequences` ← причина; spec.md не меняется.

Затем `check`: C без слова — красное «исход Dismiss без причины».
Причину не выдумывай: спроси человека в чате и внеси строкой
`- F-NN: к решению C — «причина»` через `apply`, зеркало повтори.

### 8. След в spec.md и итог

Под каждым требованием заполни комментарий шаблона
(`openspec/schemas/symphysis/templates/spec.md:11`):
`<!-- проба запретов: исходы: F-NN Specify, F-MM Dismiss, …; канон — F-KK → security.md -->`;
без оставленных — «исходы: нет». Закрой пробу строкой `notes[]`:
`{date, text: «проба запретов: требований R, оставлено K, канон → ИБ M,
Specify a, Dismiss b, Defer d»}`; кандидаты без решения входят в K
и перечисляются номерами. Затем `render-md`, `render-html`. Гейта «все
запреты решены» нет: открытый кандидат остаётся открытым — его увидят
атака и Open Questions дизайна.

## Чего скилл не делает

- не ставит исход сам: `decision` — только из `apply`, `outcome` — зеркало
  слова человека;
- не принимает Dismiss без причины и не сочиняет причину за человека;
- не чеканит гигиену и не ищет края данных и поведения — это
  `symphysis-edge-probe` и код-ревью; сырой список такта 1 в журнал
  не пишет;
- не чеканит канон и не создаёт `security.md`: канон — парковка `ИБ`;
- не ставит `Backstop` и не расширяет список исходов;
- не пишет тест и не судит: ярус — в `consequences`, тест — у `tasks`,
  суждение — у атаки или человека;
- не оценивает обратимость и не держит гейта на нерешённых: кандидат —
  не проектное решение, открытый остаётся открытым.

## Приёмка

| Проверка | Чем держится |
| --- | --- |
| решает человек | `decision` только из `apply`; `outcome.value` — по букве решения (A и B → Specify), `reason` — слово дословно |
| отказ с причиной | `check` зелёный: ни одного Dismiss с пустой причиной; причина — слово человека или `why` при «реши сам» |
| отсев сделан | у каждого кандидата — ценности, безопасность или этика; гигиены («не должен падать») в `question` нет |
| канон не чеканен | ни одной развилки `[запрет]` про OWASP, инъекции, `../`, GDPR; у них — парковка `ИБ` с текстом про `security.md` |
| ярус назван | у каждого Specify в `consequences` строка `проверка: test — …` или `проверка: judgment — …` |
| след в spec.md | у каждого требования комментарий «проба запретов» с исходами по номерам; на каждый Specify — требование MUST NOT со сценарием |
| проба закрыта счётом | строка `notes[]` с R, K, M, a, b, d и датой; ноль у чистой утилиты — зелёный |
