"""`journal.py import-md`, `render-md` и `render-design` как команды: что пишут, коды выхода, отказ на негодном журнале."""
import json
import subprocess
import sys

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import FIX, LIVE_JSON, one_record_journal, plan, ROOT, strip_check_fields
import journal


def test_cli_import_md_writes_valid_json(tmp_path):
    out = tmp_path / "plan.json"
    run = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "journal.py"), "import-md",
         str(FIX / "journal-plan.md"), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    j = json.loads(out.read_text(encoding="utf-8"))
    assert len(j["records"]) == 24 and journal.validate_journal(j) == []


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "cli" / "journal.py"), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8")


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


def test_cli_render_design_refuses_an_invalid_journal(tmp_path):
    j = one_record_journal("a.md", "q")
    j["records"][0]["status"] = "готов"
    src, out = tmp_path / "j.json", tmp_path / "design.md"
    journal.save_journal(src, j)
    run = run_cli("render-design", src, "--out", out)
    assert run.returncode == 1 and "F-01" in run.stderr
    assert not out.exists()


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


@pytest.mark.parametrize("command", ["render-md", "render-html"])
def test_cli_render_refuses_an_invalid_journal(tmp_path, command):
    j = plan()
    j["records"][2]["status"] = "готов"
    src, out = tmp_path / "j.json", tmp_path / "out"
    journal.save_journal(src, j)
    run = run_cli(command, src, "--out", out)
    assert run.returncode == 1 and "F-03" in run.stderr
    assert not out.exists()
