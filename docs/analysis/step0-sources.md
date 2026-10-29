# Шаг 0: чтение источников

Чтение 2026-10-29 по списку шага 0 плана `docs/plan-flexible-pipeline.md`,
в объёме, который назвал человек: `change-intake`, `change-drafter`,
схема `store-flow`, плагин `playground`, свежие GSD и OpenSpec.
Исходники GSD и OpenSpec лежат в `upstream/` внутри проекта.

Не читались: `mattpocock-skills` и `sdd-superpowers` (на этой машине
не установлены), `fact-keeper` и `source-researcher` (в объём не вошли).
Пути цитат — от корня своего репозитория или пакета.

| Источник | Версия | Где читали |
| --- | --- | --- |
| `change-intake`, `change-drafter`, `flow-step`, схема `store-flow` | ветка `doc/variant-a-vs-plans` | `X:\skills-store` (на рабочей машине — `gigacode-skills/skills/…`) |
| playground | плагин marketplace `claude-plugins-official` | `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/playground/` |
| GSD Core | `e2cd587`, 2026-10-29, v1.18.0+133 | `upstream/gsd-core`, свежий клон `open-gsd/gsd-core` |
| OpenSpec | 1.15.0, `6d04a1b5`, 2026-10-24 | `upstream/openspec`, свежий клон `Fission-AI/OpenSpec` |

## Сводка вердиктов

| Источник | Вердикт | Что берём |
| --- | --- | --- |
| `fork-form.md` | **берём как есть** — соглашением, без скрипта | строка улики, одна рекомендация, статус из слова человека, таблица отказов |
| `grill-form.md` | **берём как есть** — соглашением | вопрос «что ничем не подкреплено», линзы с «чего не репортить», покрытие поимённо, нет второго такта |
| `approve-form.md` | **дорабатываем** | список исходов пункта; слово к хешу — без скрипта не держится, остаётся дата и текст |
| `change-intake/SKILL.md` | **механику без кода** | тип пункта «из файлов / от человека», предпосылка вопроса, не больше двух кругов, явный ноль |
| `change-drafter` | **механику без кода** | карта опор «фраза :: ключи», слово `предположение` с дорогой, «решение излагаешь, не принимаешь» |
| схема `store-flow` | **образец формы, не содержания** | instruction, которая передаёт шаг скиллу и останавливается; для сильной модели instruction несёт механику сама |
| playground | **переписываем** (как и ждали) | единый объект состояния, промпт только из одобренного, статусы pending/approved/rejected, канва со стрелками зависимостей |
| GSD `spec-phase` + `edge-probe` + `prohibition-probe` | **механику текстом** | перспективы интервью, числовой гейт, восемь категорий, исходы Specify/Dismiss-с-причиной/Defer, вопрос о «чем это станет» |
| GSD `discuss-phase` + `context.md` | **механику текстом** | «серые зоны», что у человека не спрашивают, запись D-NN с обратимостью, «Deferred Ideas» |
| OpenSpec 1.15.0 | **рамка, форк в `upstream/`** | граф артефактов, `rules` на артефакт, `/opsx:continue` с делегированием скиллу; что менять в коде — после первой схемы |

## change-intake

Скилл держится на скрипте: «**Чек-лист пишет скрипт, модель называет
тип и текст своих пунктов.**» (`change-intake/SKILL.md:16`). Для
сильной модели скрипт уходит, но пять правил переносятся соглашением:

- **тип пункта** — «У человека спрашивается только то, чего нельзя
  проверить по файлам» (`SKILL.md:19`); в журнале это адресат
  «материалы» против «человек»;
- **предпосылка** — «Вопрос с неотвеченной предпосылкой в порцию
  не входит вовсе: ответ на него до ответа на предпосылку — догадка»
  (`SKILL.md:105`); в журнале — поле «зависит от»;
- **выход по числу** — «конец цикла решает арифметика, а не ощущение
  собранности» (`SKILL.md:110`) и «**Кругов не больше двух.**»
  (`SKILL.md:187`); план уже взял второе, первое — нет;
- **явный ноль** — «Ноль вопросов человеку — законный исход, но
  только явный» (`SKILL.md:285`);
- **улика сверяется** — «**Улика сверяется с файлом дословно**»
  (`SKILL.md:125`). Без скрипта сверяет тот, кто читает журнал:
  грепом по цитате. Это и есть место, где соглашение слабее
  скрипта — см. «Что это меняет в плане».

### fork-form.md — берём как есть

Форма развилки совпадает с форматом записи журнала из плана почти
строчно, и она проверена в эксплуатации:

- улика — `- улика: <провенанс> · «<цитата>»`, «**Цитата сверяется
  с файлом дословно**» (`references/fork-form.md:36`);
- «**Рекомендация** — ровно одна, метка названной опции»
  (`fork-form.md:39`);
- «**Статус выводится из слова человека**, а не хранится рядом
  с ним» (`fork-form.md:75`) — статусов «открыт / решён» в журнале
  не пишут, их читают по наличию слова; в формате плана поле
  `статус` лишнее при `решение`, нужен только `припаркован`;
- таблица «Что отвергается» (`fork-form.md:47` и далее): опция без
  улик, улика без провенанса, цитаты нет в файле дословно, слово
  человека в черновике — это и есть чек-лист самопроверки для
  модели, пишущей развилку.

Разделы постановки (`fork-form.md`, «Разделы постановки»): Decisions —
со словом, Open Questions — без слова, Risks — улики за отвергнутые
опции. План шага 6 говорит то же.

### grill-form.md — берём как есть

Атака шага 7 описана здесь целиком:

- «не «чего не хватает», а «какое утверждение ничем не подкреплено»»
  (`references/grill-form.md:4`);
- у каждой линзы «рядом с «что искать» стоит «чего не репортить»:
  без второй половины гриль репортит стиль»;
- «Второго такта нет: модель не перечитывает свою находку и не судит
  её — судила бы та же модель, что спрашивала» (`grill-form.md:31`);
- «Молчание по разделу читалось бы как «претензий нет», поэтому
  непройденное называется поимённо» (`grill-form.md:81`);
- «Гриль к утверждённому черновику **отзывает approve**»
  (`grill-form.md:104`).

Без скрипта покрытие по разделам держит форма ответа: раздел либо
с вопросами, либо `чисто`, в конце строка конца. Это соглашение
проверяется глазами за секунду, и его стоит оставить дословно.

### approve-form.md — дорабатываем

Остаток при approve: `отложен` и `не узнать по файлам` идут
в Open Questions, `отклонён` и `несущественен` — нет
(`references/approve-form.md:8`, таблица у `:26`). Список исходов
берём. Слово к хешу черновика без скрипта не живёт — остаётся
дата и слово дословно, как в журнале.

## change-drafter — механику без кода

Главное правило скилла — «**Подаётся реестр, а не черновик**»,
«черновик целиком модель не видит ни разу» (`change-drafter/SKILL.md:16`,
`:18`) — компенсация узкого канала, в плане снята. Нарезка «Факты
сверх 25 режутся частями» (`SKILL.md:141`) и «Ответ пишет **одну**
секцию» (`SKILL.md:142`) — то же. Остаются три приёма, которые
не зависят от канала:

- **карта опор** — «Карта — строка на фразу: `фраза написанного ::
  ключи записей`» (`SKILL.md:160`); для сильной модели это способ
  сделать утверждение артефакта проверяемым грепом;
- **названное предположение** — «Фраза, выведенная не из записей,
  помечается словом `предположение` и причиной — **и в карте,
  и в самом тексте**» (`SKILL.md:163`), с дорогой `проверить`
  (исследователь) либо `решить` (человек) — это адресат парковки
  из плана, но на уровне фразы;
- **вес, не доля** — «Предложение с числом или словом модальности
  обязано стоять на записи либо быть помечено» (`SKILL.md:189`).

Форма design: «**Решение уже принято человеком — ты его излагаешь,
а не принимаешь.**» (`references/design-form.md:3`) и «**Хотя бы одна
фраза опирается на решение человека**» (`design-form.md:46`) —
в instruction `design.md` переносится дословно. Гид секций
(`references/proposal/section-guide.md:15`): роль секции `форма` /
`сводка` / `перенос` — различение «что пишет модель, что ставит
скрипт» для схемы без скрипта упрощается до «что пишет модель, что
переносится из журнала дословно».

Слово на proposal «поверх потерянных фактов не даётся» (`SKILL.md:218`)
— без скрипта потерянные факты никто не считает. Это второе место,
где соглашение слабее скрипта.

## Схема store-flow и flow-step — образец формы

Instruction каждого артефакта однотипна: «Загрузи скилл `flow-step`
и заведи им шаг `intake`. Скилл заводит в реестре задачу приёма
и возвращает управление.» и «Файл не пиши сам»
(`config/openspec/schemas/store-flow/schema.yaml:16`, `:19`).
Переходник объясняет, зачем: «Граф схемы засчитывает шаг
по существованию файла, и артефакт, написанный мимо исполнителя,
уедет дальше без его приёмки» (`flow-step/SKILL.md:62`); «Не исполняй
задачу в том же ходе» (`:66`) — предел глубины субагентов.

Для symphysis это образец того, как instruction передаёт работу
и останавливается, — и одновременно образец дыры, которую план
закрывает вердиктом во frontmatter. Содержание шагов не берём:
при сильной модели instruction несёт механику сама, без реестра
задач и исполнителей.

## playground — переписываем

Плагин — генератор одноразовых HTML по шаблону: «Single HTML file.
Inline all CSS and JS. No external dependencies.» (`skills/playground/SKILL.md:29`),
«Prompt output. Natural language, not a value dump.» (`:31`), «Keep
a single state object.» (`:38`). Шаблоны не читают внешних данных —
данные встраиваются в HTML при генерации, — и результат уходит только
копированием промпта. Ни один шаблон не подходит как есть, два дают
части:

- `templates/document-critique.md` — статусы `pending / approved /
  rejected` в объекте предложения (`document-critique.md:54`)
  и «Generates a prompt only from approved suggestions and user
  comments» (`:40`): это и есть слово человека по развилке, которое
  агент вносит в журнал;
- `templates/concept-map.md` — «The interactive visual IS the control»
  (`concept-map.md:21`), среди тем — «Task decomposition (goals →
  sub-tasks with dependency arrows, knowledge tags)» (`:72`): канва
  со стрелками под дерево `зависит от`.

Что переписать: фиксированный просмотрщик с встроенным JSON журнала
(шаблон один, меняются данные), статусы на развилке — слово
человека, дерево по `зависит от`, подсветка несовместимого — своя
часть, в шаблонах её нет. Результат — промпт в буфер, который агент
вносит в журнал: из трёх вариантов плана это единственный, который
шаблоны уже умеют. Мелочь: «run `open <filename>.html`» (`SKILL.md:25`)
— на Windows `start`.

## GSD Core — механику текстом

Дельта от разобранного `fdc4e7a` до `e2cd587`: 20 файлов, из них
`.md` — только `CONTEXT.md`, `docs/INVENTORY.md`,
`docs/reference/roadmap-phase-entry.md`; цитируемые файлы не менялись,
разбор `sdd-frameworks-proactive-design.md` действителен на HEAD.

### spec-phase — интервью с числовым гейтом

- пять перспектив интервью, Failure Analyst — четвёртая: «Find the
  edge cases that invalidate requirements.»
  (`gsd-core/workflows/spec-phase.md:43`); «**Max 6 rounds.** Each
  round: 2–3 questions max.» (`:136`) — порция вопросов, как в intake;
- гейт — четыре измерения с весами и минимумами, «**Gate:** ambiguity
  ≤ 0.20 AND all dimensions ≥ their minimums → ready to write SPEC.md»
  (`:20`). Это число там, где у плана в «Как поймём» числа нет;
- исходы по каждому кандидату: «**Specify it**», «**Dismiss
  (reason)** → mark `dismissed` with a required non-empty reason»,
  «**Defer**» (`:347`, `:349`); мягкий гейт — «Write SPEC.md anyway —
  flag unresolved» (`:175`); «`--auto` NEVER auto-dismisses
  a prohibition — a wrong dismissal is the exact silent failure this
  probe eliminates» (`:460`).

Шаблон SPEC: «**Every requirement needs all three fields:** Current /
Target / Acceptance» (`gsd-core/templates/spec.md:315`); «**Interview
Log is evidence of rigor.**» (`:322`) — след интервью в артефакте,
не в контексте; «**SPEC.md is a one-way door for requirements.**»
(`:326`).

### edge-probe и prohibition-probe

- таксономия — восемь категорий таблицей (`gsd-core/references/edge-probe.md:72`),
  «a fixed eight the author must explicitly clear beats thirty nobody
  finishes» (`:64`); «**Dismissal requires a reason string.**» (`:89`);
  оси `status` и `verification` раздельно (`:106`);
- наблюдённый отказ, ради которого проба стоит впереди: верификатор
  «*confidently wrong*… ~0.93 confidence while catching 0/12
  omitted-edge defects» (`:19`);
- ограничение подтверждено на HEAD: «**The classifier reads English;
  `text` does not have to be.**» (`:52`) — тип (shape) требования
  в symphysis называет модель;
- prohibition probe: вопрос «What could this feature silently become
  that the author would NOT want, but the spec does not forbid?»
  (`gsd-core/references/prohibition-probe.md:53`); движка нет —
  «There is **no compiled `prohibition-probe.cjs` engine** — the recall
  stage is an LLM prose pass» (`:32`), значит переносится без потерь;
  второй такт — «**DROP routine-engineering items**» (`:63`); канон
  (OWASP, GDPR) не чеканится — «Do NOT mint a prohibition for them»
  (`:79`), а отсылается в security-шаг. Для задачи обкатки это
  существенно: инъекции через файлы проекта и `../` — канон, их
  место в чек-листе ИБ, а не в журнале развилок.

### discuss-phase и запись решения

- «Gray areas are **implementation decisions the user cares about**»
  (`gsd-core/workflows/discuss-phase.md:83`); «You are a thinking
  partner, not an interviewer.» (`:11`);
- что не спрашивают: «The user doesn't know (and shouldn't be asked):
  codebase patterns (researcher reads the code), technical risks…»
  (`:57`) — это правило плана «у человека спрашиваем только то, чего
  не прочитать в файлах», сказанное с другой стороны;
- парковка есть, адресата нет: «Capture the idea in a "Deferred Ideas"
  section. Don't lose it, don't act on it.» (`:79`);
- запись решения `D-NN` с обратимостью: «`reversible` / `costly` /
  `one-way`», обоснование обязательно при оценке
  (`workflows/discuss-phase/templates/context.md:59`); раздел
  «Claude's Discretion» — где человек сказал «решай сам» (`:79`);
  `canonical_refs` — «MANDATORY section» с полными путями (`:94`).

Обратимость решения — поле, которого в формате журнала плана нет,
и оно дешёвое: одно слово и причина. Стоит взять.

### FORCE stance

«**FORCE stance:** Assume every plan set is flawed until evidence
proves otherwise.» (`agents/gsd-plan-checker.md:30`); та же установка
у ревьюера кода, верификатора документации, аудитора — по одной фразе
на роль (`agents/gsd-code-reviewer.md:22` и соседние). Для атаки
шага 7 это одна строка в instruction, рядом с линзами гриля.

## OpenSpec 1.15.0 — рамка

Факты плана проверены на исходниках 1.15.0, все держатся:

- статус по наличию файла: «file-existence status does not imply its
  dependencies exist» (`src/core/artifact-graph/instruction-loader.ts:165`),
  `status: 'done' as const` при найденном файле (`:507`);
- `update` перезаписывает правленые скиллы, но называет причину:
  «a user who edited a SKILL.md on purpose is owed the reason their
  edit is about to be overwritten» (`src/core/update.ts:841`);
- `rules` на артефакт — в `openspec/config.yaml` проекта
  (`openspec/config.yaml:21`, собственный конфиг OpenSpec как образец),
  читаются по id артефакта (`instruction-loader.ts:381`) и подаются
  агенту отдельно от шаблона;
- `/opsx:continue`: «STOP after creating ONE artifact»
  (`src/core/templates/workflows/continue-change.ts:117`); «If the
  `instruction` field delegates creation to a specific skill or
  command, invoke it» (`:110`); «`rules`: Artifact-specific rules
  (constraints for you - do NOT include in output)» (`:100`); glob-артефакт
  «reads `done` once one matching file exists» и continue дописывает
  недостающие файлы (`:28`).

Новое с 1.13.1 (`CHANGELOG.md`), что касается схемы:

- `x-`-ключи в `.openspec.yaml` изменения — «treated as your own
  extension metadata», `validate --strict` их пропускает (`:81`):
  законное место для вердикта атаки на уровне изменения;
- `openspec init --tools gsd` (`:116`) — цель **gsd-pi**, отдельного
  агентного CLI той же организации open-gsd, а не gsd-core: скиллы
  OpenSpec пишутся в `.agents/skills/`, «No subagent files»
  (`docs-lab/reference/supported-tools.md`, коммит `a7f08b8`;
  `src/core/config.ts:73` — `skillsDir: '.agents'`). Это цель
  уровня Amp или Warp, не связка механик: в gsd-core слова
  «openspec» нет ни в одном файле. Обратный мостик у gsd-core свой —
  `plan-phase --ingest <path> --ingest-format <nygard|madr|narrative>`
  (`gsd-core/workflows/plan-phase.md:124`) читает ADR в планирование,
  то есть уже после артефакта OpenSpec, вне обкатки;
- цель `.gigacode/skills/` (`:110`) — клиент обкатки, это важнее;
- `openspec update --dry-run` (`:9`) — проверка, что перезапишется,
  до перезаписи;
- `explore` под чужой схемой больше не предлагает `design.md`
  (`:71`) — для symphysis неважно, `explore` в решение не входит.

Встроенная схема как образец instruction: design «create only if
any apply» (`schemas/spec-driven/schema.yaml:170`); «Open questions
are for genuinely deferrable unknowns, not decisions you skipped»
(`:185`); «ask the user instead of guessing» (`:187`).

Исходники лежат в `upstream/openspec` как форк по слову человека.
Что в них менять — пока не известно: всё, что план просит
от рамки, схема и `rules` выражают без правки кода. Единственное,
что не выражается, — статус артефакта по вердикту, а не по файлу;
если это понадобится в CLI, правка одна: `instruction-loader.ts`
у `:507`. Форк стоит держать на этом, а не на скиллах: пять
выпусков за месяц (1.13.1 → 1.15.0) — форк workflow-скиллов
отставал бы еженедельно.

## Что это меняет в плане

1. **Формат журнала** собирается из трёх проверенных кусков:
   строка улики и одна рекомендация (`fork-form.md`), исходы
   Specify / Dismiss с причиной / Defer и обратимость решения (GSD),
   названное `предположение` с дорогой (`change-drafter`). Поле
   `статус` не хранится — читается по слову.
2. **Два места, где соглашение заведомо слабее скрипта:** сверка
   цитаты с файлом и счёт потерянных фактов. Обкатка должна
   считать, сколько раз они сработали бы, — это и есть «где
   не хватило скрипта» из «Как поймём».
3. **Числовой гейт** брейншторма (шаги 1 и 3) есть у GSD готовый;
   план кончает круг «без новых решений и без новых фактов» —
   это число 0, но измерений ясности у него нет. Взять четыре
   измерения как есть или не брать — решение человека.
4. **Канон не в журнал.** Инъекции, `../`, токены — чек-лист ИБ
   отдельным адресатом, по правилу canon-referral; журнал держит
   только bespoke-запреты.
5. **Playground** — результат промптом в буфер, как у шаблонов;
   File System Access API и выгрузка файлом сняты.
6. **OpenSpec** — форк в `upstream/`, менять только то, что схема
   не выражает; кандидат один — статус по вердикту.
