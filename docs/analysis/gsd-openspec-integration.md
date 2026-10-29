# Разбор gsd-openspec-integration

Источник: `mshegolev/gsd-openspec-integration`, HEAD `8459e2f`
(2026-08-03), 12 коммитов за 2026-07-27…08-03, один автор, MIT.
Разбор 2026-10-29 по слову человека: «изучим в части нашей
тематики». **Клон удалён в тот же день** по слову человека:
«наработки автора как ошибки, а предложенные механики сохраним
в отчёте об исследовании, этот репозиторий можно удалять».
Восстановить: `git clone https://github.com/mshegolev/gsd-openspec-integration`,
`git checkout 8459e2f`. Номера строк ниже — на этот коммит.

Отчёт ниже написал субагент (Sonnet) по заданию: найти основные
механики связки и оценить, что переносимо в схему OpenSpec без
рантайма GSD. Ничего из репозитория не запускалось.

## Сверка отчёта

Утверждения отчёта сверены грепом по тексту; номера строк
у субагента местами уехали на единицы — ниже настоящие.

| Утверждение | Файл | Строка | Исход |
| --- | --- | --- | --- |
| механик GSD (edge/prohibition probe, Failure Analyst, Dismiss, FORCE stance) в capability нет | `capabilities/`, `docs/`, `openspec/` | — | подтверждено: ноль вхождений вне `examples/` |
| «OpenSpec owns WHAT and WHY. GSD Core owns HOW, WHO, WHEN, and EVIDENCE.» | `docs/adr/0001-openspec-as-specification-authority.md` | 19 (у субагента 13) | подтверждено |
| ADR пишет `^1.8.0` / `^1.6.0`, manifest — `>=1.6.0` | ADR `:61`, `capabilities/openspec/capability.json:9` | | подтверждено, расходятся |
| гейт `ship:pre`, предикат `artifact-frontmatter-equals`, `blocking: true` | `capability.json` | 121, 124, 131 | подтверждено |
| `status: passed` «only when every in-scope requirement resolved to `PASS` or `NOT_APPLICABLE`» | `skills/openspec-verify/SKILL.md` | 67 | подтверждено |
| пять классов расхождений исполнителя | `skills/openspec-execute/SKILL.md` | 38–42 | подтверждено |
| «Skills are prose, not code. There is no unit-test suite» | `docs/FINAL-REPORT.md` | 103 | подтверждено; гейт «Inferred, not observed» — `:85` |
| «What is NOT proven: that GSD's own ship command honours the gate at runtime» | `examples/…/artifacts/ship-gate-check.txt` | 27 | подтверждено; «exposes no gate-evaluation command» — `:23` |
| схема улик: `minItems: 1`, `status_reason` обязателен | `docs/EVIDENCE-SCHEMA.json` | 64, 82 | подтверждено |
| gsd-core локальный — 1.19.0, `evaluatePredicate` описан | `upstream/gsd-core/package.json:3`, `CONTEXT.md:461` | | подтверждено |
| форма `fragment.path` — поддерживает ли gsd-core (субагент не проверял) | `upstream/gsd-core/docs/how-to/develop-a-capability.md` | 164 | **закрыто**: «Use `fragment.path` for prompt text longer than a short sentence» |

Вывод субагента совпадает с моим чтением changelog OpenSpec и
исходников gsd-core (`step0-sources.md`, раздел OpenSpec): готовой
связки механик нет, есть связка файлов и дисциплина ссылок.

## Уроки: что у автора не сработало

Решение человека: наработки автора учитываются как ошибки, не как
образец. Каждый пункт стоит на наблюдении из отчёта ниже; рядом —
наш инвариант, который этот случай повторяет.

1. **Гейт по одному полю, которое пишет сама модель.** `ship:pre`
   читает `status` и «nothing else»; `status` ставит скилл-проза
   по собственному правилу «passed only when…». Это гейт, вызываемый
   дисциплиной исполнителя, — отказ, который у нас уже наблюдён.
   Урок: вердикт либо ставит код по уликам, либо гейта нет и так
   и сказано.
2. **Схема проверяет форму, а не отношение.** `EVIDENCE-SCHEMA.json`
   требует хотя бы одну улику и причину у статуса, но не проверяет,
   что `result` улики согласован со `status`, и ничто не связывает
   `EVIDENCE.json` с `OPENSPEC-VERIFICATION.md`. Зелёный проходит
   на выдумке с правильной формой. Урок: валидатор формы без
   проверки связи даёт ложную уверенность дороже, чем её отсутствие.
3. **Идентификаторы контрабандой в тексте.** `<!-- openspec-id -->`
   после заголовка попадает в `requirement.text` при `openspec show`,
   и каждый потребитель чистит его регуляркой. Урок: ID, которого
   нет у рамки, либо вводится в рамку (форк — у нас есть), либо
   живёт рядом описанием и пересопоставляется, а не внутри текста,
   который рамка считает своим.
4. **«Inferred, not observed».** Гейт, проекция `REQUIREMENTS.md`,
   `repair`, режимы `forensic` и `release` специфицированы и не
   прогнаны; один change, одна фаза, демо из одного требования.
   Урок наш, повторённый: статус «берём» только с артефактом
   прогона; здесь всё — «кандидат», включая то, что мы берём.
5. **Версия привязана в двух местах и по-разному**: ADR `^1.8.0`,
   манифест `>=1.6.0`; upstream движется быстро, теста совместимости
   нет, и через три месяца совместимость с текущими версиями
   неизвестна. Урок: привязка к источнику в одном месте, с хешем,
   и с проверкой, которая падает при расхождении.
6. **Второй владелец у одного знания.** `REQUIREMENTS.md` как
   «generated, synced projection» требований OpenSpec — вторая копия,
   синхронизируемая прозой, которую ни разу не запускали. Урок: одно
   отношение — одна реализация; проекция без механизма синхронизации
   — это расхождение с отсрочкой.
7. **Одиннадцать скиллов-прозы и ни одного теста на поведение**:
   тесты только на установщик и на форму демо. Урок: приём ценен
   наблюдённым отказом, а отказы не наблюдают там, где не запускают.

Что из отчёта остаётся в силе как материал: схема вердикта
с запретом PASS без улики (п. 5 отчёта), пять классов расхождений
исполнителя (п. 4, `openspec-execute`), mutation check запрещающего
требования (п. 5). Все три — текст в instruction, все три —
«кандидат» до прогона.

---

## Отчёт субагента

Пути ниже даны от корня репозитория. Цитаты и номера строк сверялись
по файлам, кроме пунктов, помеченных «по разбору агента». Ничего
из репозитория не запускалось.

### Сводка

- Главное: **в репозитории нет ни edge probe, ни prohibition probe,
  ни Failure Analyst, ни исходов Specify/Dismiss/Defer, ни FORCE
  stance.** Поиск по `edge probe|prohibition|failure analyst|dismiss|FORCE`
  находит только слово «prohibition» в демо (`SHALL NOT` в требовании)
  и обычное «defer». Репозиторий связывает файлы и вешает на связь
  дисциплину ссылок REQ-ID. Механики GSD над требованиями он
  не прогоняет.
- Это один GSD-capability `openspec` v0.2.0: 4 текстовых фрагмента
  хуков, 11 SKILL.md, один блокирующий гейт `ship:pre`. Кода почти
  нет: единственный исполняемый скрипт, `inject-ids.js`, лежит
  в `examples/`.
- Авторитет: OpenSpec отвечает за WHAT/WHY, GSD за HOW/WHO/WHEN/EVIDENCE.
  `REQUIREMENTS.md` в GSD становится генерируемой проекцией требований
  OpenSpec.
- Ценное для переноса: (а) схема вердикта шести уровней с запретом
  PASS без улики; (б) классификатор расхождений из пяти классов;
  (в) девять классов дрейфа; (г) mutation check как приём проверки
  запрещающего требования. Всё это проза, и в instruction OpenSpec
  она ложится.
- Зрелость низкая и названа автором: v0.1.0, 12 коммитов
  за 2026-07-27…08-03, тестов самой capability нет. Ship gate
  на практике ни разу не наблюдали заблокированным.
- GSD-рантайм нужен только для проводки по точкам и для гейта.
  Содержательная часть от рантайма не зависит.

### 1. Направление и авторитет

- `docs/adr/0001-openspec-as-specification-authority.md:19`:
  «**OpenSpec owns WHAT and WHY. GSD Core owns HOW, WHO, WHEN, and
  EVIDENCE.**»
- Там же: OpenSpec «is the sole normative source for product
  requirements and scenarios»; поведение «does not exist, for audit
  purposes» без `SHALL`/`MUST` и сценария Given/When/Then.
- `REQUIREMENTS.md` остаётся «a **generated, synced projection** of
  OpenSpec requirements».
- Спецификация здесь — `openspec/specs/**` и
  `openspec/changes/<id>/specs/`. План — `PLAN.md` GSD, его раскладку
  по волнам ведёт GSD. Список задач OpenSpec (`tasks.md`) только
  отображается на `PLAN.md`, но не заменяет его:
  `openspec-plan/SKILL.md:41` «Unmapped OpenSpec tasks are reported,
  not auto-created into plans — task decomposition remains the
  planner's job».
- Соответствие «OpenSpec change ↔ GSD phase» (ADR, таблица
  альтернатив): «Change ↔ phase … is the correct mapping».
- `/gsd:spec-phase` (SPEC.md) при связанном change становится
  вторичным и необязательным (ADR, раздел Negative). В самой
  capability `SPEC.md` не используется вовсе: grep по `capabilities/`
  находит только `<spec_lock>` как образец для `<openspec_lock>`.

### 2. Карта артефактов

`docs/ARCHITECTURE.md` §4 и §7:

| GSD | OpenSpec | Связь |
| --- | --- | --- |
| `REQUIREMENTS.md` | `specs/**/spec.md` | проекция, пишет `openspec-plan` |
| `CONTEXT.md` (`<canonical_refs>` + `<openspec_lock>`) | `proposal.md`, `design.md` | ссылкой, не копией |
| `PLAN.md` | `tasks.md` | задачи цитируют REQ-ID |
| `SUMMARY.md` | — | вход для `openspec-verify` |
| `SPEC.md` | — | не затронут |

- `OPENSPEC-LINK.md` — указатель фазы в OpenSpec. Frontmatter:
  `change_id`, `requirement_ids`, `scenario_ids`, `ids_pending`,
  `linked_at` (`fragments/discuss-post.md:24-32`). В демо добавлены
  `archived: true` и `linked_by`. Текст требований он «deliberately
  does **not** copy».
- `OPENSPEC-VERIFICATION.md` — отчёт `verify:post` по шести уровням.
  Frontmatter: `status: passed|gaps_found|human_needed`, таблица
  требований (`skills/openspec-verify/SKILL.md:55-65`).
- Стабильные ID: OpenSpec их не имеет, поэтому вводится комментарий
  `<!-- openspec-id: REQ-X-001 -->` после заголовка
  (`ARCHITECTURE.md` §6). Автор честно описал цену: комментарий
  попадает в `requirement.text` и `rawText` при `openspec show`,
  и потребитель обязан вычищать его регуляркой
  (`docs/FINAL-REPORT.md:93-97`).

### 3. Фрагменты хуков и capability.json

Точки подключения (`capabilities/openspec/capability.json`):

- `discuss:pre` → `orchestrator`;
- `discuss:post` → `orchestrator`, производит `OPENSPEC-LINK.md`;
- `plan:pre` → `planner` и `checker`;
- шаг `verify:post` → скилл `openspec-verify`, `onError: halt`;
- гейты: `plan:post` типа `agentVerdict`, `blocking: false` (`:117`);
  `ship:pre` типа `predicate` `artifact-frontmatter-equals`, поле
  `status`, значение `passed`, `blocking: true` (`:121-131`).

Что делает текст каждого фрагмента:

- `discuss-pre.md`. Читает `OPENSPEC-LINK.md`, иначе вызывает
  `openspec list --json`. Затем `openspec status --change ... --json`
  проверяет, что proposal, specs и design в состоянии done. При
  отсутствии change агент должен остановиться. Текст: «do not
  fabricate requirements».
- `discuss-post.md`. Выполняет `openspec show --json`, дописывает блок
  `<openspec_lock>` в `<canonical_refs>` и пишет `OPENSPEC-LINK.md`.
  Шаг назван механическим: «this is mechanical».
- `plan-pre-planner.md`. Каждая задача `PLAN.md` цитирует REQ-ID
  и SCN-ID. Поведение сверх спеки — это `OUT_OF_SCOPE_DISCOVERY`: его
  нельзя ни молча добавить в объём, ни молча подогнать спеку под
  лёгкое.
- `plan-pre-checker.md`. Каждый `requirement_id` должен встречаться
  в acceptance criteria хотя бы одного `PLAN.md`. Непокрытое —
  finding «same severity class as an uncovered `D-NN` decision».

**Ответ на главный вопрос:** edge probe и prohibition probe GSD
не прогоняются. Проверка покрытия — это сопоставление строк, то есть
наличие REQ-ID в плане. Нет ни поиска граничных случаев
в требованиях, ни анализа запретов, ни исходов Specify/Dismiss/Defer.
Единственный ближайший аналог — явное «explicitly defer with
a reason» в checker и requirement `NOT_APPLICABLE` с причиной.

Проводка: capability использует `fragment.path`; gsd-core 1.19.0
эту форму поддерживает (`docs/how-to/develop-a-capability.md:164`,
сверено при приёмке отчёта).

### 4. Скиллы

Все описаны как проза с секциями Purpose / Algorithm / Guardrails.
Скриптов в них нет.

- **bootstrap**: `openspec init --tools claude,codex,opencode`
  и `gsd-tools capability install`. Опора: CLI OpenSpec, `gsd-tools`.
- **bridge-explore**: делегирует штатному `/opsx:explore` («does not
  reimplement», `SKILL.md:36`). **Тонкая обёртка**, штатный
  `/opsx:explore` не заменяет.
- **bridge-propose**: вызывает штатные `/opsx:propose` или `/opsx:ff`,
  затем `openspec validate --change ... --json` и сверяет объём
  с целью фазы (`SKILL.md:37-41`). **Валидирующая обёртка**, штатный
  `/opsx:propose` не заменяет. «Never writes OpenSpec artifacts
  directly».
- **plan**: синхронизирует `REQUIREMENTS.md` (только строки
  с маркером `source: openspec:`) и отображает `tasks.md`
  на `PLAN.md`. Отвечает на `plan:post` как advisory. Опора:
  `id-registry.json`, проза.
- **execute**: не исполнитель, а таблица из пяти классов расхождений
  `SPEC_AMBIGUITY`, `SPEC_CONFLICT`, `DESIGN_CONFLICT`,
  `IMPLEMENTATION_BLOCKER`, `OUT_OF_SCOPE_DISCOVERY` с действием
  на каждый (`SKILL.md:38-42`). Ни к какой точке не подключён:
  «advisory text an executor reads».
- **verify**: шесть уровней — задачи, сценарии, требования,
  соответствие design, регрессия, дрейф. Тесты он сам не гоняет.
  Опора: `openspec validate`, git, чтение `SUMMARY.md`.
- **audit**: оркестрирует verify, drift и traceability в пяти режимах
  глубины. Проза.
- **drift**: девять классов дрейфа (список в `examples/…/DRIFT.md:11-21`).
  Проза.
- **traceability**: назначает ID, генерирует `TRACEABILITY.md`
  и `EVIDENCE.json`. Единственный скилл, которому разрешено писать
  внутри `openspec/`. Исполняемая реализация — только
  `examples/health-check-demo/tools/inject-ids.js`.
- **repair**: четыре маршрута исправления — код, спека, новый change,
  блок. Не исполнялся (`FINAL-REPORT.md:89`).
- **archive**: `openspec archive <id>` после успешного ship. Подгонять
  статус под архивацию запрещено.

### 5. Улики, трассируемость, дрейф, аудит, гейт

Код (проверяемый машиной):

- `docs/EVIDENCE-SCHEMA.json` — JSON Schema 2020-12. Требует
  `evidence` с `minItems: 1` (`:64`). Статусы
  `PARTIAL|NOT_APPLICABLE|BLOCKED|REMOVED` требуют непустой
  `status_reason` (`:82`). Типы улик требуют поля: `automated_test` —
  `command` и `result`; `manual_check` — `observer`, `result`,
  `detail`; `code_reference` — `file` и `lines`. Схема не проверяет,
  что `result` улики согласован со `status` (например `PASS` при
  `result: failed`) — наблюдение из чтения схемы.
- `scripts/smoke-test.sh` валидирует демо-`EVIDENCE.json` по этой
  схеме через python `jsonschema`.
- `inject-ids.js` (144 строки) — детерминированная раздача ID.
  «Reference implementation» алгоритма, лежит в демо и в capability
  не входит (`FINAL-REPORT.md:201`).

Проза, которую исполняет модель: `TRACEABILITY.md`, `DRIFT.md`,
`AUDIT-SUMMARY.md`, `OPENSPEC-VERIFICATION.md`, `id-registry.json`
и `EVIDENCE.json` в части заполнения — их содержимое пишет агент.
Поле `determined_by: agent_judgment` в демо-улике это прямо фиксирует.

Что не даёт считать артефакт готовым по одному наличию файла:

- Вердикт `status` в frontmatter и правило: `passed` пишется «only
  when every in-scope requirement resolved to `PASS` or
  `NOT_APPLICABLE` (with a reason) and zero `openspec-drift` findings
  are unresolved» (`openspec-verify/SKILL.md:67`).
- Отсутствие теста = `NOT_TESTED`, блокирующее состояние.
- Гейт `ship:pre` читает только поле `status`
  (`01-OPENSPEC-VERIFICATION.md`: «reads the `status` field above and
  nothing else»).
- Держится это на том, что скилл правдиво заполнит frontmatter.
  Схема проверяет форму `EVIDENCE.json`, но не связь между
  `EVIDENCE.json` и `status` в `OPENSPEC-VERIFICATION.md`. Этой связи
  в коде нет (`smoke-test.sh` проверяет `status` как равенство
  `passed`).
- `artifacts/ship-gate-check.txt:27`: «What is NOT proven: that GSD's
  own ship command honours the gate at runtime». Гейт тестировался
  лишь вычислением предиката над подменённым frontmatter.
- Mutation check (`artifacts/mutation-check.txt`): автор намеренно
  нарушил запрещающее требование и увидел 2 упавших теста из 5;
  нарушение откатил, тесты вернулись к 5/5. Это и есть «проверка
  запрета» этого репозитория. Она ручная и демонстрационная.
  В механику capability она не вшита.

### 6. Зрелость и версии

- Версия capability: `0.2.0` (`capability.json:4`); релиз описан как
  v0.1.0 (`FINAL-REPORT.md:3`).
- Версии: GSD Core `engines.gsd >=1.6.0` (`capability.json:9`),
  разрабатывалось на 1.8.0 и OpenSpec 1.6.0 (`README.md:11,48,332`).
  ADR пишет `^1.8.0` и `^1.6.0` (`:61`) — **ADR и manifest
  расходятся**. Для OpenSpec 1.15.0 и GSD Core 1.19.0 совместимость
  не проверена.
- Тесты: `tests/install-host-skills.sh` проверяет только установщик —
  наличие SKILL.md для Claude, Codex и OpenCode и непереписывание
  чужих файлов. `scripts/smoke-test.sh` (26 проверок) проверяет
  регистрацию, число хуков, отсутствие коллизий ключей config,
  `openspec validate --all`, схему и состояние демо. Поведение
  скиллов не проверяет никто: «Skills are prose, not code. There is
  no unit-test suite» (`FINAL-REPORT.md:103`).
- Названо автором не сделанным (`FINAL-REPORT.md`): гейт ни разу
  не наблюдался блокирующим («Inferred, not observed», `:85`);
  `openspec-repair`, режимы `forensic` и `release`, проекция
  `REQUIREMENTS.md` не запускались на реальных данных; один change
  и одна фаза; коллизия дубликатов заголовков; нет дистрибуции.
- Что устарело: утверждение «gsd-tools exposes no gate-evaluation
  command» (`ship-gate-check.txt:23`). В `gsd-core/CONTEXT.md:461`
  (1.19.0) описан общий вычислитель предикатов `evaluatePredicate`.
  Ограничение автора, вероятно, снято в новом GSD — по чтению одного
  абзаца, поведение не проверялось.
- Демо: одно требование с запретом, 2 MUST и 3 сценария, 5 тестов.

### 7. Что переносимо в схему без GSD

| механика | где | код или проза | нужен ли рантайм GSD | переносимо в схему OpenSpec |
| --- | --- | --- | --- | --- |
| Дисциплина «не выдумывать требования, при расхождении — классифицировать» | `fragments/plan-pre-planner.md`; `openspec-execute/SKILL.md:38-42` | проза | нет | **да**: в instruction `tasks`/`design` и в `rules` |
| Классификатор из 5 классов расхождений с действием на каждый | `openspec-execute` | проза | нет (ссылки на `gsd-tools state add-blocker` и `<deferred>` заменяются) | **да**, нужна правка маршрутов под наши артефакты |
| Покрытие требований задачами по REQ-ID (planner цитирует, checker сверяет) | `plan-pre-planner.md`, `plan-pre-checker.md` | проза | нет | **да**: instruction `tasks` и `rules`; но сверка идёт по ID, а ID в OpenSpec нет — нужна своя схема ID |
| Стабильные ID `<!-- openspec-id -->` | `ARCHITECTURE.md` §6; `inject-ids.js` | код (в демо) + проза | нет | **с правкой**: instruction `specs` может требовать ID при записи; автораздачу без скрипта и `id-registry.json` придётся упростить; комментарий попадает в `requirement.text` |
| Шесть уровней проверки и запрет PASS без улики, `NOT_TESTED` как блокирующее состояние | `openspec-verify/SKILL.md:38-50,67` | проза | нет | **да** как instruction артефакта-вердикта; «готовность по наличию файла» в OpenSpec остаётся, вердикт держится на дисциплине модели |
| Схема улики (обязательный `status_reason`, `observer`, `command` по типу) | `docs/EVIDENCE-SCHEMA.json` | код (JSON Schema) | нет, но валидатор надо вызывать снаружи | **с правкой**: сам файл схемы переносим; в OpenSpec нет хука, который запустил бы валидацию, — нужен внешний скрипт или правка OpenSpec |
| Девять классов дрейфа | `openspec-drift`; `DRIFT.md:11-21` | проза | нет | **да**, но тяжёлая и держится на модели |
| Mutation check запрещающего требования | `artifacts/mutation-check.txt` | ручная процедура | нет | **да** как текст instruction; здесь как механика не оформлена |
| Блокирующий ship gate по `status: passed` | `capability.json:121-131` | декларативный предикат | **да** (гейт исполняет GSD) | **нет**; в OpenSpec гейтов нет. Максимум — правило в `rules` или дисциплина `/opsx:archive` |
| `plan:post` advisory «N/M сценариев покрыто» | `capability.json:109-118`; `openspec-plan` | agentVerdict | да | **с правкой**: текст в instruction `tasks` как самопроверка |
| `<openspec_lock>` в `CONTEXT.md` и `OPENSPEC-LINK.md` | `discuss-post.md` | проза | да (`.planning/`, `CONTEXT.md`) | **нет** — у нас связь с OpenSpec нативная; идея «лочить объём ссылкой, а не копией» переносима |
| Проекция `REQUIREMENTS.md` | `openspec-plan` | проза, ни разу не запускалась | да | **нет** |
| Режимы аудита quick…forensic | `openspec-audit` | проза | нет | **с правкой**: сводка поверх verify/drift; объёмно |
| Правка самого OpenSpec | — | — | — | нужна, чтобы (1) нативные ID требований, (2) вердикт, влияющий на `openspec status`; здесь оба обходятся комментариями и внешним предикатом |

**Вывод для нашей задачи.** Для edge probe, prohibition probe, Failure
Analyst, Specify/Dismiss/Defer и FORCE stance здесь переносить нечего:
их тут нет, текст придётся писать самим по исходникам
`upstream/gsd-core`. Из этого репозитория стоит брать три вещи: схему
вердикта с запретом PASS без улики, таблицу классов расхождений
и подход к проверке запрета через mutation check. Ограничение держим
в уме: вердикт и улики здесь держатся на добросовестности модели,
а не на механизме, и сами авторы это признают.
