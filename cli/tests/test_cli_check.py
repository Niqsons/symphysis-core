"""`journal.py check` как команда: коды выхода, `--roots`, `--strict`, `--write`."""
import json
import subprocess
import sys

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import deviating, evidence_of, fork_record, journal_of, one_record_journal, ROOT, run_check
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


# --- `check` называет состав устаревшего вердикта (stale-verdict-scope, attack-stale-scope) --------

ATTACK_HEADER = ("| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |\n"
                 "| --- | --- | --- | --- | --- | --- | --- |\n")


def change_with_journal(tmp_path, names):
    """Каталог изменения: журнал с записями `names` (улика — `a.md` рядом, цитата `q` на месте), файл корней."""
    (tmp_path / "a.md").write_text("q\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    path = tmp_path / "decisions.json"
    journal.save_journal(path, journal_of(*[fork_record(n, A=["a.md"]) for n in names]))
    return path, roots


def write_journal_attack(tmp_path, sections, sha="auto", text=None):
    """`attack/decisions.md` формы журнала; `text` — готовое содержимое вместо сборки (битые файлы)."""
    if sha == "auto":
        sha = journal.sha256_file(tmp_path / "decisions.json")
    rows = "".join(f"| чисто | {s} | coverage | — | справка | есть | — |\n" for s in sections)
    body = text if text is not None else (
        f"---\nstatus: passed\ntarget: decisions.json\ntarget_sha256: {sha}\n---\n\n# Атака журнала решений\n\n{ATTACK_HEADER}{rows}")
    (tmp_path / "attack").mkdir(exist_ok=True)
    (tmp_path / "attack" / "decisions.md").write_text(body, encoding="utf-8")


def test_cli_check_names_records_added_after_verdict(tmp_path):
    """Сценарий «Записи добавлены после вердикта»: строка `[..] атака журнала: …`, код 0."""
    path, roots = change_with_journal(tmp_path, ["F-01", "F-02", "F-03"])
    write_journal_attack(tmp_path, ["F-01, решение", "F-02, решение", "F-03, решение"])
    change_with_journal(tmp_path, ["F-01", "F-02", "F-03", "F-04", "F-05"])
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[..] атака журнала: после вердикта добавлено 2 записи: F-04, F-05" in run.stdout
    assert "[!!]" not in run.stdout


def test_cli_check_is_silent_when_the_hash_matches(tmp_path):
    """Сценарий «Хеш совпал»: строк `[..] атака журнала` нет."""
    path, roots = change_with_journal(tmp_path, ["F-01"])
    write_journal_attack(tmp_path, ["F-01, решение"])
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0 and "[..] атака" not in run.stdout


def test_cli_check_scope_does_not_change_the_strict_code(tmp_path):
    """Сценарий «Состав не меняет код `--strict`»: строка есть, код 0."""
    path, roots = change_with_journal(tmp_path, ["F-01"])
    write_journal_attack(tmp_path, ["F-01, решение"])
    change_with_journal(tmp_path, ["F-01", "F-02"])
    run = run_check(path, "--roots", roots, "--strict")
    assert run.returncode == 0, run.stderr
    assert "[..] атака журнала: после вердикта добавлена 1 запись: F-02" in run.stdout


def test_cli_check_without_attack_dir_prints_nothing_about_attacks(tmp_path):
    """Сценарий «Файла атаки нет»: каталога `attack/` нет — остальные проверки прежние."""
    path, roots = change_with_journal(tmp_path, ["F-01"])
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0 and "атака" not in run.stdout
    assert "[ok] улик сверено 1 из 1" in run.stdout


@pytest.mark.parametrize("text, reason", [
    ("# Атака журнала решений\n\n" + ATTACK_HEADER, "нет frontmatter"),
    ("---\nstatus: passed\ntarget: decisions.json\ntarget_sha256: 0\n---\n\n# Атака\n", "нет таблицы атаки"),
], ids=["нет frontmatter", "нет таблицы"])
def test_cli_check_names_an_unparsable_attack_file_as_a_signal(tmp_path, text, reason):
    """Сценарий «Файл атаки не разбирается» (F-30): `[!!] attack/decisions.md: …`, код 0, с `--strict` 2."""
    path, roots = change_with_journal(tmp_path, ["F-01"])
    write_journal_attack(tmp_path, [], text=text)
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stderr
    line = next((l for l in run.stdout.splitlines() if l.startswith("[!!] attack/decisions.md: файл атаки не разбирается: ")), None)
    assert line is not None and reason in line, run.stdout
    assert str(tmp_path) not in line, "причина без пути файла"
    assert "[ok] улик сверено 1 из 1" in run.stdout, "остальные проверки идут"
    assert run_check(path, "--roots", roots, "--strict").returncode == 2


def test_cli_check_names_a_utf16_attack_file_as_not_utf8(tmp_path):
    """Канон ИБ (security.md): файл атаки не в UTF-8 — та же строка `[!!]` с причиной «не UTF-8»."""
    path, roots = change_with_journal(tmp_path, ["F-01"])
    (tmp_path / "attack").mkdir()
    (tmp_path / "attack" / "decisions.md").write_text("---\nstatus: passed\n---\n", encoding="utf-16")
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0
    assert "[!!] attack/decisions.md: файл атаки не разбирается: не UTF-8" in run.stdout


def test_cli_check_names_every_changed_artifact_target(tmp_path):
    """Атака артефактов: `[..] атака артефактов: …` по каждой изменившейся цели."""
    path, roots = change_with_journal(tmp_path, ["F-01"])
    for name in ("design.md", "tasks.md"):
        (tmp_path / name).write_text(f"# {name}\n", encoding="utf-8")
    targets = "".join(f"  - path: {n}\n    sha256: {journal.sha256_file(tmp_path / n)}\n" for n in ("decisions.json", "design.md", "tasks.md"))
    (tmp_path / "attack").mkdir()
    (tmp_path / "attack" / "artifacts.md").write_text(
        f"---\nstatus: passed\ntargets:\n{targets}---\n\n# Атака артефактов\n\n{ATTACK_HEADER}| чисто | design.md, 1 | scenario-run | — | справка | есть | — |\n",
        encoding="utf-8")
    (tmp_path / "design.md").write_text("# design 2\n", encoding="utf-8")
    (tmp_path / "tasks.md").write_text("# tasks 2\n", encoding="utf-8")
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[..] атака артефактов: design.md: изменён после вердикта" in run.stdout
    assert "[..] атака артефактов: tasks.md: изменён после вердикта" in run.stdout
