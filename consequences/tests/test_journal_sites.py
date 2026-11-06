"""Подкоманда `journal.py code-sites`: места кода из улик выбранных вариантов решённых развилок (F-15.D)."""
import hashlib
import json
import subprocess
import sys

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import ROOT, fork_record, journal_of
import journal

TOOL = ROOT / "cli" / "journal.py"


def run_sites(tmp_path, data):
    """`code-sites` на журнале `data` с корнем `tmp_path`: (stdout, код, файл журнала)."""
    file = tmp_path / "decisions.json"
    journal.save_journal(file, data)
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    done = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "code-sites", str(file), "--roots", str(roots)],
                          capture_output=True, text=True, encoding="utf-8")
    return done.stdout, done.returncode, file


def site_line(stdout, path):
    return [line for line in stdout.splitlines() if line.strip().startswith(path)]


def test_only_the_chosen_option(tmp_path):
    """Сценарий «Только выбранный вариант»."""
    out, code, _ = run_sites(tmp_path, journal_of(fork_record("F-01", "A", A=["src/Foo.java"], B=["src/Bar.java"])))
    assert code == 0
    assert site_line(out, "src/Foo.java") == ["  src/Foo.java — F-01"]
    assert "src/Bar.java" not in out


def test_open_fork_fact_and_probe_do_not_count(tmp_path):
    """Сценарий «Открытая развилка, факт и проба не входят»; признаки пробы — оба (предположение д)."""
    fact = fork_record("F-02", None, A=[])
    fact.update(kind="факт", status="решён", options=[], evidence=[{"path": "src/Fact.java", "quote": "q"}])
    probe_by_outcome = fork_record("F-03", "A", A=["src/ProbeOutcome.java"])
    probe_by_outcome["outcome"] = {"kind": "проба", "value": "Specify", "reason": ""}
    probe_by_question = fork_record("F-04", "A", A=["src/ProbeQuestion.java"])
    probe_by_question["question"] = "[empty · text] Что при пустом вводе?"
    question_outcome = fork_record("F-05", "A", A=["src/Question.java"])
    question_outcome["outcome"] = {"kind": "вопрос", "value": "закрыт", "reason": ""}
    out, code, _ = run_sites(tmp_path, journal_of(fork_record("F-01", None, A=["src/Open.java"]), fact,
                                                  probe_by_outcome, probe_by_question, question_outcome))
    assert code == 0, out
    for path in ("src/Open.java", "src/Fact.java", "src/ProbeOutcome.java", "src/ProbeQuestion.java"):
        assert path not in out
    assert site_line(out, "src/Question.java") == ["  src/Question.java — F-05"], "`outcome.kind: вопрос` — не проба"


def test_journal_is_not_changed(tmp_path):
    """Сценарий «Журнал не меняется»."""
    data = journal_of(fork_record("F-01", "A", A=["src/Foo.java"]))
    file = tmp_path / "decisions.json"
    journal.save_journal(file, data)
    before = hashlib.sha256(file.read_bytes()).hexdigest()
    out, code, file = run_sites(tmp_path, data)
    assert code == 0 and "src/Foo.java" in out
    assert hashlib.sha256(file.read_bytes()).hexdigest() == before


def test_one_file_in_different_spellings(tmp_path):
    """Сценарий «Один файл в разном написании»: косая, обратная косая, абсолютный путь с другим регистром диска."""
    absolute = str(tmp_path / "src" / "Foo.java")
    other_drive_case = absolute[0].swapcase() + absolute[1:]
    out, code, _ = run_sites(tmp_path, journal_of(fork_record("F-01", "A", A=["src\\Foo.java"]),
                                                  fork_record("F-02", "A", A=["src/Foo.java"]),
                                                  fork_record("F-03", "A", A=[other_drive_case]),
                                                  fork_record("F-04", "A", A=[absolute]),
                                                  fork_record("F-05", "A", A=["./src/Foo.java"])))
    assert code == 0
    assert site_line(out, "src/Foo.java") == ["  src/Foo.java — F-01, F-02, F-03, F-04, F-05"]
    assert out.count("Foo.java") == 1


def test_chosen_option_without_evidence(tmp_path):
    """Сценарий «Выбранный вариант без улик»: вариант человека часто без улик (F-15.D)."""
    out, code, _ = run_sites(tmp_path, journal_of(fork_record("F-07", "D", A=["src/Foo.java"], D=[])))
    assert code == 0
    assert "[..] F-07: выбранный вариант без улик" in out.splitlines()
    assert "src/Foo.java" not in out


def test_what_counts_as_a_code_file(tmp_path):
    """Сценарий «Что считается файлом кода», граница F-73.A; `upstream/…` входит (предположение г)."""
    out, code, _ = run_sites(tmp_path, journal_of(fork_record(
        "F-01", "A", A=["src/Foo.java", "docs/plan.md", "README.MD", "openspec/schemas/x/schema.yaml",
                        "openspec/changes/y/decisions.json", "runs/c3/project/openspec/changes/y/decisions.json",
                        "upstream/lib/a.ts"])))
    assert code == 0
    listed = [line.split(" — ")[0].strip() for line in out.splitlines() if line.startswith("  ")]
    assert listed == ["openspec/schemas/x/schema.yaml", "src/Foo.java", "upstream/lib/a.ts"]


def test_evidence_outside_the_root(tmp_path):
    """Сценарий «Улика вне корня»: пути в списке нет, файл не читается, вывод называет запись."""
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("секрет\n", encoding="utf-8")
    roots = {"": root}
    data = journal_of(fork_record("F-01", "A", A=["../secret.txt", str(outside), "src/Foo.java"]))
    result = journal.code_sites(data, roots)
    assert result == {"sites": {"src/Foo.java": ["F-01"]}, "notes": ["F-01: путь вне корня"]}


def test_path_outside_declared_roots_is_outside(tmp_path):
    """F-105: путь, не подошедший ни под один корень, в список не идёт — как и `..`."""
    data = journal_of(fork_record("F-01", "A", A=["src/Foo.java", "../../secret.txt"]))
    result = journal.code_sites(data, {"docs/": tmp_path})
    assert result == {"sites": {}, "notes": ["F-01: путь вне объявленных корней"]}


def test_absolute_path_under_named_root_keeps_its_prefix(tmp_path):
    """Абсолютный путь внутри именованного корня приводится к пути с префиксом этого корня."""
    (tmp_path / "wide").mkdir()
    narrow = tmp_path / "narrow"
    narrow.mkdir()
    data = journal_of(fork_record("F-01", "A", A=[str(narrow / "a.java")]))
    result = journal.code_sites(data, {"": tmp_path / "wide", "x/": narrow})
    assert result == {"sites": {"x/a.java": ["F-01"]}, "notes": []}


def test_invalid_journal_is_code_one(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"title": "т"}), encoding="utf-8")
    done = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "code-sites", str(bad)],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 1 and "[!!]" in done.stderr
