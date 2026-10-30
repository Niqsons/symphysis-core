import copy
import json
import subprocess
import sys

import pytest

import journal
from conftest import FIX, ROOT, one_record_journal

TEMPLATE = ROOT / "tools" / "playground-template.html"
LIVE_JSON = ROOT / "docs" / "plan-implementation.journal.json"
LIVE_MD = ROOT / "docs" / "plan-implementation.journal.md"


def strip_check_fields(j):
    """Копия журнала без полей сверки: `line/found/verdict` в markdown не живут."""
    j = copy.deepcopy(j)
    for rec in j["records"]:
        for ev in rec["evidence"] + [e for o in rec["options"] for e in o["evidence"]]:
            for key in ("line", "found", "verdict"):
                ev.pop(key, None)
    return j


def plan():
    return journal.import_md(FIX / "journal-plan.md")


def roundtrip(j):
    # `source` в markdown не пишется (это имя файла, из которого разобрали), его передаём.
    return journal.import_md_text(journal.render_md(j), source=j["source"])


def embedded(html):
    """JSON, который шаблон получил вместо `__JOURNAL_JSON__`."""
    start = html.index("const JOURNAL = ") + len("const JOURNAL = ")
    payload, _ = json.JSONDecoder().raw_decode(html[start:].replace("<\\/", "</"))
    return payload


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "journal.py"), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8")


# --- тесты из брифа ---------------------------------------------------------

def test_render_md_roundtrip():
    j = journal.import_md(FIX / "journal-plan.md")
    j2 = roundtrip(j)
    assert strip_check_fields(j2) == strip_check_fields(j)


def test_render_md_has_anchor_per_record():
    j = journal.import_md(FIX / "journal-plan.md")
    md = journal.render_md(j)
    assert md.count("<!-- journal:F-") == 24


def test_render_html_embeds_json(tmp_path):
    j = journal.import_md(FIX / "journal-plan.md")
    html = journal.render_html(j, ROOT / "tools/playground-template.html")
    assert "__JOURNAL_JSON__" not in html and '"F-19"' in html and "</script>" in html


# --- markdown: якорь, шапка, формат ----------------------------------------

def test_anchor_is_the_line_right_after_the_heading():
    lines = journal.render_md(plan()).splitlines()
    heads = [i for i, line in enumerate(lines) if line.startswith("## F-")]
    assert len(heads) == 24
    for i in heads:
        rid = lines[i].split()[1]
        assert lines[i + 1] == f"<!-- journal:{rid} -->"


def test_import_ignores_anchor_comment():
    md = "# Т\n\n## F-01 Вопрос?\n<!-- journal:F-01 -->\n- вид: факт\n- статус: решён\n"
    rec = journal.import_md_text(md)["records"][0]
    assert rec["question"] == "Вопрос?" and rec["kind"] == "факт" and rec["status"] == "решён"


def test_render_md_is_stable_on_second_pass():
    once = journal.render_md(plan())
    twice = journal.render_md(journal.import_md_text(once, source="x"))
    assert twice == once


def test_header_names_the_json_and_keeps_the_intro():
    j = plan()
    assert j["intro"].startswith("Формат — из `plan-flexible-pipeline.md`")
    md = journal.render_md(j, json_name="plan-implementation.journal.json")
    head = md.split("\n## F-01")[0]
    assert head.startswith(f"# {j['title']}\n")
    assert "`plan-implementation.journal.json`" in head and "не править руками" in head
    assert j["intro"] in head
    j2 = journal.import_md_text(md)
    assert j2["intro"] == j["intro"] and j2["title"] == j["title"]


def test_header_line_without_json_name_is_still_there():
    md = journal.render_md(one_record_journal("a.md", "q"))
    assert "не править руками" in md.split("\n## F-01")[0]


def test_import_intro_is_text_between_title_and_first_record():
    md = ("# Т\n\n> Рендер из `x.json`, не править руками.\n\nПервый абзац.\n\nВторой.\n\n"
          "## F-01 В?\n- вид: факт\n")
    assert journal.import_md_text(md)["intro"] == "Первый абзац.\n\nВторой."


def test_fields_in_format_order():
    md = journal.render_md(plan())
    f01 = md.split("\n## F-02")[0]
    keys = [line[2:].split(":")[0] for line in f01.splitlines() if line.startswith("- ")]
    assert keys == ["вид", "статус", "адресат", "зависит от", "поставка", "варианты", "антиподы",
                    "рекомендация", "парковка", "находка", "улики", "решение", "следствия"]
    fact = md.split("\n## F-20")[1].split("\n## F-21")[0]
    keys = [line[2:].split(":")[0] for line in fact.splitlines() if line.startswith("- ")]
    assert keys == ["вид", "статус", "адресат", "зависит от", "поставка", "улики", "спор", "следствия"]


def test_option_lines_carry_evidence_then_unlikely():
    md = journal.render_md(plan())
    f01 = md.split("\n## F-02")[0].splitlines()
    i = f01.index("  - C. Файл на решение в стиле ADR (MADR/Nygard), журнал — каталог")
    assert f01[i + 1].startswith("    - улика: `upstream/gsd-core/")
    assert f01[i + 2].startswith("    - маловероятно: десятки файлов")


# --- рекомендация: сырая строка --------------------------------------------

def test_recommendation_keeps_the_raw_line_as_text():
    recs = {r["id"]: r for r in plan()["records"]}
    for rid in ("F-06", "F-08", "F-11", "F-18"):
        text = recs[rid]["recommendation"]["text"]
        assert text and text.startswith(recs[rid]["recommendation"]["option"])
    assert recs["F-06"]["recommendation"]["text"].startswith(
        "B для процедур и A для коротких правил; слово")
    assert recs["F-06"]["recommendation"]["option"] == "B"


def test_render_writes_recommendation_from_raw_text():
    j = plan()
    lines = journal.render_md(j).splitlines()
    forks = [r for r in j["records"] if r["recommendation"]]
    assert len(forks) == 19
    for r in forks:
        assert f"- рекомендация: {r['recommendation']['text']}" in lines


def test_recommendation_without_text_falls_back_to_option_and_why():
    j = one_record_journal("a.md", "q")
    j["records"][0]["recommendation"] = {"option": "A", "why": "потому что"}
    assert "- рекомендация: A — потому что" in journal.render_md(j).splitlines()


# --- «» вокруг слова человека и вопроса парковки ----------------------------

def test_unquote_strips_exactly_one_outer_pair_for_word_and_parking():
    md = ("# Т\n\n## F-01 Вопрос?\n- вид: развилка\n- статус: решён\n- варианты:\n  - A. а\n"
          "- парковка: человек — «вопрос «внутри» ещё»\n"
          "- решение: A — «слово «внутри» ещё», 2026-10-29\n")
    rec = journal.import_md_text(md)["records"][0]
    assert rec["decision"]["word"] == "слово «внутри» ещё"
    assert rec["parking"][0]["text"] == "вопрос «внутри» ещё"


def test_unquote_leaves_unquoted_and_half_quoted_values_alone():
    md = ("# Т\n\n## F-01 Вопрос?\n- вид: развилка\n- статус: решён\n- варианты:\n  - A. а\n"
          "- парковка: человек — «начало» и конец\n"
          "- решение: A — просто слово, 2026-10-29\n")
    rec = journal.import_md_text(md)["records"][0]
    assert rec["decision"]["word"] == "просто слово"
    assert rec["parking"][0]["text"] == "«начало» и конец"


@pytest.mark.parametrize("text, expected", [
    ("«а» и «б»", "«а» и «б»"),                # первая « закрыта раньше последней »: пара не внешняя
    ("«а «б» в»", "а «б» в"),                  # первая « закрыта последней »: пара внешняя
    ("««а» и «б»»", "«а» и «б»"),              # слово, само начавшееся с «а», обёрнуто один раз
    ("«просто»", "просто"),
    ("«»", ""),
    ("«скобка « без пары»", "скобка « без пары"),   # без баланса — прежнее поведение: снять внешнюю пару
    ("«начало» и конец", "«начало» и конец"),
    ("слово", "слово"),
])
def test_unquote_strips_the_outer_pair_only_when_the_first_guillemet_closes_at_the_end(text, expected):
    assert journal._unquote(text) == expected


def test_decision_word_of_two_quoted_phrases_survives_the_roundtrip():
    j = one_record_journal("a.md", "q")
    rec = j["records"][0]
    rec["status"] = "решён"
    rec["decision"] = {"option": "A", "word": "«а» и «б»", "date": "2026-10-29"}
    assert "- решение: A — ««а» и «б»», 2026-10-29" in journal.render_md(j)
    assert strip_check_fields(roundtrip(j)) == strip_check_fields(j)


def test_render_writes_word_and_parking_back_in_guillemets():
    md = journal.render_md(plan())
    lines = md.splitlines()
    assert any(line.startswith("- решение: B — «видимо тогда вариант B") and line.endswith("», 2026-10-29")
               for line in lines)
    assert any(line.startswith("- парковка: материалы — «json разбирать") and line.endswith("»")
               for line in lines)
    assert "- решение: A, 2026-10-29" in lines          # F-04: слова нет, кавычек нет


def test_inner_guillemets_survive_the_roundtrip():
    j = one_record_journal("a.md", "q")
    rec = j["records"][0]
    rec["status"] = "решён"
    rec["decision"] = {"option": "A", "word": "слово «внутри» ещё", "date": "2026-10-29"}
    rec["parking"] = [{"addressee": "человек", "text": "вопрос «внутри» ещё", "finding": "ответ"}]
    md = journal.render_md(j)
    assert "- решение: A — «слово «внутри» ещё», 2026-10-29" in md
    assert "- парковка: человек — «вопрос «внутри» ещё»" in md
    assert strip_check_fields(roundtrip(j)) == strip_check_fields(j)


# --- пометка «добавлен человеком» -------------------------------------------

def test_added_marker_is_not_doubled():
    source = (FIX / "journal-plan.md").read_text(encoding="utf-8")
    j = plan()
    md = journal.render_md(j)
    assert md.count("(добавлен человеком") == source.count("(добавлен человеком") >= 1
    added = [o for r in j["records"] for o in r["options"] if o["added"]]
    assert added and all(o["text"].count("(добавлен человеком") == 1 for o in added)


def test_added_option_without_marker_gets_it_once():
    j = one_record_journal("a.md", "q")
    opt = j["records"][0]["options"][0]
    opt["added"], opt["text"] = True, "свой вариант"
    md = journal.render_md(j)
    assert md.count("(добавлен человеком") == 1
    assert journal.import_md_text(md)["records"][0]["options"][0]["added"] is True


# --- HTML ------------------------------------------------------------------

def test_render_html_payload_follows_the_viewer_contract():
    j = plan()
    data = embedded(journal.render_html(j, TEMPLATE))
    recs = {r["id"]: r for r in data["records"]}
    park = j["records"][0]["parking"][0]
    assert recs["F-01"]["parking"] == [{"addressee": park["addressee"], "text": park["text"],
                                        "finding": park["finding"]}]
    assert recs["F-01"]["finding"] == park["finding"]
    assert recs["F-02"]["parking"] == [] and recs["F-02"]["finding"] == ""
    forks = [r for r in j["records"] if r["kind"] == "развилка"]
    assert data["source"] == "journal-plan.md" and data["title"] == j["title"]
    assert data["stats"]["records"] == 24 and data["stats"]["forks"] == 19 and data["stats"]["facts"] == 5
    assert data["stats"]["decided"] == sum(1 for r in forks if r["decision"]) and data["stats"]["parked"] == 1
    assert "generated" not in data      # дата сборки — из журнала; своей даты рендер не придумывает


def test_render_html_counts_checked_evidence(tmp_path):
    (tmp_path / "a.md").write_text("q\n", encoding="utf-8")
    j = one_record_journal("a.md", "q")
    journal.check_evidence(j, {"": tmp_path})
    data = embedded(journal.render_html(j, TEMPLATE))
    assert data["stats"]["evidence_total"] == 1 and data["stats"]["evidence_found"] == 1
    ev = data["records"][0]["options"][0]["evidence"][0]
    assert ev["line"] == 1 and ev["found"] is True and ev["verdict"] == "сверено"


def test_render_html_escapes_script_close_tag():
    j = one_record_journal("a.md", "q")
    j["records"][0]["question"] = "до </script> после"
    html = journal.render_html(j, TEMPLATE)
    assert html.count("</script>") == TEMPLATE.read_text(encoding="utf-8").count("</script>")
    assert embedded(html)["records"][0]["question"] == "до </script> после"


def test_render_html_requires_the_placeholder(tmp_path):
    template = tmp_path / "t.html"
    template.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="__JOURNAL_JSON__"):
        journal.render_html(plan(), template)


def test_renderers_do_not_mutate_the_journal():
    j = plan()
    before = copy.deepcopy(j)
    journal.render_md(j)
    journal.render_html(j, TEMPLATE)
    assert j == before


# --- командная строка ------------------------------------------------------

def test_cli_render_md_writes_crlf_and_roundtrips(tmp_path):
    src, out = tmp_path / "j.json", tmp_path / "j.md"
    j = plan()
    journal.save_journal(src, j)
    run = run_cli("render-md", src, "--out", out)
    assert run.returncode == 0, run.stderr
    raw = out.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    text = raw.decode("utf-8")
    assert "`j.json`" in text.split("\n## F-01")[0]
    assert strip_check_fields(journal.import_md_text(text, source=j["source"])) == strip_check_fields(j)


def html_fixture(tmp_path, quote):
    """Журнал с одной уликой и файл корней: всё внутри `tmp_path`, машина не важна."""
    (tmp_path / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    src = tmp_path / "j.json"
    journal.save_journal(src, one_record_journal("a.md", quote))
    return src, roots


def test_cli_render_html_writes_lf_and_checks_evidence(tmp_path):
    src, roots = html_fixture(tmp_path, "дв")
    before = src.read_bytes()
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[ok] улик сверено 1 из 1" in run.stdout and "[!!]" not in run.stdout
    raw = out.read_bytes()
    assert b"\r" not in raw
    data = embedded(raw.decode("utf-8"))
    assert data["stats"]["evidence_total"] == 1 and data["stats"]["evidence_found"] == 1
    ev = data["records"][0]["options"][0]["evidence"][0]
    assert (ev["line"], ev["found"], ev["verdict"]) == (2, True, "сверено")
    assert src.read_bytes() == before     # сверка в памяти: журнал-источник не меняется


def test_cli_render_html_reports_unmatched_evidence_and_still_renders(tmp_path):
    src, roots = html_fixture(tmp_path, "нет такого")
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[ok] улик сверено 0 из 1" in run.stdout
    assert "[!!] не сверено — F-01: a.md «нет такого» — цитаты нет дословно" in run.stdout
    data = embedded(out.read_text(encoding="utf-8"))
    assert data["stats"]["evidence_found"] == 0
    assert data["records"][0]["options"][0]["evidence"][0]["found"] is False


@pytest.mark.parametrize("command", ["render-md", "render-html"])
def test_cli_render_refuses_an_invalid_journal(tmp_path, command):
    j = plan()
    j["records"][2]["status"] = "готов"
    src, out = tmp_path / "j.json", tmp_path / "out"
    journal.save_journal(src, j)
    run = run_cli(command, src, "--out", out)
    assert run.returncode == 1 and "F-03" in run.stderr
    assert not out.exists()


# --- заметки: раздел «Заметки» в конце markdown ------------------------------

NOTES = [
    {"date": "2026-10-30",
     "text": "круг 1 закончен: решений 2, фактов 1, открытых развилок 0, парковок материалам 1"},
    {"date": "2026-10-31", "text": "стрелка F-03 → F-15 лишняя\nи вторая строка"},
]


def test_render_md_writes_notes_as_the_last_section():
    j = one_record_journal("a.md", "q")
    assert "## Заметки" not in journal.render_md(j)
    j["notes"] = copy.deepcopy(NOTES)
    md = journal.render_md(j)
    assert md.index("## Заметки") > md.index("## F-01")
    tail = md.split("\n## Заметки\n")[1]
    assert tail.splitlines() == [
        "- 2026-10-30 — круг 1 закончен: решений 2, фактов 1, открытых развилок 0, парковок материалам 1",
        "- 2026-10-31 — стрелка F-03 → F-15 лишняя",
        "  и вторая строка",
    ]


def test_import_reads_the_notes_section_back_into_notes():
    j = one_record_journal("a.md", "q")
    j["notes"] = copy.deepcopy(NOTES)
    back = roundtrip(j)
    assert back["notes"] == NOTES
    assert journal.validate_journal(back) == []
    assert list(back).index("notes") < list(back).index("records")
    assert "notes" not in roundtrip(one_record_journal("a.md", "q"))


# --- исход: строка «- исход:» между решением и следствиями --------------------

PROBE_OUTCOME = {"kind": "проба", "value": "Dismiss",
                 "reason": "выход канонически отсортирован — пары равных нет"}


def decided_probe(outcome):
    """Решённый кандидат пробы: решение, исход и следствия — три поля, порядок которых проверяется."""
    j = one_record_journal("a.md", "q")
    rec = j["records"][0]
    rec["status"] = "решён"
    rec["decision"] = {"option": "A", "word": "слово", "date": "2026-10-30"}
    rec["outcome"] = outcome
    rec["consequences"] = "в spec.md: сценарий"
    return j


def test_render_md_writes_outcome_between_decision_and_consequences():
    lines = journal.render_md(decided_probe(PROBE_OUTCOME)).splitlines()
    keys = [line[2:].split(":")[0] for line in lines if line.startswith("- ")]
    assert keys[-3:] == ["решение", "исход", "следствия"]
    assert "- исход: проба — Dismiss — выход канонически отсортирован — пары равных нет" in lines
    assert "исход" in journal.render_md.__doc__


def test_render_md_omits_the_reason_tail_when_reason_is_empty():
    md = journal.render_md(decided_probe({"kind": "проба", "value": "Defer", "reason": ""}))
    assert "- исход: проба — Defer\n" in md
    assert "- исход:" not in journal.render_md(one_record_journal("a.md", "q"))


@pytest.mark.parametrize("outcome", [
    PROBE_OUTCOME,                                                   # причина сама содержит « — »
    {"kind": "проба", "value": "Defer", "reason": ""},               # причины нет — хвоста нет
    {"kind": "вопрос", "value": "не узнать по файлам", "reason": "файлов нет"},
])
def test_outcome_survives_the_roundtrip(outcome):
    j = decided_probe(outcome)
    back = roundtrip(j)
    assert back["records"][0]["outcome"] == outcome
    assert strip_check_fields(back) == strip_check_fields(j)


def test_import_skips_an_outcome_line_not_by_form(capsys):
    head = "# Т\n\n## F-01 В?\n- вид: развилка\n- статус: открыт\n- варианты:\n  - A. а\n"
    assert journal.import_md_text(head + "- исход: —\n")["records"][0]["outcome"] is None
    rec = journal.import_md_text(head + "- исход: что-то — Defer\n")["records"][0]
    assert rec["outcome"] is None
    assert "F-01: исход не по форме" in capsys.readouterr().err


# --- живой журнал ----------------------------------------------------------

def test_live_journal_roundtrips_through_markdown():
    j = journal.load_journal(LIVE_JSON)
    assert strip_check_fields(roundtrip(j)) == strip_check_fields(j)


def test_committed_markdown_is_the_render_of_the_json():
    j = journal.load_journal(LIVE_JSON)
    assert LIVE_MD.read_text(encoding="utf-8") == journal.render_md(j, json_name=LIVE_JSON.name)


# --- что сказано в документации модуля и в --help ----------------------------

def test_docs_state_unmatched_prefix_and_check_exit_code():
    doc = " ".join(journal.__doc__.split())
    assert "корня для пути нет" in doc and "отката на корень symphysis нет" in doc
    helptext = " ".join(run_cli("-h").stdout.split())
    assert "негодный по схеме журнал — код 1" in helptext
