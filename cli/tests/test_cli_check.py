"""`journal.py check` как команда: коды выхода, `--roots`, `--strict`, `--write`."""
import json
import subprocess
import sys

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import deviating, evidence_of, one_record_journal, ROOT, run_check
import journal


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


def test_cli_check_rejects_a_bad_deviation_with_code_1(tmp_path):
    path = tmp_path / "j.json"
    journal.save_journal(path, deviating("F-09"))
    run = subprocess.run([sys.executable, str(ROOT / "cli" / "journal.py"), "check", str(path)],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 1
    assert "[!!] F-02: вариант B — отступление от постановки F-09 — такой записи нет" in run.stderr
