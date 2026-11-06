import copy
import json
import shutil
import subprocess
import sys

import pytest

import journal
from conftest import FIX, ROOT

LIVE_JSON = ROOT / "docs" / "plan-implementation.journal.json"
TEMPLATE = ROOT / "viewer" / "playground-template.html"
DATE = "2026-10-30"

HEADER_LINK = "### Решения по журналу [j.md](http://j.md), 2026-10-29:\n\n"
HEADER_PLAIN = "Решения по журналу j.md, 2026-10-29:\n"


def plan():
    """Журнал в состоянии после круга 1 (решения, парковка F-01, споры по фактам)."""
    return journal.import_md(FIX / "journal-plan.md")


def before():
    """Журнал до круга 1: решений, парковки, споров и добавленных вариантов нет."""
    return journal.import_md(FIX / "journal-plan-before-round1.md")


def rec_of(j, rid):
    return next(r for r in j["records"] if r["id"] == rid)


def apply(j, text, date=DATE):
    return journal.apply_answers(j, journal.parse_answers(text), date=date)


def snapshot(j):
    return json.dumps(j, ensure_ascii=False, sort_keys=True)


def embedded(html):
    """JSON, который шаблон получил вместо `__JOURNAL_JSON__`."""
    start = html.index("const JOURNAL = ") + len("const JOURNAL = ")
    payload, _ = json.JSONDecoder().raw_decode(html[start:].replace("<\\/", "</"))
    return payload


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "cli" / "journal.py"), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8")


# --- тесты из брифа ---------------------------------------------------------

def test_apply_round1_reproduces_current_journal():
    j = journal.import_md(FIX / "journal-plan-before-round1.md")
    ans = journal.parse_answers((FIX / "answers-round1.md").read_text(encoding="utf-8"))
    journal.apply_answers(j, ans, date="2026-10-29")
    now = journal.load_journal(ROOT / "docs/plan-implementation.journal.json")
    # записи после круга 1 (с F-25, слово владельца 2026-10-30) дописаны в конец: промпт круга их не знал
    ids = [r["id"] for r in j["records"]]
    assert [r["id"] for r in now["records"]][:len(ids)] == ids
    for a, b in zip(j["records"], now["records"]):
        if a["id"] == "F-01":   # в промпте круга 1 F-01 припаркован; решение B дал круг 2, словом в чате
            continue
        assert (a["decision"] or {}).get("option") == (b["decision"] or {}).get("option"), a["id"]


def test_apply_rejects_unknown_letter():
    j = journal.import_md(FIX / "journal-plan.md")
    before_ = json.dumps(j, ensure_ascii=False)
    report = journal.apply_answers(j, journal.parse_answers("- F-05: Q — «x»"), date="2026-10-30")
    assert any("F-05" in r and "Q" in r for r in report) and json.dumps(j, ensure_ascii=False) == before_


def test_apply_parking_does_not_clear_decision():
    j = journal.import_md(FIX / "journal-plan.md")
    journal.apply_answers(j, journal.parse_answers("- F-02: припарковано → ИБ — «проверить токены»"), date="2026-10-30")
    r = next(x for x in j["records"] if x["id"] == "F-02")
    assert r["decision"]["option"] == "B" and r["parking"][-1]["addressee"] == "ИБ"


# --- круг 1 целиком ---------------------------------------------------------

def round1():
    j = before()
    report = journal.apply_answers(
        j, journal.parse_answers((FIX / "answers-round1.md").read_text(encoding="utf-8")), date="2026-10-29")
    return j, report, journal.load_journal(LIVE_JSON)


def test_round1_has_no_refusals_and_leaves_a_valid_journal():
    j, report, _ = round1()
    assert not [r for r in report if r.startswith("отказ")], report
    assert journal.validate_journal(j) == []


def test_round1_f01_is_parked_and_undecided():
    # круг 1 припарковал F-01; решение B пришло в круге 2, словом в чате, — в промпте его нет
    j, _, now = round1()
    f01, live = rec_of(j, "F-01"), rec_of(now, "F-01")
    assert f01["decision"] is None and f01["status"] == "припаркован"
    assert [(p["addressee"], p["text"]) for p in f01["parking"]] == [(p["addressee"], p["text"]) for p in live["parking"]]


def test_round1_words_dates_and_disputes_match_the_live_journal():
    # Слово у решений через добавленный вариант (F-05, F-06, F-08, F-11, F-17) живой журнал
    # получил редакторской правкой — модель разнесла текст строки между вариантом и словом;
    # apply вносит дословно и не толкует, поэтому там сверяются вариант, дата и статус.
    j, _, now = round1()
    for a, b in zip(j["records"], now["records"]):
        if a["kind"] == "факт":
            assert a["dispute"] and b["dispute"].startswith(a["dispute"]), a["id"]
        elif a["id"] != "F-01":
            via_added = any(o["added"] for o in a["options"])
            mine, live = dict(a["decision"]), dict(b["decision"])
            if via_added:
                mine["word"] = live["word"] = ""
            assert mine == live, a["id"]
            assert a["status"] == b["status"], a["id"]


def test_round1_added_options_match_the_live_letters():
    j, _, now = round1()
    for a, b in zip(j["records"], now["records"]):
        assert [(o["letter"], o["added"]) for o in a["options"]] == [(o["letter"], o["added"]) for o in b["options"]], a["id"]


# --- разбор промпта ---------------------------------------------------------

@pytest.mark.parametrize("line, expected", [
    ("- F-02: B — «слово»",
     {"id": "F-02", "op": "decide", "option": "B", "was": None, "word": "слово"}),
    ("- F-02: B (было A) — «слово «внутри» ещё»",
     {"id": "F-02", "op": "decide", "option": "B", "was": "A", "word": "слово «внутри» ещё"}),
    ("- F-04: A — (без слова)",
     {"id": "F-04", "op": "decide", "option": "A", "was": None, "word": ""}),
    ("- F-01: припарковано → материалы — «вопрос?»",
     {"id": "F-01", "op": "park", "addressee": "материалы", "text": "вопрос?"}),
    ("- F-05: добавлен вариант C. Вариант А + жанры",
     {"id": "F-05", "op": "add_option", "letter": "C", "text": "Вариант А + жанры"}),
    ("- F-05: зависимость добавлена F-07",
     {"id": "F-05", "op": "dep_add", "dep": "F-07"}),
    ("- F-05: зависимость снята F-04",
     {"id": "F-05", "op": "dep_remove", "dep": "F-04"}),
    ("- F-20: факт оспорен — «не так»",
     {"id": "F-20", "op": "dispute", "word": "не так"}),
    ("- F-02: к решению B — «ещё слово»",
     {"id": "F-02", "op": "word", "option": "B", "word": "ещё слово"}),
    ("- F-02: без выбора — «слово»",
     {"id": "F-02", "op": "word", "option": None, "word": "слово"}),
    # слово, начавшееся с «а», просмотрщик обернул один раз: внешняя пара — крайняя
    ("- F-02: B — ««а» и «б»»",
     {"id": "F-02", "op": "decide", "option": "B", "was": None, "word": "«а» и «б»"}),
    # руками правленный промпт без внешней обёртки: «а» и «б» — два слова, пара не внешняя
    ("- F-02: B — «а» и «б»",
     {"id": "F-02", "op": "decide", "option": "B", "was": None, "word": "«а» и «б»"}),
    ("- F-02: припарковано → человек — «а» и «б»",
     {"id": "F-02", "op": "park", "addressee": "человек", "text": "«а» и «б»"}),
    ("- F-20: факт оспорен — «а» и «б»",
     {"id": "F-20", "op": "dispute", "word": "«а» и «б»"}),
    ("- F-02: к решению B — «а» и «б»",
     {"id": "F-02", "op": "word", "option": "B", "word": "«а» и «б»"}),
    ("- F-N1: вопрос — варианты: x | y — «а» и «б»",
     {"id": "F-N1", "op": "new_fork", "question": "вопрос", "options": ["x", "y"], "word": "«а» и «б»"}),
    ("- F-N1: вопрос — варианты: x | y — ««а» и «б»»",
     {"id": "F-N1", "op": "new_fork", "question": "вопрос", "options": ["x", "y"], "word": "«а» и «б»"}),
])
def test_parse_line_shapes(line, expected):
    assert journal.parse_answers(line) == [expected]


@pytest.mark.parametrize("header", [HEADER_LINK, HEADER_PLAIN, ""])
def test_parse_tolerates_the_markdown_linked_header_and_the_plain_one(header):
    ops = journal.parse_answers(header + "- F-02: B — «слово»\n")
    assert [(o["id"], o["op"]) for o in ops] == [("F-02", "decide")]


def test_parse_real_round1_prompt():
    ops = journal.parse_answers((FIX / "answers-round1.md").read_text(encoding="utf-8"))
    assert len(ops) == 29      # 29 строк `- F-NN:`; многострочное слово F-07 — одна из них
    assert ops[0] == {"id": "F-01", "op": "park", "addressee": "материалы",
                      "text": ops[0]["text"]} and ops[0]["text"].startswith("json разбирать проще")
    assert [o["op"] for o in ops if o["id"] == "F-05"] == ["add_option", "decide"]
    assert sum(1 for o in ops if o["op"] == "dispute") == 5


@pytest.mark.parametrize("eol", ["\n", "\r\n"])
def test_parse_keeps_a_multiline_word_in_one_item(eol):
    text = eol.join(["Решения по журналу j.md, 2026-10-29:", "- F-07: B — «первая строка", "",
                     "вторая строка»", "- F-08: A — (без слова)", ""])
    ops = journal.parse_answers(text)
    assert [o["id"] for o in ops] == ["F-07", "F-08"]
    assert ops[0]["word"] == "первая строка\n\nвторая строка"


def test_parse_new_forks_and_notes_block():
    text = ("Решения по журналу j.md, 2026-10-29:\n"
            "- F-02: B — (без слова)\n"
            "Новые развилки:\n"
            "- F-N1: Что делаем с X? — варианты: первый | второй — «потому что»\n"
            "- F-N2: Вопрос без слова — варианты: a | b\n"
            "Замечания к схеме: первая строка\n"
            "вторая строка про - F-01: внутри замечания\n")
    ops = journal.parse_answers(text)
    assert ops[1] == {"id": "F-N1", "op": "new_fork", "question": "Что делаем с X?",
                      "options": ["первый", "второй"], "word": "потому что"}
    assert ops[2] == {"id": "F-N2", "op": "new_fork", "question": "Вопрос без слова",
                      "options": ["a", "b"], "word": ""}
    assert ops[3] == {"id": None, "op": "note",
                      "text": "первая строка\nвторая строка про - F-01: внутри замечания"}
    assert len(ops) == 4


def test_parse_empty_prompt_gives_no_ops():
    text = HEADER_PLAIN + "(нового нет — решения из журнала остаются как есть, молчание по открытой развилке оставляет её открытой)\n"
    assert journal.parse_answers(text) == []


def test_parse_unrecognised_line_is_kept_as_unknown_and_refused_by_name():
    ops = journal.parse_answers("- F-02: что-то странное")
    assert ops == [{"id": "F-02", "op": "unknown", "raw": "что-то странное"}]
    j = plan()
    before_ = snapshot(j)
    report = journal.apply_answers(j, ops, date=DATE)
    assert any("F-02" in r and "что-то странное" in r for r in report) and snapshot(j) == before_


# --- решение ----------------------------------------------------------------

def test_decision_on_an_open_fork_sets_option_word_date_and_status():
    j = before()
    assert apply(j, "- F-04: A — «берём»") == ["F-04: решено A"]
    r = rec_of(j, "F-04")
    assert r["decision"] == {"option": "A", "word": "берём", "date": DATE} and r["status"] == "решён"


def test_decision_without_word_has_an_empty_word():
    j = before()
    apply(j, "- F-04: A — (без слова)")
    assert rec_of(j, "F-04")["decision"]["word"] == ""


def test_decision_word_is_flattened_to_one_line():
    j = before()
    apply(j, "- F-07: B — «первая строка\n\nвторая   строка»")
    assert rec_of(j, "F-07")["decision"]["word"] == "первая строка вторая строка"


def test_decision_change_with_matching_was_replaces_the_decision():
    j = plan()
    apply(j, "- F-02: C (было B) — «передумал»")
    assert rec_of(j, "F-02")["decision"] == {"option": "C", "word": "передумал", "date": DATE}


def test_decision_change_with_wrong_was_is_refused_and_leaves_journal_unchanged():
    j = plan()
    before_ = snapshot(j)
    report = apply(j, "- F-02: C (было A) — «передумал»")
    assert any("F-02" in r and "B" in r and "A" in r for r in report)
    assert snapshot(j) == before_


def test_decision_change_without_was_over_an_existing_decision_is_refused():
    j = plan()
    before_ = snapshot(j)
    report = apply(j, "- F-02: C — «передумал»")
    assert any("F-02" in r and "B" in r for r in report) and snapshot(j) == before_


def test_decision_with_was_on_an_undecided_fork_is_refused():
    j = before()
    before_ = snapshot(j)
    report = apply(j, "- F-04: A (было B) — «x»")
    assert any("F-04" in r and "B" in r for r in report) and snapshot(j) == before_


def test_decision_on_a_fact_is_refused():
    j = plan()
    before_ = snapshot(j)
    report = apply(j, "- F-20: A — «x»")
    assert any("F-20" in r for r in report) and snapshot(j) == before_


@pytest.mark.parametrize("line, needle", [
    ("- F-99: A — «x»", "F-99"),
    ("- F-05: Я — «x»", "Я"),
    ("- F-05: припарковано → бухгалтерия — «x»", "бухгалтерия"),
    ("- F-05: зависимость добавлена F-99", "F-99"),
    ("- F-05: зависимость снята F-99", "F-99"),
    ("- F-05: зависимость добавлена F-05", "F-05"),
])
def test_refusals_name_the_culprit_and_change_nothing(line, needle):
    j = plan()
    before_ = snapshot(j)
    report = apply(j, line)
    assert any(r.startswith("отказ") and needle in r for r in report), report
    assert snapshot(j) == before_


def test_one_refusal_keeps_the_whole_prompt_out_of_the_journal():
    j = before()
    before_ = snapshot(j)
    report = apply(j, "- F-04: A — «берём»\n- F-05: Q — «x»\n")
    assert snapshot(j) == before_
    assert any("F-05" in r for r in report) and not any("F-04: решено" in r for r in report)


# --- слово к решению --------------------------------------------------------

def test_word_is_appended_to_the_existing_decision():
    j = plan()
    old = rec_of(j, "F-02")["decision"]["word"]
    apply(j, "- F-02: к решению B — «ещё слово»")
    dec = rec_of(j, "F-02")["decision"]
    assert dec["word"] == old + " ещё слово" and dec["option"] == "B"


def test_word_already_in_the_decision_is_not_added_twice():
    j = plan()
    apply(j, "- F-02: к решению B — «ещё слово»")
    once = snapshot(j)
    apply(j, "- F-02: к решению B — «ещё слово»")
    assert snapshot(j) == once


def test_word_without_a_decision_is_refused():
    j = before()
    before_ = snapshot(j)
    report = apply(j, "- F-04: к решению A — «слово»")
    assert any("F-04" in r and "нет решения, к которому добавить слово" in r for r in report)
    assert snapshot(j) == before_


def test_word_for_another_option_than_decided_is_refused():
    j = plan()
    before_ = snapshot(j)
    report = apply(j, "- F-02: к решению A — «слово»")
    assert any("F-02" in r and "B" in r and "A" in r for r in report) and snapshot(j) == before_


def test_word_without_choice_is_refused_on_an_undecided_and_on_a_decided_fork():
    for j in (before(), plan()):
        before_ = snapshot(j)
        report = apply(j, "- F-02: без выбора — «слово»")
        assert any(r.startswith("отказ") and "F-02" in r for r in report)
        assert snapshot(j) == before_


# --- парковка ---------------------------------------------------------------

def test_parking_on_an_undecided_fork_marks_it_parked():
    j = before()
    apply(j, "- F-04: припарковано → человек — «а что с X?»")
    r = rec_of(j, "F-04")
    assert r["parking"] == [{"addressee": "человек", "text": "а что с X?"}]
    assert r["decision"] is None and r["status"] == "припаркован"


def test_parking_on_a_decided_fork_keeps_status():
    j = plan()
    apply(j, "- F-02: припарковано → ИБ — «проверить токены»")
    assert rec_of(j, "F-02")["status"] == "решён"


def test_parking_is_appended_and_a_repeat_is_not_added_twice():
    j = plan()
    apply(j, "- F-01: припарковано → человек — «второй вопрос»")
    apply(j, "- F-01: припарковано → человек — «второй вопрос»")
    texts = [p["text"] for p in rec_of(j, "F-01")["parking"]]
    assert len(texts) == 2 and texts[-1] == "второй вопрос"


def test_parking_on_a_fact_is_refused():
    j = plan()
    before_ = snapshot(j)
    report = apply(j, "- F-20: припарковано → человек — «x»")
    assert any("F-20" in r for r in report) and snapshot(j) == before_


# --- вариант ----------------------------------------------------------------

def test_added_option_is_appended_with_the_marker_and_can_be_chosen_in_the_same_prompt():
    j = before()
    report = apply(j, "- F-05: добавлен вариант C. Вариант А + жанры\n- F-05: C — (без слова)\n")
    r = rec_of(j, "F-05")
    assert r["options"][-1] == {"letter": "C", "text": "Вариант А + жанры (добавлен человеком)",
                                "added": True, "unlikely": None, "evidence": []}
    assert r["decision"]["option"] == "C" and len(report) == 2


def test_added_option_with_a_taken_letter_is_refused():
    j = before()
    before_ = snapshot(j)
    report = apply(j, "- F-05: добавлен вариант B. текст")
    assert any("F-05" in r and "B" in r for r in report) and snapshot(j) == before_


def test_added_option_on_a_fact_is_refused():
    j = plan()
    before_ = snapshot(j)
    report = apply(j, "- F-20: добавлен вариант A. текст")
    assert any("F-20" in r for r in report) and snapshot(j) == before_


# --- зависимости ------------------------------------------------------------

def test_dependency_added_and_removed():
    j = plan()
    assert rec_of(j, "F-05")["depends_on"] == ["F-04"]
    apply(j, "- F-05: зависимость добавлена F-07")
    assert rec_of(j, "F-05")["depends_on"] == ["F-04", "F-07"]
    apply(j, "- F-05: зависимость снята F-04")
    assert rec_of(j, "F-05")["depends_on"] == ["F-07"]


def test_dependency_repeat_changes_nothing():
    j = plan()
    apply(j, "- F-05: зависимость добавлена F-07\n- F-05: зависимость добавлена F-07")
    assert rec_of(j, "F-05")["depends_on"] == ["F-04", "F-07"]
    apply(j, "- F-05: зависимость снята F-04\n- F-05: зависимость снята F-04")
    assert rec_of(j, "F-05")["depends_on"] == ["F-07"]


# --- спор по факту ----------------------------------------------------------

def test_dispute_sets_the_word_in_guillemets_like_the_journal_does():
    j = before()
    apply(j, "- F-20: факт оспорен — «не так»")
    assert rec_of(j, "F-20")["dispute"] == "«не так»"


def test_dispute_is_added_after_an_existing_one_and_not_twice():
    j = plan()
    old = rec_of(j, "F-22")["dispute"]
    apply(j, "- F-22: факт оспорен — «второй раз»")
    apply(j, "- F-22: факт оспорен — «второй раз»")
    assert rec_of(j, "F-22")["dispute"] == old + " «второй раз»"


def test_dispute_on_a_fork_is_refused():
    j = plan()
    before_ = snapshot(j)
    report = apply(j, "- F-02: факт оспорен — «x»")
    assert any("F-02" in r for r in report) and snapshot(j) == before_


# --- новые развилки ---------------------------------------------------------

def test_new_forks_get_the_next_free_ids_and_a_fork_shape():
    j = plan()
    report = apply(j, "Новые развилки:\n"
                      "- F-N1: Как называем? — варианты: раз | два | три — «почему это развилка»\n"
                      "- F-N2: Второй вопрос — варианты: да | нет\n")
    first, second = j["records"][-2], j["records"][-1]
    assert (first["id"], second["id"]) == ("F-25", "F-26")
    assert first["kind"] == "развилка" and first["status"] == "открыт" and first["decision"] is None
    assert first["question"] == "Как называем?"
    assert [(o["letter"], o["text"], o["added"]) for o in first["options"]] == [
        ("A", "раз", False), ("B", "два", False), ("C", "три", False)]
    assert "почему это развилка" in first["consequences"]
    assert [o["letter"] for o in second["options"]] == ["A", "B"] and second["consequences"] == ""
    assert any("F-N1" in r and "F-25" in r for r in report)
    assert journal.validate_journal(j) == []


def test_new_fork_without_a_question_is_refused():
    j = plan()
    before_ = snapshot(j)
    report = apply(j, "- F-N1:  — варианты: a | b")
    assert any("F-N1" in r for r in report) and snapshot(j) == before_


# --- замечания к схеме ------------------------------------------------------

def test_notes_go_to_the_journal_with_the_date_and_the_result_is_valid():
    j = plan()
    apply(j, HEADER_PLAIN + "Замечания к схеме: стрелка F-03 → F-15 лишняя\nи вторая строка\n")
    assert j["notes"] == [{"date": DATE, "text": "стрелка F-03 → F-15 лишняя\nи вторая строка"}]
    assert journal.validate_journal(j) == []


def test_notes_accumulate_over_prompts():
    j = plan()
    apply(j, "Замечания к схеме: первое", date="2026-10-30")
    apply(j, "Замечания к схеме: второе", date="2026-10-31")
    assert j["notes"] == [{"date": "2026-10-30", "text": "первое"}, {"date": "2026-10-31", "text": "второе"}]


# --- общее ------------------------------------------------------------------

def test_apply_refuses_a_result_that_breaks_the_schema():
    j = plan()
    before_ = snapshot(j)
    report = journal.apply_answers(j, journal.parse_answers("- F-04: B (было A) — «x»"), date="30.10.2026")
    assert any(r.startswith("отказ") for r in report) and snapshot(j) == before_


def test_apply_with_nothing_to_apply_changes_nothing():
    j = plan()
    before_ = snapshot(j)
    assert journal.apply_answers(j, [], date=DATE) == []
    assert snapshot(j) == before_


def test_apply_does_not_touch_the_arguments_it_was_given():
    j = plan()
    answers = journal.parse_answers("- F-02: припарковано → ИБ — «x»")
    answers_before = copy.deepcopy(answers)
    journal.apply_answers(j, answers, date=DATE)
    assert answers == answers_before


# --- командная строка -------------------------------------------------------

@pytest.fixture
def workdir(tmp_path):
    path = tmp_path / "j.json"
    journal.save_journal(path, plan())
    return tmp_path, path


def test_cli_apply_writes_the_journal_in_place_with_the_given_date(workdir):
    tmp, path = workdir
    answers = tmp / "a.md"
    answers.write_text(HEADER_LINK + "- F-06: A (было D) — «передумал»\n", encoding="utf-8")
    run = run_cli("apply", path, answers, "--date", "2026-11-01")
    assert run.returncode == 0, run.stderr + run.stdout
    raw = path.read_bytes()
    assert b"\r" not in raw
    dec = rec_of(journal.load_journal(path), "F-06")["decision"]
    assert dec == {"option": "A", "word": "передумал", "date": "2026-11-01"}
    assert "render-md" in run.stdout and "render-html" in run.stdout


def test_cli_apply_dry_run_reports_and_does_not_write(workdir):
    tmp, path = workdir
    before_bytes = path.read_bytes()
    answers = tmp / "a.md"
    answers.write_text("- F-06: A (было D) — «передумал»\n", encoding="utf-8")
    run = run_cli("apply", path, answers, "--dry-run")
    assert run.returncode == 0 and "F-06" in run.stdout
    assert path.read_bytes() == before_bytes


def test_cli_apply_refusal_exits_1_names_the_record_and_does_not_write(workdir):
    tmp, path = workdir
    before_bytes = path.read_bytes()
    answers = tmp / "a.md"
    answers.write_text("- F-06: A (было D) — «передумал»\n- F-05: Q — «x»\n", encoding="utf-8")
    run = run_cli("apply", path, answers)
    assert run.returncode == 1 and "F-05" in run.stdout + run.stderr
    assert path.read_bytes() == before_bytes


def test_cli_apply_default_date_is_today(workdir):
    import datetime
    tmp, path = workdir
    answers = tmp / "a.md"
    answers.write_text("- F-06: A (было D) — «x»\n", encoding="utf-8")
    assert run_cli("apply", path, answers).returncode == 0
    assert rec_of(journal.load_journal(path), "F-06")["decision"]["date"] == datetime.date.today().isoformat()


def test_cli_apply_rejects_a_malformed_date(workdir):
    tmp, path = workdir
    answers = tmp / "a.md"
    answers.write_text("- F-06: A (было D) — «x»\n", encoding="utf-8")
    run = run_cli("apply", path, answers, "--date", "30.10.2026")
    assert run.returncode == 2 and "YYYY-MM-DD" in run.stderr


def test_cli_apply_reads_a_bom_prefixed_prompt(workdir):
    tmp, path = workdir
    answers = tmp / "a.md"
    answers.write_bytes(b"\xef\xbb\xbf" + "- F-06: A (было D) — «x»\r\n".encode("utf-8"))
    assert run_cli("apply", path, answers).returncode == 0


def test_cli_apply_says_so_when_the_prompt_is_not_utf8(workdir):
    tmp, path = workdir
    before_bytes = path.read_bytes()
    answers = tmp / "a.md"
    answers.write_bytes("- F-06: A (было D) — «x»\n".encode("utf-16"))
    run = run_cli("apply", path, answers)
    assert run.returncode == 1 and "UTF-8" in run.stdout + run.stderr
    assert path.read_bytes() == before_bytes


def test_cli_apply_refuses_an_invalid_journal(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"title": "т"}', encoding="utf-8")
    answers = tmp_path / "a.md"
    answers.write_text("- F-06: A — «x»\n", encoding="utf-8")
    assert run_cli("apply", bad, answers).returncode == 1


def test_apply_help_says_render_is_a_separate_step():
    text = " ".join(run_cli("apply", "-h").stdout.split())
    assert "render-md" in text and "render-html" in text and "не рендерит" in text
    assert "apply" in " ".join(journal.__doc__.split())


# --- просмотрщик: парковка списком, дата сборки -----------------------------

def test_render_html_passes_every_parking_element_to_the_viewer():
    j = plan()
    rec_of(j, "F-01")["parking"].append({"addressee": "человек", "text": "второй вопрос"})
    data = embedded(journal.render_html(j, TEMPLATE))
    recs = {r["id"]: r for r in data["records"]}
    assert [p["text"] for p in recs["F-01"]["parking"]] == [p["text"] for p in rec_of(j, "F-01")["parking"]]
    assert recs["F-01"]["parking"][0]["finding"] == rec_of(j, "F-01")["parking"][0]["finding"]
    assert recs["F-02"]["parking"] == []


def test_render_html_generated_comes_from_the_journal_or_is_absent():
    j = plan()
    assert "generated" not in embedded(journal.render_html(j, TEMPLATE))
    j["generated"] = "2026-10-29"
    assert embedded(journal.render_html(j, TEMPLATE))["generated"] == "2026-10-29"
    assert journal.validate_journal(j) == []


def test_render_html_is_reproducible():
    j = plan()
    assert journal.render_html(j, TEMPLATE) == journal.render_html(copy.deepcopy(j), TEMPLATE)


node = shutil.which("node")
requires_node = pytest.mark.skipif(node is None, reason="нет node: шаблон просмотрщика не прогнать")


@requires_node
def test_viewer_script_is_valid_javascript(tmp_path):
    html = journal.render_html(plan(), TEMPLATE)
    script = html[html.rindex("<script>") + len("<script>"):html.rindex("</script>")]
    js = tmp_path / "viewer.js"
    js.write_text(script, encoding="utf-8")
    run = subprocess.run([node, "--check", str(js)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr


@requires_node
def test_viewer_renders_every_parking_element(tmp_path):
    j = plan()
    rec_of(j, "F-01")["parking"].append({"addressee": "ИБ", "text": "второй вопрос парковки"})
    html = tmp_path / "v.html"
    html.write_text(journal.render_html(j, TEMPLATE), encoding="utf-8", newline="\n")
    run = subprocess.run([node, str(FIX / "viewer-smoke.js"), str(html)],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert "парковка: 2" in out["cards"]
    assert "json разбирать проще" in out["cards"] and "второй вопрос парковки" in out["cards"]
    assert "в журнале" in out["cards"] and "→ ИБ" in out["cards"]
    assert "с парковкой <b>1</b>" in out["stats"]


@requires_node
def test_viewer_drops_ingested_parking_from_the_browser_state(tmp_path):
    # браузер помнит парковку, которую apply уже внёс в журнал: она не должна показываться дважды
    j = plan()
    rec_of(j, "F-01")["parking"].append({"addressee": "ИБ", "text": "второй вопрос парковки"})
    html, state = tmp_path / "v.html", tmp_path / "state.json"
    html.write_text(journal.render_html(j, TEMPLATE), encoding="utf-8", newline="\n")
    first, second = [p["text"] for p in rec_of(j, "F-01")["parking"]]
    state.write_text(json.dumps({"decisions": {"F-01": {"choice": None, "word": "", "parked": [
        {"text": first, "addressee": "материалы"}, {"text": second, "addressee": "ИБ"},
        {"text": "ещё не внесённый вопрос", "addressee": "человек"}]}}}, ensure_ascii=False), encoding="utf-8")
    run = subprocess.run([node, str(FIX / "viewer-smoke.js"), str(html), str(state)],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert "парковка: 3" in out["cards"]       # два из журнала и один свой
    kept = json.loads(out["saved"])["decisions"]["F-01"]["parked"]
    assert [p["text"] for p in kept] == ["ещё не внесённый вопрос"]
