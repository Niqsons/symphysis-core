"""Корни улик и поиск цитаты (`roots/roots.py`): файл корней, `default_roots`, выход за корень, ссылка наружу,
бинарные и не UTF-8 файлы, сверка без нормализации. Сверку зовут через `journal.check_evidence`."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import evidence_of, FIX, one_record_journal, ROOT
import journal


def test_check_does_not_join_lines_for_a_one_line_quote(tmp_path):
    """Сверка без нормализации (F-36): однострочная цитата через перенос строки не находится."""
    (tmp_path / "a.md").write_text("первая\nвторая строка\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="первая вторая")
    r = journal.check_evidence(j, {"": tmp_path})
    assert r["found"] == 0 and j["records"][0]["options"][0]["evidence"][0]["verdict"] == "цитаты нет дословно"


def test_check_quote_with_inner_guillemets(tmp_path):
    (tmp_path / "a.md").write_text("он сказал «да» и ушёл\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="сказал «да» и")
    assert journal.check_evidence(j, {"": tmp_path})["found"] == 1


def test_check_missing_file_is_signal_not_error(tmp_path):
    j = one_record_journal(path="nope.md", quote="x")
    r = journal.check_evidence(j, {"": tmp_path})
    assert r["missing"] and "файла нет" in r["missing"][0]


def test_check_multiline_quote_matches_consecutive_lines_ignoring_endings(tmp_path):
    (tmp_path / "a.md").write_bytes("раз\r\nдва\r\nтри\r\nчетыре\r\n".encode("utf-8"))
    j = one_record_journal(path="a.md", quote="аз\nдва\nтр")
    journal.check_evidence(j, {"": tmp_path})
    assert (evidence_of(j)["line"], evidence_of(j)["found"], evidence_of(j)["verdict"]) == (1, True, "сверено")


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


def test_default_roots_cover_symphysis_and_file():
    roots = journal.default_roots()
    assert roots["docs/"] == ROOT / "docs"
    # `upstream/` в worktree — соединение на основной клон (`.context/04-workflow.md`): сравнение по разрешённому пути
    assert roots["upstream/"] == (ROOT / "upstream").resolve()
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


def verdict_of(j) -> tuple:
    ev = evidence_of(j)
    return ev["found"], ev["line"], ev["verdict"]


def test_path_escaping_the_root_is_outside_and_file_is_not_read(tmp_path, monkeypatch):
    """Сценарий «Выход за корень»: файл вне корня существует и содержит цитату, но не читается."""
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("тайна\n", encoding="utf-8")
    opened = []
    real = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda self: opened.append(self) or real(self))
    for path in ("../secret.txt", "../../Windows/win.ini", "sub/../../secret.txt"):
        j = one_record_journal(path=path, quote="тайна")
        r = journal.check_evidence(j, {"": root})
        assert verdict_of(j) == (False, None, "вне корня") and r["found"] == 0
        assert "вне корня" in r["missing"][0]
    assert opened == []


def test_absolute_tail_after_prefix_is_outside(tmp_path):
    (tmp_path / "secret.txt").write_text("тайна\n", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    for path in (str(tmp_path / "secret.txt"), "/secret.txt"):
        j = one_record_journal(path=path, quote="тайна")
        journal.check_evidence(j, {"": root})
        assert verdict_of(j)[2] == "вне корня"


def test_path_inside_the_root_is_read(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "plan.md").write_text("пункт плана\n", encoding="utf-8")
    j = one_record_journal(path="docs/plan.md", quote="пункт")
    journal.check_evidence(j, {"": tmp_path})
    assert verdict_of(j) == (True, 1, "сверено")


def test_separators_and_drive_case_are_normalized(tmp_path):
    """Сценарий «Разделители и регистр диска»: обратные косые в пути, корень с другим регистром диска."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "plan.md").write_text("пункт плана\n", encoding="utf-8")
    root = str(tmp_path).replace("\\", "/")
    if len(root) > 1 and root[1] == ":":
        root = root[0].swapcase() + root[1:]
    j = one_record_journal(path="docs\\plan.md", quote="пункт")
    journal.check_evidence(j, {"": Path(root)})
    assert verdict_of(j) == (True, 1, "сверено")
    j = one_record_journal(path="docs\\plan.md", quote="пункт")
    journal.check_evidence(j, {"docs/": Path(root) / "docs"})
    assert verdict_of(j) == (True, 1, "сверено")


def test_link_pointing_outside_the_root_is_outside(tmp_path):
    """Сценарий «Ссылка наружу»: junction внутри корня ведёт вне корня."""
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "a.md").write_text("за корнем\n", encoding="utf-8")
    link = root / "link"
    if sys.platform == "win32":
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                              capture_output=True, text=True).returncode == 0
    else:
        try:
            link.symlink_to(outside, target_is_directory=True)
            made = True
        except OSError:
            made = False
    if not made:
        pytest.skip("не удалось создать junction/симлинк: нет прав")
    j = one_record_journal(path="link/a.md", quote="за корнем")
    journal.check_evidence(j, {"": root})
    assert verdict_of(j) == (False, None, "вне корня")


@pytest.mark.parametrize("name, binary", [
    ("evidence-nul-at-8191.bin", True),     # NUL последним байтом порога
    ("evidence-nul-at-8192.txt", False),    # NUL сразу за порогом — файл читается как текст
    ("evidence-utf16le-bom.txt", True),     # UTF-16 с BOM: нули в каждом втором байте
    ("evidence-pixel.png", True),
])
def test_binary_probe_boundary(name, binary):
    """Тест-страховка F-42: граница порога, UTF-16, PNG."""
    j = one_record_journal(path=name, quote="needle")
    r = journal.check_evidence(j, {"": FIX})
    if binary:
        assert verdict_of(j) == (None, None, "не проверить: бинарный файл")
        assert r["missing"] == [] and r["found"] == 0 and len(r["unchecked"]) == 1
    else:
        assert verdict_of(j)[2] != "не проверить: бинарный файл"


def test_non_utf8_file_is_not_checked_too(tmp_path):
    (tmp_path / "a.txt").write_bytes("привет".encode("cp1251"))
    j = one_record_journal(path="a.txt", quote="привет")
    journal.check_evidence(j, {"": tmp_path})
    assert verdict_of(j) == (None, None, "не проверить: не UTF-8")


def test_comparison_has_no_normalization(tmp_path):
    """Сценарий «Сверка без нормализации»: NBSP != пробел; CRLF против LF в сравнение не входит."""
    (tmp_path / "a.md").write_text("слово слово\n", encoding="utf-8")
    (tmp_path / "b.md").write_bytes("первая\r\nвторая\r\nтретья\r\n".encode("utf-8"))
    j = one_record_journal(path="a.md", quote="слово слово")
    j["records"][0]["options"][0]["evidence"].append({"path": "b.md", "quote": "первая\nвторая"})
    r = journal.check_evidence(j, {"": tmp_path})
    nbsp, crlf = j["records"][0]["options"][0]["evidence"]
    assert (nbsp["found"], nbsp["verdict"]) == (False, "цитаты нет дословно")
    assert (crlf["found"], crlf["line"], crlf["verdict"]) == (True, 1, "сверено")
    assert r["found"] == 1


def test_multiline_quote_needs_whole_middle_lines(tmp_path):
    (tmp_path / "a.md").write_text("а\nб в\nг\n", encoding="utf-8")
    for quote, found in (("а\nб в\nг", True), ("б в\nг", True), ("а\nб\nг", False), ("а\nг", False)):
        j = one_record_journal(path="a.md", quote=quote)
        journal.check_evidence(j, {"": tmp_path})
        assert evidence_of(j)["found"] is found, quote


def test_default_roots_for_a_journal_outside_openspec_changes_keeps_the_roots_file(tmp_path):
    """Проект из пути не вывести — прежнее поведение: файл корней."""
    roots = tmp_path / "r.json"
    roots.write_text(json.dumps({"": str(tmp_path / "a")}), encoding="utf-8")
    assert journal.default_roots(roots)[""] == tmp_path / "a"
