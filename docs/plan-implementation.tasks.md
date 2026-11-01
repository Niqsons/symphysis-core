# symphysis — план задач

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** собрать в symphysis всё, что нужно для обкатки во flow-specs: схему OpenSpec `symphysis` с журналом решений, четыре скилла из GSD, форк OpenSpec со статусом по вердикту, служебные скрипты и npm-инсталлятор — и прогнать схему на ней самой.

**Architecture:** OpenSpec остаётся рамкой (граф артефактов, `status`, `/opsx:continue`); журнал решений — JSON-артефакт графа, markdown и HTML рендерятся из него; механики GSD — текстовые скиллы, которые зовёт instruction артефакта; форк меняется в двух точках (готовность по вердикту во frontmatter, шаг `continue` с проверкой вердикта); инсталлятор — npm-пакет поверх форка.

**Tech Stack:** OpenSpec 1.15.0 fork (TypeScript, Node ≥20.19, pnpm, vitest, zod, yaml); Python 3.13 (`py -3.13`, pytest, jsonschema); скиллы — markdown; просмотрщик — один HTML без зависимостей.

**Spec:** `docs/plan-implementation.md` (поставки, этапы, решения круга 1–2) и `docs/plan-implementation.journal.md` (развилки F-01…F-19 со словом человека, факты F-20…F-24). Исходники для переноса: `upstream/gsd-core`, `upstream/openspec`; разборы: `docs/analysis/step0-sources.md`, `docs/analysis/gsd-openspec-integration.md`.

## Сводка

Шесть частей, каждая — отдельно исполняемый подплан со своим выходом.
Порядок — по этапам плана; A, B, C, D после задачи 0 независимы.
Заголовки задач несут сквозной номер `Task N` (0–26) для скрипта
брифов; имена частей (A1, C3…) — в скобках и в ссылках по тексту.

| Часть | Этап | Поставка | Выход | Задач |
| --- | --- | --- | --- | --- |
| 0 | — | окружение и git | `pnpm test` форка зелёный, pytest ставится | 1 |
| A | Э1, Э4 | П2 формат журнала, П5 скрипты | `tools/journal.py`: import-md, check, render-md, render-html, apply, apply-md4h; JSON-схема | 6 |
| B | Э1 | П1 схема | `openspec/schemas/symphysis/` + `config.yaml`; `openspec status` показывает граф | 4 |
| C | Э3 | П4 форк | артефакт с `verdict` не `done` без `status: passed`; `continue` ведёт к вердикту | 5 |
| D | Э2 | П3 скиллы | четыре `skills/*/SKILL.md` с копиями GSD и перечнем отличий перевода | 5 |
| E | Э5 | П6 инсталлятор | `npx <пакет> install` / `check` | 4 |
| F | Э6 | сухой прогон | артефакты графа на задаче «спроектировать схему symphysis», отчёт со счётчиками | 2 |

**Мои решения, которых нет в журнале** (назвать человеку при ревью плана):

- артефакт графа — `decisions.json` (источник по F-01.B); `decisions.md` — рендер для человека и md4h, в граф не входит;
- второй круг брейншторма — не отдельный артефакт (тот же файл), а первый шаг instruction артефакта `attack-decisions`;
- чек-лист ИБ — артефакт `security.md` после `specs`, по адресату «ИБ» из F-11;
- ключи JSON — английские (`id`, `question`, `options`…), значения — русские; так уже устроен просмотрщик;
- вердикт объявляется в схеме полем `verdict: { frontmatter: status, value: passed }` у артефакта; glob-артефакт с `verdict` — ошибка схемы;
- инсталлятор — отдельный пакет `installer/` в symphysis, зависящий от форка по `file:`; имя пакета и публикация — слово человека (плейсхолдер `<scope>/symphysis`);
- git в symphysis заводится в задаче 0; `upstream/` в `.gitignore`, форк живёт в своём репозитории на ветке `symphysis`.

## Global Constraints

- Решение человека — в план дословно, с датой (`CLAUDE.md`).
- Утверждение о фреймворке — с `путь:строка` и цитатой; несверенное помечается «по разбору агента» (`CLAUDE.md`).
- Копии файлов GSD несут их copyright notice: «MIT License / Copyright (c) 2026 Open GSD» (`upstream/gsd-core/LICENSE:1-3`).
- Python — `py -3.13`: «под 3.14 нет пакетов, pip получает 403» (`CLAUDE.md`).
- В Git Bash нет `jq` — скрипты без него (`CLAUDE.md`).
- Файлы `.md` проекта — CRLF; `.py`, `.ts`, `.html`, `.json` — LF.
- Форк: upstream пин `6d04a1b5` (1.15.0); «каждый выпуск upstream сначала разбирается, потом решается, втягивать ли» (F-03).
- Результат сверки улик — сигнал, не стоп (F-12): скрипты печатают и возвращают 0, `--strict` возвращает 2.
- Адресаты парковки — ровно `материалы | человек | ИБ` (F-11).
- Рекомендация в просмотрщике — под списком вариантов, не диалогом (слово человека, круг 1).
- Перевод скиллов — не механический; у каждого скилла перечень мест, где смысл инструкции изменён (F-14).
- Числового гейта брейншторма нет; новый круг только по слову человека, отказ пишется строкой «брейншторм закончен по решению человека» (F-07).

## Review Focus

1. Цитата улики с переносом строки или с `«»` внутри — `check` обязан найти через схлопнутые пробелы и не падать на вложенных кавычках (A2).
2. Frontmatter с CRLF и с BOM — `readFrontmatter` обязан прочитать `status: passed` из файла, написанного на Windows (C2).
3. Glob-артефакт с `verdict` в схеме — `parseSchema` обязан отказать с именем артефакта, а не молча считать по первому файлу (C1).
4. Ответ человека с буквой, которой нет среди вариантов (`F-05: Q`) — `apply` обязан отказать поимённо и не менять JSON (A4).
5. Проект, где `openspec/config.yaml` уже есть с другой схемой — `install` обязан слить, не перезаписать, и назвать это (E2).
6. md4h-связка, чей `source_sha256` не совпадает с текущим рендером — `apply-md4h` обязан отказать до любой правки (A6).

---

## Task 0: окружение и git

**Files:**
- Create: `.gitignore`, `UPSTREAM.md` (в `upstream/openspec`), `requirements-dev.txt`
- Modify: `CLAUDE.md` (раздел «Окружение»)

**Interfaces:**
- Produces: команды окружения, которые читают все части: `py -3.13 -m pytest`, `pnpm --dir upstream/openspec test`, `node upstream/openspec/bin/openspec.js`.

- [ ] **Step 1: git в symphysis**

Run: `git -C X:\symphysis init -b main` и `.gitignore` со строками `upstream/`, `node_modules/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`. Первый коммит — всё, что лежит сейчас в `docs/`, `tools/`, `CLAUDE.md`.
Expected: `git status --short` пуст после коммита, `git check-ignore upstream/openspec` печатает путь.

- [ ] **Step 2: ветка форка и пин**

Run: `git -C upstream/openspec switch -c symphysis` и файл `upstream/openspec/UPSTREAM.md`: строка `upstream: Fission-AI/OpenSpec @ 6d04a1b5 (1.15.0)`, строка правила из F-03 дословно, пустая таблица «Выпуск upstream · разобран · решение».
Expected: `git -C upstream/openspec branch --show-current` → `symphysis`.

- [ ] **Step 3: pnpm и тесты форка до правок**

Run: `corepack enable && corepack prepare pnpm@latest --activate`; затем `pnpm --dir upstream/openspec install` и `pnpm --dir upstream/openspec test`.
Expected: тесты зелёные; число пройденных записать в `UPSTREAM.md` строкой «базовый прогон: N passed».

- [ ] **Step 4: python-зависимости**

`requirements-dev.txt`: `pytest`, `jsonschema`. Run: `py -3.13 -m pip install -r requirements-dev.txt` и `py -3.13 -m pytest --version`.
Expected: версия pytest напечатана.

- [ ] **Step 5: CLAUDE.md «Окружение»**

Добавить три строки: как запускать pytest, тесты форка, CLI форка (`node upstream/openspec/bin/openspec.js` до сборки пакета — `pnpm --dir upstream/openspec build`).

- [ ] **Step 6: Commit**

```bash
git add .gitignore requirements-dev.txt CLAUDE.md
git commit -m "chore: git, окружение форка и python"
```

---

## Часть A — формат журнала и скрипты (П2, П5)

### Task 1 (A1): JSON-схема журнала и миграция markdown → JSON

**Files:**
- Create: `docs/journal.schema.json`, `tools/journal.py`, `tests/test_journal_schema.py`, `tests/fixtures/` (копия `docs/plan-implementation.journal.md` как `journal-plan.md`)
- Modify: `tools/journal_render.py` → парсер переезжает в `tools/journal.py`, старый файл удаляется в A3

**Interfaces:**
- Produces: `journal.py` CLI с подкомандами (argparse): `import-md <md> --out <json>`, `check <json> [--strict]`, `render-md <json> --out <md>`, `render-html <json> --out <html> [--template]`, `apply <json> <answers.md|txt> [--date]`, `apply-md4h <json> <feedback.md> --render <md>`.
- Produces: функции `load_journal(path) -> dict`, `save_journal(path, journal) -> None` (JSON, `ensure_ascii=False`, indent 1, LF), `validate_journal(journal) -> list[str]` (ошибки по JSON-схеме плюс правила ниже).
- Схема (`journal.schema.json`, draft 2020-12): корень `{title, source, records[]}`; запись: `id` (`^F-\d+$`), `question`, `kind` (`развилка|факт`), `status` (`открыт|припаркован|решён`), `addressee` (`материалы|человек|ИБ|""`), `depends_on[]`, `delivery`, `options[] {letter, text, added, unlikely, evidence[] {path, quote, line?, found?, verdict?}}`, `antipodes[] {option, other}`, `recommendation {option, why}|null`, `decision {option, word, date}|null`, `reversibility {level: обратимо|дорого|в одну сторону, why}|null` (F-10), `outcome {kind: проба|вопрос, value, reason}|null` (F-09), `parking[] {addressee, text, finding?}`, `dispute`, `consequences`, `evidence[]` (улики записи), `comments[] {round, lines, text}` (из md4h).
- Правила сверх схемы: антипод ссылается на существующие `id.letter`; `depends_on` — существующие id, без самоссылок; у факта нет `options`; у варианта с `unlikely` непустая причина; `decision.option` — буква из `options`.

- [ ] **Step 1: тест схемы и миграции**

```python
# tests/test_journal_schema.py
def test_import_md_matches_counts(tmp_path):
    j = journal.import_md(FIX / "journal-plan.md")
    assert len(j["records"]) == 24
    assert sum(1 for r in j["records"] if r["kind"] == "развилка") == 19
    assert journal.validate_journal(j) == []

def test_validate_rejects_unknown_antipode():
    j = journal.import_md(FIX / "journal-plan.md")
    j["records"][1]["antipodes"].append({"option": "B", "other": "F-99.A"})
    assert any("F-99.A" in e for e in journal.validate_journal(j))

def test_validate_rejects_fact_with_options():
    j = journal.import_md(FIX / "journal-plan.md")
    fact = next(r for r in j["records"] if r["kind"] == "факт")
    fact["options"] = [{"letter": "A", "text": "x", "added": False, "unlikely": None, "evidence": []}]
    assert any(fact["id"] in e for e in journal.validate_journal(j))
```

- [ ] **Step 2: запустить — падает**

Run: `py -3.13 -m pytest tests/test_journal_schema.py -v`
Expected: FAIL, `ModuleNotFoundError: journal` или `AttributeError`.

- [ ] **Step 3: реализовать `import_md`, `validate_journal`, схему**

`import_md(path: Path) -> dict` — парсер из `journal_render.py` (`parse`) плюс поля `parking` списком (`парковка:` → один элемент; `находка:` → его `finding`), `outcome`/`reversibility` — `None`, `comments` — `[]`. `validate_journal(j: dict) -> list[str]` — `jsonschema.Draft202012Validator` по `docs/journal.schema.json` плюс правила выше, каждая ошибка — строкой с id записи.

- [ ] **Step 4: запустить — проходит**

Run: `py -3.13 -m pytest tests/test_journal_schema.py -v`
Expected: PASS ×3.

- [ ] **Step 5: мигрировать журнал плана**

Run: `py -3.13 tools/journal.py import-md docs/plan-implementation.journal.md --out docs/plan-implementation.journal.json`
Expected: файл создан, `validate_journal` пуст; markdown-журнал остаётся до A3.

- [ ] **Step 6: Commit**

```bash
git add docs/journal.schema.json tools/journal.py tests/ docs/plan-implementation.journal.json
git commit -m "feat(journal): JSON-схема журнала и миграция из markdown"
```

### Task 2 (A2): сверка улик `check`

**Files:**
- Modify: `tools/journal.py`
- Test: `tests/test_journal_check.py`

**Interfaces:**
- Produces: `check_evidence(journal: dict, roots: dict[str, Path]) -> dict` → `{"total": int, "found": int, "missing": [str]}`, мутирует улики полями `line`, `found`, `verdict`. `roots` — префиксы путей (`docs/`, `upstream/`, `CLAUDE.md` → symphysis; `store/`, `playground/`, `md4h/` — как в `journal_render.py`), читаются из `tools/journal-roots.json` с возможностью переопределить `--roots`.
- CLI: `check <json> [--strict] [--write]`: печатает `[ok] улик сверено N из M`, каждую несверенную — `[!!] F-NN: путь «цитата» — причина`; код 0; `--strict` → 2 при несверенных; `--write` сохраняет `line/found` в JSON.

- [ ] **Step 1: тесты**

```python
def test_check_finds_quote_across_linebreak(tmp_path):
    (tmp_path / "a.md").write_text("первая\nвторая строка\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="первая вторая")
    r = journal.check_evidence(j, {"": tmp_path})
    assert r["found"] == 1 and j["records"][0]["options"][0]["evidence"][0]["line"] == 1

def test_check_quote_with_inner_guillemets(tmp_path):
    (tmp_path / "a.md").write_text("он сказал «да» и ушёл\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="сказал «да» и")
    assert journal.check_evidence(j, {"": tmp_path})["found"] == 1

def test_check_missing_file_is_signal_not_error(tmp_path):
    j = one_record_journal(path="nope.md", quote="x")
    r = journal.check_evidence(j, {"": tmp_path})
    assert r["missing"] and "файла нет" in r["missing"][0]

def test_check_plan_journal_all_found():
    j = journal.load_journal(ROOT / "docs/plan-implementation.journal.json")
    r = journal.check_evidence(j, journal.default_roots())
    assert r["found"] == r["total"] == 71
```

- [ ] **Step 2: запустить — падает**

Run: `py -3.13 -m pytest tests/test_journal_check.py -v` → FAIL (`check_evidence` нет).

- [ ] **Step 3: реализовать**

`check_evidence` — `find_quote` из `journal_render.py` (построчно, затем схлопнутые пробелы); `default_roots() -> dict[str, Path]` читает `tools/journal-roots.json`.

- [ ] **Step 4: запустить — проходит**

Expected: PASS ×4; `py -3.13 tools/journal.py check docs/plan-implementation.journal.json` печатает «сверено 71 из 71», код 0.

- [ ] **Step 5: Commit**

```bash
git add tools/journal.py tools/journal-roots.json tests/test_journal_check.py
git commit -m "feat(journal): сверка улик грепом — сигнал, не стоп"
```

### Task 3 (A3): рендер markdown и HTML из JSON

**Files:**
- Modify: `tools/journal.py`; `tools/playground-template.html` (без изменений логики — только метка)
- Delete: `tools/journal_render.py`
- Test: `tests/test_journal_render.py`

**Interfaces:**
- Produces: `render_md(journal: dict) -> str` — формат `plan-flexible-pipeline.md`, у каждой записи первой строкой после заголовка HTML-комментарий `<!-- journal:F-02 -->` (якорь для md4h); `render_html(journal: dict, template: Path) -> str` — подстановка `__JOURNAL_JSON__` как сейчас.
- Инвариант round-trip: `import_md(render_md(import_md(md)))` равен `import_md(md)` по всем полям, кроме `line/found/verdict`.

- [ ] **Step 1: тесты**

```python
def test_render_md_roundtrip():
    j = journal.import_md(FIX / "journal-plan.md")
    j2 = journal.import_md_text(journal.render_md(j))
    assert strip_check_fields(j2) == strip_check_fields(j)

def test_render_md_has_anchor_per_record():
    j = journal.import_md(FIX / "journal-plan.md")
    md = journal.render_md(j)
    assert md.count("<!-- journal:F-") == 24

def test_render_html_embeds_json(tmp_path):
    j = journal.import_md(FIX / "journal-plan.md")
    html = journal.render_html(j, ROOT / "tools/playground-template.html")
    assert "__JOURNAL_JSON__" not in html and '"F-19"' in html and "</script>" in html
```

- [ ] **Step 2: запустить — падает** (`render_md` нет).

- [ ] **Step 3: реализовать**

`render_md` пишет поля в порядке формата (вид, статус, адресат, зависит от, поставка, варианты с уликами и `маловероятно:`, антиподы, рекомендация, парковка, находка, улики, спор, решение, следствия); `import_md_text(text: str) -> dict`. Удалить `journal_render.py`; обновить `CLAUDE.md` и `docs/playground-template-llm-pipeline.md`: команда сборки теперь `journal.py render-html`.

- [ ] **Step 4: запустить — проходит**; пересобрать `docs/plan-implementation.md` из JSON: `render-md … --out docs/plan-implementation.journal.md` и `render-html … --out docs/plan-implementation.html`.

Expected: PASS ×3; markdown-журнал теперь производный, в шапке строка «рендер из `plan-implementation.journal.json`, не править руками».

- [ ] **Step 5: Commit**

```bash
git add -A tools docs tests
git commit -m "feat(journal): markdown и HTML — рендер из JSON; markdown производный"
```

### Task 4 (A4): `apply` — внесение промпта возврата

**Files:**
- Modify: `tools/journal.py`
- Test: `tests/test_journal_apply.py`, фикстура `tests/fixtures/answers-round1.md` (копия `docs/recieve-answers.md`)

**Interfaces:**
- Produces: `parse_answers(text: str) -> list[dict]` — строки формата просмотрщика: `- F-02: B — «слово»`, `- F-02: B (было A) — «…»`, `- F-01: припарковано → материалы — «…»`, `- F-05: добавлен вариант C. текст`, `- F-05: зависимость добавлена F-07` / `снята F-04`, `- F-20: факт оспорен — «…»`, `- F-NN: к решению B — «…»` (слово без смены), `Новые развилки:` + `- F-N1: вопрос — варианты: a | b — «слово»`, `Замечания к схеме: …`. Каждая строка → `{"id", "op", ...}`.
- Produces: `apply_answers(journal: dict, answers: list[dict], date: str) -> list[str]` — применяет и возвращает отчёт строками; отказ поимённо без изменений, если: id нет, буква не из вариантов, адресат не из трёх, зависимость на несуществующий id. Новая развилка получает следующий `F-NN`. Замечания к схеме — в `journal["notes"][]` с датой.
- CLI: `apply <json> <answers> [--date YYYY-MM-DD] [--dry-run]`.

- [ ] **Step 1: тесты**

```python
def test_apply_round1_reproduces_current_journal():
    j = journal.import_md(FIX / "journal-plan-before-round1.md")   # снимок до круга 1 — восстановить из git истории файла
    ans = journal.parse_answers((FIX / "answers-round1.md").read_text(encoding="utf-8"))
    journal.apply_answers(j, ans, date="2026-10-29")
    now = journal.load_journal(ROOT / "docs/plan-implementation.journal.json")
    for a, b in zip(j["records"], now["records"]):
        assert (a["decision"] or {}).get("option") == (b["decision"] or {}).get("option"), a["id"]

def test_apply_rejects_unknown_letter():
    j = journal.import_md(FIX / "journal-plan.md")
    before = json.dumps(j, ensure_ascii=False)
    report = journal.apply_answers(j, journal.parse_answers("- F-05: Q — «x»"), date="2026-10-30")
    assert any("F-05" in r and "Q" in r for r in report) and json.dumps(j, ensure_ascii=False) == before

def test_apply_parking_does_not_clear_decision():
    j = journal.import_md(FIX / "journal-plan.md")
    journal.apply_answers(j, journal.parse_answers("- F-02: припарковано → ИБ — «проверить токены»"), date="2026-10-30")
    r = next(x for x in j["records"] if x["id"] == "F-02")
    assert r["decision"]["option"] == "B" and r["parking"][-1]["addressee"] == "ИБ"
```

Снимок «до круга 1» — файл `tests/fixtures/journal-plan-before-round1.md`: версия журнала до внесения ответов; собрать из JSON текущего журнала, обнулив `decision`, `parking`, `dispute` и варианты с `added: true`.

- [ ] **Step 2: запустить — падает**; **Step 3: реализовать**; **Step 4: запустить — проходит** (PASS ×3).

- [ ] **Step 5: Commit**

```bash
git add tools/journal.py tests/
git commit -m "feat(journal): apply — промпт возврата вносится в JSON без переписывания"
```

### Task 5 (A5): `design.md` из журнала

**Files:**
- Modify: `tools/journal.py`
- Test: `tests/test_journal_design.py`

**Interfaces:**
- Produces: `render_design(journal: dict) -> str` — секции по шаблону `upstream/openspec/schemas/spec-driven/templates/design.md`: `Decisions` — записи с `decision`, первыми с `reversibility.level == "в одну сторону"` (F-10), каждое с словом человека дословно и уликами выбранной опции; `Risks / Trade-offs` — улики отвергнутых опций решённых развилок (`fork-form.md`: «улики за отвергнутые опции решённых развилок»); `Open Questions` — развилки без решения и записи `parking` с адресатом; факты — в `Context`.
- CLI: `render-design <json> --out <md>`.

- [ ] **Step 1: тесты**

```python
def test_design_one_way_first():
    j = journal.load_journal(ROOT / "docs/plan-implementation.journal.json")
    j["records"][2]["reversibility"] = {"level": "в одну сторону", "why": "форк"}
    md = journal.render_design(j)
    assert md.index("F-03") < md.index("F-02")

def test_design_rejected_evidence_in_risks():
    j = journal.load_journal(ROOT / "docs/plan-implementation.journal.json")
    md = journal.render_design(j)
    risks = md.split("## Risks")[1].split("## ")[0]
    assert "file-existence status does" in risks      # улика отвергнутой F-02.A
```

- [ ] **Step 2–4:** падает → реализовать → проходит.

- [ ] **Step 5: Commit** — `feat(journal): design.md из журнала`.

### Task 6 (A6): `apply-md4h` — комментарии к рендеру

**Files:**
- Modify: `tools/journal.py`
- Test: `tests/test_journal_md4h.py`, фикстура `tests/fixtures/md4h-feedback.md` (обезличенная копия `X:\skills-store\.md4h\feedback\research\variant-B-2026-10-28.md--20261028T201340Z-dfa6\feedback.md`, три комментария)

**Interfaces:**
- Produces: `parse_md4h(text: str) -> dict` — frontmatter (`source`, `source_sha256`, `state`, `round`) и список `{id, lines: (a, b), feedback}` из блоков `## F1 · text` → `**Source lines:** a-b` → ```markdown … ``` под `### Feedback` (только он — инструкция человека; формат `md4h-feedback/v2`).
- Produces: `apply_md4h(journal: dict, bundle: dict, rendered_md: Path) -> list[str]` — отказ, если `state != sealed` или `sha256(rendered_md) != source_sha256`; иначе каждому комментарию находится запись по ближайшему якорю `<!-- journal:F-NN -->` выше строки `a`, в `record["comments"]` добавляется `{round, lines, text}`; отчёт строками.

- [ ] **Step 1: тесты**

```python
def test_md4h_refuses_sha_mismatch(tmp_path):
    md = tmp_path / "d.md"; md.write_text("<!-- journal:F-01 -->\n# x\n", encoding="utf-8")
    b = journal.parse_md4h(FIX.joinpath("md4h-feedback.md").read_text(encoding="utf-8"))
    j = journal.import_md(FIX / "journal-plan.md")
    report = journal.apply_md4h(j, b, md)
    assert report and "sha256" in report[0] and all(not r["comments"] for r in j["records"])

def test_md4h_maps_comment_to_record(tmp_path):
    j = journal.import_md(FIX / "journal-plan.md")
    md = tmp_path / "d.md"; md.write_text(journal.render_md(j), encoding="utf-8")
    b = journal.parse_md4h(FIX.joinpath("md4h-feedback.md").read_text(encoding="utf-8"))
    b["source_sha256"] = journal.sha256_file(md); b["items"][0]["lines"] = (line_of(md, "<!-- journal:F-03 -->") + 2,) * 2
    journal.apply_md4h(j, b, md)
    assert next(r for r in j["records"] if r["id"] == "F-03")["comments"][0]["text"]
```

- [ ] **Step 2–4:** падает → реализовать → проходит.

- [ ] **Step 5: Commit** — `feat(journal): apply-md4h — комментарии к рендеру с проверкой SHA`.

---

## Часть B — схема `symphysis` (П1)

### Task 7 (B1): граф артефактов

**Files:**
- Create: `openspec/schemas/symphysis/schema.yaml`
- Test: `tests/test_schema.py`

**Interfaces:**
- Produces: схема `name: symphysis, version: 1` с артефактами в порядке: `decisions` (`decisions.json`), `research` (`research/**/*.md`, requires decisions), `attack-decisions` (`attack/decisions.md`, requires research, `verdict: {frontmatter: status, value: passed}`), `proposal` (requires attack-decisions), `specs` (`specs/**/*.md`, requires proposal), `design` (requires proposal), `security` (`security.md`, requires specs), `tasks` (requires specs, design), `attack-artifacts` (`attack/artifacts.md`, requires specs, design, security, tasks, `verdict` как выше); `apply: {requires: [tasks, attack-artifacts], tracks: tasks.md}`.
- Instruction каждого артефакта — короткая, называет скилл по имени (F-06): `decisions` → `symphysis-brainstorm`; `attack-*` → `symphysis-attack`; `specs` → после написания позвать `symphysis-edge-probe` и `symphysis-prohibition-probe` на каждое требование; `research`, `design`, `security`, `tasks` — правила в instruction без скилла. Instruction `attack-decisions` начинается со второго круга: «закрыть записи с адресатом материалы по файлам `research/`; спросить человека, нужен ли новый круг; отказ записать строкой «брейншторм закончен по решению человека»» (F-07).

- [ ] **Step 1: тест**

```python
def test_schema_parses_in_fork(tmp_path):
    proj = make_project(tmp_path, schema="symphysis")       # копирует openspec/schemas/symphysis и config.yaml, создаёт пустой change
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    ids = [a["id"] for a in out["artifacts"]]
    assert ids == ["decisions", "research", "attack-decisions", "proposal", "specs", "design", "security", "tasks", "attack-artifacts"]
    assert out["artifacts"][0]["status"] == "ready" and out["artifacts"][1]["status"] == "blocked"
```

`run_openspec` зовёт `node upstream/openspec/bin/openspec.js` (после `pnpm build`) с `cwd=proj`; до задачи C1 поле `verdict` в схеме отсутствует — тест B1 пишется без него, C1 его добавляет.

- [ ] **Step 2–4:** падает (схемы нет) → написать `schema.yaml` → проходит.

- [ ] **Step 5: Commit** — `feat(schema): граф symphysis`.

### Task 8 (B2): шаблоны артефактов

**Files:**
- Create: `openspec/schemas/symphysis/templates/decisions.json`, `research.md`, `attack.md`, `proposal.md`, `spec.md`, `design.md`, `security.md`, `tasks.md`
- Test: `tests/test_schema.py` (добавить)

**Interfaces:**
- `decisions.json` — `{ "title": "", "source": "", "records": [] }`, валиден по `docs/journal.schema.json`.
- `research.md` — frontmatter `genre: устройство|размещение|края|проверка|аналоги`, `question: F-NN`, тело: «Найдено» с `путь:строка «цитата»`, «Не найдено» с «искал: шаблоны дословно» (F-05.C, `store/research/variant-B-2026-10-28.md` «отрицаниями по рецепту»).
- `attack.md` — frontmatter `status: gaps_found|passed`, `target:` путь, `target_sha256:`; тело — таблица «утверждение · раздел · опора есть/нет · чем закрыть».
- `security.md` — чек-лист канона (инъекции через содержимое файлов, пути с `../`, токены и срок их жизни, права, бинарные файлы) с колонкой «применимо / неприменимо — причина» (F-11; `prohibition-probe.md` «Do NOT mint a prohibition for them»).
- `design.md` — секции spec-driven; `Decisions`, `Risks`, `Open Questions` помечены «генерируется `journal.py render-design`».

- [ ] **Step 1: тест** — `test_templates_exist_and_decisions_template_valid`: все восемь файлов есть, `decisions.json` проходит `validate_journal`, `attack.md` начинается с `---\nstatus:`.
- [ ] **Step 2–4:** падает → написать → проходит.
- [ ] **Step 5: Commit** — `feat(schema): шаблоны артефактов`.

### Task 9 (B3): `config.yaml` и `rules`

**Files:**
- Create: `openspec/config.symphysis.yaml` (образец для проекта: `schema: symphysis` + `rules`)
- Test: `tests/test_schema.py` (добавить)

**Interfaces:**
- `rules` на артефакт — короткие правила (F-06: «A для коротких правил»): `decisions`: «у каждого варианта улика — путь и цитата», «маловероятный вариант показывается с причиной», «адресат парковки — материалы, человек, ИБ»; `specs`: «предположение помечается словом `предположение` и дорогой `проверить|решить`» (`change-drafter/SKILL.md` «помечается»); `design`: «решение излагается, не принимается» (`design-form.md` «Решение уже принято»); `attack-*`: «FORCE stance»; `security`: «канон не чеканится в журнал».

- [ ] **Step 1: тест** — `test_rules_reach_instructions`: `openspec instructions decisions --change demo --json` в проекте-фикстуре возвращает `rules` с тремя строками для `decisions`.
- [ ] **Step 2–4;** **Step 5: Commit** — `feat(schema): config.yaml с rules`.

### Task 10 (B4): валидация `validate` и `status` на заполненном изменении

**Files:**
- Create: `tests/fixtures/change-demo/` — изменение с `decisions.json` (три записи), одним `research/*.md`, без `attack/`
- Test: `tests/test_schema.py` (добавить)

- [ ] **Step 1: тест** — `test_status_after_research`: `attack-decisions` — `ready`, `proposal` — `blocked` с `missingDeps == ["attack-decisions"]`; `openspec validate --all` в фикстуре — код 0.
- [ ] **Step 2–4;** **Step 5: Commit** — `test(schema): статус на заполненном изменении`.

---

## Часть C — форк OpenSpec (П4)

### Task 11 (C1): поле `verdict` в схеме артефакта

**Files:**
- Modify: `upstream/openspec/src/core/artifact-graph/schema.ts:29-36` (`ArtifactSchema`), `parseSchema` (`:23-47`)
- Test: `upstream/openspec/test/core/artifact-graph/schema.test.ts`

**Interfaces:**
- Produces: `ArtifactSchema` получает `verdict: z.object({ frontmatter: z.string().min(1), value: z.string().min(1) }).optional()`; тип `Artifact` включает `verdict?: { frontmatter: string; value: string }`.
- Produces: `validateVerdictTargets(artifacts: Artifact[]): void` — бросает `SchemaValidationError('Artifact "<id>" declares verdict but generates a glob pattern')` при `isGlobPattern(artifact.generates)` (`outputs.ts:230`).

- [ ] **Step 1: тесты (vitest)**

```ts
it('accepts verdict on a single-file artifact', () => {
  const s = parseSchema(yamlWith({ id: 'attack', generates: 'attack.md', verdict: { frontmatter: 'status', value: 'passed' } }));
  expect(s.artifacts[0].verdict).toEqual({ frontmatter: 'status', value: 'passed' });
});
it('rejects verdict on a glob artifact by name', () => {
  expect(() => parseSchema(yamlWith({ id: 'specs', generates: 'specs/**/*.md', verdict: { frontmatter: 'status', value: 'passed' } })))
    .toThrow(/"specs" declares verdict but generates a glob/);
});
```

- [ ] **Step 2:** `pnpm --dir upstream/openspec test -- schema.test.ts` → FAIL.
- [ ] **Step 3:** реализовать; вызвать `validateVerdictTargets(schema.artifacts)` в `parseSchema` после `validateRequiresReferences`.
- [ ] **Step 4:** PASS; добавить `verdict` в `openspec/schemas/symphysis/schema.yaml` (B1) у обоих `attack-*`.
- [ ] **Step 5: Commit** (в форке) — `feat(schema): verdict — артефакт готов по значению frontmatter`.

### Task 12 (C2): frontmatter и готовность по вердикту

**Files:**
- Create: `upstream/openspec/src/core/artifact-graph/frontmatter.ts`
- Modify: `upstream/openspec/src/core/artifact-graph/state.ts:14-29` (`detectCompleted`)
- Test: `upstream/openspec/test/core/artifact-graph/frontmatter.test.ts`, `state.test.ts`

**Interfaces:**
- Produces: `readFrontmatter(filePath: string): Record<string, unknown> | null` — читает файл, снимает BOM, принимает CRLF, разбирает блок между первой строкой `---` и следующей `---` через `parse` из `yaml`; `null`, если блока нет или YAML не разобран.
- Produces: `detectCompleted(graph, changeDir)` — для артефакта с `verdict`: `completed`, только если файл есть **и** `String(readFrontmatter(path)?.[verdict.frontmatter]) === verdict.value`.
- Produces: `verdictState(artifact: Artifact, changeDir: string): 'n/a' | 'missing' | 'mismatch' | 'ok'` — для C3.

- [ ] **Step 1: тесты**

```ts
it('reads frontmatter with CRLF and BOM', () => {
  write(file, '\uFEFF---\r\nstatus: passed\r\n---\r\n# t\r\n');
  expect(readFrontmatter(file)).toEqual({ status: 'passed' });
});
it('verdict artifact with file but no frontmatter is not completed', () => {
  write(path.join(changeDir, 'attack.md'), '# no frontmatter');
  expect(detectCompleted(graphWithVerdict(), changeDir).has('attack')).toBe(false);
});
it('verdict artifact with status passed is completed', () => {
  write(path.join(changeDir, 'attack.md'), '---\nstatus: passed\n---\n');
  expect(detectCompleted(graphWithVerdict(), changeDir).has('attack')).toBe(true);
});
it('verdict artifact with status gaps_found is not completed', () => { /* аналогично, false */ });
```

- [ ] **Step 2–4:** FAIL → реализовать → PASS.
- [ ] **Step 5: Commit** — `feat(state): готовность артефакта по вердикту во frontmatter`.

### Task 13 (C3): статус с полем `verdict` и подсказкой

**Files:**
- Modify: `upstream/openspec/src/core/artifact-graph/instruction-loader.ts:474-540` (`formatChangeStatus`), `:161-172` (`ArtifactStatus`)
- Test: `upstream/openspec/test/core/artifact-graph/instruction-loader.test.ts`

**Interfaces:**
- Produces: `ArtifactStatus.verdict?: 'missing' | 'mismatch' | 'ok'` — только у артефактов с `verdict`; `ready` + файл есть + вердикта нет → `verdict: 'missing'`; значение не то → `'mismatch'`.
- Produces: строка `nextSteps`: `Artifact "<id>" exists but has no verdict (status: passed) — run its instruction to produce one` (английский, как остальные строки CLI).

- [ ] **Step 1: тест** — `status --json` на фикстуре с `attack.md` без frontmatter: `artifacts[attack].status === 'ready'`, `.verdict === 'missing'`, `nextSteps` содержит `has no verdict`.
- [ ] **Step 2–4;** **Step 5: Commit** — `feat(status): verdict в статусе артефакта`.

### Task 14 (C4): шаблон `continue` с проверкой вердикта

**Files:**
- Modify: `upstream/openspec/src/core/templates/workflows/continue-change.ts` (обе функции — skill и command)
- Test: `upstream/openspec/test/core/templates/continue-verdict.test.ts`

**Interfaces:**
- Produces: константа `VERDICT_CHECK` — блок перед «If artifacts are ready to create»: «**If the first ready artifact has `verdict: "missing"` or `"mismatch"`**: the file exists; do NOT rewrite it. Get its instructions and follow them to produce the verdict (the instruction names the attack skill). Verify `openspec status --json` now shows `verdict: "ok"`. STOP — that counts as this invocation's ONE artifact.» Вставляется в `getContinueChangeSkillTemplate` и `getOpsxContinueCommandTemplate`.

- [ ] **Step 1: тест**

```ts
it('continue skill and command carry the verdict step before artifact creation', () => {
  for (const text of [getContinueChangeSkillTemplate().instructions, getOpsxContinueCommandTemplate().content]) {
    expect(text).toContain('verdict: "missing"');
    expect(text.indexOf('verdict: "missing"')).toBeLessThan(text.indexOf('If artifacts are ready to create'));
  }
});
```

- [ ] **Step 2–4:** FAIL → реализовать → PASS; если парити-тест шаблонов называет устаревший пин, обновить пин инструментом репозитория (`test/core/templates/parity-hash-shared.test.ts` описывает перезапись пинов).
- [ ] **Step 5: Commit** — `feat(continue): шаг вердикта перед следующим артефактом`.

### Task 15 (C5): сборка форка и дымовой прогон на схеме symphysis

**Files:**
- Modify: `upstream/openspec/UPSTREAM.md` (строка «правки форка: C1–C4, тесты N passed»)
- Test: `tests/test_schema.py` (добавить)

- [ ] **Step 1:** `pnpm --dir upstream/openspec build && pnpm --dir upstream/openspec test` → все зелёные, число записать.
- [ ] **Step 2: тест** — `test_verdict_blocks_proposal`: фикстура с `attack/decisions.md` без frontmatter → `attack-decisions` `ready` с `verdict missing`, `proposal` `blocked`; дописать `status: passed` → `attack-decisions` `done`, `proposal` `ready`.
- [ ] **Step 3:** PASS. **Step 4: Commit** (symphysis) — `test(schema): вердикт держит граф`.

---

## Часть D — скиллы из GSD (П3)

Общее для D1–D4: каталог `skills/<имя>/`: `SKILL.md` (frontmatter `name`, `description` по-русски с «Применяй, когда…» и «Не применяй…»), `references/<оригинал>.md` — копия файла GSD с шапкой `<!-- MIT License, Copyright (c) 2026 Open GSD; источник: upstream/gsd-core/<путь> @ e2cd587 -->`, `TRANSLATION-NOTES.md` — таблица «место · в источнике · у нас · почему смысл изменён» (F-14). Тест общий — `tests/test_skills.py`.

### Task 16 (D1): `symphysis-brainstorm` — интервью и журнал

**Files:**
- Create: `skills/symphysis-brainstorm/SKILL.md`, `references/spec-phase.md` (копия `gsd-core/workflows/spec-phase.md`, только разделы `<purpose>`, `<interview_perspectives>`, Step 4), `references/discuss-phase-gray-areas.md` (`<philosophy>`, `<gray_area_identification>`, `<scope_guardrail>` из `discuss-phase.md`), `TRANSLATION-NOTES.md`

**Interfaces:**
- Скилл пишет `decisions.json` по `docs/journal.schema.json`: перспективы интервью — Researcher, Simplifier, Boundary Keeper, Failure Analyst, Seed Closer (`spec-phase.md:43` «Failure Analyst (round 4)»); порция — «2–3 questions max» за круг (`:136`); факт отличается от развилки; парковка с адресатом; стоп — круг без новых решений и фактов, не больше двух; новый круг — вопрос человеку; отказ — запись «брейншторм закончен по решению человека» (F-07); обратимость решения (`context.md:59` «Reversibility:»); «Deferred Ideas» → парковка (`discuss-phase.md:79`).
- Чего нет: числового гейта (`spec-phase.md:20`) — в TRANSLATION-NOTES как снятое по F-07.

- [ ] **Step 1: тест** — `test_brainstorm_skill_shape`: frontmatter есть; в SKILL.md пять перспектив по имени; строка «брейншторм закончен по решению человека»; `references/spec-phase.md` начинается с copyright-шапки; `TRANSLATION-NOTES.md` содержит строку про снятый числовой гейт.
- [ ] **Step 2–4;** **Step 5: Commit** — `feat(skills): symphysis-brainstorm`.

### Task 17 (D2): `symphysis-edge-probe` — проба краёв

**Files:**
- Create: `skills/symphysis-edge-probe/SKILL.md`, `references/edge-probe.md` (копия `gsd-core/references/edge-probe.md` целиком), `TRANSLATION-NOTES.md`

**Interfaces:**
- Таблица восьми категорий дословно и в переводе рядом (`edge-probe.md:72`); форму требования (`numeric-range | collection | text | stateful | io`) называет модель и пишет в запись, человек правит (F-08.D; `:52` «The classifier reads English»); исходы кандидата — `Specify | Dismiss с причиной | Backstop | Defer` (`spec-phase.md:347`), отказ без причины не принимается (`:89` «Dismissal requires a reason string»); результат — записи журнала с `outcome.kind == "проба"`.

- [ ] **Step 1: тест** — `test_edge_probe_has_eight_categories`: все восемь id (`boundary, adjacency, empty, encoding, ordering, precision, idempotency, concurrency`) в SKILL.md; четыре исхода; copyright-шапка в копии.
- [ ] **Step 2–4;** **Step 5: Commit** — `feat(skills): symphysis-edge-probe`.

### Task 18 (D3): `symphysis-prohibition-probe` — проба запретов

**Files:**
- Create: `skills/symphysis-prohibition-probe/SKILL.md`, `references/prohibition-probe.md` (копия), `TRANSLATION-NOTES.md`

**Interfaces:**
- Вопрос дословно по-английски и в переводе: «What could this feature silently become that the author would NOT want, but the spec does not forbid?» (`prohibition-probe.md:53`); два такта — recall ~10, precision ~2–3, «DROP routine-engineering items» (`:63`); канон (OWASP, GDPR, инъекции, `../`) не чеканится — строка-отсылка в `security.md` (`:79` «Do NOT mint a prohibition for them»; F-11, F-24); исходы и `verification: test | judgment`.

- [ ] **Step 1: тест** — `test_prohibition_probe_question_verbatim`: английская фраза есть дословно; слово `security.md` есть; copyright-шапка.
- [ ] **Step 2–4;** **Step 5: Commit** — `feat(skills): symphysis-prohibition-probe`.

### Task 19 (D4): `symphysis-attack` — атака артефакта

**Files:**
- Create: `skills/symphysis-attack/SKILL.md`, `references/force-stance.md` (строки «FORCE stance» из `agents/gsd-plan-checker.md:30`, `gsd-code-reviewer.md:22`, `gsd-doc-verifier.md` — с шапкой), `references/grill-lenses.md` (пять линз с «чего не репортить» по `store/change-intake/references/grill-form.md`, своё), `TRANSLATION-NOTES.md`

**Interfaces:**
- Установка: «Assume every plan set is flawed until evidence proves otherwise» в переводе; проход — «какое утверждение ничем не подкреплено» по разделам, покрытие поимённо, «Молчание по разделу» не «чисто» (`grill-form.md:81`), второго такта нет (`:31`); выход — `attack/<цель>.md` с frontmatter `status: passed | gaps_found`, `target`, `target_sha256` и таблицей утверждений; `passed` только при нуле утверждений без опоры (аналог `openspec-verify` «only when every in-scope requirement resolved», `docs/analysis/gsd-openspec-integration.md`).

- [ ] **Step 1: тест** — `test_attack_skill_writes_verdict_contract`: в SKILL.md есть `status: passed`, `target_sha256`, «FORCE stance», пять линз.
- [ ] **Step 2–4;** **Step 5: Commit** — `feat(skills): symphysis-attack`.

### Task 20 (D5): общий тест скиллов и перечень отличий

**Files:**
- Test: `tests/test_skills.py` (свод)

- [ ] **Step 1: тест** — для каждого из четырёх: `references/*.md` с шапкой MIT/Open GSD (кроме `grill-lenses.md` — своё), `TRANSLATION-NOTES.md` непустой с заголовком таблицы, `SKILL.md` ≤ 1500 слов (ориентир из памяти владельца, превышение — не падение, а предупреждение в выводе теста).
- [ ] **Step 2–4;** **Step 5: Commit** — `test(skills): форма скиллов и перечни отличий перевода`.

---

## Часть E — инсталлятор (П6)

### Task 21 (E1): каркас пакета

**Files:**
- Create: `installer/package.json` (`name: "<scope>/symphysis"` — плейсхолдер, `bin: { symphysis: "./bin/symphysis.js" }`, `dependencies: { "@fission-ai/openspec": "file:../upstream/openspec" }`, `files: [bin, lib, payload]`, `scripts.test: "node --test test/"`), `installer/bin/symphysis.js`, `installer/lib/paths.js`, `installer/test/cli.test.js`

**Interfaces:**
- Produces: CLI `symphysis install [--project <dir>] [--tools claude,gigacode]` и `symphysis check [--project <dir>]`; `payload/` — копия `openspec/schemas/symphysis/`, `skills/`, `tools/journal.py`, `tools/journal-roots.json`, `tools/playground-template.html`, `docs/journal.schema.json` (собирается скриптом `installer/scripts/sync-payload.js` из корня symphysis).
- Produces: `lib/paths.js`: `targets(project, tools) -> { schemaDir, configPath, skillsDirs[], toolsDir }`; для `claude` — `.claude/skills/`, для `gigacode` — `.gigacode/skills/` (цель OpenSpec 1.14.0, `upstream/openspec/CHANGELOG.md:110`); `toolsDir` — `<project>/.symphysis/`.

- [ ] **Step 1: тест** — `node --test`: `symphysis --help` печатает обе команды; `targets(p, ['claude','gigacode']).skillsDirs` — два пути.
- [ ] **Step 2–4;** **Step 5: Commit** — `feat(installer): каркас пакета и раскладка целей`.

### Task 22 (E2): `install`

**Files:**
- Create: `installer/lib/install.js`
- Test: `installer/test/install.test.js`

**Interfaces:**
- Produces: `install(project: string, opts: { tools: string[] }) -> { written: string[], merged: string[], skipped: string[] }`: копирует схему в `openspec/schemas/symphysis/`, скиллы в каждый `skillsDir/<имя>/`, `tools` в `.symphysis/`; `openspec/config.yaml`: нет — создать из `openspec/config.symphysis.yaml`; есть — слить: `schema: symphysis` ставится, чужие ключи и чужие `rules` сохраняются, свои `rules` добавляются; каждая слитая запись — в `merged`, с печатью «config.yaml уже был: схема переключена с <прежняя> на symphysis, rules добавлены». Существующий файл скилла с другим содержимым — не перезаписывается, в `skipped` с подсказкой `--force`.

- [ ] **Step 1: тесты** — `install` в пустой tmp-проект: все пути из `targets` существуют; повторный `install` — `written` пуст; проект с `config.yaml` `schema: spec-driven` и своими `rules.specs` — после установки `schema: symphysis`, `rules.specs` содержит и старые, и новые строки, `merged` содержит `openspec/config.yaml`.
- [ ] **Step 2–4;** **Step 5: Commit** — `feat(installer): install со слиянием config.yaml`.

### Task 23 (E3): `check`

**Files:**
- Create: `installer/lib/check.js`
- Test: `installer/test/check.test.js`

**Interfaces:**
- Produces: `check(project) -> { ok: boolean, findings: string[] }`: версия `openspec --version` равна пину из `installer/package.json` (`symphysis.openspecPin`); файлы схемы побайтно равны `payload/` (иначе «схема изменена: <файл>» — не чинит, называет); `config.yaml` содержит `schema: symphysis`; у каждого `skillsDir` все четыре скилла; `py -3.13 --version` отвечает; `node … journal.py check` на `decisions.json` каждого активного change печатает счёт (сигнал). Код выхода 0 при `ok`, 2 иначе; принцип «гейт называет, а не чинит» (`store/tools/openspec_setup.py` — образец).

- [ ] **Step 1: тесты** — после `install` → `ok`; подменить байт в `schema.yaml` → `ok === false`, `findings[0]` содержит `schema.yaml`; убрать `schema:` из config → finding с `config.yaml`.
- [ ] **Step 2–4;** **Step 5: Commit** — `feat(installer): check — называет расхождения`.

### Task 24 (E4): `npx` из чистого каталога

**Files:**
- Modify: `installer/README.md`, `CLAUDE.md` («Где что»: `installer/`)
- Test: `installer/test/npx.test.js`

- [ ] **Step 1: тест** — `npm pack` в `installer/`, затем в tmp-каталоге `npx --yes ./<tgz> install --tools claude` → `check` возвращает 0.
- [ ] **Step 2–4;** **Step 5: Commit** — `feat(installer): установка через npx из пакета`.

---

## Часть F — сухой прогон (Э6)

### Task 25 (F1): схема проходит сама себя

**Files:**
- Create: `openspec/changes/symphysis-schema/` в symphysis (через `openspec new change symphysis-schema` форка после `symphysis install --project X:\symphysis`)
- Create: `docs/dry-run-journal.md` — дневник прогона

- [ ] **Step 1:** `install` в symphysis, `check` зелёный.
- [ ] **Step 2:** `decisions.json` — перенос журнала плана (`journal.py` A1) как первый артефакт; `openspec status` показывает `decisions` done, `research` ready.
- [ ] **Step 3:** пройти `/opsx:continue` по графу до `attack-artifacts`; каждый шаг — строка дневника: артефакт, что сделал скилл, что пришлось делать руками, что сломалось.
- [ ] **Step 4:** вердикты `attack/*.md` ставит скилл `symphysis-attack`; `status` форка держит граф (C5).

### Task 26 (F2): отчёт со счётчиками

**Files:**
- Create: `docs/dry-run-report.md`

- [ ] **Step 1:** таблица из «Как поймём» плана: утверждения без опоры (сколько, на каком шаге пойманы); развилки, оказавшиеся фактами, и наоборот; улики, не сверившиеся грепом; что переделано и почему; где не хватило скрипта. Каждая строка — с указанием на файл прогона.
- [ ] **Step 2:** вердикт по ставке плана: «соглашения вместо скриптов» — где держалось, где нет; кандидаты вернуть проверку в код.
- [ ] **Step 3: Commit** — `docs: сухой прогон схемы на себе — отчёт`.

---

## Правки по калибровке

Правки по итогам сухого прогона ведёт изменение `calibration-fixes`:
задачи и их порядок — в `openspec/changes/calibration-fixes/tasks.md`
(здесь не дублируются).

---

## Самопроверка плана

- **Покрытие спеки:** П1 → B1–B4; П2 → A1, A3; П3 → D1–D5; П4 → C1–C5; П5 → A2, A4–A6; П6 → E1–E4; П7 — вне плана (форк плагина по кругам обратной связи, `docs/plan-implementation.md`, «Чего в плане нет»); Э6 → F1–F2. Решения F-01…F-19 — каждое названо в задаче, где применяется.
- **Шаги:** у каждой задачи с кодом — тест с именем и утверждениями, сигнатуры, команда запуска; тел функций нет.
- **Имена:** `journal.py` подкоманды и функции совпадают между A1–A6 и E3; `verdict` одинаково в C1–C5 и B1; `targets()` одно в E1–E3.
- **Review Focus:** 1 → A2 тест с переносом и кавычками; 2 → C2 тест CRLF/BOM; 3 → C1 тест glob; 4 → A4 тест буквы; 5 → E2 тест слияния; 6 → A6 тест SHA.
- **Пропорция:** план короче суммы кода, который описывает; тела функций не выписаны.
