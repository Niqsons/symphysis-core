# Дневник сухого прогона symphysis на себе

Прогон схемы symphysis на задаче `symphysis-schema` (Tasks 25–26 плана F).
Исполнитель: `ollama/deepseek-v4-pro:0813` через opencode.
Режим: без Claude Code — исполнитель сам исполняет workflow `/opsx:continue` (рулинг 3).
Формат шага — фиксированные поля (рулинг 6, 11): `шаг · артефакт · скилл · что сделал скилл · руками · сломалось · без опоры · развилка↔факт · улики не нашлись · переделано · не хватило скрипта · время · ходы`.

---

## Шаг 0. Окружение и вход

- **время**: 21:16–21:16 · **ходы**: 6 (чтение брифов, контекста, CLAUDE.md; сверка путей).

- **шаг**: чтение брифов `task-25-brief.md`, `task-26-brief.md`, контекста `task-25-context.md`, `CLAUDE.md`.
- **артефакт**: — (подготовка).
- **скилл**: —.
- **что сделал скилл**: —.
- **руками**: сверены пути и команды: CLI форка `node upstream/openspec/bin/openspec.js`, журнал `py -3.13 -X utf8 .symphysis/tools/journal.py`, инсталлятор `node installer/bin/symphysis.js`.
- **сломалось**: —.
- **без опоры**: —.
- **развилка↔факт**: рулинги 1–12 — факты (заданы человеком, не оспариваются).
- **улики не нашлись**: —.
- **переделано**: —.
- **не хватило скрипта**: —.

---

## Шаг 1. init → install → check

- **время**: 21:16–21:17 · **ходы**: 4.

- **шаг**: `init --tools claude --no-animation` → `install --project "X:/symphysis-dryrun-deepseek"` → `check`.
- **артефакт**: `openspec/config.yaml`, `.claude/` (производные).
- **скилл**: — (CLI форка и инсталлятор, не скилл).
- **что сделал скилл**: —.
- **руками**: порядок init→install→check выдержан вручную (рулинг 1).
- **сломалось**: —.
- **без опоры**: —.
- **развилка↔факт**: —.
- **улики не нашлись**: —.
- **переделано**: —.
- **не хватило скрипта**: инсталлятор слил `schema: symphysis` и `rules`, но **отбросил блок `context:`** из `config.symphysis.yaml` — в `openspec/config.yaml` после install остался только комментарий-заглушка `# Project context (optional)`. Контекст схемы (решения в журнале, улика = путь + цитата) до агента не доходит.

Детали:
- `init` создал `.claude/` (7 workflow-скиллов + команды `opsx`), `openspec/config.yaml` со `schema: spec-driven`.
- `install` → «записано 27», `config.yaml` переключён на `schema: symphysis` + `rules`.
- `check` → `check: ok`, код выхода 0.

---

## Шаг 2. `new change` + перенос журнала в decisions.json

- **время**: 21:17–21:18 · **ходы**: 5.

- **шаг**: `new change symphysis-schema --schema symphysis`; `decisions.json` = копия `docs/plan-implementation.journal.json`; `journal.py check --write`.
- **артефакт**: `openspec/changes/symphysis-schema/decisions.json`.
- **скилл**: — (`journal.py`, не скилл).
- **что сделал скилл**: —.
- **руками**: копия журнала плана (рулинг 5), перенос 27 записей F-01…F-27 с 89 уликами.
- **сломалось**: —.
- **без опоры**: —.
- **развилка↔факт**: 27 записей — 22 развилки + 5 фактов (F-20…F-24), перенесены как есть.
- **улики не нашлись**: **27 из 89** (`check` → «улик сверено 62 из 89»). Все 27 — пути к внешним материалам: `store/` (X:\skills-store), `playground/` (плагин claude), `md4h/` (расширение Markdown Editor for Humans). Корень: `.symphysis/tools/journal-roots.json` после install = `{"": "<root>/.."}` — **минимальный**, без префиксов `store/`, `playground/`, `md4h/`.
- **переделано**: —.
- **не хватило скрипта**: **инсталлятор не переносит исходный `tools/journal-roots.json`** (в нём прописаны `store/` → `X:\skills-store`, `playground/`, `md4h/`). В `installer/lib/install.js` жёстко задан `ROOTS_CONTENT = '{"": "<root>/.."}\n'` и пишется с `keepExisting: true`; `installer/scripts/sync-payload.js` в списке `FILES` не содержит `tools/journal-roots.json`. Итог — 27 улик «файла нет», хотя файлы физически есть во внешних корнях.

---

## Шаг 3. research — закрытие парковки «материалы» F-01

- **время**: 21:18–21:19 · **ходы**: 6.

- **шаг**: `instructions research --json` → написан `research/F-01.md`.
- **артефакт**: `openspec/changes/symphysis-schema/research/F-01.md`.
- **скилл**: — (instruction research не зовёт скилл по имени; механика из разбора).
- **что сделал скилл**: —.
- **руками**: чтение md4h readme (`$USERPROFILE/.vscode/extensions/concretio.markdown-for-humans-0.4.5/readme.md`), `store/.md4h/feedback/research/variant-B-.../feedback.md`, `store/research/variant-B-2026-10-28.md`; цитаты вписаны вручную с путём.
- **сломалось**: —.
- **без опоры**: —.
- **развилка↔факт**: парковка F-01 с адресатом «материалы» → ответ в `finding` (жанр: устройство).
- **улики не нашлись**: — (цитаты для research брались напрямую из внешних файлов, минуя roots).
- **переделано**: —.
- **не хватило скрипта**: —.

Детали: `research/F-01.md` — genre `устройство`, вопрос F-01, разделы `Найдено` (5 цитат) и `Не найдено`. Статус: research done, attack-decisions ready.

---

## Шаг 4. attack-decisions — атака журнала

- **время**: 21:19–21:24 · **ходы**: 14.

- **шаг**: второй круг брейншторма (закрыты материалы-парковки — их одна, F-01, уже с finding) → `instructions attack-decisions --json` → скилл `symphysis-attack` → `attack/decisions.md` → `status --json`.
- **артефакт**: `openspec/changes/symphysis-schema/attack/decisions.md`.
- **скилл**: `symphysis-attack` (FORCE stance, линзы plan-checker).
- **что сделал скилл**: дал закрытый список линз (13), форму таблицы (утверждение·раздел·линза·инвариант·тяжесть·опора·чем закрыть), правило вердикта (`passed` только при нуле блокер/предупреждение), правило «улики руками не грепать: `found: false` → строка «нет»».
- **руками**: сверка 27 записей по полям; выявление пустых `recommendation.why` (F-10, F-14); выявление 27 улик `found:false`; подсчёт строк таблицы; `check --write` + `sha256sum`; `status --json`.
- **сломалось**: —.
- **без опоры**: **поймано** — 15 записей с уликами `found:false` (claim-extraction) + 2 записи с пустым `recommendation.why` (research-resolution). «Не выводится» строк нет.
- **развилка↔факт**: — (атака не рождает развилок).
- **улики не нашлись**: 27 — те же внешние пути, что в шаге 2 (каскад от корня журнала).
- **переделано**: —.
- **не хватило скрипта**: **линзы атаки не покрывают `reversibility`** — у 24 из 27 записей `reversibility: null` (брейншторм требует поле, но ни одна линза атаки его не проверяет). Строка, которую не закрыла ни одна линза → дневник.

Детали:
- **Строки атаки**: 17 блокеров (15 `claim-extraction` + 2 `research-resolution`), 0 предупреждений, 10 справок (`coverage` «чисто»), 0 «не выводится».
- **Вердикт**: `status: gaps_found`.
- **`status --json` форка**: `attack-decisions` → `status: ready`, `verdict: mismatch`; `proposal` и всё ниже → `status: blocked` (`missingDeps: attack-decisions`). `nextSteps`: «Artifact "attack-decisions" has verdict status=gaps_found but passed is required — run its instruction again».
- **Хеш цели**: `69fa58491eae0eb751fc3f1fbeb21260db0c8cfcb163b0ad6339bdb55a2f5f37` (после `notes[]` и `check --write`).

**Что дала каждая линза (рулинг 8)**:
- `claim-extraction` — 15 строк (все 27 улик `found:false`).
- `research-resolution` — 2 строки (пустой `why` в F-10, F-14).
- `coverage` — 10 строк «чисто».
- Молчали: `requirement-coverage`, `task-completeness`, `dependency-correctness`, `key-links`, `scope-sanity`, `verification-derivation`, `context-compliance` (антиподы не «оба решены»), `scope-reduction`, `data-contracts`, `claim-authority`, `honest-verifier`.
- **Строка без линзы**: `reversibility` — 24 записи без оценки обратимости, ни одна линза не ловит.

**Причина блокировки графа** — две независимые:
1. Пустой `recommendation.why` у F-10 и F-14 (дефект исходного журнала плана).
2. Каскад инсталлятора: минимальный `journal-roots.json` → 27 улик «файла нет» → 15 блокеров claim-extraction, хотя файлы существуют во внешних корнях (фикс — переносить исходный `tools/journal-roots.json`, отдельная задача, не прогон).

---

## Блок остановки (шаг 4 завершён — прогон останавливается здесь)

- **время**: 21:24–21:29 · **ходы**: 6 (сводка контроллеру, ожидание ответа).

- **шаг**: вердикт `attack-decisions` = `gaps_found` → граф форка блокирует `proposal` и всё ниже. Контроллер выбрал **вариант 2**: остановка на `attack-decisions` — результат прогона, не поломка; человек отсутствует (рулинг 4), поля журнала за него не заполняются, в обход гейта не идти.
- **артефакт**: — (нет нового артефакта; прогон до `attack-artifacts` не доводится).
- **скилл**: —.
- **что сделал скилл**: —.
- **руками**: сведён статус графа, оформлен блок остановки.
- **сломалось**: — (блок — штатное поведение вердиктного гейта, не отказ).
- **без опоры**: 17 блокеров атаки зафиксированы выше; закрывать их в прогоне нельзя (корни — отдельная задача инсталлятора, рулинг 10; `why` — за человека, рулинг 4).
- **развилка↔факт**: —.
- **улики не нашлись**: 27 (каскад от корня журнала, шаги 2 и 4).
- **переделано**: —.
- **не хватило скрипта**: подтверждено два кандидата — (1) инсталлятор не переносит `tools/journal-roots.json`; (2) инсталлятор отбрасывает блок `context:` из `config.symphysis.yaml`; плюс (3) линзы атаки не покрывают `reversibility`.

### Вывод `status --json` (существенное)

```
"nextSteps": [
  "Artifact \"attack-decisions\" has verdict status=gaps_found but passed is required — run its instruction again",
  "Run openspec instructions attack-decisions --change \"symphysis-schema\" --json before writing that artifact."
]
```

Граф артефактов (id → status → requires):
- `decisions` → done
- `research` → done
- `attack-decisions` → ready, **verdict: mismatch**
- `proposal` → blocked (missingDeps: attack-decisions)
- `specs` → blocked (missingDeps: proposal)
- `design` → blocked (missingDeps: proposal)
- `security` → blocked (missingDeps: specs)
- `tasks` → blocked (missingDeps: specs, design)
- `attack-artifacts` → blocked (missingDeps: specs, design, security, tasks)

`isPlanningComplete: false`, `isComplete: false`, `applyRequires: [tasks, attack-artifacts]`.

### След линз (рулинг 8)

- **Дали строки**: `claim-extraction` (15), `research-resolution` (2), `coverage` (10 «чисто»).
- **Молчали** (не дали ни строки): `requirement-coverage`, `task-completeness`, `dependency-correctness`, `key-links`, `scope-sanity`, `verification-derivation`, `context-compliance`, `scope-reduction`, `data-contracts`, `claim-authority`, `honest-verifier`.
- **Строка без линзы**: `reversibility` — поле требуют (брейншторм), но ни одна линза атаки его не проверяет → 24 записи остались `null` незамеченными.

**Итог прогона**: граф доведён до `attack-decisions`; дальше вердиктный гейт остановил планирование. Причина — не поломка схемы, а две независимые дыры: пустой `recommendation.why` (дефект журнала плана) и каскад инсталлятора с корнями улик (ложные «файла нет»).
