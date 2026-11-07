# Обновление upstream GSD Core: e2cd587 → v1.20.1 → origin/next

- **Пин проекта:** `e2cd587` (2026-10-29, `git describe` — `v1.18.0-133-ge2cd587e0`; тег `v1.19.0`
  лежит на `main` и предком `e2cd587` не является, зато `e2cd587` — предок `v1.20.0` и `v1.20.1`).
- **Remote:** `origin/next` = `f04db9d` (2026-11-07); теги `v1.20.0` = `b14172e` (2026-11-03),
  `v1.20.1` = `9385f46` (2026-11-05).
- **Цель:** разделить изменения на механики и код/CI/рантаймы; найти, что задевает взятое у GSD
  и что кандидат взять; дать человеку факты и варианты пина с причинами.
- **Дата:** 2026-11-07. **Автор:** агент, по файлам `upstream/gsd-core` (только чтение:
  `git -C X:/symphysis/upstream/gsd-core show origin/next:<путь>` и `v1.20.1:<путь>`; рабочий
  каталог клона остаётся на `e2cd587`). Ревизия у каждой цитаты названа явно.

## Объём

| Отрезок | Коммитов | Файлов | +/− | Записей CHANGELOG |
| --- | --- | --- | --- | --- |
| `HEAD..v1.20.0` | 19 | 253 | +8232/−2115 | 10 новых из 96 в разделе 1.20.0 |
| `v1.20.0..v1.20.1` | 20 | 136 | +6540/−489 | 8 (раздел 1.20.1 целиком) |
| `v1.20.1..origin/next` | 47 | 68 | +5131/−709 | Unreleased пуст; 15 changeset-файлов, из них 7 новых тем |
| Всего `HEAD..origin/next` | 86 | 383 | +19778/−3188 | |

**Как считались «новые» записи 1.20.0.** Раздел 1.20.0 покрывает 2026-10-26..11-03, пин —
2026-10-29. Для каждого номера `(#NNNN)` в разделе проверено `git log HEAD --grep="(#NNNN)"`:
из 170 номеров в `HEAD` отсутствуют 17 (`#3923 #4100 #4101 #4435 #4559 #5692 #5787 #5810 #5827
#5832 #5835 #5836 #5839 #5840 #5841 #5842` и `#3628` — последний только как номер ADR в коммите
`a8ed8ea12` от 2026-10-25, его записи `#5717/#5720/#5722` в пине есть). Эти 17 номеров дают
ровно 10 записей (пары «issue + PR»). Остальные 86 записей раздела 1.20.0 уже в пине.

**Три «кандидата по changelog», названные в задании, — до пина, не новые:**

| Запись | Коммит | Дата | Где в файлах (`v1.20.1`, не менялись с `HEAD`) |
| --- | --- | --- | --- |
| plan-checker `## VERIFICATION PASSED` с BLOCKER/WARNING читается как `## ISSUES FOUND` (#5578/#5644) | `39bb1b367` | 2026-10-23 | `gsd-core/workflows/plan-phase.md:1121` |
| TDD: GREEN после RED по родословной коммитов (#5275/#5660) | `4ea522763` | 2026-10-24 | `gsd-core/references/tdd.md:345` |
| `check_spec`/`spec_lock` во всех режимах discuss (#5629/#5673) | `931858736` | 2026-10-24 | `gsd-core/workflows/discuss-phase.md:185-197`, `:317`, `:404-407` |

Что они значат для нас — в разделе «Механики», пункт М8.

**Состав 47 невыпущенных коммитов** (`v1.20.1..origin/next`): 15 повторных посадок хотфиксов
1.20.1 на `next` (те же заголовки, другие хеши: `#5910 #5909 #5908 #5906 #5907 #5905 #5896 #5899
#5898 #5891 #5893 #5892 #5887 #5878 #5849`); 6 merge/sync-коммитов; 14 коммитов серии `#5831`
(атомарная запись архива при prune `STATE.md`: 12 коммитов серии, затем `2e928c6e4` «Fix state
prune archive integrity» и его откат `f3f3a1826` (#5941) в тот же день 2026-11-05 — changeset
`patient-cranes-leap.md` на `origin/next` отсутствует); 12 уникальных: `#5912` CI timeout,
`#5847` symlinked `$HOME`, `#5921` чистка `.gsd/phase`, `#5928` verifier (#5741), `#5927`
isolation record (#5758), `#5930` тело GitHub Release, `#5929` гейт code-review-fix (#5753),
`#5917` RED evidence (#5721), `#5924` CHANGELOG вне сканов, `#5872` реестр musk, `#5875` и
`#5873` записи `.out-of-scope/`.

Изменённые файлы по каталогам (`HEAD..origin/next`): `.changeset/` 102, `tests/` 92 (с фикстурами),
`src/` 29, `scripts/` 16, `docs/` 32, `capabilities/` 47 (по одной строке реестра на каждый),
`.github/` 8, `gsd-core/` 16 (workflows 6, references 4, bin 6), `agents/` 5, `pi/` 7,
`commands/gsd/` 3, `skills/` 3, `hooks/` 3. Под `gsd-core/references`, `gsd-core/workflows`,
`agents` — 15 файлов: `+495/−206`.

## Код, CI, рантаймы

Записи, которые не меняют того, как модель рассуждает, проверяет или интервьюирует.
Без подробностей; номер — issue/PR, как в CHANGELOG.

| Выпуск | Запись | Номер |
| --- | --- | --- |
| 1.20.0 | `/gsd-config --advanced` задаёт порог и интервал stall-детектора планировщика; `0` больше не ломает watch (`settings-advanced.md`, `stall-detection-helpers.md`) | #3923/#5827 |
| 1.20.0 | `state begin-phase --plans 0` пишет 0 | #5787/#5841 |
| 1.20.0 | два читателя ROADMAP Progress снова видят то, что видели до «одного владельца» | #5692/#5810 |
| 1.20.0 | патчи advisories re2js и `@hono/node-server` в lockfile | #5840/#5842 |
| 1.20.0 | `--depth=quick` code-review гонит все перечисленные grep-проверки (регэкспы разошлись со списком) | #4101/#5835 |
| 1.20.0 | без записи: CI timeout budget ×4, ADR-5812 `worktree.reap-orphans`, `shellSingleQuote` вынесен, ADR-4629 цитируется по символу, bump `qs`, `lint:ci` ловит рукописный Progress-паттерн | #5838 #5826 #5815 #5783 #5833 #5829 #5744 #5795 #5809 |
| 1.20.1 | кеш fork-probe внутри проекта и вне git | #5757/#5908 |
| 1.20.1 | инсталлятор переписывает `~/.claude` один раз, литеральными путями, для всех рантаймов | #5715/#5906 |
| 1.20.1 | `effort sync --apply` пишет хеши в манифест установки | #5683/#5899 |
| 1.20.1 | два оркестратора в одном checkout не затирают решения изоляции друг друга | #5682/#5891 |
| 1.20.1 | `drift-guard phase-status` и workstream progress читают `M-NN` целиком | #5675/#5887 |
| 1.20.1 | `phase insert` называет чужой milestone | #5679/#5893 |
| 1.20.1 | `new-project`/`new-milestone` отсылают к `/gsd-discuss-phase`, а не к `plan-phase` (`commands/gsd/new-project.md`, `skills/gsd-new-project/SKILL.md`) | #5723/#5905 |
| 1.20.1 | `phase complete`, `state sync`, init progress читают `M-NN` целиком | #5676/#5896 |
| 1.20.1 | без записи: фикстуры вне prompt-injection-скана, changeset-lint для PR релиза, замер attribution от fork point, merge-коммиты и проверка ancestry main/next, исключение back-merge PR из гейтов | #5904 #5903 #5902 #5894 #5890 |
| next | реестр capability `musk` (сторонний «subtraction pass» по milestone и требованиям — только ссылка в реестре, кода в GSD нет) | #5869/#5872 |
| next | обход корня проекта останавливается на symlinked `$HOME` | #5624/#5847 |
| next | тело GitHub Release — раздел CHANGELOG | #5922/#5930 |
| next | запись dispatch-isolation читается как ограниченный обычный файл | #5758/#5927 |
| next | гейт code-review-fix идёт по `workflow.code_review`, а не по hook-точке | #5753/#5929 |
| next | `check tdd-red-evidence`: упавший при загрузке тестовый файл — `INVALID_RED`, не RED (`src/tdd-red-evidence.cts`, `src/report-parser.cts`) | #5721/#5917 |
| next | серия `#5831` prune `STATE.md` + откат `#5941`; чистка `.gsd/phase` из git; CHANGELOG вне сканов инсталлятора; CI timeout ×2 | #5831 #5941 #3677/#5921 #5923/#5924 #5912 #5849 |
| next | `.out-of-scope/`: второй именованный проект в одном репозитории — отказ (#5862); разделение «завершено» и «проверка свежа» — отказ по ADR-5057 (#5851) | #5875 #5873 |

## Механики

Все цитаты — `origin/next`, если не сказано иное; у файлов, не менявшихся после `v1.20.1`,
номера строк на обеих ревизиях совпадают (проверено `git diff --stat v1.20.1..origin/next --
gsd-core agents`: после выпуска менялись только `agents/gsd-verifier.md`,
`references/checkpoints.md`, `references/planner-human-verify-mode.md`,
`workflows/code-review-fix.md`).

Вердикты: **(а)** меняет механику, которую symphysis уже взял; **(б)** кандидат взять;
**(в)** не про нас.

### М1. Necessity review — «код, который страхует от невозможного» (#4100/#5832, 1.20.0)

Новый файл `gsd-core/references/necessity-review.md` (48 строк), четвёртая категория
`gsd-code-reviewer`, правила `gsd-code-fixer` и цикла `code-review-fix`.

- `necessity-review.md:3` — «It asks a question the other three categories do not: **does the
  problem this code addresses actually occur in this stack?** Correct, clean, well-tested code
  can still guard against nothing.»
- `:11-15` — таксономия из пяти подтипов: impossible-state guard, already-defended-elsewhere,
  cargo-culted pattern, phantom requirement («Solves a requirement that was never real or has
  provably lapsed»), generality without instantiation («An abstraction with exactly one
  instantiation for its whole lifetime»).
- `:19` — правило улики: «A necessity finding must state **why the guarded state cannot occur**
  (or why the requirement lapsed) and cite where that is proven: the type signature, the
  build/deploy configuration, the call sites, the flag's values. The pattern name alone is not a
  finding — drop it.»
- `:25` — «**Never Critical.** Removal is a scope decision for a human, not a defect fix.»
- `:29-33` — отрицательное пространство: trust boundary, defense in depth, test seams —
  не находки.
- `agents/gsd-code-reviewer.md:64` — «**4. Necessity** (#4100) — reachable code whose
  guarded-against problem cannot occur in this stack…»; `:331` — «Emit `necessity:` only at
  standard/deep depth. It counts the necessity findings among `warning` + `info` and is never
  added to `total`.»
- `agents/gsd-code-fixer.md:479` — «`critical_warning` excludes necessity findings (removing code
  is a scope decision for the human, #4100). The marker overrides the prefix».
- `gsd-core/workflows/code-review-fix.md:274-277` — «The fixer is the scope authority: its
  REVIEW-FIX.md `findings_in_scope` is read strictly»; `:620` — «a vacuous all_fixed (nothing
  was in scope) must not claim the review is resolved.»
- Источник таксономии — `necessity-review.md:5`: «Taxonomy adapted from the
  `functionality-complexity-tradeoff` skill in l-gevity/l-gevity-skills (MIT)».

**Вердикт: (в) для описи последствий, (б) слабый — линза атаки артефактов.**

- Пересечение с описью (`consequences/skills/symphysis-consequences/SKILL.md`) — обратное по
  направлению: опись берёт код, на который изменение *опирается*, и спрашивает «что при отказе
  ветки» (`SKILL.md:14-17`, `:149-150` «допущение: … что сломается, если это не так»); necessity
  спрашивает о *новом* коде «а бывает ли вообще то, от чего он страхует». «Lapsed requirement» в
  терминах OpenSpec — требование в `openspec/specs/`, которого никто не ждёт; у нас это предмет
  графа трассируемости (`trace/trace_graph.py`), не описи. Исход описи «Исключить»
  (`SKILL.md:102` «конструкция на него не опирается») — про место, не про недостижимую ветку;
  вводить исход «ветка недостижима» ради симметрии не стоит: опись и так сигнал, не стоп.
- Кандидат — линза `attack-artifacts` по `design.md`: «конструкция вводит механизм против
  состояния, которое спеки исключают» или «абстракция с одной реализацией». Правило улики `:19`
  (назвать, *где* доказана невозможность) и «Never Critical» `:25` ложатся в нашу таблицу
  (тяжесть `предупреждение`, опора `путь:строка`). **Против:** F-07.A сознательно снял десять линз
  plan-checker до двух (`attack/skills/symphysis-attack/sources/plan-checker-dimensions.md:2`),
  новая линза — это решение владельца, а не перенос; и у GSD это ревью кода *после*
  реализации, у нас `design.md` до неё — доказательства «невозможности» (типы, деплой) на этом
  шаге чаще нет. Если брать — только как `предупреждение` и только с уликой, как в `:19`.

### М2. Рубрика CI/CD для code-review (#4101/#5835, 1.20.0)

Новый `gsd-core/references/cicd-review-patterns.md` (45 строк): `:3` — «Rubric for the **CI/CD
pipelines** entry of `gsd-code-reviewer`'s language-aware checks… These defects rarely fail a
test. They show up at release or deploy time»; `:13-20` — восемь проверок (non-idempotent step,
missing timeout, missing concurrency guard, per-environment rebuild, deploy without
rollback, load-bearing `continue-on-error`, static cloud credentials, unpinned action);
`:26` — «Cite the line»; `:30-35` — что не находка. `agents/gsd-code-reviewer.md:96` — вход по
пути файла.

**Вердикт: (в).** Ревью файлов пайплайна, у symphysis шага ревью кода нет. Единственное общее —
форма «проверка · сигнал · почему · тяжесть + отрицательное пространство», которую мы уже
держим в каноне (`docs/skills-canon.md`, таблицы только для справки).

### М3. Лейны ревью: промпт ограничен, перебор — отказ, не обрезка (#4559/#5839, 1.20.0)

`gsd-core/workflows/review.md` (−130 строк: снят per-lane budget trimming).

- `:297` — «Every lane receives `gsd-review-prompt.md` whole — it is never trimmed per lane
  (#4559). A lane whose prompt exceeds its cap is refused in `invoke_reviewers`, not shortened.»
- `:388-391` — «#4559: no per-lane trimming. Every lane receives the whole prompt; `review-lane
  invoke` measures it against the lane's cap (its own `promptBudgetKey`, the global
  `review.max_prompt_tokens`, or the default derived from its declared context window) and
  REFUSES a lane that is over, writing a `review did not run: prompt exceeds` stub. A trimmed
  prompt reviewed something other than the plans.»
- `:443-445` — отказанный лейн «did not run, so it must not count as a lane result».
- `:465` — типизированная причина `prompt_exceeds_context`; `:531-533` — при отказе всех лейнов
  «name the cap and the `review.context_window_tokens.<slug>` /
  `review.max_prompt_tokens_per_reviewer.<slug>` keys that raise it».
- CHANGELOG 1.20.0: «a reviewer that never saw part of the plan set returned a review that read
  like a clean pass… Lanes with a known default model… now cap at 65% of a declared context
  window».

**Вердикт: (б) — водители и brief.** Это наш вопрос «что делает водитель, когда цели brief не
вмещаются». В `docs/skills-canon.md` раздел 10 и `skill-shared/driver.md` правила размера нет
(поиск по «размер/объём/токен» рядом с «brief» в `docs/`, `skill-shared/`, журнале и
`openspec/changes` — пусто); ближайшее — прогон 2026-11-06 «до 160 тысяч токенов на прогон»
(`skills-canon.md:353`), это про браузер, не про размер целей. Что взять — принцип, одной строкой
в `skill-shared/driver.md` (раздел прав/отчёта) и в разделе 10 канона: водитель, которому не
хватает контекста на все `targets`, **не читает часть** и не ставит вердикт по части, а
возвращает отчёт с «Итог: не выполнено» и строкой «Не сделано: цели не вмещаются, `<счёт>`» —
главная нить делит brief. Наша форма уже это умеет: раздел «Не сделано» отчёта
(`skill-shared/driver.md:54`), строки покрытия атаки (`attack/skills/symphysis-attack/SKILL.md:154`),
`targets` с хешами как манифест покрытия (у GSD тот же приём — `.plans-manifest.md`,
`review.md:290`, #3301). Чего не брать: числовой порог «65% окна» — у нас нет замера токенов
в brief, и F-12 «сигнал, не стоп» распространяется на главную нить, не на водителя, который
молча прочёл половину. **Против:** правило без замера опирается на самооценку модели
«вмещается ли» — GSD именно от этого ушёл к счёту токенов; без счёта строка в brief
(`inputs`, `targets`) и так ограничивает чтение, и реальный случай переполнения у нас пока
один (просмотрщик, браузер), не водитель атаки.

### М4. `/gsd-update --reapply --interactive` — своя правка поверх обновлённого upstream (#4435/#5836, 1.20.0)

`gsd-core/workflows/reapply-patches.md` (+104 строки к существующему файлу; файл не новый —
на `HEAD` 525 строк, на `origin/next` 629).

- `:9` — инвариант: «Every file in `gsd-local-patches/` was backed up because the installer's
  hash comparison detected it was modified. The workflow must NEVER conclude "no custom content"
  for any backed-up file… When in doubt, classify as CONFLICT requiring user review, not SKIP.»
- `:270-272` — «Verbatim matching cannot see an edit that upstream adopted in different words, an
  edit whose surrounding stock text upstream rewrote, or an edit whose anchor lines upstream
  deleted. Interactive mode shows each user edit (hunk) and lets the USER decide. Present and
  gate: the tool recommends, the user decides, and nothing is retired without the user's answer.»
- `:307-309` — причины рекомендации: `already_upstream`, `partially_upstream`,
  `region_changed_upstream`, `anchor_orphaned`, `baseline_unconfirmed`, `diff_too_large`.
- `:315-316` — «Never write `retire` or `rewrite` for a hunk the user was not asked about, and
  never pick an answer on the user's behalf, even when the recommendation is `retire`.»
- `:548-551` — «a recorded answer no longer matches its hunk because the backup or baseline
  changed after the user saw it. STOP, discard `DECISIONS_FILE`… Never edit the decisions file to
  make it match.» (решения привязаны к `hunk_hash`; расхождение — exit 2 `stale decision`).
- `:553-557` — «The gate can prove that a decision matches the exact text that was shown, but not
  who made it, so the user's confirmation of this list is the final check.»

**Вердикт: (в) для форка, переносить нечего; приём подтверждает наш.** Задача GSD —
установленные файлы без git: три версии (pristine, backup, новая) и ручной трёхсторонний merge.
У нас форк OpenSpec — ветка `symphysis` с перечнем правок C1–C14
(`upstream/openspec/UPSTREAM.md:10-24`) и правило F-03 «сначала анализ выпуска, потом решение»
(`UPSTREAM.md:6-8`): втягивание — `git merge`/`rebase`, конфликты видит git, а не классификатор
по словам. Приём «решение привязано к хешу текста, который видел человек; чужой хеш — `stale`,
не подгонять» — это буквально наши F-06.A/F-26.E (вердикт с чужим хешем целей — `stale`) и
«решения возвращаются промптом и вносятся без переписывания» (CLAUDE.md «Как работаем»).
Единственное, чего у нас нет и что можно обсудить отдельно: явное подтверждение человеком
*списка* внесённых слов после `apply` («не кто сделал, а подтвердите, что это ваши») — но у нас
слово вносит хук плагина от действия человека, посредника-агента между кнопкой и журналом нет,
так что и подтверждать нечего.

### М5. Verifier собирает все human-check, даже с записанным вердиктом (#5741/#5928, только `origin/next`)

- `agents/gsd-verifier.md:537` — «Harvest every block, even one whose `<expected>` already
  records a verdict: a recorded verdict is not a reason to omit the check, and `<expected>` is
  carried through unmodified. Deduplicate only against your own analysis (same check).»
- `gsd-core/references/checkpoints.md:33` и `planner-human-verify-mode.md:30` — та же вставка
  «even when its `<expected>` already records a verdict».

**Вердикт: (в).** Правка в `:522-537` — блок «Harvest deferred items from PLAN.md»; наша выписка
`attack/skills/symphysis-attack/sources/gap-output.md` берёт `:603-646` и `:828-839`, сдвига
строк нет (замена строка-в-строку, `+2/−2`), цитаты `:609-631` и `:828` целы. По смыслу это
про планировщик, который заранее вписал вердикт в проверку для человека, — у нас таких
предзаписанных вердиктов нет: вердикт ставит таблица атаки, человек видит строки в
просмотрщике. Единственная перекличка — `attack/skills/symphysis-attack/SKILL.md:351` «При
`status: passed` строки `предупреждение` повтора не требуют» и `:378` «Список идёт и при
`passed`: иначе предупреждения останутся в файле»: наш «записанный вердикт» тоже не прячет
строки от человека. Менять нечего.

### М6. Цикл `code-review --fix --auto` останавливается, когда в scope пусто; гейт по тумблеру (#4100, #5753/#5929)

`gsd-core/workflows/code-review-fix.md:89-101` — гейт по `workflow.code_review`, «a manual
invocation must work regardless of which automatic point is currently configured»; `:270-277`
и `:620` — см. М1.

**Вердикт: (в).** Цикл фикса кода. Принцип «пустой scope ≠ „всё исправлено“» у нас уже есть в
другой форме — `status: passed` не скрывает предупреждения (`SKILL.md:378`, `:409`).

### М7. Пороги stall-детектора из `/gsd-config --advanced` (#3923/#5827)

`gsd-core/workflows/plan-phase/steps/stall-detection-helpers.md:106-110` — «Zero is rejected too
(#3923): an interval of 0 makes every gsd_stall_watch cycle a zero-length sleep, and a threshold
of 0 declares a healthy agent stalled on the first check»; `settings-advanced.md:151-152` — два
вопроса 1b, только пока детектор включён.

**Вердикт: (в)** — конфигурация и валидация, в таблице кода; здесь только потому, что меняет
`workflows/`.

### М8. Три записи «до пина», названные в задании

Все три уже в `e2cd587` (см. «Объём»); файлы с тех пор не менялись (`git diff --stat
HEAD..v1.20.1` по ним пуст).

- **#5644 — PASSED с BLOCKER/WARNING = ISSUES FOUND.** `gsd-core/workflows/plan-phase.md:1121`
  (`v1.20.1`): «`marker_received` + `## VERIFICATION PASSED`: If the return lists an entry whose
  severity is BLOCKER or WARNING, in the YAML issues block or listed in prose (a mention such as
  "no warnings" or a zero count is not an entry), treat it as `## ISSUES FOUND`». У symphysis то
  же по построению: `attack/skills/symphysis-attack/SKILL.md:358` «`status: passed` ставится,
  только когда в таблице нет ни одной строки с тяжестью `блокер`», `:102` «иначе вердикт ставит
  модель, а не таблица», `:406`. **Вердикт: (в) — уже покрыто, записи журнала не требует.**
- **#5660 — GREEN после RED по ancestry.** `gsd-core/references/tdd.md:345` (`v1.20.1`): «Order is
  commit ancestry, not log position or commit date: a GREEN counts only when it descends from a
  RED commit of the plan». Реализация — `src/gate-tdd-review-checkpoint.cts`. **Вердикт: (в):**
  TDD-гейта у symphysis нет; `#5721` на `next` — продолжение той же линии в коде
  (`tdd.md:97` уже на пине: «A nonzero exit alone is NOT RED — syntax errors, zero-test discovery,
  fixture crashes…»).
- **#5673 — `check_spec`/`spec_lock`.** `gsd-core/workflows/discuss-phase.md:185-191`
  (`v1.20.1`): «Check whether the phase has a SPEC.md… SPEC.md locks requirements before
  implementation decisions. Init already resolved it: use `has_spec` and `spec_path`, which come
  from one shared definition of "the phase SPEC"»; `:317` «If `spec_loaded = true`:
  `<locked_requirements>` are pre-answered… Do NOT generate gray areas about WHAT to build or
  WHY.» Выписка брейншторма берёт `:52-60`, `:62-80`, `:82-99` — `check_spec` вне выписки.
  **Вердикт: (в):** у нас порядок `intent → decisions → … → specs`, спеки на момент брейншторма
  и второго круга в `research` ещё не существуют; роль «замка» несёт `intent.md` (F-13.A, F3
  владельца о противоречии схемы и `intent.md`).

### М9. Запись `.out-of-scope/stale-verification-completion-split.md` (#5851, 2026-11-03, `next`)

Не механика в коде, но решение о механике, которое прямо касается нашего `stale`:
«`docs/adr/5057-one-owner-per-workflow-verdict.md` makes a passed-but-stale phase EXECUTED,
never COMPLETE, in every surface… The fail-closed staleness contract was kept on purpose…
listing weakening the fail-closed staleness contract as a non-goal.»

**Вердикт: (в), к сведению.** GSD держит «устарел — значит не завершён» без окна; у нас F-64.B
даёт окно: `stale` гейтует, пока не начался следующий шаг, дальше сигнал
(`upstream/openspec/UPSTREAM.md:16-17`). Решение наше, не заимствованное; GSD-запись — довод
«за» строгий вариант, если человек захочет окно пересмотреть; переносить нечего.

## Сверка цитат

Ожидание задания подтверждено: все цитируемые файлы, кроме `agents/gsd-verifier.md`, между
`HEAD` и `origin/next` не менялись (`git diff --stat HEAD..origin/next` по 11 файлам — только
`gsd-verifier.md | 4 ++--`); между `HEAD` и `v1.20.1` не менялся ни один (`diff --stat` пуст).
Ниже — выборочная сверка текста на `v1.20.1` по строкам из комментариев `<!-- src: -->` тел
скиллов (собраны `grep -rhoE "<!-- src:[^>]*-->"`, 63 уникальных комментария).

| Файл GSD | Цитата из тела скилла | Строки | На `v1.20.1` |
| --- | --- | --- | --- |
| `gsd-core/references/edge-probe.md` | «a fixed eight the author must explicitly clear beats thirty nobody finishes» | `:64-65` | совпадает |
| | «The classifier reads English; `text` does not have to be.» | `:52` | совпадает |
| | «Dismissal requires a reason string… silence is not» | `:89-90` | совпадает |
| | «~0.93 confidence while catching 0/12 omitted-edge defects» | `:20` | совпадает |
| | таблица восьми категорий, фильтр применимости | `:70-79`, `:85-88` | совпадает (`:70` шапка таблицы, `:85` «Relevance filter first») |
| `gsd-core/references/prohibition-probe.md` | «There is **no compiled `prohibition-probe.cjs` engine**» | `:32-33` | совпадает |
| | «The probe runs **after** the edge-probe in the spec phase, over the same requirement list» | `:41-42` | совпадает |
| | «What could this feature silently become that the author would NOT want, but the spec does not forbid?» | `:53-54` | совпадает |
| | «That over-production is intentional — recall first» | `:57-58` | совпадает |
| | «the correct precision outcome for a pure utility, not a failure» | `:73-74` | совпадает |
| | «Do NOT mint a prohibition for them» / «duplicates other tooling and drowns the bespoke signal» | `:79-80`, `:90-91` | совпадает |
| | «accompanied by a required, non-empty reason string… silence is not» | `:101-103` | совпадает |
| | «a negative test, a lint rule, an assertion that the audit log contains no raw SSN» / «cannot be reduced to a mechanical test» | `:107-108`, `:109-111` | совпадает |
| | «an explicit assumption the downstream planner must surface, not silently drop» | `:233-234` | совпадает |
| `gsd-core/references/thinking-models-planning.md` | «assume it has already failed. List the 3 most likely reasons for failure» | `:15` | совпадает |
| `gsd-core/references/honest-verifier.md` | «Exogenous, not endogenous… there is **no "are you sure?" prompt**» | `:25-29` | совпадает |
| | таблица диспозиции, «**abstain** → ⚠️ `insufficient_spec`… **never `passed`**» | `:35-43`, `:41` | совпадает (`:41` — строка «Inferable… never abstained», `:43` — abstain) |
| `gsd-core/workflows/spec-phase.md` | «Failure Analyst (round 4): Find the edge cases that invalidate requirements.» | `:43` | совпадает |
| | «**Max 6 rounds.** Each round: 2–3 questions max.» | `:136` | совпадает |
| | «propose a CONCRETE candidate edge (not "consider boundaries"…)» | `:344-345` | совпадает |
| | «never auto-dismiss — a wrong dismissal is the exact silent failure being eliminated» | `:370-371` | совпадает |
| | Step 5.6 «Prohibition-Completeness Probe (must-NOT)» | `:384` | совпадает |
| | «a wrong dismissal is the exact silent failure this probe eliminates» | `:460-461` | совпадает |
| | «Scout the codebase BEFORE the first question — grounded questions only» | `:542` | совпадает |
| | `<interview_perspectives>` | `:25-52` | совпадает (`:25` открывает, `:52` закрывает тег) |
| `gsd-core/workflows/discuss-phase.md` | «**User = founder/visionary. Claude = builder.**» | `:52-53` | совпадает |
| | ограда объёма «Does this clarify how we implement… or does it add a new capability» | `:69` | совпадает |
| | «Capture the idea in a "Deferred Ideas" section» | `:79` | совпадает |
| | «**Don't use generic category labels** (UI, UX, Behavior)» | `:89` | совпадает |
| `…/discuss-phase/templates/context.md` | «— **Reversibility:** …» / «The rationale is required whenever a rating is given» | `:58-59`, `:62-64` | совпадает |
| `agents/gsd-plan-checker.md` | «do not credit effort or intent, only verifiable coverage» | `:9` | совпадает |
| | «**FORCE stance:** Assume every plan set is flawed until evidence proves otherwise…» | `:30` | совпадает |
| | «Issues without a severity classification are not valid output…» | `:43-44` | совпадает |
| | Dimension 7: Context Compliance | `:376` | совпадает |
| | Numeric/Factual Claim Authority (#1480) | `:705-720` | совпадает |
| | «State it as the invariant, not the edit…» | `:933-935` | совпадает |
| `agents/gsd-doc-verifier.md` | «**FORCE stance:** Assume every factual claim in the doc is wrong…» | `:29` | совпадает |
| | `<claim_extraction>` … «Do NOT execute any commands. Existence check only.» | `:58-98`, `:77` | совпадает |
| | `<skip_rules>` | `:100-110` | совпадает |
| `agents/gsd-verifier.md` | Step 10 «Structure Gap Output… confirm that status is not `passed` when human verification items exist» | `:609-631` | совпадает; на `origin/next` те же строки (сдвига нет) |
| | «Self-check the written status (#5118)» … «never edit `status` to match it» | `:828-839` | совпадает; на `origin/next` то же |
| `agents/gsd-assumptions-analyzer.md` | «Every assumption MUST state a concrete consequence if wrong» | `:93` | совпадает |
| `agents/gsd-code-reviewer.md` (цитируется только в `sources/force-stance.md`) | «**FORCE stance:** Assume every submitted implementation contains defects…» | `:22` | совпадает на `v1.20.1` и на `origin/next` (файл изменён ниже, `:64+`) |

Сверка выписок `sources/` целиком (`v1.20.1` и `origin/next`):

- `probes/…/symphysis-edge-probe/sources/edge-probe.md` и
  `symphysis-prohibition-probe/sources/prohibition-probe.md` — копии целиком: без строки шапки и
  без `\r` **байт в байт совпадают** с обеими ревизиями. Первая попытка `diff` показала «все 458
  строк различны» — это CRLF в рабочей копии symphysis (`file`: «with CRLF line terminators»)
  против LF у `git show`; на текст не влияет.
- Частичные выписки (`claim-extraction.md` 41 строка, `gap-output.md` 42, `honest-verifier.md`
  49, `plan-checker-dimensions.md` 82, `assumptions-analyzer.md` 38, `pre-mortem.md` 11,
  `discuss-phase-gray-areas.md` 33, `spec-phase.md` 69) — каждая непустая строка, кроме
  комментариев `<!-- -->`, найдена в файле `v1.20.1` дословно: **0 расхождений** из 365 строк.

Расхождений нет. Цитаты в `docs/analysis/sdd-frameworks-proactive-design.md` и `step0-sources.md`
(16 путей GSD) пересекаются с изменёнными файлами только в `agents/gsd-code-reviewer.md`, и
там цитируется `:22`, которая не менялась.

## Варианты пина

Общее для всех: содержимое доноров symphysis на `v1.20.1` и на `origin/next` совпадает с
`e2cd587` байт в байт (раздел «Сверка цитат»); выписки, тела скиллов и TRANSLATION-NOTES по
существу править не нужно ни при каком варианте. Перенос пина — это правка *подписи*, не
текста. Объекты `origin/next` уже в клоне, поэтому любой файл любой ревизии читается
`git show` без смены рабочей копии — для чтения механик М1–М4 переносить пин не обязательно.

Где подпись `e2cd587` живёт (отслеживаемые файлы; `.claude/`, `.symphysis/` — в `.gitignore`,
производные `install`; `installer/payload/` собирается `scripts/sync-payload.js`;
`.superpowers/` — отчёты прогонов, история):

- 11 шапок выписок `<модуль>/skills/<имя>/sources/*.md` (первая строка, «… `@ e2cd587`»);
- 5 `sources/TRANSLATION-NOTES.md` (attack, consequences, brainstorm, edge-probe,
  prohibition-probe; строка 3 «Источник — GSD Core @ e2cd587»);
- `tests/test_skills.py:17` — `GSD_PIN = "@ e2cd587"`, проверка `:119` «в шапке нет пина»;
- `docs/plan-flexible-pipeline.md:77` и `:252` (там же «v1.18.0+133» — совпадает с
  `git describe`, не ошибка);
- `docs/plan-implementation.tasks.md:564` — образец шапки «`@ e2cd587`» в задании D1–D4;
- `installer/THIRD-PARTY-NOTICES.md:11` «версия e2cd587» (и его копия в `payload/docs/`);
- `docs/analysis/step0-sources.md:185` — историческая дельта `fdc4e7a → e2cd587`, править не
  надо (факт о прошлом).

### 1. Оставить `e2cd587`

- **За:** доноры не изменились — пин точно описывает то, что переведено; ноль правок; 86
  коммитов не дали ни одной механики класса (а). Кандидаты (б) — М3 (правило водителя) и
  М1 (линза) — переносятся принципом, без копии файла GSD, значит без шапки с пином.
- **Против:** рабочая копия клона не содержит новых файлов (`necessity-review.md`,
  `cicd-review-patterns.md`): поиск по каталогу их не найдёт, читать только `git show`;
  разбор выпусков GSD придётся вести от точки, которая уже не версия (`v1.18.0-133`), и каждая
  следующая сверка снова будет считать «что из 1.20.0 до пина, что после»; у упоминаний пина в
  документах нет даты выпуска, к которому его можно привязать.
- **Что править:** ничего.

### 2. Перейти на `v1.20.1` (выпуск 2026-11-05)

- **За:** именованный выпуск вместо коммита между выпусками — следующий разбор идёт по
  разделам CHANGELOG без пересчёта; цитируемые файлы на `v1.20.1` байт в байт те же — переход
  ничего не ломает ни в телах, ни в выписках, ни в номерах строк; в рабочей копии появляются
  `necessity-review.md`, `cicd-review-patterns.md`, новый `review.md` и `reapply-patches.md`;
  `v1.20.1` — предок `origin/next`, то есть не боковая ветка.
- **Против:** 17 правок подписи ради нулевого изменения содержания (шум в git blame выписок);
  `git checkout v1.20.1` в клоне — операция человека (отчёт сделан без неё); механика М5
  (verifier) в `v1.20.1` ещё не входит, но она (в).
- **Что править:** 11 шапок `sources/*.md`, 5 `TRANSLATION-NOTES.md`, `tests/test_skills.py:17`,
  `docs/plan-flexible-pipeline.md:252` (и `:77` — дата чтения там 2026-10-29, корректнее
  дописать «пин перенесён на v1.20.1 2026-11-NN»), `docs/plan-implementation.tasks.md:564`,
  `installer/THIRD-PARTY-NOTICES.md:11` + пересборка payload; плюс строка в этом разборе о
  решении. Содержание выписок — без правок (проверено).

### 3. Перейти на `origin/next` = `f04db9d` (невыпущенное, 2026-11-07)

- **За:** самая свежая точка; включает М5 и гейт `#5753`; номера строк всех наших цитат и на
  ней целы (`gsd-verifier.md` изменён в `:522-537`, выписка берёт `:603-646` и `:828-839`,
  сдвига нет).
- **Против:** ветка в движении — серия `#5831` за один день получила фикс и откат (`2e928c6e4`
  → `f3f3a1826`), 15 из 47 коммитов — повторные посадки хотфикса, `.changeset/` не сведён в
  CHANGELOG; пин на коммит без имени выпуска повторяет текущую ситуацию (`v1.20.1-47-g…`) и
  через неделю снова «между выпусками»; выигрыш против `v1.20.1` — одна механика класса (в).
- **Что править:** то же, что в варианте 2, подпись `f04db9d`.

Сравнение вариантов 2 и 3 между собой: разница для symphysis — ноль по содержанию и минус
«именованный выпуск» у варианта 3; единственная причина брать `next` — если решено
втягивать GSD чаще, чем раз в выпуск, а такого правила нет (F-03 для OpenSpec — «сначала
анализ, потом решение», тот же подход естественно распространить на GSD).

## Итог одной строкой

Новых записей 1.20.0 относительно пина — 10, 1.20.1 — 8, невыпущенных тем — 7 (+ серия prune
с откатом); механик, задевающих взятое у GSD (класс а), — нет; кандидаты (б) — правило
«не вмещается — отказ, не часть» для водителя (М3) и, со слабым доводом, линза necessity
для атаки `design.md` (М1); три кандидата из задания (#5644, #5660, #5673) — до пина и уже
покрыты или не про нас; цитаты и выписки совпадают на `v1.20.1` и `origin/next` без единого
расхождения.
