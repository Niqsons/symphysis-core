"""`journal.py apply` и `apply-md4h` как команды: коды выхода, `--dry-run`, дата, кодировка, отказы."""
import itertools
import json
import re

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import comments_of, fixture_text, HEADER_LINK, line_of, plan, rec_of, rendered, run_cli
import journal


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


def write_feedback(tmp_path, md, *spans, state="sealed", name="feedback.md"):
    """Файл связки на диске: фикстура с SHA рендера `md` и строками `spans` у первых комментариев."""
    text = fixture_text().replace("\r\n", "\n")
    text = re.sub(r"(?m)^source_sha256: .*$", f"source_sha256: {journal.sha256_file(md)}", text)
    text = re.sub(r"(?m)^state: .*$", f"state: {state}", text)
    count = itertools.count()      # комментариев больше, чем spans, — берётся последний span
    text = re.sub(r"(?m)^\*\*Source lines:\*\* .*$",
                  lambda m: "**Source lines:** %d-%d" % spans[min(next(count), len(spans) - 1)], text)
    out = tmp_path / name
    out.write_text(text, encoding="utf-8", newline="\r\n")
    return out


def cli_setup(tmp_path):
    """Журнал на диске, его рендер и строка первой записи F-03 в рендере."""
    j = plan()
    src = tmp_path / "j.json"
    journal.save_journal(src, j)
    md = rendered(tmp_path, j)
    return j, src, md, line_of(md, "<!-- journal:F-03 -->")


def test_cli_apply_md4h_writes_comments_and_reports(tmp_path):
    j, src, md, f3 = cli_setup(tmp_path)
    fb = write_feedback(tmp_path, md, (f3 + 1, f3 + 2), (f3 + 3, f3 + 3), (f3 + 4, f3 + 5))
    run = run_cli("apply-md4h", src, fb, "--render", md)
    assert run.returncode == 0, run.stderr
    assert "[ok] комментариев внесено 3" in run.stdout and "F-03" in run.stdout
    saved = journal.load_journal(src)
    assert [c["lines"] for c in comments_of(saved, "F-03")] == [[f3 + 1, f3 + 2], [f3 + 3, f3 + 3], [f3 + 4, f3 + 5]]
    assert journal.validate_journal(saved) == []
    assert "не рендерит" in run.stdout


def test_cli_apply_md4h_twice_leaves_the_file_as_it_was(tmp_path):
    j, src, md, f3 = cli_setup(tmp_path)
    fb = write_feedback(tmp_path, md, (f3 + 1, f3 + 2), (f3 + 3, f3 + 3), (f3 + 4, f3 + 5))
    assert run_cli("apply-md4h", src, fb, "--render", md).returncode == 0
    src.write_text(json.dumps(journal.load_journal(src), ensure_ascii=False, indent=4), encoding="utf-8")
    after_first = src.read_bytes()      # другая вёрстка: переписанный файл отличался бы от этого
    run = run_cli("apply-md4h", src, fb, "--render", md)
    assert run.returncode == 0, run.stderr
    assert "[ok] комментариев внесено 0" in run.stdout and "уже внесён" in run.stdout
    assert src.read_bytes() == after_first


def test_cli_apply_md4h_refuses_a_foreign_sha_with_code_2(tmp_path):
    j, src, md, f3 = cli_setup(tmp_path)
    fb = write_feedback(tmp_path, md, (f3 + 1, f3 + 1))
    md.write_text(journal.render_md(j) + "\nправка\n", encoding="utf-8", newline="\r\n")
    before = src.read_bytes()
    run = run_cli("apply-md4h", src, fb, "--render", md)
    assert run.returncode == 2
    assert "[!!]" in run.stderr and "sha256" in run.stderr
    assert "комментариев внесено" not in run.stdout
    assert src.read_bytes() == before


def test_cli_apply_md4h_refuses_an_unsealed_bundle_with_code_2(tmp_path):
    j, src, md, f3 = cli_setup(tmp_path)
    fb = write_feedback(tmp_path, md, (f3 + 1, f3 + 1), state="draft")
    before = src.read_bytes()
    run = run_cli("apply-md4h", src, fb, "--render", md)
    assert run.returncode == 2 and "связка не запечатана" in run.stderr
    assert src.read_bytes() == before


def test_cli_apply_md4h_refuses_a_comment_above_the_first_record_with_code_2(tmp_path):
    j, src, md, f3 = cli_setup(tmp_path)
    fb = write_feedback(tmp_path, md, (1, 1))
    before = src.read_bytes()
    run = run_cli("apply-md4h", src, fb, "--render", md)
    assert run.returncode == 2 and "комментарий F1 выше первой записи" in run.stderr
    assert src.read_bytes() == before


def test_cli_apply_md4h_refuses_an_invalid_journal_with_code_1(tmp_path):
    j, src, md, f3 = cli_setup(tmp_path)
    fb = write_feedback(tmp_path, md, (f3 + 1, f3 + 1))
    j["records"][0]["status"] = "готов"
    journal.save_journal(src, j)
    before = src.read_bytes()
    run = run_cli("apply-md4h", src, fb, "--render", md)
    assert run.returncode == 1 and "F-01" in run.stderr
    assert src.read_bytes() == before


def test_cli_apply_md4h_reports_a_broken_bundle_with_code_1(tmp_path):
    j, src, md, f3 = cli_setup(tmp_path)
    fb = write_feedback(tmp_path, md, (f3 + 1, f3 + 1))
    fb.write_text(fb.read_text(encoding="utf-8").replace("md4h-feedback/v2", "md4h-feedback/v9"),
                  encoding="utf-8", newline="\r\n")
    before = src.read_bytes()
    run = run_cli("apply-md4h", src, fb, "--render", md)
    assert run.returncode == 1 and "md4h-feedback/v9" in run.stderr
    assert src.read_bytes() == before


def test_cli_apply_md4h_reports_missing_files_with_code_1(tmp_path):
    j, src, md, f3 = cli_setup(tmp_path)
    fb = write_feedback(tmp_path, md, (f3 + 1, f3 + 1))
    run = run_cli("apply-md4h", src, tmp_path / "нет.md", "--render", md)
    assert run.returncode == 1 and "нет.md" in run.stderr and "файла нет" in run.stderr
    run = run_cli("apply-md4h", src, fb, "--render", tmp_path / "нет-рендера.md")
    assert run.returncode == 1 and "нет-рендера.md" in run.stderr and "файла нет" in run.stderr


def test_cli_apply_md4h_requires_the_render_argument(tmp_path):
    j, src, md, f3 = cli_setup(tmp_path)
    fb = write_feedback(tmp_path, md, (f3 + 1, f3 + 1))
    run = run_cli("apply-md4h", src, fb)
    assert run.returncode == 2 and "--render" in run.stderr
