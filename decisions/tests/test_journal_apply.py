import copy
import json

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import FIX, HEADER_LINK, plan, rec_of, ROOT, run_cli
import journal


LIVE_JSON = ROOT / "docs" / "plan-implementation.journal.json"
DATE = "2026-10-30"

HEADER_PLAIN = "Решения по журналу j.md, 2026-10-29:\n"


def before():
    """Журнал до круга 1: решений, парковки, споров и добавленных вариантов нет."""
    return journal.import_md(FIX / "journal-plan-before-round1.md")


def apply(j, text, date=DATE):
    return journal.apply_answers(j, journal.parse_answers(text), date=date)


def snapshot(j):
    return json.dumps(j, ensure_ascii=False, sort_keys=True)


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
    # круг 1 припарковал F-01; решение B пришло в круге 2, словом в чате, — в промпте его нет.
    # Адресат в фикстуре промпта новый («агент»), в живом журнале плана — старый («материалы»): старое значение
    # читается, а строку `apply` с ним скрипт отвергает, поэтому сверяются тексты парковок, значения названы порознь.
    j, _, now = round1()
    f01, live = rec_of(j, "F-01"), rec_of(now, "F-01")
    assert f01["decision"] is None and f01["status"] == "припаркован"
    assert [p["text"] for p in f01["parking"]] == [p["text"] for p in live["parking"]]
    assert [p["addressee"] for p in f01["parking"]] == ["агент"]
    assert [p["addressee"] for p in live["parking"]] == ["материалы"]


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
    ("- F-01: припарковано → агент — «вопрос?»",
     {"id": "F-01", "op": "park", "addressee": "агент", "text": "вопрос?"}),
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
    assert ops[0] == {"id": "F-01", "op": "park", "addressee": "агент",
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
    ("- F-05: припарковано → материалы — «x»", "материалы"),
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


# --- адресат «агент» и старое «материалы» (parking-addressee-agent: F-17.A) ---------------------------------------

OLD_ADDRESSEE_LINE = "- F-01: припарковано → материалы — «вопрос»"
OLD_ADDRESSEE_REFUSAL = "F-01: адресат «материалы» — допустимы агент | человек | ИБ"


def test_parking_to_the_agent_marks_an_undecided_fork_parked():
    """Строка с `агент` вносится: парковка в `parking[]`, статус `припаркован`, журнал годен."""
    j = before()
    assert apply(j, "- F-04: припарковано → агент — «найти в коде»") == ["F-04: припарковано → агент"]
    r = rec_of(j, "F-04")
    assert r["parking"] == [{"addressee": "агент", "text": "найти в коде"}]
    assert r["decision"] is None and r["status"] == "припаркован"
    assert journal.validate_journal(j) == []


def test_parking_to_the_old_addressee_is_refused_with_the_three_allowed():
    """Сценарий «Строка apply со старым значением»: отказ называет запись, старое значение и три допустимых."""
    j = before()
    before_ = snapshot(j)
    report = apply(j, OLD_ADDRESSEE_LINE)
    assert report[0] == f"отказ: {OLD_ADDRESSEE_REFUSAL}", report
    assert snapshot(j) == before_


def test_apply_cli_refuses_the_old_addressee_and_leaves_the_file_byte_for_byte(tmp_path):
    """Сценарий «Строка apply со старым значением» через командную строку: код 1, файл журнала прежний."""
    path = tmp_path / "decisions.json"
    journal.save_journal(path, before())
    raw = path.read_bytes()
    answers = tmp_path / "answers.md"
    answers.write_text(OLD_ADDRESSEE_LINE + "\n", encoding="utf-8")
    done = run_cli("apply", path, answers)
    assert done.returncode == 1, done.stdout + done.stderr
    assert f"[!!] отказ: {OLD_ADDRESSEE_REFUSAL}" in done.stderr
    assert path.read_bytes() == raw


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


# --- строка о тяжести (F-47.A) ----------------------------------------------

SEV_A = ("- тяжесть: openspec/changes/x/attack.md · Утверждения · "
         "«опора `a · b`: «цитата» → не то — «слово»» → предупреждение — «не критично»")
SEV_B = "- тяжесть: openspec/changes/x/attack.md · Раздел · «второе» → блокер — «ломает»"


def severities(text):
    return [a for a in journal.parse_answers(text) if a["op"] == "severity"]


def test_severity_lines_before_first_item_and_after_decision_give_two_items():
    text = HEADER_PLAIN + SEV_A + "\n- F-03: A — «слово»\n" + SEV_B + "\n"
    ops = journal.parse_answers(text)
    assert [a["op"] for a in ops] == ["severity", "decide", "severity"]
    assert ops[1]["word"] == "слово"
    assert "слово" not in str(ops[0]) .replace("«слово»", "") and "слово" not in str(ops[2])
    assert ops[2]["why"] == "ломает"


def test_severity_fields_verbatim():
    a = severities(SEV_A)[0]
    assert a == {"id": None, "op": "severity", "path": "openspec/changes/x/attack.md", "section": "Утверждения",
                 "claim": "опора `a · b`: «цитата» → не то — «слово»", "severity": "предупреждение",
                 "why": "не критично"}


def test_severity_section_with_separator_goes_to_field():
    a = severities("- тяжесть: p.md · Разд · ел · «у» → блокер — «п»")[0]
    assert (a["path"], a["section"], a["claim"]) == ("p.md", "Разд · ел", "у")


def test_severity_two_line_why_is_one_field_and_next_item_resumes():
    text = "- тяжесть: p.md · Р · «у» → блокер — «первая\nвторая»\n- F-03: A\n"
    ops = journal.parse_answers(text)
    assert [a["op"] for a in ops] == ["severity", "decide"]
    assert ops[0]["why"] == "первая\nвторая"


def test_severity_without_word_is_empty_why_and_after_new_forks():
    text = "Новые развилки:\n- F-N1: вопрос — варианты: a | b\n- тяжесть: p.md · Р · «у» → блокер — (без слова)\n"
    ops = journal.parse_answers(text)
    assert [a["op"] for a in ops] == ["new_fork", "severity"]
    assert ops[1]["why"] == ""


def test_severity_stops_at_notes():
    ops = journal.parse_answers(SEV_B + "\nЗамечания к схеме:\n" + SEV_A + "\n")
    assert [a["op"] for a in ops] == ["severity", "note"]


def test_apply_skips_severity_item_without_change_or_refusal():
    j = before()
    snap = snapshot(j)
    report = apply(j, HEADER_PLAIN + SEV_A + "\n" + SEV_B + "\n")
    assert snapshot(j) == snap
    assert report == []


def test_severity_line_off_form_is_refused_by_name():
    j = before()
    snap = snapshot(j)
    bad = "- тяжесть: p.md · Р · «у» → блокер — обоснование без кавычек"
    assert journal.parse_answers(bad)[0]["op"] == "unknown"
    report = apply(j, bad + "\n- F-03: A\n")
    assert snapshot(j) == snap
    assert report[0].startswith("отказ: строка о тяжести:") and "обоснование без кавычек" in report[0]
