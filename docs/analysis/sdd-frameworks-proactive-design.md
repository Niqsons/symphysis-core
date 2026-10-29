# Проактивное проектирование в SDD-фреймворках

Разбор 2026-10-29 к плану `docs/plan-flexible-pipeline.md`.
Написан во flow-specs (`.gigacode/analysis/`), перенесён сюда тогда же.
Вопрос: где в методологии SDD и её фреймворках момент проактивного
проектирования — поиска того, о чём запрос молчит, — а не описания
реализации заданного; как устроен брейншторм.

Сравнение по исходникам, не по обкатке: ни один фреймворк
на рабочей задаче не запускался.

## Как собрано

| Фреймворк | Версия | Где читали |
| --- | --- | --- |
| OpenSpec | 1.13.1 | установленный пакет `%APPDATA%\npm\node_modules\@fission-ai\openspec\` |
| sdd-superpowers | 3.2.0 | кэш плагина `~/.claude/plugins/cache/anthropic-plugin-directory/sdd-superpowers/3.2.0-52d08018203e/` |
| spec-kit | `e7f44e2`, 2026-10-29 | клон `github/spec-kit` |
| BMAD-METHOD | `61e01f8`, 2026-10-18, ветка V7 preview alpha | клон `bmad-code-org/BMAD-METHOD` |
| GSD Core | `fdc4e7a`, 2026-10-29 | клон `open-gsd/gsd-core` |

Клоны — shallow, в `C:\Work\scratchpad\sdd-frameworks\`, вне
репозитория; scratchpad могут почистить — коммиты выше позволяют
восстановить. Пути в цитатах — от корня своего репозитория
или пакета.

spec-kit, BMAD и GSD разобраны отдельными агентами; цитаты,
на которых стоят выводы, сверены по файлам. Что не сверено,
помечено «по разбору агента».

Оговорки:

- BMAD: «**V7** is in preview alpha on this branch» (`README.md:18`),
  стабильная — v6.12; часть v6-скиллов в V7 удалена, выводы
  на v6 переносятся не целиком.
- GSD: исходный `gsd-build/get-shit-done` в архиве с 2026-06-26,
  развитие — в форке `open-gsd/gsd-core`.

## Короткий ответ

В прочитанных текстах о методологии отдельного момента проактивного
проектирования нет. Спека в них — «source of truth», и механика
нацелена на то, чтобы задуманное дошло до кода без потерь. Поиск
того, о чём запрос молчит, каждый фреймворк пристраивает сбоку —
как quality gate между спекой и планом. Отдельным шагом со своими
разделами в артефакте его сделал только GSD (`spec-phase`).

## Три разных механизма

Под «проактивностью» во фреймворках — три вещи, и ловят они разное.

1. **Проход по закрытой таксономии** — `clarify` spec-kit, edge probe
   GSD, чек-лист `sdd-review`. Систематичен, но видит только свои
   категории.
2. **Атака отдельным проходом с обратной установкой** — ревьюер
   архитектуры BMAD, FORCE stance и prohibition probe GSD. Ищет
   не пропуски, а несовместимость принятых решений и то, во что
   фича может «silently become».
3. **Генерация по техникам** — брейншторм и элиситация BMAD. Ведёт
   человек; источник вариантов, а не проверка.

Почему искать пропуски надо до проверки, обосновал только GSD —
замером (`gsd-core/references/edge-probe.md:17-25`): «A goal-backward
verifier only checks assertions that exist… the verifier is
*confidently wrong* about it (measured: ~0.93 confidence while
catching 0/12 omitted-edge defects…) versus 100% / 0.03 on edges
the spec did state). The fix is not a better verifier… The fix is
**spec completeness**». Это наш тезис о тихом провале сильной
модели — с цифрой.

## По фреймворкам

### OpenSpec 1.13.1

- Брейншторм — `explore`, входит в профиль `core`
  (`dist/core/profiles.js:11`): «This is a stance, not a workflow.
  There are no fixed steps, no required sequence, no mandatory
  outputs.» (`dist/core/templates/workflows/explore.js:45`).
- Совпадает с нашими соглашениями: «Do not ask the user to repeat
  facts you can verify» (`explore.js:8`), «Silence is not
  acceptance» (`:13`).
- Расходится: «Track decisions in the conversation, not in files»
  (`explore.js:13`). Риски — среди возможностей, не обязанность:
  «Surface risks and unknowns» (`:111`).
- `propose` спрашивает только о неясностях, которые «would
  materially affect scope, externally observable behavior,
  compatibility, or acceptance criteria»; остальное — «make
  a reasonable assumption and record it» (`propose.js:52`).
- Ошибки попадают в артефакты лишь формулировкой instruction:
  «Inputs, outputs, and error conditions»
  (`schemas/spec-driven/schema.yaml:61`); `design.md` условный —
  «create only if any apply» (`:158`).
- Атаки нет: `verify` сверяет код с артефактами после реализации.
- Кастомизация декларативная: граф артефактов в `schema.yaml`,
  `rules` по артефакту в `config.yaml`; instruction может передать
  работу скиллу — так `store-flow` зовёт `flow-step`.

### sdd-superpowers 3.2.0

- Брейншторм — `sdd-brainstorm`: вопросы по одному, 2–3 подхода,
  ADR на решение, `prd.md`, одобрение человека. Исследование влито
  в него в 3.0.0.
- Поиск умолчаний — чек-лист `sdd-review` (режим A): «Are there
  edge cases missing? (empty states, error states, permission
  boundaries)» (`skills/sdd-review/reference.md:38`); Error
  Scenarios в `spec.md` обязательны.
- Ревьюер PRD и ADR настроен на одобрение: «Approve unless there
  are serious gaps.»
  (`skills/sdd-brainstorm/spec-document-reviewer-prompt.md:57`).
- Неизвестное — `[NEEDS CLARIFICATION]`, без адресата; в одобренной
  спеке их быть не должно.
- Процесс зашит в тексты скиллов и `routing.md`, держат его хуки.

### spec-kit

- Брейншторма в ядре нет: `specify` идёт от описания прямо к спеке —
  «Make informed guesses based on context and industry standards»
  (`templates/commands/specify.md:123`).
- О части тем спрашивать запрещено: «Examples of reasonable defaults
  (don't ask about these)» (`specify.md:310`), среди них
  «Authentication method: Standard session-based or OAuth2 for web
  apps» (`:315`). Меток — «Maximum 3 [NEEDS CLARIFICATION] markers
  total» (`:128`), остальное агент угадывает.
- Проактивность ядра — необязательный `clarify`: скан по таксономии
  из 10 групп, в ней «Security & privacy (authN/Z, data protection,
  threat assumptions)» (`templates/commands/clarify.md:96`),
  «External services/APIs and failure modes» (`:100`),
  «Protocol/versioning assumptions» (`:102`), «Conflict resolution
  (e.g., concurrent edits)» (`:107`).
- Лимит: «Maximum of 5 total questions across the whole session»
  (`clarify.md:130`), отбор — «top 5 by (Impact * Uncertainty)
  heuristic» (`:138`), «Present EXACTLY ONE question at a time»
  (`:141`). Не влезшее — «flag them under Deferred with rationale»
  (`:237`), но только в отчёте в чате, файла под это нет.
- `checklist` — «UNIT TESTS FOR REQUIREMENTS WRITING»
  (`templates/commands/checklist.md:11`); пропущенный класс
  сценариев → «Are [scenario type] requirements intentionally
  excluded or missing? [Gap]» (`:221`).
- `analyze` проверяет согласованность написанного, не мир: «NEVER
  hallucinate missing sections» (`templates/commands/analyze.md:248`).
- Брейншторм и улики — в официальном необязательном расширении
  `assess`: «This stage exists to *challenge* the idea as much as
  support it» (`extensions/assess/commands/speckit.assess.research.md:7`),
  «Every claim must carry a citation or be flagged as an
  assumption.» (`:47`), раздел «Evidence Against the Idea» —
  «every time» (`:93`).
- Атака — только в сторонних расширениях каталога, они не читались:
  Red Team — «Adversarial review of functional specs before
  /speckit.plan… catch hostile actors, silent failures, and
  regulatory blind spots that clarify/analyze cannot»
  (`extensions/catalog.community.json:4924`); ThreatSpec — «STRIDE
  and AI/ML threat modeling» (`:6421`).
- Кастомизация — по разбору агента: хуки `before_<cmd>` /
  `after_<cmd>` в `.specify/extensions.yml`, presets
  (replace / prepend / append / wrap), workflow overlays.

### BMAD-METHOD, V7 alpha

- Брейншторм методичный, но цель — идеи: 108 техник; три установки,
  среди них «**Facilitator** (you never supply ideas — a forcing
  function for theirs)» (`skills/bmad-brainstorming/SKILL.md:12`);
  «Aim past 100 ideas; resist concluding.» (`:37`).
- Техники, близкие к поиску дыр
  (`skills/bmad-brainstorming/assets/brain-methods.csv`): Reverse
  Brainstorming — «'how could we make this fail?'» (`:18`),
  Assumption Reversal (`:22`), Chaos Engineering (`:56`).
- Элиситация — словарь атак, но по вызову человека
  (`skills/bmad-advanced-elicitation/assets/methods.csv`): Pre-mortem
  Analysis (`:60`), Assumption Audit — «rate each by confidence and
  impact - then stress-test the weakest» (`:65`), Security Audit
  Personas (`:70`), Boundary & Edge Case Sweep (`:72`).
- Атака по умолчанию — только у архитектуры: «Attack the spine as
  an adversary: construct two units one level down that each obey
  every AD to the letter yet still build incompatibly — clashing
  shared-data shapes, two owners of one entity, conflicting
  state-mutation paths. Every pair you find is a hole to close with
  a new or tightened AD.» (`skills/bmad-architecture/customize.toml:98`).
  Там же: «a whole dimension left silent… is the failure»
  (`skills/bmad-architecture/SKILL.md:76`).
- Ревью-линзы — только по вызову: «Never invoke this uninvited»
  (`skills/bmad-review/SKILL.md:3`); линза adversarial — «Find at
  least ten issues» (`skills/bmad-review/references/lens-adversarial.md:5`).
- Неизвестное с адресатом — ближе всех к нашему журналу
  (`skills/bmad-agent-po/assets/ticket-template.md:68-73`):
  «Assumption: [an unconfirmed choice; once confirmed, a dated
  Decision]», «Open question: [… what the source leaves open, and
  who waits …]», «Unknown: …», «Parked: …», «Source conflict:
  [… source vs code or another source]».
- Маршрут неизвестного: «if the repository can tell you, go look
  and fix the plan; if a human has to decide, add an `## Open
  Questions` entry. Do not invent the answer.»
  (`skills/bmad-build/step-02-plan.md:37`).
- Строже всех к уликам: «Never conclude from training data alone»
  (`skills/bmad-deep-recon/SKILL.md:16`); «The research firewall.
  Project context… shapes *what to ask*, never *what is true*»
  (`:17`); «A claim is a sentence with a source» (`:23`).
- Модели угроз нет — по разбору агента: безопасность — необязательный
  блок PRD, методы элиситации, персона в party mode.

### GSD Core

- Проактивность — отдельный шаг `/gsd-spec-phase`, необязательный,
  перед discuss:
  - раунд интервью «**Failure Analyst (round 4):** Find the edge
    cases that invalidate requirements.»
    (`gsd-core/workflows/spec-phase.md:43`);
  - edge probe — закрытая таксономия из 8 категорий
    (`gsd-core/references/edge-probe.md:70-79`): boundary,
    adjacency, empty, encoding, ordering, precision, idempotency,
    concurrency; «propose a CONCRETE candidate edge (not "consider
    boundaries")» (`spec-phase.md:344`); отклонить — только
    с причиной, «--auto never auto-dismisses» (`:544`);
  - prohibition probe — «What could this feature silently become
    that the author would NOT want, but the spec does not forbid?»
    (`gsd-core/references/prohibition-probe.md:53`).
- Пропуск шага не отменяет проб: без SPEC их запускает plan-phase,
  переключатель «default-ON»
  (`gsd-core/references/specless-probe-fallback.md:13`).
- Почему таксономия закрытая: «a fixed eight the author must
  explicitly clear beats thirty nobody finishes»
  (`edge-probe.md:64-65`).
- Ограничение для нас: «The classifier reads English; `text` does
  not have to be.» (`edge-probe.md:52`) — русским требованиям
  нужен `text_en` или явные `shapes`, иначе проба молчит.
- discuss-phase описательный: «Gray areas are **implementation
  decisions the user cares about**»
  (`gsd-core/workflows/discuss-phase.md:83`).
- Атака — установка проверяющих: «**FORCE stance:** Assume every
  plan set is flawed until evidence proves otherwise.»
  (`agents/gsd-plan-checker.md:30`); Pre-Mortem — «assume it has
  already failed. List the 3 most likely reasons for failure»
  (`gsd-core/references/thinking-models-planning.md:15`).
- Модель угроз — STRIDE в планировщике (`agents/gsd-planner.md:457`);
  аудитор после реализации проверяет только объявленное: «Does NOT
  scan blindly for new vulnerabilities»
  (`agents/gsd-security-auditor.md:16`).
- Улики в исследовании: «`[ASSUMED]` — based on training knowledge,
  not verified in this session» (`agents/gsd-phase-researcher.md:31`),
  рядом `[VERIFIED]` и `[CITED]`.
- Своя нестыковка: `new-project.md` отсылает к техникам «Surface
  assumptions / Find edges» в `questioning.md`, а в нём слов «edge»
  и «assumption» нет.

## Сравнение

| | Брейншторм | Поиск умолчаний | Атака | Неизвестное |
| --- | --- | --- | --- | --- |
| OpenSpec | `explore` — разговор без шагов, решения в нём | нет; формулировки instruction | нет | Open Questions в `design.md` |
| sdd-superpowers | `sdd-brainstorm`: 2–3 подхода, ADR | чек-лист `sdd-review` | ревьюер «Approve unless there are serious gaps» | `[NEEDS CLARIFICATION]` |
| spec-kit | в ядре нет; расширение `assess` | `clarify`: 10 групп, не больше 5 вопросов; `checklist` с `[Gap]` | только сторонние расширения | не больше 3 меток, остальное угадывается |
| BMAD V7 | 108 техник, ведущий без своих идей | Concern scan PRD; «dimension left silent» в архитектуре | ревьюер архитектуры по умолчанию: пары узлов, совместимых с каждым AD, но не друг с другом | `Open question … who waits`, `Unknown`, `Parked`, `Source conflict` |
| GSD | `explore`, `sketch`, `spike` | `spec-phase`: Failure Analyst, edge probe, prohibition probe; без SPEC — в plan-phase по умолчанию | FORCE stance проверяющих; STRIDE у планировщика | `[ASSUMED]`, `checkpoint:decision` |

## Проверка на edge cases рабочей задачи

Оценка, не прогон: какой механизм поймал бы пункт из списка
шага 2 плана.

| Edge case | Кто поймал бы |
| --- | --- |
| данные проекта уходят в модель CLI-агента | prohibition probe GSD; «threat assumptions» в `clarify` |
| несохранённые правки в открытой вкладке | concurrency в edge probe; «concurrent edits» в `clarify` |
| инъекции через содержимое файлов | никто по умолчанию: STRIDE у планировщика GSD, Security Audit Personas BMAD — по вызову |
| токен истекает посреди работы | concurrency («If interrupted») — частично |
| агент зацикливается на записи, нужны лимиты | idempotency; prohibition probe |
| несколько агентов на одном проекте | concurrency |
| бинарные файлы | encoding |
| пути с `../` | никто по умолчанию; частично «permission boundaries» в `sdd-review` |
| функцию выключили посреди сессии | concurrency — частично |
| совместимость схем инструментов | «Protocol/versioning assumptions» в `clarify` |

Поправка к предварительному выводу в плане («модель угроз
и жизненный цикл сессии чек-листом не ловятся»): верно для
чек-листа `sdd-review`, неверно в целом. Жизненный цикл сессии
таксономии GSD и `clarify` ловят по большей части. Не ловит ни одна
таксономия границу доверия — инъекции и `../`: это модель угроз,
а она у всех либо в планировщике, либо по вызову.

## Кандидаты для конвейера — решает человек

Решение 2026-10-29 — в плане, раздел «Решение по основе»: OpenSpec —
рамка, механики GSD — в ядре, BMAD — библиотека сбоку.

1. **Основа — OpenSpec, остальные — доноры.** Кастомизация
   декларативная, остальные зашивают процесс в тексты скиллов.
   Доноры: Error Scenarios и Given/When/Then — sdd-superpowers;
   правило улик и «Evidence Against» — `assess` spec-kit; «research
   firewall» — BMAD; FORCE stance — GSD; чек-лист `sdd-review` —
   нижняя планка атаки шага 7.
2. **Журнал решений — артефакт схемы, от которого зависит
   `proposal`.** Тогда его видит `openspec status`, а `explore`
   пишет его по instruction.
3. **Шаг поиска умолчаний — между брейнштормом и исследованием**,
   по образцу edge probe GSD:
   - закрытая таксономия под домен «агент ↔ API инструментов»:
     граница доверия, жизненный цикл сессии, одновременная работа
     человека и агентов, содержимое файла как инструкция,
     совместимость;
   - на каждую категорию — конкретный кандидат; отклонение —
     с причиной;
   - выход — записи журнала.

   До исследования, потому что именно он порождает вопросы
   с адресатом «материалы». Сейчас edge cases шага 2 — список,
   написанный вручную.
4. **Исходы записи журнала — по GSD, плюс вид из BMAD.** Specify →
   «решён», Dismiss с причиной → «решён: не применимо», Defer →
   «припаркован». Добавить вид «противоречие источников»
   (`Source conflict:` у BMAD): в заметках к v33 расхождения
   уже есть, а места для них в формате нет.
5. **Атака шага 7 — по образцу ревьюера архитектуры BMAD**: пары
   решений журнала, каждое верно само по себе, вместе несовместимы.
   Это та «подсветка несовместимого», что ждали от playground
   шага 5: находит её проход, playground показывает.

## Не разобрано

- Kiro: исходники закрыты, разбор документации остановлен.
- Сторонние расширения spec-kit Red Team и ThreatSpec — чужие
  репозитории, не читались.
- BMAD v6.12, стабильная, — читалась V7 alpha.
