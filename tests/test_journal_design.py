import copy
import subprocess
import sys

import journal
from conftest import ROOT, one_record_journal

LIVE_JSON = ROOT / "docs" / "plan-implementation.journal.json"
SECTIONS = ["# Design", "## Context", "## Goals / Non-Goals", "## Decisions", "## Risks / Trade-offs",
            "## Migration Plan", "## Open Questions"]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "journal.py"), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8")


def ev(path, quote, **extra):
    return {"path": path, "quote": quote, **extra}


def opt(letter, text, evidence=(), unlikely=None):
    return {"letter": letter, "text": text, "added": False, "unlikely": unlikely, "evidence": list(evidence)}


def record(rid, question="вопрос?", options=(), **fields):
    """Запись по схеме: берём годную из conftest и правим поля."""
    rec = copy.deepcopy(one_record_journal("a.md", "q")["records"][0])
    rec.update(id=rid, question=question, options=list(options), **fields)
    return rec


def decided(rid, letter, options, word="слово", date="2026-10-30", **fields):
    return record(rid, f"вопрос {rid}?", options, status="решён",
                  decision={"option": letter, "word": word, "date": date}, **fields)


def design_of(*records):
    return journal.render_design({"title": "т", "source": "s.md", "records": list(records)})


def section(md, name):
    """Текст секции `## name` — до следующей `## `; заголовки `###` не считаются границей."""
    lines = md.split("\n")
    start = lines.index(f"## {name}") + 1
    body = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


# --- тесты из брифа ---------------------------------------------------------

def test_design_one_way_first():
    j = journal.load_journal(ROOT / "docs/plan-implementation.journal.json")
    j["records"][2]["reversibility"] = {"level": "в одну сторону", "why": "форк"}
    md = journal.render_design(j)
    assert md.index("F-03") < md.index("F-02")


def test_design_rejected_evidence_in_risks():
    j = journal.load_journal(ROOT / "docs/plan-implementation.journal.json")
    md = journal.render_design(j)
    # В брифе граница секции — `split("## ")`; улика F-01.A в живом журнале сама цитата
    # «## F-01 <вопрос>», и такая граница рвёт Risks на первой же строке. Граница — начало строки.
    risks = md.split("## Risks")[1].split("\n## ")[0]
    assert "file-existence status does" in risks      # улика отвергнутой F-02.A


# --- разделы ----------------------------------------------------------------

def test_sections_follow_the_openspec_template_order():
    md = design_of(decided("F-01", "A", [opt("A", "первый"), opt("B", "второй")]))
    positions = [md.split("\n").index(s) for s in SECTIONS]
    assert positions == sorted(positions)
    assert section(md, "Goals / Non-Goals").strip() == "Цели и не-цели — из proposal; здесь только решения."
    assert section(md, "Migration Plan").strip() == "Не применимо к журналу решений; см. tasks.md."


def test_empty_sections_say_so():
    md = design_of()
    for name in ("Context", "Risks / Trade-offs", "Open Questions"):
        assert section(md, name).strip() == "—", name
    assert section(md, "Decisions").strip() == "нет: решённых развилок в журнале нет"


def test_live_journal_renders_every_section_once():
    md = journal.render_design(journal.load_journal(LIVE_JSON))
    lines = md.split("\n")
    for s in SECTIONS:
        assert lines.count(s) == 1, s


# --- Context: факты ---------------------------------------------------------

def test_facts_go_to_context_with_their_evidence():
    fact = record("F-20", "факт о файле", kind="факт", evidence=[
        ev("upstream/x.ts", "готов по файлу", line=12, found=True, verdict="сверено"),
        ev("docs/y.md", "ещё цитата")])
    md = design_of(fact)
    context = section(md, "Context")
    assert "- F-20 факт о файле" in context
    assert "upstream/x.ts:12 «готов по файлу»" in context
    assert "docs/y.md «ещё цитата»" in context      # строка неизвестна — путь без `:строка`
    assert "F-20" not in section(md, "Decisions")


def test_unmatched_fact_evidence_is_kept_with_the_verdict():
    fact = record("F-20", "факт", kind="факт", evidence=[
        ev("upstream/x.ts", "нет такой", line=None, found=False, verdict="цитаты нет дословно")])
    context = section(design_of(fact), "Context")
    assert "upstream/x.ts «нет такой» — цитаты нет дословно" in context


def test_unverifiable_evidence_carries_its_verdict():
    """Финальное ревью, minor 7: `found: null` после `check` — «не проверить: …» (бинарный файл, не UTF-8),
    пометка как у `found: false`; улика, которую не сверяли (нет ни `found`, ни `verdict`), — как есть."""
    fact = record("F-20", "факт", kind="факт", evidence=[
        ev("docs/bin.dat", "байты", line=None, found=None, verdict="не проверить: бинарный файл"),
        ev("docs/new.md", "не сверяли")])
    context = section(design_of(fact), "Context")
    assert "docs/bin.dat «байты» — не проверить: бинарный файл" in context
    assert "  - docs/new.md «не сверяли»" in context.splitlines()


# --- Decisions --------------------------------------------------------------

def test_decision_block_carries_choice_word_reversibility_evidence_and_rejected():
    options = [
        opt("A", "держим в JSON", [ev("docs/a.md", "улика А", line=3, found=True)]),
        opt("B", "держим в markdown", [ev("docs/b.md", "улика Б")]),
        opt("C", "ничего не держим", unlikely="так не делают"),
    ]
    rec = decided("F-07", "B", options, word="пусть будет markdown", date="2026-10-29",
                  reversibility={"level": "дорого", "why": "формат тянут скрипты"})
    block = section(design_of(rec), "Decisions")
    assert "### F-07 вопрос F-07?" in block
    assert "- **Выбрано:** B. держим в markdown" in block
    assert "- **Слово человека (2026-10-29):** «пусть будет markdown»" in block
    assert "- **Обратимость:** дорого — формат тянут скрипты" in block
    assert "- **Улики выбранного:** docs/b.md «улика Б»" in block
    assert "улика А" not in block                       # улика отвергнутого — не в Decisions
    assert "- **Отвергнуто:** A. держим в JSON" in block
    assert "- **Отвергнуто:** C. ничего не держим — маловероятно: так не делают" in block
    assert "Отвергнуто:** B" not in block               # выбранный не отвергнут


def test_each_chosen_evidence_gets_its_own_line():
    options = [opt("A", "раз", [ev("a.md", "первая", line=1), ev("b.md", "вторая")]), opt("B", "два")]
    block = section(design_of(decided("F-01", "A", options)), "Decisions")
    assert block.count("- **Улики выбранного:**") == 2
    assert "- **Улики выбранного:** a.md:1 «первая»" in block
    assert "- **Улики выбранного:** b.md «вторая»" in block


def test_decision_without_word_or_reversibility_omits_those_lines():
    rec = decided("F-01", "A", [opt("A", "раз"), opt("B", "два")], word="")
    block = section(design_of(rec), "Decisions")
    assert "Слово человека" not in block and "Обратимость" not in block and "Улики выбранного" not in block


def test_reversibility_without_reason_is_the_bare_level():
    rec = decided("F-01", "A", [opt("A", "раз")], reversibility={"level": "обратимо", "why": ""})
    assert "- **Обратимость:** обратимо\n" in section(design_of(rec), "Decisions") + "\n"


def test_one_way_decisions_first_then_by_id():
    recs = [decided(f"F-{n:02d}", "A", [opt("A", "раз")]) for n in (1, 2, 3, 4, 10)]
    for rec in (recs[3], recs[4]):          # F-04 и F-10 — в одну сторону
        rec["reversibility"] = {"level": "в одну сторону", "why": "форк"}
    recs.reverse()                          # порядок в журнале не должен решать
    block = section(design_of(*recs), "Decisions")
    heads = [line.split()[1] for line in block.split("\n") if line.startswith("### ")]
    assert heads == ["F-04", "F-10", "F-01", "F-02", "F-03"]


def test_undecided_fork_lands_only_in_open_questions():
    undecided = record("F-02", "кто решает?", [opt("A", "раз", [ev("a.md", "улика открытой")]), opt("B", "два")])
    md = design_of(decided("F-01", "A", [opt("A", "раз")]), undecided)
    assert "F-02" not in section(md, "Decisions")
    assert "F-02" not in section(md, "Risks / Trade-offs")
    assert "улика открытой" not in md
    assert "- F-02 кто решает? — открыта" in section(md, "Open Questions")
    assert "F-01" not in section(md, "Open Questions")


# --- кандидаты проб: `outcome.kind == "проба"` — не проектные решения ---------

PROBE_OPTIONS = [opt("A", "Specify"), opt("B", "Dismiss"), opt("C", "Backstop"), opt("D", "Defer")]


def probe(rid, letter, value, question, reason=""):
    """Решённый кандидат пробы: слово человека внесено `apply`, исход отзеркален скиллом."""
    rec = decided(rid, letter, PROBE_OPTIONS, outcome={"kind": "проба", "value": value, "reason": reason})
    rec["question"] = question
    return rec


def test_probe_candidates_stay_out_of_decisions_and_a_deferred_one_is_open():
    fork = decided("F-01", "A", [opt("A", "раз"), opt("B", "два", [ev("b.md", "довод против")])])
    specified = probe("F-02", "A", "Specify", "[boundary · numeric-range] порог ровно 100")
    deferred = probe("F-03", "D", "Defer", "[empty · collection] пустой список")
    md = design_of(fork, specified, deferred)
    heads = [line.split()[1] for line in section(md, "Decisions").split("\n") if line.startswith("### ")]
    assert heads == ["F-01"]                             # кандидаты проб — не решения дизайна
    assert "F-02" not in md                              # Specify закрыт: в дизайне ему нет места
    assert "F-03" not in section(md, "Risks / Trade-offs")
    assert "- F-03 [empty · collection] пустой список — отложена (Defer)" in section(md, "Open Questions")
    assert "F-02" not in section(md, "Open Questions")


def test_deferred_probe_candidate_carries_the_human_word():
    deferred = probe("F-03", "D", "Defer", "[io · io] обрыв сети", reason="после замера")
    assert "- F-03 [io · io] обрыв сети — отложена (Defer) — «после замера»" in section(design_of(deferred), "Open Questions")


def test_question_level_evidence_is_printed_under_its_own_label():
    rec = decided("F-07", "A", [opt("A", "раз", [ev("a.md", "улика выбранного")]), opt("B", "два")], evidence=[
        ev("docs/q.md", "улика вопроса", line=9, found=True),
        ev("docs/r.md", "несверенная"),
        ev("docs/s.md", "потерянная", line=None, found=False, verdict="цитаты нет дословно")])
    block = section(design_of(rec), "Decisions")
    assert "- **Улики вопроса:** docs/q.md:9 «улика вопроса»" in block
    assert "- **Улики вопроса:** docs/r.md «несверенная»" in block
    assert "- **Улики вопроса:** docs/s.md «потерянная» — цитаты нет дословно" in block
    assert block.count("- **Улики вопроса:**") == 3
    assert "- **Улики выбранного:** a.md «улика выбранного»" in block       # метка выбранного та же
    assert block.index("Улики вопроса") < block.index("Отвергнуто")


def test_decision_without_question_level_evidence_has_no_such_line():
    block = section(design_of(decided("F-01", "A", [opt("A", "раз", [ev("a.md", "улика")])])), "Decisions")
    assert "Улики вопроса" not in block


def test_question_level_evidence_of_an_undecided_fork_stays_out_of_the_document():
    rec = record("F-02", "открытая?", [opt("A", "раз")], evidence=[ev("docs/q.md", "улика открытой")])
    assert "улика открытой" not in design_of(rec)


def test_multiline_quotes_stay_on_one_line_in_every_section():
    broken = "первая строка\n- ложный пункт\n## Ложный раздел\n\n  вторая   строка"
    flat = "первая строка - ложный пункт ## Ложный раздел вторая строка"
    fact = record("F-20", "факт", kind="факт", evidence=[ev("docs/f.md", broken, line=3, found=True)])
    options = [opt("A", "выбранный", [ev("docs/a.md", broken)]), opt("B", "отвергнутый", [ev("docs/b.md", broken)])]
    rec = decided("F-01", "A", options, evidence=[ev("docs/q.md", broken)])
    md = design_of(fact, rec)
    assert f"  - docs/f.md:3 «{flat}»" in section(md, "Context")
    decisions = section(md, "Decisions")
    assert f"- **Улики выбранного:** docs/a.md «{flat}»" in decisions
    assert f"- **Улики вопроса:** docs/q.md «{flat}»" in decisions
    assert f"- [Risk] {flat} (F-01, отвергнут B: docs/b.md) → Mitigation: решение A" in section(md, "Risks / Trade-offs")
    lines = md.split("\n")
    assert not [line for line in lines if line.startswith("- ложный") or line.startswith("## Ложный")]
    assert [line for line in lines if line.startswith("## ")] == SECTIONS[1:]


# --- Risks / Trade-offs -----------------------------------------------------

def test_risks_are_rejected_options_evidence_with_the_chosen_letter_as_mitigation():
    options = [
        opt("A", "выбранный", [ev("docs/a.md", "улика выбранного")]),
        opt("B", "отвергнутый", [ev("docs/b.md", "довод против", line=7, found=True),
                                 ev("docs/c.md", "второй довод")]),
        opt("C", "без улик"),
    ]
    risks = section(design_of(decided("F-05", "A", options)), "Risks / Trade-offs")
    assert "- [Risk] довод против (F-05, отвергнут B: docs/b.md:7) → Mitigation: решение A" in risks
    assert "- [Risk] второй довод (F-05, отвергнут B: docs/c.md) → Mitigation: решение A" in risks
    assert "улика выбранного" not in risks
    assert risks.count("[Risk]") == 2                   # у C улик нет — строки нет


def test_risks_include_the_evidence_of_unlikely_rejected_options():
    options = [opt("A", "выбранный"), opt("B", "маловероятный", [ev("docs/b.md", "всё же довод")], unlikely="редко")]
    risks = section(design_of(decided("F-05", "A", options)), "Risks / Trade-offs")
    assert "- [Risk] всё же довод (F-05, отвергнут B: docs/b.md) → Mitigation: решение A" in risks


def test_risk_quote_with_markdown_markup_is_kept_verbatim():
    options = [opt("A", "раз", [ev("docs/f.md", "## F-01 <вопрос>")]), opt("B", "два")]
    risks = section(design_of(decided("F-01", "B", options)), "Risks / Trade-offs")
    assert "- [Risk] ## F-01 <вопрос> (F-01, отвергнут A: docs/f.md) → Mitigation: решение B" in risks


def test_risks_follow_the_decision_order():
    first = decided("F-01", "A", [opt("A", "раз"), opt("B", "два", [ev("a.md", "довод первой")])])
    second = decided("F-02", "A", [opt("A", "раз"), opt("B", "два", [ev("b.md", "довод второй")])],
                     reversibility={"level": "в одну сторону", "why": "форк"})
    risks = section(design_of(first, second), "Risks / Trade-offs")
    assert risks.index("довод второй") < risks.index("довод первой")


# --- Open Questions ---------------------------------------------------------

def test_parking_and_dispute_lines_appear():
    parked = decided("F-01", "A", [opt("A", "раз")], parking=[
        {"addressee": "человек", "text": "а как же так?", "finding": "так уже делают"},
        {"addressee": "ИБ", "text": "есть ли риск?"}])
    fact = record("F-20", "факт", kind="факт", dispute="«не понял»")
    questions = section(design_of(parked, fact), "Open Questions")
    assert "- F-01 → человек: «а как же так?» — находка: так уже делают" in questions
    assert "- F-01 → ИБ: «есть ли риск?»\n" in questions + "\n"
    assert "- F-20 — спор: «не понял»" in questions
    assert "находка" not in questions.split("есть ли риск?")[1]


def test_open_questions_order_is_forks_then_parking_then_disputes():
    undecided = record("F-02", "открытая?", [opt("A", "раз")])
    parked = decided("F-01", "A", [opt("A", "раз")], parking=[{"addressee": "материалы", "text": "что с материалами?"}])
    fact = record("F-20", "факт", kind="факт", dispute="спорим")
    questions = section(design_of(parked, undecided, fact), "Open Questions")
    assert (questions.index("— открыта") < questions.index("→ материалы")
            < questions.index("— спор: спорим"))


# --- чистота ----------------------------------------------------------------

def test_render_design_does_not_mutate_the_journal():
    j = journal.load_journal(LIVE_JSON)
    before = copy.deepcopy(j)
    journal.render_design(j)
    assert j == before


def test_render_design_is_deterministic():
    j = journal.load_journal(LIVE_JSON)
    assert journal.render_design(j) == journal.render_design(copy.deepcopy(j))


# --- командная строка -------------------------------------------------------

def test_cli_render_design_writes_the_file(tmp_path):
    src, out = tmp_path / "j.json", tmp_path / "design.md"
    j = journal.load_journal(LIVE_JSON)
    journal.save_journal(src, j)
    run = run_cli("render-design", src, "--out", out)
    assert run.returncode == 0, run.stderr
    assert f"[ok] {out}" in run.stdout
    assert out.read_text(encoding="utf-8") == journal.render_design(j, source="j.json")


def test_cli_render_design_writes_crlf_like_render_md(tmp_path):
    src, out = tmp_path / "j.json", tmp_path / "design.md"
    journal.save_journal(src, journal.load_journal(LIVE_JSON))
    assert run_cli("render-design", src, "--out", out).returncode == 0
    data = out.read_bytes()
    assert b"\r\n" in data and data.count(b"\n") == data.count(b"\r\n")      # ни одного голого \n
    md_out = tmp_path / "journal.md"
    assert run_cli("render-md", src, "--out", md_out).returncode == 0
    md = md_out.read_bytes()
    assert md.count(b"\n") == md.count(b"\r\n")                              # render-md пишет так же


def test_cli_render_design_header_names_the_json(tmp_path):
    src, out = tmp_path / "plan.journal.json", tmp_path / "design.md"
    journal.save_journal(src, one_record_journal("a.md", "q"))
    assert run_cli("render-design", src, "--out", out).returncode == 0
    head = out.read_text(encoding="utf-8").split("\n")[:4]
    assert head == ["# Design", "", "> Рендер из `plan.journal.json`, не править руками.", ""]


def test_render_design_header_is_only_there_when_the_source_is_named():
    j = {"title": "т", "source": "s.md", "records": []}
    assert "Рендер из" not in journal.render_design(j)
    assert journal.render_design(j).split("\n")[:2] == ["# Design", ""]
    named = journal.render_design(j, source="j.json").split("\n")
    assert named[:4] == ["# Design", "", "> Рендер из `j.json`, не править руками.", ""]
    assert named[4] == "## Context"


def test_render_design_header_matches_the_one_of_render_md():
    j = {"title": "т", "source": "s.md", "records": []}
    md_header = journal.render_md(j, json_name="j.json").split("\n")[2]
    assert journal.render_design(j, source="j.json").split("\n")[2] == md_header


def test_cli_render_design_refuses_an_invalid_journal(tmp_path):
    j = one_record_journal("a.md", "q")
    j["records"][0]["status"] = "готов"
    src, out = tmp_path / "j.json", tmp_path / "design.md"
    journal.save_journal(src, j)
    run = run_cli("render-design", src, "--out", out)
    assert run.returncode == 1 and "F-01" in run.stderr
    assert not out.exists()


# --- сценарии 5.6 -----------------------------------------------------------

def test_decisions_come_only_from_forks_without_outcome():
    probe = decided("F-02", "A", [opt("A", "край")], outcome={"kind": "проба", "value": "Specify", "reason": ""})
    fact = record("F-03", "факт?", kind="факт")
    md = design_of(decided("F-01", "A", [opt("A", "первый")]), probe, fact)
    heads = [line.split()[1] for line in section(md, "Decisions").split("\n") if line.startswith("### ")]
    assert heads == ["F-01"]


def test_journal_without_decided_forks_says_so():
    md = design_of(record("F-01", "кто решает?", [opt("A", "раз")]))
    assert section(md, "Decisions").strip() == "нет: решённых развилок в журнале нет"
    assert "- F-01 кто решает? — открыта" in section(md, "Open Questions")


def test_decision_to_change_nothing_is_marked_under_chosen():
    for text in ("Оставить как есть: цена выше пользы", "  ничего не менять", "Ничего не менять"):
        block = section(design_of(decided("F-01", "A", [opt("A", text), opt("B", "переписать")])), "Decisions")
        lines = block.split("\n")
        chosen = next(i for i, line in enumerate(lines) if line.startswith("- **Выбрано:**"))
        assert lines[chosen + 1] == "- **Конструкция не меняется.**", text


def test_ordinary_decision_is_not_marked():
    block = section(design_of(decided("F-01", "A", [opt("A", "Переписать"), opt("B", "Оставить как есть")])), "Decisions")
    assert "Конструкция не меняется" not in block      # «оставить» — отвергнутый вариант, не выбранный


# --- отступление от постановки: только у выбранного отступающего варианта (5.1, ruling) ---------

def deviating_option(letter, text, target="F-01"):
    return {**opt(letter, text), "deviation": target}


def test_decision_on_a_deviating_option_names_the_setting_fact():
    fork = decided("F-02", "B", [opt("A", "как в постановке"), deviating_option("B", "наследование")])
    lines = section(design_of(fork), "Decisions").split("\n")
    chosen = next(i for i, line in enumerate(lines) if line.startswith("- **Выбрано:**"))
    assert lines[chosen + 1] == "- **Отступление от постановки:** F-01"


def test_decision_on_a_keeping_option_has_no_deviation_line():
    """Отступающий вариант отвергнут — решение не отступает, строки нет."""
    fork = decided("F-02", "A", [opt("A", "как в постановке"), deviating_option("B", "наследование")])
    assert "Отступление от постановки" not in design_of(fork)


def test_ordinary_decision_has_no_deviation_line():
    assert "Отступление от постановки" not in design_of(decided("F-01", "A", [opt("A", "раз")]))
