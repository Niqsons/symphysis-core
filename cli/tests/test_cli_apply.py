"""`journal.py apply` и `apply-md4h` как команды: коды выхода, `--dry-run`, дата, кодировка, отказы."""
import hashlib
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


def test_cli_apply_puts_the_read_flag_text_into_one_note(workdir):
    """attack-warning-read, «Отметка попадает в промпт» → заметка: строка «Замечания к схеме:» с текстом флага
    и спором ложится одной заметкой `notes[]` с датой и текстом как есть — по ней страница ставит флаг."""
    tmp, path = workdir
    text = "предупреждение прочитано: F-12, options.B · атака attack/decisions.md · claim-authority · «…» — спор: опора есть"
    answers = tmp / "a.md"
    answers.write_text(HEADER_LINK + "Замечания к схеме: " + text + "\n", encoding="utf-8")
    run = run_cli("apply", path, answers, "--date", "2026-11-07")
    assert run.returncode == 0, run.stderr + run.stdout
    notes = journal.load_journal(path).get("notes") or []
    assert notes[-1] == {"date": "2026-11-07", "text": text}
    assert sum(1 for n in notes if "предупреждение прочитано:" in n["text"]) == 1


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


# --- строки о тяжести (`attack-severity-word`, F-17, F-27, F-32.B, F-42, F-45.B) ---

SEV_HEAD = ("---\nstatus: gaps_found\ntarget: decisions.json\ntarget_sha256: abc123\n---\n\n"
            "| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n")
ROW_BLOCK = "| а | F-01 | scenario-run | инв | блокер (старая причина) | нет | чинить |"
ROW_WARN = "| б | F-02 | honest-verifier | инв | предупреждение | нет | чинить |"
DECISIONS = "openspec/changes/ch/attack/decisions.md"
ARTIFACTS = "openspec/changes/ch/attack/artifacts.md"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sev_line(path, claim, severity, why, section="F-01"):
    return f"- тяжесть: {path} · {section} · «{claim}» → {severity} — «{why}»\n"


@pytest.fixture
def project(tmp_path):
    change = tmp_path / "openspec" / "changes" / "ch"
    (change / "attack").mkdir(parents=True)
    j = plan()
    path = change / "decisions.json"
    journal.save_journal(path, j)
    for name in ("decisions", "artifacts"):
        (change / "attack" / f"{name}.md").write_bytes((SEV_HEAD + ROW_BLOCK + "\n" + ROW_WARN + "\n").encode("utf-8"))
    return tmp_path, change, path


def apply_sev(project, prompt, *flags):
    tmp, change, path = project
    answers = tmp / "a.md"
    answers.write_text(HEADER_LINK + prompt, encoding="utf-8")
    return run_cli("apply", path, answers, *flags, "--date", "2026-11-08")


def snapshot(project):
    _, change, path = project
    return {p: sha(p) for p in (path, change / "attack" / "decisions.md", change / "attack" / "artifacts.md")}


def test_apply_lowers_the_last_blocker_and_leaves_the_journal_alone(project):
    """«Понижен последний блокер» — status passed, SHA-256 decisions.json прежний."""
    _, change, path = project
    before = snapshot(project)
    run = apply_sev(project, sev_line(DECISIONS, "а", "предупреждение", "решено человеком"))
    assert run.returncode == 0, run.stderr + run.stdout
    text = (change / "attack" / "decisions.md").read_text(encoding="utf-8")
    assert "status: passed" in text and "предупреждение (решено человеком) |" in text
    assert sha(path) == before[path]
    assert sha(change / "attack" / "artifacts.md") == before[change / "attack" / "artifacts.md"]
    assert "→ предупреждение" in run.stdout and "«а»" in run.stdout


@pytest.mark.parametrize("bad", ["../other/attack/decisions.md", "C:/x/attack/decisions.md",
                                 "openspec/changes/other/attack/decisions.md",
                                 "openspec/changes/ch/../ch/attack/decisions.md"])
def test_apply_refuses_a_path_outside_the_change(project, bad):
    """«Путь вне каталога изменения» — код 1, ни один файл не изменён."""
    before = snapshot(project)
    run = apply_sev(project, sev_line(bad, "а", "предупреждение", "слово"))
    assert run.returncode == 1 and bad in run.stderr and "[!!]" in run.stderr
    assert DECISIONS in run.stderr and "openspec/changes/ch/attack/artifacts.md" in run.stderr   # названа принимаемая форма
    assert snapshot(project) == before


@pytest.mark.parametrize("why", ["   ", None])
def test_apply_refuses_an_empty_justification(project, why):
    """«Пустое обоснование» — из пробелов и из `(без слова)`."""
    before = snapshot(project)
    line = (sev_line(DECISIONS, "а", "предупреждение", why) if why
            else f"- тяжесть: {DECISIONS} · F-01 · «а» → предупреждение — (без слова)\n")
    run = apply_sev(project, line)
    assert run.returncode == 1 and "нет обоснования" in run.stderr
    assert snapshot(project) == before


def test_apply_refuses_two_lines_for_one_attack_row(project):
    before = snapshot(project)
    run = apply_sev(project, sev_line(DECISIONS, "а", "предупреждение", "раз") + sev_line(DECISIONS, "а", "блокер", "два"))
    assert run.returncode == 1 and "две строки о тяжести для одной строки атаки" in run.stderr
    assert snapshot(project) == before


def test_apply_good_journal_line_and_bad_severity_line_write_nothing(project):
    """«Годное решение и негодная строка о тяжести» — F-03 открыт, строка о нём годна сама по себе; пустое обоснование
    строки о тяжести — код 1, ничего не записано, решение F-03 пусто."""
    _, _, path = project
    j = journal.load_journal(path)
    rec = rec_of(j, "F-03")
    rec["decision"], rec["status"] = None, "открыт"
    journal.save_journal(path, j)
    before = snapshot(project)
    run = apply_sev(project, "- F-03: A — «слово»\n" + sev_line(DECISIONS, "а", "предупреждение", "   "))
    assert run.returncode == 1 and "нет обоснования" in run.stderr
    assert "F-03" not in run.stderr
    assert snapshot(project) == before
    assert rec_of(journal.load_journal(path), "F-03")["decision"] is None


def test_apply_good_line_with_unparsable_attack_file_is_refused(project):
    _, change, _ = project
    (change / "attack" / "artifacts.md").write_text("не файл атаки\n", encoding="utf-8")
    before = snapshot(project)
    run = apply_sev(project, sev_line(ARTIFACTS, "а", "предупреждение", "слово"))
    assert run.returncode == 1 and "artifacts.md" in run.stderr
    assert snapshot(project) == before
    (change / "attack" / "artifacts.md").unlink()
    run = apply_sev(project, sev_line(ARTIFACTS, "а", "предупреждение", "слово"))
    assert run.returncode == 1 and "файла нет" in run.stderr


def test_apply_good_line_for_one_file_and_bad_for_the_other_changes_neither(project):
    before = snapshot(project)
    run = apply_sev(project, sev_line(DECISIONS, "а", "предупреждение", "слово")
                    + sev_line(ARTIFACTS, "нет такой", "предупреждение", "слово"))
    assert run.returncode == 1
    assert snapshot(project) == before


def test_apply_writes_both_attack_files_and_the_journal_first(project):
    """«Строки о двух файлах атаки» — оба файла правятся, журнал со своей строкой пишется."""
    _, change, path = project
    run = apply_sev(project, "- F-03: A (было C) — «слово»\n" + sev_line(DECISIONS, "а", "предупреждение", "раз")
                    + sev_line(ARTIFACTS, "б", "блокер", "два", section="F-02"))
    assert run.returncode == 0, run.stderr + run.stdout
    assert rec_of(journal.load_journal(path), "F-03")["decision"]["option"] == "A"  # было C
    assert "status: passed" in (change / "attack" / "decisions.md").read_text(encoding="utf-8")
    assert "блокер (два) |" in (change / "attack" / "artifacts.md").read_text(encoding="utf-8")


def test_apply_dry_run_touches_no_file_and_names_the_line(project):
    """«Пробное внесение не трогает файл атаки»."""
    before = snapshot(project)
    run = apply_sev(project, "- F-03: A (было C) — «слово»\n" + sev_line(DECISIONS, "а", "предупреждение", "раз"), "--dry-run")
    assert run.returncode == 0 and "→ предупреждение" in run.stdout and "decisions.md" in run.stdout
    assert "не записан" in run.stdout
    assert snapshot(project) == before


def test_apply_keeps_crlf_and_bom_of_the_attack_file(project):
    _, change, _ = project
    file = change / "attack" / "decisions.md"
    file.write_bytes(b"\xef\xbb\xbf" + file.read_bytes().replace(b"\n", b"\r\n"))
    run = apply_sev(project, sev_line(DECISIONS, "а", "предупреждение", "слово"))
    assert run.returncode == 0, run.stderr
    raw = file.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and raw.count(b"\r\n") == raw.count(b"\n")
    assert b"status: passed" in raw


def test_apply_two_severity_lines_for_two_rows_of_one_file(project):
    """Две строки о тяжести для разных строк одного файла — применяются за один запуск по цепочке в памяти."""
    _, change, path = project
    before = snapshot(project)
    run = apply_sev(project, sev_line(DECISIONS, "а", "предупреждение", "раз") + sev_line(DECISIONS, "б", "блокер", "два", "F-02"))
    assert run.returncode == 0, run.stderr + run.stdout
    text = (change / "attack" / "decisions.md").read_text(encoding="utf-8")
    assert "предупреждение (раз) |" in text and "блокер (два) |" in text
    assert "status: passed" not in text and "status: gaps_found" in text
    assert sha(path) == before[path]
