import json
import subprocess
import sys
from pathlib import Path

import journal
from conftest import ROOT, one_record_journal, requires_evidence_roots


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


@requires_evidence_roots
def test_check_plan_journal_all_found():
    j = journal.load_journal(ROOT / "docs/plan-implementation.journal.json")
    r = journal.check_evidence(j, journal.default_roots())
    assert r["found"] == r["total"] == 80   # 71 улика F-01…F-24 + 6 улик F-25 (D4b) + 3 улики F-26 (D7)


# --- что именно записывается в улику ---------------------------------------

def evidence_of(j):
    return j["records"][0]["options"][0]["evidence"][0]


def test_check_records_line_found_verdict(tmp_path):
    (tmp_path / "a.md").write_text("раз\nдва\nтри целиком\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="три целиком")
    journal.check_evidence(j, {"": tmp_path})
    assert evidence_of(j) == {"path": "a.md", "quote": "три целиком",
                              "line": 3, "found": True, "verdict": "сверено"}
    assert journal.validate_journal(j) == []


def test_check_linebreak_verdict_names_the_wrap(tmp_path):
    (tmp_path / "a.md").write_bytes("раз\r\nдва\r\nтри\r\n".encode("utf-8"))
    j = one_record_journal(path="a.md", quote="два три")
    journal.check_evidence(j, {"": tmp_path})
    assert (evidence_of(j)["line"], evidence_of(j)["verdict"]) == (2, "сверено через перенос")


def test_check_missing_is_found_false_not_null(tmp_path):
    """«Проверили — нет» (false) отличимо от «не проверяли» (нет поля / null)."""
    (tmp_path / "a.md").write_text("текст\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="чего-то нет")
    r = journal.check_evidence(j, {"": tmp_path})
    ev = evidence_of(j)
    assert (ev["line"], ev["found"], ev["verdict"]) == (None, False, "цитаты нет дословно")
    assert r == {"total": 1, "found": 0,
                 "missing": ["F-01: a.md «чего-то нет» — цитаты нет дословно"]}
    assert journal.validate_journal(j) == []


def test_schema_accepts_not_checked_evidence_as_null():
    j = one_record_journal(path="a.md", quote="x")
    evidence_of(j).update({"line": None, "found": None, "verdict": None})
    assert journal.validate_journal(j) == []


def test_check_covers_record_level_evidence(tmp_path):
    (tmp_path / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="раз")
    j["records"][0]["evidence"].append({"path": "a.md", "quote": "два"})
    r = journal.check_evidence(j, {"": tmp_path})
    assert r["total"] == 2 and r["found"] == 2
    assert j["records"][0]["evidence"][0]["line"] == 2


def test_check_picks_longest_prefix(tmp_path):
    (tmp_path / "wide").mkdir()
    (tmp_path / "narrow").mkdir()
    (tmp_path / "narrow" / "a.md").write_text("узкий корень\n", encoding="utf-8")
    j = one_record_journal(path="x/a.md", quote="узкий корень")
    roots = {"": tmp_path / "wide", "x/": tmp_path / "narrow"}
    assert journal.check_evidence(j, roots)["found"] == 1


def test_check_path_outside_roots_is_reported(tmp_path):
    j = one_record_journal(path="чужой/a.md", quote="x")
    r = journal.check_evidence(j, {"docs/": tmp_path})
    assert r["found"] == 0 and "корня для пути нет" in r["missing"][0]


# --- корни -----------------------------------------------------------------

def test_default_roots_cover_symphysis_and_file():
    roots = journal.default_roots()
    assert roots["docs/"] == ROOT / "docs"
    assert roots["upstream/"] == ROOT / "upstream"
    assert roots["CLAUDE.md"] == ROOT / "CLAUDE.md"
    assert {"store/", "playground/", "md4h/"} <= set(roots)
    assert "" not in roots


def test_roots_file_expands_home_and_overrides(tmp_path):
    f = tmp_path / "roots.json"
    f.write_text(json.dumps({"a/": "<home>/дом", "b/": "~/тильда", "c/": str(tmp_path)}),
                 encoding="utf-8")
    roots = journal.default_roots(f)
    assert roots["a/"] == Path.home() / "дом" and roots["b/"] == Path.home() / "тильда"
    assert roots["c/"] == tmp_path
    assert "docs/" not in roots and "store/" not in roots


def test_roots_file_expands_root_placeholder(tmp_path):
    f = tmp_path / "roots.json"
    f.write_text(json.dumps({"": "<root>/..", "a/": "<root>/docs"}), encoding="utf-8")
    roots = journal.default_roots(f)
    assert roots[""] == ROOT.parent
    assert roots["a/"] == ROOT / "docs"


def test_empty_prefix_is_default_root_only_when_configured(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.md").write_text("строка улики\n", encoding="utf-8")
    j = one_record_journal(path="src/a.md", quote="строка улики")
    assert journal.check_evidence(j, {"": tmp_path})["found"] == 1
    r = journal.check_evidence(j, {"docs/": tmp_path})
    assert r["found"] == 0 and "корня для пути нет" in r["missing"][0]


# --- командная строка ------------------------------------------------------

def run_check(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "journal.py"), "check", *map(str, args)],
        capture_output=True, text=True, encoding="utf-8")


def cli_fixture(tmp_path, quote):
    (tmp_path / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    path = tmp_path / "j.json"
    journal.save_journal(path, one_record_journal(path="a.md", quote=quote))
    return path, roots


def test_cli_check_ok_prints_count_and_exits_zero(tmp_path):
    path, roots = cli_fixture(tmp_path, "дв")
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[ok] улик сверено 1 из 1" in run.stdout and "[!!]" not in run.stdout


def test_cli_check_missing_is_signal_exit_zero(tmp_path):
    path, roots = cli_fixture(tmp_path, "нет такого")
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[ok] улик сверено 0 из 1" in run.stdout
    assert "[!!] F-01: a.md «нет такого» — цитаты нет дословно" in run.stdout


def test_cli_strict_exits_two_only_when_missing(tmp_path):
    path, roots = cli_fixture(tmp_path, "нет такого")
    assert run_check(path, "--roots", roots, "--strict").returncode == 2
    path, roots = cli_fixture(tmp_path, "дв")
    assert run_check(path, "--roots", roots, "--strict").returncode == 0


def test_cli_write_saves_line_found_verdict_only_with_flag(tmp_path):
    path, roots = cli_fixture(tmp_path, "дв")
    before = path.read_bytes()
    run_check(path, "--roots", roots)
    assert path.read_bytes() == before
    run = run_check(path, "--roots", roots, "--write")
    assert run.returncode == 0, run.stderr
    saved = journal.load_journal(path)
    ev = evidence_of(saved)
    assert (ev["line"], ev["found"], ev["verdict"]) == (2, True, "сверено")
    assert journal.validate_journal(saved) == []


def test_cli_check_rejects_invalid_journal(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"title": "т", "source": "s", "records": [{"id": "F-01"}]}),
                    encoding="utf-8")
    run = run_check(path)
    assert run.returncode == 1 and "[!!] F-01" in run.stderr
