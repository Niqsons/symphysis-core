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
    j["records"][0]["outcome"] = {"kind": "проба", "value": "проверить", "reason": "нет данных"}
    j["records"][1]["comments"] = [{"round": "20261028T201340Z-dfa6", "lines": [3, 4], "text": "правка"}]
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
        [sys.executable, str(ROOT / "tools" / "journal.py"), "import-md",
         str(FIX / "journal-plan.md"), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    j = json.loads(out.read_text(encoding="utf-8"))
    assert len(j["records"]) == 24 and journal.validate_journal(j) == []
