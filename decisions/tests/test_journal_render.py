import copy
import re

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import (core_files, deviation_journal, FIX, one_record_journal, plan, render_page, requires_node, ROOT,
                      run_cli, scheme_embedded, smoke, strip_check_fields, TEMPLATE)
import journal


LIVE_JSON = ROOT / "docs" / "plan-implementation.journal.json"
LIVE_MD = ROOT / "docs" / "plan-implementation.journal.md"


def roundtrip(j):
    # `source` в markdown не пишется (это имя файла, из которого разобрали), его передаём.
    return journal.import_md_text(journal.render_md(j), source=j["source"])


# --- тесты из брифа ---------------------------------------------------------

def test_render_md_roundtrip():
    j = journal.import_md(FIX / "journal-plan.md")
    j2 = roundtrip(j)
    assert strip_check_fields(j2) == strip_check_fields(j)


def test_render_md_has_anchor_per_record():
    j = journal.import_md(FIX / "journal-plan.md")
    md = journal.render_md(j)
    assert md.count("<!-- journal:F-") == 24


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


# --- рекомендация: вариант и причина ----------------------------------------

def test_import_splits_the_line_into_option_and_reason():
    recs = {r["id"]: r for r in plan()["records"]}
    for rid in ("F-06", "F-08", "F-11", "F-18"):
        assert set(recs[rid]["recommendation"]) == {"option", "why"} and recs[rid]["recommendation"]["why"]
    assert recs["F-06"]["recommendation"]["option"] == "B"
    assert recs["F-06"]["recommendation"]["why"].startswith("для процедур и A для коротких правил; слово")


def test_render_writes_the_option_and_the_reason_of_each_recommendation():
    j = plan()
    lines = journal.render_md(j).splitlines()
    forks = [r for r in j["records"] if r["recommendation"]]
    assert len(forks) == 19
    for r in forks:
        assert f"- рекомендация: {r['recommendation']['option']} — {r['recommendation']['why']}" in lines


def test_render_shows_the_reason_without_text():
    """Сценарий «Поля `text` нет»."""
    j = one_record_journal("a.md", "q")
    j["records"][0]["recommendation"] = {"option": "A", "why": "потому что"}
    assert "- рекомендация: A — потому что" in journal.render_md(j).splitlines()


def test_render_shows_the_reason_when_text_is_present():
    """Сценарий «Есть поле `text`»: причина видна, а строка `text` в файл не попадает."""
    j = one_record_journal("a.md", "q")
    j["records"][0]["recommendation"] = {"option": "A", "why": "дешевле откатить", "text": "A — кратко"}
    md = journal.render_md(j)
    assert "- рекомендация: A — дешевле откатить" in md.splitlines()
    assert "A — кратко" not in md


def test_import_of_a_composite_recommendation_writes_no_text():
    """Сценарий «Импорт составной рекомендации»."""
    md = "# Т\n\n## F-01 В?\n- вид: развилка\n- рекомендация: B для процедур и A для коротких правил\n"
    assert journal.import_md_text(md)["records"][0]["recommendation"] == {
        "option": "B", "why": "для процедур и A для коротких правил"}


def test_roundtrip_keeps_the_option_and_the_reason():
    """Сценарий «Круговой разбор»: запись совпадает после вывода и нового импорта, поля `text` не появляется."""
    once = plan()
    again = roundtrip(once)
    assert [r["recommendation"] for r in again["records"]] == [r["recommendation"] for r in once["records"]]
    composite = next(r for r in again["records"] if r["id"] == "F-06")["recommendation"]
    assert composite == {"option": "B", "why": composite["why"]}
    assert composite["why"].startswith("для процедур и A для коротких правил; слово")


TEXT_OF_RECOMMENDATION = re.compile(
    r"""\b(?:recommendation|rc|rec)\b['"\]]*\s*(?:\?\.|\.|\[)\s*(?:get\(\s*)?['"]?text\b""")


def test_tools_do_not_read_the_text_of_a_recommendation():
    """Страховка F-30: поле осталось только старым журналам, новое чтение вернуло бы ловушку F-08, F-09.
    Снимается вместе с полем."""
    files = [*(path for path in core_files() if path.suffix == ".py"), TEMPLATE]
    reads = [f"{path.relative_to(ROOT)}:{number}"
             for path in files
             for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
             if TEXT_OF_RECOMMENDATION.search(line)]
    assert reads == []


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


def test_renderers_do_not_mutate_the_journal():
    j = plan()
    before = copy.deepcopy(j)
    journal.render_md(j)
    journal.render_html(j, TEMPLATE)
    assert j == before


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
    {"kind": "проба", "value": "Defer", "reason": "   "},            # причина из пробелов — как пустая
])
def test_outcome_survives_the_roundtrip(outcome):
    j = decided_probe(outcome)
    back = roundtrip(j)
    expected = {**outcome, "reason": outcome["reason"].strip()}      # импорт причину обрезает
    assert back["records"][0]["outcome"] == expected
    j["records"][0]["outcome"] = expected
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


# --- пометка «отступление от постановки»: `options[].deviation` (5.1, ruling: у варианта, F-28.E) ----


def test_render_md_marks_the_deviating_option_line():
    md = journal.render_md(deviation_journal())
    fork = md.split("\n## F-02")[1].splitlines()
    assert "  - B. наследование (отступление от F-01)" in fork
    assert "  - A. вариант" in fork                                         # вариант без пометки — как был
    assert "отступление от" not in md.split("\n## F-02")[0]                # у факта пометки нет
    assert not any(line.startswith("- отступление") for line in fork)     # строки записи больше нет
    assert "отступление от F-NN" in journal.render_md.__doc__


def test_deviation_survives_the_roundtrip():
    j = deviation_journal()
    back = roundtrip(j)
    options = back["records"][1]["options"]
    assert options[1]["deviation"] == "F-01" and options[1]["text"] == "наследование"
    assert "deviation" not in options[0] and "deviation" not in back["records"][1]
    assert strip_check_fields(back) == strip_check_fields(j)
    assert journal.render_md(back) == journal.render_md(j)


def test_deviation_mark_follows_the_added_mark_and_survives_the_roundtrip():
    """Вариант, добавленный человеком и отступающий: обе пометки, импорт разбирает обе."""
    j = deviation_journal()
    j["records"][1]["options"][1]["added"] = True
    md = journal.render_md(j)
    assert "  - B. наследование (добавлен человеком) (отступление от F-01)" in md
    back = roundtrip(j)["records"][1]["options"][1]
    assert back["added"] is True and back["deviation"] == "F-01"


# 3. хвост отступления в тексте варианта без поля: импорт не превращает его в поле

def test_deviation_tail_in_option_text_does_not_turn_into_the_field(tmp_path):
    """Ревью: текст варианта без поля, сам оканчивающийся «(отступление от F-NN)», после рендера и импорта получил
    бы поле и усечённый текст. Такой текст `check` отвергает (код 1), render-md его не пишет; тот же оборот
    в середине текста и хвост при настоящем поле проходят круг без потерь."""
    j = deviation_journal()
    a = j["records"][1]["options"][0]
    a["text"] = "вариант (отступление от F-01) в середине"
    back = roundtrip(j)
    assert back["records"][1]["options"][0]["text"] == a["text"] and "deviation" not in back["records"][1]["options"][0]

    a["text"] = "вариант (отступление от F-01)"
    assert journal.validate_journal(j) == \
        ["F-02: вариант A — текст варианта оканчивается пометкой отступления без поля"]
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    run = run_cli("render-md", path, "--out", tmp_path / "j.md")
    assert run.returncode == 1 and not (tmp_path / "j.md").exists()
    assert "[!!] F-02: вариант A — текст варианта оканчивается пометкой отступления без поля" in run.stderr

    # триаж финального ревью: хвостовой пробел не прячет пометку от check — импорт её всё равно принял бы
    a["text"] = "вариант (отступление от F-01) "
    assert journal.validate_journal(j) == \
        ["F-02: вариант A — текст варианта оканчивается пометкой отступления без поля"]

    a["text"] = "вариант (отступление от F-01)"
    a["deviation"] = "F-01"
    assert journal.validate_journal(j) == []
    back = roundtrip(j)
    assert back["records"][1]["options"][0] == {**a, "evidence": back["records"][1]["options"][0]["evidence"]}
    assert strip_check_fields(back) == strip_check_fields(j)


# --- сценарии `decision-viewer` после разреза journal_render (module-structure, 2.2) ----------


@requires_node
def test_page_copied_out_of_the_project_shows_scheme_text_and_runs_modes(tmp_path):
    """`decision-viewer`: «Страница перенесена из проекта» — страница вне проекта, где нет `.symphysis/tools/`: схема
    решения показана текстом (путь к mermaid пуст), режимы и промпт возврата работают."""
    html, _ = render_page(tmp_path, "```mermaid\nflowchart TD\n  A --> B\n```\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    copied = elsewhere / "symphysis.html"
    copied.write_text(html, encoding="utf-8", newline="\n")
    assert not (tmp_path / ".symphysis" / "tools").exists()   # проекта рядом нет
    page = copied.read_text(encoding="utf-8")
    scheme = scheme_embedded(page)
    assert scheme["mermaid"] is None and scheme["text"] == "flowchart TD\n  A --> B\n"
    done = smoke(elsewhere, page)
    assert "F-19" in done["cards"] and done["out"]
    for mode in ("check", "attack"):
        assert smoke(elsewhere, page, {"__suffixes__": {":mode": mode}})["modes"]
