import copy
import json
import subprocess
import sys

import pytest

import journal
from conftest import FIX, ROOT


def plan():
    return journal.import_md(FIX / "journal-plan.md")


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


def test_import_counts_evidence_and_facts():
    j = plan()
    ev = sum(len(r["evidence"]) + sum(len(o["evidence"]) for o in r["options"]) for r in j["records"])
    assert ev == 71
    assert sum(1 for r in j["records"] if r["kind"] == "факт") == 5


def test_import_fields_of_f01():
    r = plan()["records"][0]
    assert r["id"] == "F-01" and r["kind"] == "развилка" and r["status"] == "решён"
    assert r["addressee"] == "человек" and r["depends_on"] == [] and r["delivery"] == "П2"
    assert [o["letter"] for o in r["options"]] == ["A", "B", "C"]
    assert r["options"][0]["evidence"][0] == {
        "path": "docs/plan-flexible-pipeline.md", "quote": "## F-01 <вопрос>"}
    assert r["options"][2]["unlikely"].startswith("десятки файлов")
    assert r["options"][0]["unlikely"] is None
    assert r["recommendation"]["option"] == "A"
    assert r["decision"]["option"] == "B" and r["decision"]["date"] == "2026-10-29"
    assert r["decision"]["word"].startswith("видимо тогда вариант B")
    assert len(r["parking"]) == 1
    assert r["parking"][0]["addressee"] == "материалы"
    assert r["parking"][0]["finding"].startswith("Markdown Editor for Humans")
    assert len(r["evidence"]) == 5
    assert r["reversibility"] is None and r["outcome"] is None and r["comments"] == []


def test_import_decision_without_word_and_added_option():
    recs = {r["id"]: r for r in plan()["records"]}
    assert recs["F-04"]["decision"] == {"option": "A", "word": "", "date": "2026-10-29"}
    assert recs["F-11"]["options"][3]["added"] is True
    assert recs["F-11"]["options"][0]["added"] is False


def test_import_fact_keeps_dispute_and_evidence():
    f = next(r for r in plan()["records"] if r["id"] == "F-20")
    assert f["kind"] == "факт" and f["options"] == [] and len(f["evidence"]) == 2
    assert f["dispute"].startswith("«Ответил в F-02»")


def test_import_text_takes_title_and_source():
    j = journal.import_md_text("# Журнал X\n\n## F-01 Вопрос?\n- вид: факт\n", source="x.md")
    assert j["title"] == "Журнал X" and j["source"] == "x.md"
    assert j["records"][0]["question"] == "Вопрос?"


def test_save_and_load_roundtrip_lf(tmp_path):
    j = plan()
    out = tmp_path / "j.json"
    journal.save_journal(out, j)
    raw = out.read_bytes()
    assert raw.endswith(b"}\n") and b"\r" not in raw
    assert "решён" in raw.decode("utf-8")
    assert journal.load_journal(out) == j


def test_validate_rejects_schema_violation_with_record_id():
    j = plan()
    j["records"][2]["status"] = "готов"
    errors = journal.validate_journal(j)
    assert any(e.startswith("F-03") and "status" in e for e in errors)


def test_validate_rejects_depends_on_unknown_and_self():
    j = plan()
    j["records"][3]["depends_on"] = ["F-99", "F-04"]
    errors = journal.validate_journal(j)
    assert any("F-04" in e and "F-99" in e for e in errors)
    assert any(e.startswith("F-04") and "самого себя" in e for e in errors)


def test_validate_rejects_empty_unlikely_reason():
    j = plan()
    j["records"][0]["options"][0]["unlikely"] = ""
    assert any(e.startswith("F-01") and "маловероятно" in e for e in journal.validate_journal(j))


def test_validate_rejects_decision_outside_options():
    j = plan()
    j["records"][0]["decision"]["option"] = "Z"
    assert any(e.startswith("F-01") and "Z" in e for e in journal.validate_journal(j))


def test_validate_rejects_antipode_to_missing_letter():
    j = plan()
    j["records"][1]["antipodes"].append({"option": "B", "other": "F-03.Q"})
    assert any(e.startswith("F-02") and "F-03.Q" in e for e in journal.validate_journal(j))


def test_validate_accepts_reversibility_and_outcome():
    j = plan()
    j["records"][0]["reversibility"] = {"level": "дорого", "why": "формат читают скрипты"}
    j["records"][0]["outcome"] = {"kind": "проба", "value": "Dismiss", "reason": "нет данных"}
    j["records"][1]["comments"] = [{"round": "20261028T201340Z-dfa6", "lines": [3, 4], "text": "правка"}]
    assert journal.validate_journal(j) == []


# --- исход пробы: четыре слова GSD (F-09.C); причины исход не требует ---------------

def probe_outcome(value, reason):
    j = plan()
    j["records"][0]["outcome"] = {"kind": "проба", "value": value, "reason": reason}
    return j


@pytest.mark.parametrize("value, reason", [
    ("Specify", ""), ("Dismiss", "вход — ограниченный enum, границы нет"), ("Backstop", ""), ("Defer", ""),
])
def test_validate_accepts_the_four_probe_outcomes(value, reason):
    assert journal.validate_journal(probe_outcome(value, reason)) == []


def test_validate_rejects_a_probe_outcome_outside_the_four():
    errors = journal.validate_journal(probe_outcome("проверить", "нет данных"))
    assert len(errors) == 1 and errors[0].startswith("F-01") and "проверить" in errors[0]
    assert all(token in errors[0] for token in ("Specify", "Dismiss", "Backstop", "Defer"))


def test_validate_accepts_dismiss_without_a_reason():
    assert journal.validate_journal(probe_outcome("Dismiss", "  ")) == []


def test_validate_leaves_the_question_vocabulary_to_its_own_skill():
    j = plan()
    j["records"][0]["outcome"] = {"kind": "вопрос", "value": "что угодно", "reason": ""}
    assert journal.validate_journal(j) == []


def test_validate_accepts_notes_and_generated_at_the_top_level():
    j = plan()
    j["notes"] = [{"date": "2026-10-30", "text": "замечание"}]
    j["generated"] = "2026-10-29"
    assert journal.validate_journal(j) == []


@pytest.mark.parametrize("notes", [
    [{"date": "30.10.2026", "text": "x"}],        # дата не ISO
    [{"date": "2026-10-30"}],                      # нет текста
    [{"date": "2026-10-30", "text": "x", "by": "я"}],
    "замечание",
])
def test_validate_rejects_malformed_notes(notes):
    j = plan()
    j["notes"] = notes
    assert any("notes" in e for e in journal.validate_journal(j))


def test_validate_does_not_mutate_input():
    j = plan()
    before = copy.deepcopy(j)
    journal.validate_journal(j)
    assert j == before


def test_cli_import_md_writes_valid_json(tmp_path):
    out = tmp_path / "plan.json"
    run = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "journal.py"), "import-md",
         str(FIX / "journal-plan.md"), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    j = json.loads(out.read_text(encoding="utf-8"))
    assert len(j["records"]) == 24 and journal.validate_journal(j) == []


def test_live_journal_records_attack_source_fork():
    """F-25 (D4b): источник механики атаки — слой проверки GSD, не гриль store; решено словом
    владельца 2026-10-30, улики на обе стороны — настоящие строки файлов."""
    j = journal.load_journal(ROOT / "docs" / "plan-implementation.journal.json")
    assert journal.validate_journal(j) == []
    rec = next(r for r in j["records"] if r["id"] == "F-25")
    assert (rec["kind"], rec["status"], rec["addressee"], rec["delivery"]) == ("развилка", "решён", "человек", "П3")
    assert rec["depends_on"] == ["F-06"]
    assert [o["letter"] for o in rec["options"]] == ["A", "B"]
    assert all(o["evidence"] for o in rec["options"]), "у каждого варианта улика путь:цитата"
    assert rec["recommendation"]["option"] == "B" and rec["recommendation"]["why"]
    assert rec["decision"]["option"] == "B" and rec["decision"]["date"] == "2026-10-30"
    assert "gsd-сore" in rec["decision"]["word"], "слово владельца дословно, с его написанием"
    assert rec["reversibility"] == {"level": "обратимо", "why": "текст скилла"}


def test_live_journal_records_viewer_as_own_skill():
    """F-26 (D7): просмотрщик — свой скилл `symphysis-viewer` и свой шаблон, Playground — образец, не точка
    расширения; пересматривает F-18.B; решено словом владельца 2026-10-30, слово о группировке строк атаки
    по линзам — в следствиях, не только в TRANSLATION-NOTES."""
    j = journal.load_journal(ROOT / "docs" / "plan-implementation.journal.json")
    assert journal.validate_journal(j) == []
    rec = next(r for r in j["records"] if r["id"] == "F-26")
    assert (rec["kind"], rec["status"], rec["addressee"], rec["delivery"]) == ("развилка", "решён", "человек", "П7")
    assert rec["depends_on"] == ["F-18"]
    assert [o["letter"] for o in rec["options"]] == ["A", "B"]
    assert all(o["evidence"] for o in rec["options"]), "у каждого варианта улика путь:цитата"
    assert {ev["path"] for o in rec["options"] for ev in o["evidence"]} == {"playground/SKILL.md", "tools/journal_render.py"}
    assert rec["recommendation"]["option"] == "B" and rec["recommendation"]["why"]
    assert rec["decision"]["option"] == "B" and rec["decision"]["date"] == "2026-10-30"
    assert rec["decision"]["word"].startswith("нам стоит сделать свой скилл и шаблон на базе Playground")
    assert rec["decision"]["word"].endswith("а не точка расширения.")
    assert "сгруппировать по ним их \"претензии\" к содержимому" in rec["consequences"]
    assert "symphysis-viewer" in rec["consequences"] and "форк плагина снят" in rec["consequences"]
    assert rec["reversibility"]["level"] == "обратимо" and rec["reversibility"]["why"]


# --- факт постановки и пометка отступления (5.1: F-17.A, F-08.A, F-36 Dismiss) ---------------

FIXTURE_JOURNALS = sorted(FIX.glob("*/decisions.json"))
LIVE_JOURNALS = [ROOT / "docs" / "plan-implementation.journal.json",
                 *sorted((ROOT / "openspec" / "changes" / "archive").glob("*/decisions.json"))]


def setting_journal(**fork_changes) -> dict:
    """Факт постановки F-01 и развилка F-02 с вариантами A и B; `fork_changes` — поля развилки."""
    fact = {"id": "F-01", "question": "критерий готовности", "kind": "факт", "status": "решён",
            "addressee": "постановка", "depends_on": [], "delivery": "", "options": [], "antipodes": [],
            "recommendation": None, "decision": None, "reversibility": None, "outcome": None,
            "parking": [], "dispute": "", "consequences": "F-02",
            "evidence": [{"path": "openspec/changes/x/intent.md", "quote": "критерий"}], "comments": []}
    fork = {"id": "F-02", "question": "развилка?", "kind": "развилка", "status": "открыт",
            "addressee": "человек", "depends_on": ["F-01"], "delivery": "",
            "options": [{"letter": "A", "text": "как в постановке", "added": False, "unlikely": None, "evidence": []},
                        {"letter": "B", "text": "иначе, чем в постановке", "added": False, "unlikely": None,
                         "evidence": []}],
            "antipodes": [], "recommendation": None, "decision": None, "reversibility": None, "outcome": None,
            "parking": [], "dispute": "", "consequences": "", "evidence": [], "comments": [], **fork_changes}
    return {"title": "т", "source": "decisions.json", "records": [fact, fork]}


def test_setting_fact_is_valid():
    """Сценарий «Факт постановки»: `kind: факт`, `addressee: постановка` с уликой из intent.md — годен."""
    assert journal.validate_journal(setting_journal()) == []


@pytest.mark.parametrize("value", ["Постановка", "постановка ", " постановка", "ПОСТАНОВКА"])
def test_setting_addressee_is_not_normalized(value):
    """F-36 Dismiss: регистр и пробелы не нормализуются — ошибка схемы с именем записи и полем."""
    j = setting_journal()
    j["records"][0]["addressee"] = value
    errors = journal.validate_journal(j)
    assert errors and all(e.startswith("F-01: addressee:") for e in errors), errors
    assert repr(value) in errors[0]


def test_setting_is_not_a_parking_addressee():
    """Адресат парковки остаётся из трёх (F-11.D): `постановка` — значение записи, не парковки."""
    j = setting_journal()
    j["records"][1]["parking"] = [{"addressee": "постановка", "text": "вопрос"}]
    assert any(e.startswith("F-02: parking/0/addressee:") for e in journal.validate_journal(j))


@pytest.mark.parametrize("path", FIXTURE_JOURNALS + LIVE_JOURNALS, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_fixture_and_live_journals_stay_valid(path):
    """Журналы плеч (fixtures) и живые журналы годны: без `постановка` и `options[].deviation` — как прежде
    (новое значение и поле необязательны), с ними — по новым правилам."""
    assert journal.validate_journal(journal.load_journal(path)) == []


def test_fixture_journals_are_found():
    assert len(FIXTURE_JOURNALS) >= 4, [p.name for p in FIXTURE_JOURNALS]


def deviating(target="F-01", letter="B", **fork_changes) -> dict:
    """Журнал `setting_journal`, у варианта `letter` развилки F-02 — `deviation: target`."""
    j = setting_journal(**fork_changes)
    next(o for o in j["records"][1]["options"] if o["letter"] == letter)["deviation"] = target
    return j


def test_deviation_on_an_option_pointing_at_a_setting_fact_is_valid():
    """Пометка «отступление от постановки» — поле `deviation` варианта, чьё поведение противоречит сценарию
    факта постановки (F-28.E): номер этого факта; у варианта-уточнения поля нет."""
    assert journal.validate_journal(deviating()) == []


def test_deviation_with_a_human_decision_against_the_fact_is_valid():
    """F-55.E: видимость без замка — выбран отступающий вариант, со словом и без слова — журнал годен."""
    for word in ("наследование — сознательно", ""):
        j = deviating(status="решён", decision={"option": "B", "word": word, "date": "2026-10-31"},
                      reversibility={"level": "обратимо", "why": "одно условие в обработчике"})
        assert journal.validate_journal(j) == []


def test_deviation_is_no_longer_a_record_field():
    """Ruling: на уровне записи поля нет — запись с `deviation` негодна по схеме."""
    errors = journal.validate_journal(setting_journal(deviation="F-01"))
    assert errors and errors[0].startswith("F-02: Additional properties") and "'deviation'" in errors[0], errors


@pytest.mark.parametrize("value", ["F01", "f-01", "F-01.A", "", "F-"])
def test_deviation_is_a_record_id(value):
    errors = journal.validate_journal(deviating(value))
    assert errors and errors[0].startswith("F-02: options/1/deviation:"), errors


def test_deviation_only_on_a_fork_option():
    j = setting_journal()
    j["records"][0]["options"] = [{"letter": "A", "text": "а", "added": False, "unlikely": None, "evidence": [],
                                   "deviation": "F-01"}]
    assert "F-01: вариант A — отступление от постановки у факта — пометка ставится только у варианта развилки" in \
        journal.validate_journal(j)


def test_deviation_to_a_missing_record():
    assert journal.validate_journal(deviating("F-09")) == \
        ["F-02: вариант B — отступление от постановки F-09 — такой записи нет"]


@pytest.mark.parametrize("change, what", [
    ({"addressee": "материалы"}, "факт с адресатом «материалы»"),
    ({"kind": "развилка", "status": "открыт", "evidence": [],
      "options": [{"letter": "A", "text": "а", "added": False, "unlikely": None, "evidence": []}]}, "развилка"),
])
def test_deviation_must_point_at_a_setting_fact(change, what):
    j = deviating()
    j["records"][0].update(change)
    assert journal.validate_journal(j) == \
        [f"F-02: вариант B — отступление от постановки F-01 — запись не факт `addressee: постановка`: {what}"]


def test_old_journal_without_deviation_has_no_such_key_after_import():
    """Поле необязательно: импорт не добавляет `deviation` ни записи, ни варианту без пометки в строке варианта."""
    records = plan()["records"]
    assert all("deviation" not in r for r in records)
    assert all("deviation" not in o for r in records for o in r["options"])


def test_cli_check_rejects_a_bad_deviation_with_code_1(tmp_path):
    path = tmp_path / "j.json"
    journal.save_journal(path, deviating("F-09"))
    run = subprocess.run([sys.executable, str(ROOT / "cli" / "journal.py"), "check", str(path)],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 1
    assert "[!!] F-02: вариант B — отступление от постановки F-09 — такой записи нет" in run.stderr


# --- повторный номер записи (F-138.A) --------------------------------------

def with_repeated_id(tmp_path):
    """Журнал с двумя записями `F-02`: на диске, для вызова через командную строку."""
    j = plan()
    second = copy.deepcopy(next(r for r in j["records"] if r["id"] == "F-02"))
    j["records"].append(second)
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    return j, path


def journal_cli(*args):
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "cli" / "journal.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_validate_rejects_a_repeated_record_id(tmp_path):
    j, _ = with_repeated_id(tmp_path)
    assert journal.validate_journal(j) == ["F-02: номер записи повторяется"]


def test_check_answers_code_1_on_a_repeated_record_id(tmp_path):
    _, path = with_repeated_id(tmp_path)
    done = journal_cli("check", str(path))
    assert done.returncode == 1
    assert "[!!] F-02: номер записи повторяется" in done.stderr


def test_apply_refuses_a_journal_with_a_repeated_record_id(tmp_path):
    _, path = with_repeated_id(tmp_path)
    before = path.read_bytes()
    answers = tmp_path / "answers.md"
    answers.write_text("F-02: A\n", encoding="utf-8")
    done = journal_cli("apply", str(path), str(answers))
    assert done.returncode == 1
    assert "[!!] F-02: номер записи повторяется" in done.stderr
    assert path.read_bytes() == before


def test_real_journals_have_no_repeated_record_ids():
    journals = sorted((ROOT / "openspec" / "changes").glob("**/decisions.json"))
    assert journals
    for path in journals:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert not [e for e in journal.validate_journal(loaded) if e.endswith("номер записи повторяется")], path


# --- nodes: необязательная ссылка записи на узлы схемы (F-23, F-24, F-86) ------

def run_check(path):
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "cli" / "journal.py"), "check", str(path)],
                          capture_output=True, text=True, encoding="utf-8")


def test_old_journal_without_nodes_stays_valid():
    j = plan()
    assert not any("nodes" in r for r in j["records"])
    assert journal.validate_journal(j) == []


@pytest.mark.parametrize("nodes", [[], ["A"], ["A", "узел1"]])
def test_nodes_as_a_list_of_strings_is_valid(nodes):
    j = plan()
    j["records"][2]["nodes"] = nodes
    assert journal.validate_journal(j) == []


@pytest.mark.parametrize("nodes", ["A", 1, None, [1], ["A", None]])
def test_nodes_of_a_wrong_form_names_the_record_and_the_field(nodes, tmp_path):
    j = plan()
    j["records"][2]["nodes"] = nodes
    assert any(e.startswith("F-03") and "nodes" in e for e in journal.validate_journal(j))
    src = tmp_path / "decisions.json"
    src.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    run = run_check(src)
    assert run.returncode == 1 and "F-03" in run.stderr + run.stdout and "nodes" in run.stderr + run.stdout
