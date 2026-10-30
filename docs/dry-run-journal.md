# Сухой прогон: схема symphysis проходит сама себя — дневник

Задача F1 плана (`docs/plan-implementation.tasks.md`, Task 25): изменение
`symphysis-schema` проходит граф схемы `symphysis` от `decisions`
до `attack-artifacts` по workflow `continue` форка. Исполнитель — модель
(Claude Fable 5.1, один контекст на F1 и F2); человека в прогоне нет
(рулинг 4): где скилл ждёт его слова, стоит строка «нужен человек: …»,
развилки остаются открытыми, синтетических решений нет. Схема, скиллы,
форк и инструменты по ходу не правятся — только записываются.

Дата прогона — 2026-10-30. Ветка `impl/plan-tasks`, HEAD на старте
`2192b6e`. Форк OpenSpec — `node upstream/openspec/bin/openspec.js`,
`1.15.0-symphysis.1`. Команды — из корня `X:\symphysis`, Git Bash.

## Как читать

На каждый шаг (один артефакт = один «вызов» `continue`) — блок с фиксированными
полями (рулинг 6, 11); пустое поле — «—». Под блоком — ход: команды,
их вывод и заметки, на которые ссылаются поля. Отчёт F2
(`docs/dry-run-report.md`) считает по полям блоков.

Поля: **шаг · артефакт · скилл · что сделал скилл · руками · сломалось ·
без опоры (поймано на шаге?) · развилка↔факт · улики не нашлись ·
переделано · не хватило скрипта · время · ходы**. «Ходы» — число вызовов
инструментов на шаг по собственному счёту исполнителя (чтение файлов,
команды, записи файлов — каждый вызов один ход); записи в сам дневник
в счёт не входят. Счёт пересчитан по журналу вызовов после шага 4:
у шага 3 первая запись занизила его (5 → 6).

Подготовка до шага 1 — чтение брифов, рулингов, `CLAUDE.md`, схемы, пяти
скиллов, шаблона `continue` форка, кода инсталлятора и `journal.py`:
20:17–20:25, 15 ходов. В счёт шагов не входит.

## Шаг 1 — установка: `init` → `install` → `check`

| Поле | Значение |
| --- | --- |
| шаг | 1 |
| артефакт | — (окружение: `openspec/config.yaml`, `.claude/`, `.symphysis/`) |
| скилл | — (инсталлятор `installer/`, форк `init`) |
| что сделал скилл | `init --tools claude --no-animation` создал каркас `openspec/` и 6+6 workflow-файлов; `install` поставил 5 скиллов и инструменты, слил `config.yaml` (`spec-driven` → `symphysis`, rules добавлены); `check` — код 0 |
| руками | (1) workflow `continue` не ставится профилем по умолчанию — добавил `continue` в глобальный конфиг OpenSpec (`config set workflows …`, вне проекта) и повторил `init`; (2) путь `--project` пришлось дать с прямыми слешами: `X:\symphysis` без кавычек в Git Bash превратился в drive-relative `X:symphysis`, и инсталлятор молча поставил всё в `installer/symphysis/` — удалил, повторил |
| сломалось | `check` против неверного каталога (`installer/symphysis/`) дал `check: ok` — проверка не знает, что каталог не проект (ни `.git`, ни `openspec/` там не было до install) |
| без опоры (поймано на шаге?) | — |
| развилка↔факт | — |
| улики не нашлись | — |
| переделано | `install` + `check` — второй раз, из-за пути (моя ошибка кавычек, не инсталлятора) |
| не хватило скрипта | `check` не проверяет, что workflow `continue` (или команда `/opsx:continue`) установлен у клиента — а схема без него не ходит; `install` не предупреждает, что проект не содержит `openspec/` (ставит в любой каталог) |
| время | 20:25–20:28 |
| ходы | 11 |

Ход:

- `node upstream/openspec/bin/openspec.js init --tools claude --no-animation` —
  интерактивных вопросов не было (`< /dev/null`, код 0). Вывод: «6 skills
  and 6 commands in .claude/ … Note: 6 more workflows are available (new,
  continue, ff, bulk-archive, verify, onboard). Add them with `openspec config
  profile`». Создано: `openspec/config.yaml` (`schema: spec-driven`,
  комментарии-примеры), `openspec/specs/.gitkeep`,
  `openspec/changes/archive/.gitkeep`, `.claude/commands/opsx/{apply,archive,
  explore,propose,sync,update}.md`, `.claude/skills/openspec-*/SKILL.md` ×6.
  **`continue` среди них нет** — рулинг 3 велит читать его из `.claude/`.
- Глобальный конфиг форка (`openspec config path` →
  `C:\Users\User\AppData\Roaming\openspec\config.json`) до прогона:
  `profile: custom`, `workflows: propose, explore, apply, update, sync,
  archive`. Неинтерактивного пути к `continue` кроме правки глобального
  списка нет (`config profile` без TTY отказывает: «Interactive mode
  required»; у `init --profile` только `core|custom`, custom берёт список
  из глобального конфига). Сделано:
  `openspec config set workflows '["propose","explore","apply","update","sync","archive","continue"]'`,
  затем `init --tools claude --no-animation` повторно → «Refreshed: Claude
  Code, 7 skills and 7 commands». **Побочный эффект вне проекта**;
  откат: `openspec config set workflows '["propose","explore","apply","update","sync","archive"]'`.
  `.claude/skills/openspec-continue-change/SKILL.md` (143 строки) несёт шаг
  вердикта (`verdict: "mismatch"` — строка 70) — тот же текст, что
  `VERDICT_CHECK` в `continue-change.ts:47`.
- `cd installer && npm install && node scripts/sync-payload.js` — «payload: 14
  источников», 37 файлов.
- `node bin/symphysis.js install --project X:\symphysis` (без кавычек) → «записано 38»
  в `installer/symphysis/` — drive-relative путь. `check` с тем же путём: «check:
  ok». Удалено `rm -rf installer/symphysis`.
- `node bin/symphysis.js install --project X:/symphysis` → «записано 27;
  config.yaml уже был: схема переключена с spec-driven на symphysis, rules
  добавлены». Файлы схемы (10) не в списке: байты совпали — ожидаемо
  (рулинг 2), сообщения `skipped` нет, потому что одинаковые файлы
  не считаются пропуском.
- `SYMPHYSIS_OPENSPEC=X:/symphysis/upstream/openspec/bin/openspec.js node bin/symphysis.js check --project X:/symphysis`
  → «check: ok», код 0.
- Поставлено: `.symphysis/tools/{journal.py, journal_apply.py, journal_cli.py,
  journal_model.py, journal_render.py, journal-roots.json,
  playground-template.html}`, `.symphysis/docs/journal.schema.json`,
  `.claude/skills/symphysis-{attack,brainstorm,edge-probe,prohibition-probe,viewer}/`.
  `journal-roots.json` = `{"": "<root>/.."}` — как ожидал рулинг 5.
- `.gitignore` += `.claude/`, `.symphysis/` (рулинг 2). Воспроизведение:
  команды выше (`config set workflows`, `init --tools claude --no-animation`,
  `npm install`, `sync-payload`, `install --project X:/symphysis`).
  `openspec/specs/.gitkeep` и `openspec/changes/archive/.gitkeep` — каркас
  `init`; коммитятся вместе с `config.yaml` (в рулинге 2 не названы,
  без них `git status` остаётся грязным).

## Шаг 2 — `decisions` (decisions.json)

| Поле | Значение |
| --- | --- |
| шаг | 2 |
| артефакт | `decisions` → `decisions.json` (27 записей, 89 улик) |
| скилл | `symphysis-brainstorm` — назван instruction; интервью не велось |
| что сделал скилл | — (интервью нужен человек; журнал — перенос журнала плана, рулинг 5). `check --write` сверил улики; `render-md`, `render-html` собрались; `status` форка: `decisions` done, `research` ready |
| руками | (1) перенос: `docs/plan-implementation.journal.json` → `decisions.json` скриптом-однодневкой (`title`, `source`, `intro` под изменение, записи дословно); (2) корни улик: `.symphysis/tools/journal-roots.json` дописан тремя корнями вне проекта (`store/`, `playground/`, `md4h/`) — иначе 27 улик «файла нет» |
| сломалось | `new change` кладёт в каталог только `.openspec.yaml`; скилл говорит «шаблон уже лежит там (`title`, `source`, `intro`, `records: []`)» — его там нет, шаблон приходит полем `template` в `instructions --json` |
| без опоры (поймано на шаге?) | — |
| развилка↔факт | — |
| улики не нашлись | 27 из 89 при корнях по умолчанию (`{"": "<root>/.."}`): `store/` 19, `playground/` 6, `md4h/` 2 — все «файла нет», ни одной «цитаты нет дословно»; после правки корней — 89 из 89 |
| переделано | `check --write` — дважды (до и после корней) |
| не хватило скрипта | `install` создаёт корни `{"": "<root>/.."}` и не переносит корни проекта-источника (`tools/journal-roots.json` непереносим: там `<root>` — корень репозитория, в установленной копии — `.symphysis/`); скрипта «добавить запись/корень» нет — JSON правится руками |
| время | 20:29–20:30 |
| ходы | 6 |

Ход:

- `status --json` → `decisions` ready, остальные blocked; `instructions decisions --json` —
  instruction зовёт `symphysis-brainstorm`, rules три, `template` — пустой
  журнал. `planningHome.defaultSchema: "spec-driven"` при `schema: symphysis`
  в `config.yaml` — поле глобального умолчания, изменение берёт схему
  из `.openspec.yaml` (`schema: symphysis`); заметка, не поломка.
- **Нужен человек:** интервью по пяти перспективам (`symphysis-brainstorm` §2–3) —
  вопросы «что главное, как выглядит готово» задаются человеку. В прогоне
  их заменяет уже прожитый круг плана: 22 развилки решены словом владельца
  в просмотрщике плана, 5 фактов с уликами, одна парковка «материалы»
  (F-01) с `finding`.
- Перенос: `scratchpad/transfer.py` (не в репозитории) — `json.load` →
  `title: «Журнал решений: symphysis-schema»`, `source: decisions.json`,
  `intro` += абзац о переносе и корнях → `save_journal` из установленной
  копии `journal_model`. `validate_journal` — ok.
- `py -3.13 -X utf8 .symphysis/tools/journal.py check --write …/decisions.json`
  при корнях по умолчанию: «улик сверено 62 из 89», 27 строк `[!!] … — файла
  нет` (все три внешних префикса). Код 0 — сигнал, не стоп (F-12).
- Корни: `.symphysis/tools/journal-roots.json` ←
  `{"": "<root>/..", "store/": "X:\\skills-store", "playground/": "<home>/.claude/plugins/marketplaces/claude-plugins-official/plugins/playground/skills/playground", "md4h/": "<home>/.vscode/extensions/concretio.markdown-for-humans-0.4.5"}`.
  Файл в `.gitignore` (`.symphysis/`), воспроизведение — эта строка.
  Повторный `check --write` — «89 из 89».
- `render-md` → `decisions.md` (27 записей); `render-html` →
  `openspec/changes/symphysis-schema/decisions.html` (142 КБ; путь человеку —
  рулинг 4, не открывался). Рендеры — производные, но лежат в каталоге
  изменения и уйдут в коммит вместе с ним (скиллы считают их частью
  каталога изменения).
- `status --json`: `decisions` done (`existingOutputPaths: [decisions.json]`),
  `research` ready. Вердикта у `decisions` нет (не вердикт-артефакт).

## Шаг 3 — `research` (research/F-01.md)

| Поле | Значение |
| --- | --- |
| шаг | 3 |
| артефакт | `research` → `research/F-01.md` (один файл: в журнале одна парковка «материалы») |
| скилл | — (у `research` скилла нет, F-05.C: правила в instruction) |
| что сделал скилл | instruction + шаблон: frontmatter `genre/question/brief`, «Найдено» с `путь:строка «цитата»`, «Не найдено» с «искал:», «Вопросы, которые открылись» — заполнены по прочитанным файлам |
| руками | парковка F-01 уже несла `finding` (исследование прожито в плане 28.10) — файл написан заново по источникам, не из `finding`: 14 находок с номерами строк из `md4h/readme.md`, связки md4h в store и `tools/journal_apply.py`; два отрицания с шаблонами поиска |
| сломалось | — |
| без опоры (поймано на шаге?) | — |
| развилка↔факт | — |
| улики не нашлись | — (все цитаты взяты из файлов при чтении; `docs/FEEDBACK.md`, на который ссылается readme md4h, в расширении отсутствует — «не найдено» с «искал») |
| переделано | — |
| не хватило скрипта | жанр и структуру отчёта ничто не проверяет (`openspec validate` смотрит только spec-грамматику); «не найдено» без «искал» никто не отвергнет, кроме атаки |
| время | 20:31–20:33 |
| ходы | 6 |

Ход:

- `instructions research --json` — `rules: null` (у `research` в `config.yaml`
  правил нет; поле отсутствует, не пустой список), `resolvedOutputPath` —
  glob `research/**/*.md`, зависимость `decisions` done. Мой первый разбор
  JSON упал на отсутствующем ключе `rules` — моя ошибка, не форка.
- Источники прочитаны заново: `grep -n` по `readme.md` расширения
  (строки 43, 45, 48), `feedback.md` связки store (строки 2, 4, 8, 9, 19,
  22, 27, 29), `tools/journal_apply.py` (381, 387, 537, 555).
- Два вопроса открылись: версия формата `md4h-feedback/v2` (что делает
  `apply-md4h` на v3) и детерминизм рендера `decisions.md` для якорей —
  кандидаты в записи; в журнал не внесены (их внесёт второй круг или проба).

## Шаг 4 — `attack-decisions` (attack/decisions.md), два прохода

| Поле | Значение |
| --- | --- |
| шаг | 4 |
| артефакт | `attack-decisions` → `attack/decisions.md`; проход 1 — `gaps_found`, проход 2 — `passed` |
| скилл | `symphysis-attack` (оба прохода); `symphysis-brainstorm` — второй круг по instruction, интервью не велось |
| что сделал скилл | FORCE-проход по 27 записям, поле за полем; линзы журнала — context-compliance, research-resolution, claim-authority, claim-extraction, coverage; измерения грепом/`ls`/`git log` до строки. Проход 1: 54 строки — 0 блокеров, 10 предупреждений, 44 справки → `gaps_found`; `notes[]` ← строка итога; `status --json`: `verdict: mismatch`, `proposal` blocked. Второй круг (вызов 5, ветка `VERDICT_CHECK`): десять строк закрыты правкой записей; проход 2 с начала (хеш разошёлся) — 54 строки, 54 справки → `passed`; `status`: `verdict: ok`, `proposal` ready |
| руками | (1) второй круг без человека: десять правок записей скриптом-однодневкой (`fix1.py`) — только поля модели (consequences F-04, F-09, F-13, F-18, F-19, F-25, F-26; `why` F-10, F-14; `reversibility` у F-01…F-19 с причинами), `decision` не тронуто; (2) покрытие «чисто» — одной строкой на запись («остальные поля»), не на каждое поле: 27 строк вместо ~160; (3) атака шла в том же контексте, что писал перенос и research — второго контекста нет; (4) три ячейки переписаны без `\|` после отказа парсера (см. «сломалось»); (5) счёт строк по тяжестям для `notes[]` — до записи таблицы, вручную |
| сломалось | `render-html --attack attack/decisions.md` → код 2: «в строке таблицы ячеек 8, нужно 7 (`\|` внутри ячейки не поддерживается)» — парсер файла атаки не понимает экранированную черту markdown; просмотрщик не собрался, пока ячейки не переписаны |
| без опоры (поймано на шаге?) | 10 — все пойманы на шаге 4 (атака журнала), все в полях модели: 7 устаревших имён и ссылок в `consequences` (F-04 `decisions.md`, F-13 `attack.md`, F-19 `Э5`, F-25 `Task D4b`, F-26 `Task D7`, F-18 «форк плагина — поставка П7» при F-26.B, F-09 «два закрытых списка»), 2 пустых `why` (F-10, F-14), 1 — обратимость не оценена у 19 решённых записей. Слово человека — ни одно |
| развилка↔факт | — (ни одна развилка фактом не оказалась и наоборот) |
| улики не нашлись | 0 из 89 (`check --write` в обоих проходах — «89 из 89») |
| переделано | атака целиком: 54 строки написаны дважды — после правки цели хеш разошёлся, скилл запрещает перенос строк («прежние строки не переносятся») |
| не хватило скрипта | (a) счёт строк по тяжестям и сверка `status` с таблицей — руками; (b) валидность строки (слуг из списка, тяжесть из трёх, инвариант) проверяет только парсер просмотрщика — и он падает на `\|`; (c) «у решённой записи есть `reversibility`» и «у рекомендации непустой `why`» — детерминированные инварианты, `check` их не проверяет; (d) существование путей и имён из `consequences` (doc-verifier «существование грепом») — делал руками, скрипта нет; (e) строки `notes[]` добавляются python-однострочником — команды нет |
| время | 20:33–20:43 |
| ходы | 18 (проход 1 — 9, второй круг и проход 2 — 9) |

Ход:

- Вызов 4: `status --json` → `attack-decisions` ready, `verdict: missing`,
  `existingOutputPaths: []` → обычная ветка (файла нет).
  `instructions attack-decisions --json`: rules — одна строка FORCE,
  зависимость `research` done, `verdict: null` в выводе instructions
  (вердикт показывает только `status`).
- Второй круг (instruction, до атаки): парковки «материалы» — одна (F-01),
  `finding` уже есть, `research/F-01.md` его подтверждает; записи не правил.
  **Нужен человек:** «Начать новый круг?» — не задан никому; строка
  «брейншторм закончен по решению человека» в `notes[]` не записана.
  Два вопроса из `research/F-01.md` записями не стали.
- Проход 1 (`symphysis-attack` §1–§5): `check --write` → 89/89; измерения
  одной командой (`grep -c -i copyright`, `grep подтверждён…`, `grep
  архитектор`, `grep showSaveFilePicker`, `ls references`, `git log
  --diff-filter=D`, `grep D4b`, теги форка, `grep consequences
  journal_render.py`). Находки — в `attack/decisions.md` прохода 1 (текст
  перезаписан проходом 2; строки прохода 1 перечислены в поле «без опоры»).
  Тяжесть: по таблице линз 9 из 10 находок — «блокер» (claim-extraction
  «несуществующее», research-resolution «пустой why»); снижены
  до «предупреждение» с причиной: записи решены словом человека, страдает
  только `design.md` (куда `render-design` переносит `consequences`
  дословно — `tools/journal_render.py:98-99`), не цель изменения.
  Строка итога → `notes[]`, затем `check --write`, `sha256sum` →
  `4cf42da4…`; файл с `status: gaps_found`.
- Рулинг 9, после прохода 1: `status --json` → `attack-decisions ready
  mismatch ['attack\decisions.md']`, `proposal blocked`, `nextSteps[0]`:
  «Artifact "attack-decisions" has verdict status=gaps_found but passed is
  required — run its instruction again». Совпадает с C5.
- Вызов 5 (ветка `VERDICT_CHECK` шаблона `continue`): `instructions` те же;
  второй круг — `fix1.py` (валидация `validate_journal` ok), `check` 89/89,
  `render-md`; `notes[]` ← строка второго круга и строка итога прохода 2;
  `check --write`; `sha256sum` → `3096773b…`. Проход 2 — таблица
  с начала: 10 строк подтверждения правок (справка, опора есть), прежние
  справки перепроверены, F-16 получила строку (источники схем
  `project → user → package`, `resolver.ts:308`), 27 «чисто». `passed`.
- Рулинг 9, после прохода 2: `attack-decisions done ok`, `proposal ready`,
  `nextSteps`: «Run openspec instructions proposal…». Совпадает с C5.
- Рулинг 8, след линз: context-compliance — 5 строк (2 предупреждения
  прохода 1: F-18, обратимость ×19; 3 справки); research-resolution — 5
  (2 предупреждения: `why` F-10, F-14; 3 справки); claim-authority — 3
  (1 предупреждение: F-09; 2 справки: пять выпусков, четыре скилла);
  claim-extraction — 15 (5 предупреждений: F-04, F-13, F-19, F-25, F-26;
  10 справок); coverage — 27. **Молчали:** requirement-coverage,
  task-completeness, dependency-correctness, key-links, scope-sanity,
  verification-derivation, scope-reduction, data-contracts, honest-verifier —
  у них в таблице скилла цели только артефакты. **Строка без своей линзы:**
  «обратимость не оценена у решённых записей» — положена под
  context-compliance как ближайшую, с причиной; «пустое `decision.word`» —
  справка там же. Строк «по спеке не выводится» — 0: вопросов человеку
  атака журнала не породила.
- `render-html … --attack attack/decisions.md` — код 2 (см. «сломалось»);
  после замены `\|` в трёх ячейках — повтор ниже, в шаге 5.

## Шаг 5 — `proposal` (proposal.md)

| Поле | Значение |
| --- | --- |
| шаг | 5 |
| артефакт | `proposal` → `proposal.md` (9 capabilities, все новые) |
| скилл | — (правила instruction + rule «сначала запись») |
| что сделал скилл | instruction: Why/What Changes/Capabilities/Impact, основание — F-NN, capabilities по устойчивому поведению; rule: утверждение без F-NN — предположение. Написано по 27 решённым записям; каждая capability и каждый пункт What Changes несут номера F-NN; `status`: `proposal` done, `specs` и `design` ready |
| руками | состав capabilities (9) — суждение модели по группировке решений; «Modified Capabilities — нет» — `openspec/specs/` пуст |
| сломалось | `instructions proposal --json` → `context: null`: блок `context` из `config.symphysis.yaml` при слиянии с существующим `config.yaml` не перенесён (`install` сливает только `schema` и `rules`; README так и описывает) — модель не получила «Проект использует схему symphysis…» |
| без опоры (поймано на шаге?) | — (все утверждения привязаны к F-NN; проверит атака артефактов) |
| развилка↔факт | — |
| улики не нашлись | — |
| переделано | — |
| не хватило скрипта | привязку утверждений к F-NN («каждое утверждение о механике — с записью») ничто не проверяет, кроме атаки; существование названных F-NN грепом — скриптом было бы детерминированно |
| время | 20:44–20:45 |
| ходы | 2 (instructions, запись файла; `status` — общий с шагом 6) |

Ход:

- `status --json` после `passed`: `proposal` ready, `design` blocked (requires proposal).
  `instructions proposal --json`: rules — «утверждение … без записи F-NN —
  предположение», зависимость `attack-decisions` done, `unlocks: [specs, design]`.
- Просмотрщик, режим «проверка» перед proposal (скилл viewer): `render-html
  --attack` — первая попытка код 2 (`\|`), ячейки переписаны (две строки
  ещё держали `\|` внутри backticks — парсер не различает code span),
  повтор — в шаге 6.
- `proposal.md`: Why — F-06, F-23, F-25, F-20, F-02, F-12, F-27, F-04, F-05,
  F-13, F-17, F-26, F-15, F-16, F-19; capabilities: `decision-journal`,
  `artifact-graph`, `verdict-readiness`, `brainstorm-interview`,
  `requirement-probes`, `artifact-attack`, `decision-viewer`,
  `skill-transfer`, `project-installer` — у каждой список F-NN.
- `status --json`: `proposal` done; **`specs` и `design` ready одновременно**
  (design требует только proposal) — workflow берёт первый ready: `specs`.

## Шаг 6 — `specs` (specs/*/spec.md), пробы краёв и запретов

| Поле | Значение |
| --- | --- |
| шаг | 6 |
| артефакт | `specs` → 9 файлов `specs/<capability>/spec.md`, 23 требования, 45 сценариев; журнал 27 → 83 записи (F-28…F-83), улики 89 → 145 |
| скилл | `symphysis-edge-probe`, `symphysis-prohibition-probe` (оба по instruction `specs`); просмотрщик — `symphysis-viewer` |
| что сделал скилл | instruction + rules (`предположение … проверить\|решить`, сценарий у каждого требования): написаны 23 требования с SHALL/MUST, у 5 — пометка «предположение» с дорогой «проверить/решить». Проба краёв: форма у каждого требования названа моделью, категории по фильтру применимости, 45 кандидатов с четырьмя вариантами дословно, уликой `### Requirement: …` и рекомендацией после вариантов; проба запретов: такт 1 про себя, такт 2 оставил 7 запретов (ценности/продукт), 4 пункта канона — парковки адресату ИБ (факты `припаркован`); комментарии «проба краёв/запретов» под каждым требованием; две строки `notes[]`; `check` 145/145; `render-md`, `render-html --attack` — код 0 |
| руками | (1) записи-кандидаты — 56 штук — сгенерированы скриптом-однодневкой (`probes.py`) из компактных кортежей: команды «добавить запись» у `journal.py` нет; (2) комментарии spec.md заполнены тем же скриптом; (3) 5 требований укорочены после `validate --strict` (>500 символов); (4) состав форм и категорий — суждение модели (F-08.D), человек не правил |
| сломалось | `openspec validate symphysis-schema --strict` — код 1 до и после укорочения (см. ход); виновник — см. ниже |
| без опоры (поймано на шаге?) | 5 предположений помечены самим автором (детерминизм рендера; цели атаки без `research/`; гейт на пин; `references/` у viewer; `context` при слиянии) — по rule, до атаки |
| развилка↔факт | — (кандидаты проб — развилки по определению; 4 канона — факты-парковки) |
| улики не нашлись | 0 из 145 |
| переделано | 5 требований (текст >500 символов → короче, детали ушли в сценарии) |
| не хватило скрипта | (a) добавление записи в журнал и заполнение комментариев spec.md — руками/однодневкой; (b) `validate --strict` красит длину требования, но не форму кандидата пробы (четыре варианта дословно, префикс `[категория · форма]`) — проверяемо детерминированно, не проверяется; (c) счёт N/a/b/c/d для `notes[]` — руками |
| время | 20:45–20:55 |
| ходы | 19 (+5 — хвост шага 4: четыре правки `\|` в файле атаки и повтор `render-html`) |

Ход:

- `instructions specs --json`: rules две, зависимость `proposal`,
  `unlocks: [security, tasks, attack-artifacts]`; glob `specs/**/*.md`.
- Написаны 9 файлов. `validate symphysis-schema --strict` → код 1,
  5 WARNING «Requirement text is very long (>500 characters)» — укорочены.
  **Нужен человек:** все 52 кандидата (45 краёв + 7 запретов) открыты;
  исходы не ставились, сценариев Specify нет; просмотрщик собран —
  `openspec/changes/symphysis-schema/decisions.html` (режим «решения»:
  56 новых записей; «атака»: `attack/decisions.md`). Не открывался.
- Пробы: `probes.py` → «записей: 83; краёв 45, запретов 7, канон 4»;
  `validate_journal` ok; `check` «145 из 145» (улики кандидатов —
  строки `### Requirement:` в spec.md, корень `""`). Две строки `notes[]`:
  «проба краёв: кандидатов 45, Specify 0, Dismiss 0, Backstop 0, Defer 0;
  без решения все: F-28…F-72 — нужен человек», «проба запретов:
  требований 23, оставлено 7, канон → ИБ 4 (парковок 4), … — нужен
  человек».
- Наблюдённые в прогоне края вошли кандидатами: `\|` в ячейке атаки (F-30),
  два `ready` одновременно (F-34), нуль парковок «материалы» — тупик
  `research` (F-36), пустое слово решения (F-46), `references/` у viewer
  (F-64), CRLF и хеши целей (F-31).
- `status --json`: `specs` done (9 путей в `existingOutputPaths`),
  `design` и `security` ready, `tasks` blocked (требует design).

## Шаг 7 — `design` (design.md)

| Поле | Значение |
| --- | --- |
| шаг | 7 |
| артефакт | `design` → `design.md` (рендер 359 строк + три раздела руками) |
| скилл | — (`render-design` + правила instruction) |
| что сделал скилл | `render-design` собрал Context (5 фактов + 4 канон-парковки как факты), Decisions (22 решения, «в одну сторону» первым — F-14, по обратимости из шага 4), Risks / Trade-offs (46 строк), Open Questions (52 кандидата, 5 парковок, 5 споров); руками — Context (вводный абзац), Goals / Non-Goals, Migration Plan; `status`: `design` done, `security` и `tasks` ready |
| руками | Context, Goals / Non-Goals, Migration Plan — как велит instruction; заглушка рендера в Migration Plan («Не применимо к журналу решений; см. tasks.md») заменена текстом |
| сломалось | баннер рендера «> Рендер из `decisions.json`, не править руками» стоит над файлом, который instruction велит дописывать руками — противоречие текстов, не поломка; Risks / Trade-offs — строки вида «[Risk] rules: (F-06, отвергнут C: …) → Mitigation: решение D»: «риск» — цитата улики отвергнутого варианта, не формулировка риска; канон-парковки (F-80…F-83) попали в Context как факты |
| без опоры (поймано на шаге?) | — (проверит атака артефактов) |
| развилка↔факт | 4 канон-парковки — факты по схеме (`kind: факт`, `припаркован`), в Context читаются как утверждения о системе, хотя утверждают только «канон применим» |
| улики не нашлись | — |
| переделано | — |
| не хватило скрипта | рендер Risks не отличает цитату-улику от формулировки риска — поля «риск» в журнале нет; Open Questions не разделяет кандидатов проб (52) и развилки замысла — читателю design.md 52 строки `[категория · форма] …` закрывают содержание |
| время | 20:56–20:57 |
| ходы | 7 |

Ход:

- `instructions design --json`: rules две («решение излагается, не принимается»;
  «утверждение без F-NN — предположение»), зависимость `proposal` done,
  `unlocks: [tasks, attack-artifacts]`.
- `render-design … --out design.md` — код 0, 359 строк / 66 КБ: Decisions
  начинается с F-14 («в одну сторону»), дальше F-01…; улики с номерами
  строк из `check --write`.
- Руками: Context — абзац состояния и ограничений с F-NN, мотивация —
  ссылкой на proposal.md; Goals / Non-Goals — с F-NN; Migration Plan —
  шаги установки (включая профиль с `continue` — наблюдение шага 1)
  и откат.
- `status --json`: `design` done; `security` и `tasks` ready одновременно
  (tasks требует specs + design); workflow берёт `security`.

## Шаг 8 — `security` (security.md)

| Поле | Значение |
| --- | --- |
| шаг | 8 |
| артефакт | `security` → `security.md` (7 строк: 5 пунктов instruction + 2 из парковок ИБ) |
| скилл | — (instruction + rule «канон не чеканится в журнал») |
| что сделал скилл | таблица «пункт · применимо/неприменимо — причина · чем проверено»; применимые называют требование specs или честно пишут, что закрывающего требования нет; парковки F-80…F-83 из пробы запретов легли строками |
| руками | три проверки кодом перед таблицей (`_resolve` без защиты от `../`; `find_quote` с `errors="replace"`; `esc(` в шаблоне) — чтение файлов, не тесты |
| сломалось | — |
| без опоры (поймано на шаге?) | 3 строки «применимо — закрывающего требования в specs нет» (инъекции через файлы, `../`, HTML) — поймано здесь, до атаки; по линзе task-completeness атаки это блокеры |
| развилка↔факт | — |
| улики не нашлись | — |
| переделано | — |
| не хватило скрипта | «чем проверено» — чтение кода руками; тест на `../` и на `<script>` — кандидаты (tasks 2.3, 8.2) |
| время | 20:58–21:00 |
| ходы | 2 (греп-проверки, запись файла) |

Ход:

- `instructions security --json`: rules одна, зависимость `specs` done,
  `unlocks: [attack-artifacts]`.
- Проверки: `tools/journal_apply.py:48-53` — `roots[prefix] / path[len(prefix):]`
  без проверки выхода за корень; `:78` — `read_text(…, errors="replace")`;
  `grep "esc(" tools/playground-template.html` — есть (331);
  `grep -i token|secret|password tools/*.py installer/lib/*.js` — пусто.
- Два пункта сверх пяти: инъекции в HTML (F-82) и телеметрия форка (F-79,
  наблюдение шага 1).

## Шаг 9 — `tasks` (tasks.md)

| Поле | Значение |
| --- | --- |
| шаг | 9 |
| артефакт | `tasks` → `tasks.md` (10 групп, 22 задачи с проверкой в строке) |
| скилл | — (instruction + rule «сначала запись») |
| что сделал скилл | группы по capabilities, порядок по зависимости (группа 1 — слово человека), каждая задача с проверкой; открытые кандидаты — допущения в строке (`допущение: F-NN открыт`) |
| руками | состав задач: «сверить сценарии spec.md с существующими тестами» на каждую capability — работа схемы уже сделана до прогона (Task 0–24 плана), задачи — приёмка спек тестами плюс наблюдения прогона |
| сломалось | — |
| без опоры (поймано на шаге?) | — |
| развилка↔факт | — |
| улики не нашлись | — |
| переделано | — |
| не хватило скрипта | «каждая задача называет проверку» и «допущение названо, не скрыто» — проверяемо грепом по строке, не проверяется |
| время | 21:00–21:01 |
| ходы | 1 (запись файла; instructions — общий вызов с шагом 8) |

Ход:

- **Нужен человек:** «открытый вопрос design, меняющий задачи, реши
  с человеком до списка» — 52 кандидата и 5 предположений; список
  построен с допущениями, группа 1 — их решение.
- `instructions tasks --json`: зависимости `specs`, `design` done.
- Оба артефакта (8 и 9) записаны одним ходом исполнителя — два вызова
  workflow подряд без промежуточного `status`; `status` после обоих —
  в шаге 10.

## Шаг 10 — `attack-artifacts` (attack/artifacts.md), один проход

| Поле | Значение |
| --- | --- |
| шаг | 10 |
| артефакт | `attack-artifacts` → `attack/artifacts.md`: 59 строк — 5 блокеров, 12 предупреждений (5 «по спеке не выводится»), 42 справки → `gaps_found` |
| скилл | `symphysis-attack` |
| что сделал скилл | FORCE-проход по 13 целям (журнал как опора, 9 spec.md, design, security, tasks): хеши после `check --write`, журнал первым в `targets[]`; линзы артефактов; покрытие поимённо (23 требования, разделы design, 7 строк security, 23 задачи); строка итога в `notes[]` до хеша; `status --json`: `verdict: mismatch`, подсказка «has verdict status=gaps_found but passed is required», `isPlanningComplete: false` |
| руками | (1) счёт строк по тяжестям — руками, и он ошибся: в `notes[]` «строк 60, справок 43», в таблице 59/42 (поправка в файле атаки, журнал не правился — хеш уже взят); (2) две ячейки с `\|` внутри backticks снова уронили `render-html --attack` (та же ловушка, что в шаге 4) — переписаны; (3) второго прохода нет: пять блокеров и семь из двенадцати предупреждений закрываются только словом человека (записи журнала, F-18, F-30…F-79, пять предположений) — `passed` недостижим без него; три предупреждения правкой артефакта (DJ1 «не редактируется руками», Goals, задача 1.1) оставлены в таблице, чтобы F2 считал их как есть |
| сломалось | `render-html --attack attack/artifacts.md` — код 2 на строке 45 (`\|`); **поправка к шагу 4:** там причина снижения тяжести опиралась на «`render-design` переносит consequences в design.md дословно (`journal_render.py:98-99`)» — строки 98-99 принадлежат `_render_record` (рендер markdown), `render_design` следствий не выводит: утверждение атаки было без опоры; снижения тяжести от этого не меняются (имена уходили в `decisions.md` и просмотрщик), но ошибка атаки зафиксирована |
| без опоры (поймано на шаге?) | 17 строк не-справок: 5 блокеров — security «применимо» без закрывающего требования (инъекции через файлы, `../`, бинарные, HTML, телеметрия); 5 «не выводится» — предположения specs (детерминизм рендера, цели атаки без `research/`, `context` при слиянии, `references/` у viewer, гейт на пин); 1 — требование о действии человека, не поведении (DJ1); 4 — design (Goals «со словом человека» при трёх пустых словах; F-18 как действующее при F-26; парковка F-01 с `finding` в Open Questions; Risks — цитаты улик, не риски); 2 — tasks (7 задач на открытых записях; задача 1.1 шире сеанса). Все пойманы на шаге 10 |
| развилка↔факт | 4 канон-факта (F-80…F-83) в Context design читаются как факты о системе — справка, не поломка |
| улики не нашлись | 0 из 145 |
| переделано | — (повтор атаки не делался — см. «руками» (3)) |
| не хватило скрипта | (a) счёт строк по тяжестям (ошибся на 1); (b) «`\|` в ячейке» — второй раз за прогон; (c) хеши 13 целей — `find … xargs sha256sum` руками и перенос в YAML руками; (d) «применимо без требования» в security и «задача на открытой записи» в tasks — грепом проверяемые инварианты (строка «допущение: F-NN открыт» ↔ `status` записи); (e) рендер design не отличает закрытую парковку от открытой и цитату от риска — поле/правило для `render-design` |
| время | 21:01–21:05 |
| ходы | 7 (instructions — общий вызов с шагами 8–9; измерения 3, заметка+хеш 1, запись файла 1, `status`+рендер 1, правки 1) |

Ход:

- Вызов 10: `status --json` → `attack-artifacts` ready, `verdict: missing`,
  файла нет → обычная ветка. `instructions attack-artifacts --json`: цели
  названы в instruction, rules — FORCE.
- Измерения до строк: функция у `journal_render.py:98-99` — `_render_record`;
  существование `state.ts`, `frontmatter.ts`, `schema.ts`, `test/core/artifact-graph`,
  `test/commands/status-verdict.test.ts`, `tests/test_journal_render.py`,
  `installer/test` — все есть; хеши 12 файлов `find specs -name '*.md' | sort
  | xargs sha256sum; sha256sum design.md security.md tasks.md`.
- Строка итога → `notes[]` (6-я заметка), `check --write` «145 из 145»,
  `sha256sum decisions.json` → `cf569791…` — первым в `targets[]`.
- Рулинг 9, после записи: `attack-artifacts ready mismatch
  ['attack\artifacts.md']`, `isPlanningComplete: false`, `nextSteps[0]`:
  «Artifact "attack-artifacts" has verdict status=gaps_found but passed is
  required — run its instruction again». Совпадает с C5. Следующий вызов
  `continue` ушёл бы в ветку `VERDICT_CHECK` → атака снова → те же дыры:
  **прогон остановлен здесь — нужен человек.**
- Рулинг 8, след линз: task-completeness — 7 строк (5 блокеров security,
  2 справки); honest-verifier — 5 (все «по спеке не выводится»);
  context-compliance — 6 (4 предупреждения design, 2 справки);
  verification-derivation — 2 (1 предупреждение DJ1, 1 справка tasks);
  dependency-correctness — 1 (предупреждение); scope-sanity — 1
  (предупреждение); requirement-coverage — 1 (справка); key-links — 1
  (справка); scope-reduction — 1 (справка); data-contracts — 1 (справка);
  claim-extraction — 4 (справки); coverage — 28 (18 specs + 10 tasks).
  **Молчали:** ни одна — у каждой линзы артефактов есть строка (у журнала
  в шаге 4 молчали девять). **Строка без своей линзы:** «Risks — цитаты
  улик, не риски» — под context-compliance с причиной; «парковка с finding
  в Open Questions» — туда же. Тяжесть снижена с «блокер» до
  «предупреждение» с причиной в 3 строках из 17 (F-18, F-01 в Open
  Questions, задачи на открытых записях).
- `render-html … --attack attack/decisions.md --attack attack/artifacts.md`
  → код 2 (`\|`, строка 45); после правки двух ячеек — код 2 снова
  (строка 85, третья ячейка с `\|` внутри backticks: `grep "a\|b"`).
  Команда рендера стояла в цепочке `… | tail -1 && git add … && git commit`:
  код выхода пайпа — у `tail`, и коммит F1 (`1849834`) прошёл с несобранным
  `decisions.html` (от 20:55, без атаки артефактов) и непочиненной ячейкой —
  **та самая ловушка `| tail`, о которой предупреждал бриф.** Поправлено:
  третья ячейка переписана, рендер повторён с прямой проверкой кода,
  коммит дополнен (`amend`, не запушен — один коммит F1 по брифу).
  Итого за прогон `\|` уронил рендер четыре раза (шаг 4 — дважды, шаг 10 —
  дважды).

## Итог прогона (вызовы 1–10)

`status --json` на конец прогона: `decisions`, `research`, `attack-decisions`
(`verdict: ok`), `proposal`, `specs`, `design`, `security`, `tasks` — done;
`attack-artifacts` — ready, `verdict: mismatch` (`status: gaps_found`);
`isPlanningComplete: false`. Остановка — по рулингу 4: дальше нужен
человек (52 кандидата проб, 5 предположений specs, 5 канонов ИБ
без требования, пересмотр F-18).

Производные `.claude/` и `.symphysis/` — в `.gitignore`; глобальный конфиг
форка получил `continue` (откат — шаг 1). Время от `init` до последнего
`status`: 20:25–21:05, 40 минут; ходов по шагам: 11 + 6 + 6 + 18 + 2 + 19
+ 7 + 2 + 1 + 7 = 79 (плюс 5 хвоста шага 4 и 15 подготовки).
