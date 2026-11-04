import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import journal
from conftest import ROOT, one_record_journal, requires_evidence_roots


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


@requires_evidence_roots
def test_check_plan_journal_all_found():
    j = journal.load_journal(ROOT / "docs/plan-implementation.journal.json")
    r = journal.check_evidence(j, journal.default_roots())
    # 71 улика F-01…F-24 + 6 улик F-25 (D4b) + 3 улики F-26 (D7) + 9 улик F-27; без нормализации (F-36)
    # не находится одна — цитата F-07 из docs/plan-flexible-pipeline.md переходит через перенос строки
    assert r["total"] == 89 and r["found"] == 88
    assert len(r["missing"]) == 1 and r["missing"][0].startswith("F-07: docs/plan-flexible-pipeline.md")


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


def test_check_multiline_quote_matches_consecutive_lines_ignoring_endings(tmp_path):
    (tmp_path / "a.md").write_bytes("раз\r\nдва\r\nтри\r\nчетыре\r\n".encode("utf-8"))
    j = one_record_journal(path="a.md", quote="аз\nдва\nтр")
    journal.check_evidence(j, {"": tmp_path})
    assert (evidence_of(j)["line"], evidence_of(j)["found"], evidence_of(j)["verdict"]) == (1, True, "сверено")


def test_check_missing_is_found_false_not_null(tmp_path):
    """«Проверили — нет» (false) отличимо от «не проверяли» (нет поля / null)."""
    (tmp_path / "a.md").write_text("текст\n", encoding="utf-8")
    j = one_record_journal(path="a.md", quote="чего-то нет")
    r = journal.check_evidence(j, {"": tmp_path})
    ev = evidence_of(j)
    assert (ev["line"], ev["found"], ev["verdict"]) == (None, False, "цитаты нет дословно")
    assert r == {"total": 1, "found": 0, "unchecked": [],
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


# --- правила журнала для check (5.2) ----------------------------------------

def fact_journal(**changes) -> dict:
    j = one_record_journal(path="a.md", quote="x")
    rec = j["records"][0]
    rec.update(kind="факт", options=[], status="решён", **changes)
    return j


def test_fact_without_evidence_is_an_error(tmp_path):
    """Сценарий «Факт без улики»: код 1, строка с префиксом [!!]."""
    path = tmp_path / "j.json"
    journal.save_journal(path, fact_journal())
    assert "F-01: факт без улики" in journal.validate_journal(journal.load_journal(path))
    run = run_check(path)
    assert run.returncode == 1 and "[!!] F-01: факт без улики" in run.stderr


def test_parked_fact_without_evidence_is_fine(tmp_path):
    """Сценарий «Припаркованный факт без улики»: ни парковка, ни статус «припаркован» не дают ошибки."""
    parked = fact_journal(parking=[{"addressee": "материалы", "text": "найти"}])
    parked["records"][0]["status"] = "припаркован"
    assert journal.validate_journal(parked) == []
    assert journal.validate_journal(fact_journal(parking=[{"addressee": "материалы", "text": "найти"}])) == []
    only_status = fact_journal()
    only_status["records"][0]["status"] = "припаркован"
    assert journal.validate_journal(only_status) == []
    path = tmp_path / "j.json"
    journal.save_journal(path, parked)
    run = run_check(path)
    assert run.returncode == 0 and "факт без улики" not in run.stdout + run.stderr


def test_fact_with_record_evidence_is_fine():
    assert journal.validate_journal(fact_journal(evidence=[{"path": "a.md", "quote": "x"}])) == []


def test_empty_why_is_an_error(tmp_path):
    """Сценарий «Пустое why»: код 1; why из пробелов считается пустым."""
    for why in ("", "  "):
        j = one_record_journal(path="a.md", quote="x")
        j["records"][0]["recommendation"] = {"option": "A", "why": why}
        path = tmp_path / "j.json"
        journal.save_journal(path, j)
        run = run_check(path)
        assert run.returncode == 1 and "[!!] F-01: рекомендация без why" in run.stderr
    j["records"][0]["recommendation"]["why"] = "потому что"
    assert journal.validate_journal(j) == []


def parking_fixture(tmp_path, with_research=True, finding=None):
    j = one_record_journal(path="a.md", quote="раз")
    parking = {"addressee": "материалы", "text": "найти"}
    if finding is not None:
        parking["finding"] = finding
    j["records"][0]["parking"] = [parking]
    (tmp_path / "a.md").write_text("раз\n", encoding="utf-8")
    if with_research:
        (tmp_path / "research").mkdir()
        (tmp_path / "research" / "F-01.md").write_text("находка\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    return path, roots


def test_parking_without_finding_at_research_file_is_a_signal(tmp_path):
    """Сценарий «Парковка без находки при файле»: код 0, с --strict — 2."""
    path, roots = parking_fixture(tmp_path)
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[!!] F-01: парковка «материалы» без finding при research/F-01.md" in run.stdout
    assert run_check(path, "--roots", roots, "--strict").returncode == 2


def test_parking_signal_needs_the_research_file_and_no_finding(tmp_path):
    for sub, kw in (("a", {"with_research": False}), ("b", {"finding": "нашли"})):
        (tmp_path / sub).mkdir()
        path, roots = parking_fixture(tmp_path / sub, **kw)
        run = run_check(path, "--roots", roots, "--strict")
        assert run.returncode == 0 and "без finding" not in run.stdout


# --- корень улики (5.3) ------------------------------------------------------

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


# --- бинарные файлы (5.4) -----------------------------------------------------

FIX = ROOT / "tests" / "fixtures"


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


def test_binary_evidence_does_not_stop_the_others(tmp_path):
    """Сценарий «Улика указывает на PNG»: check --write, остальные улики сверены, код 0, даже с --strict."""
    (tmp_path / "a.md").write_text("раз\n", encoding="utf-8")
    shutil.copy(FIX / "evidence-pixel.png", tmp_path / "p.png")
    j = one_record_journal(path="p.png", quote="любая")
    j["records"][0]["options"][0]["evidence"].append({"path": "a.md", "quote": "раз"})
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    run = run_check(path, "--roots", roots, "--write", "--strict")
    assert run.returncode == 0, run.stderr
    assert "[ok] улик сверено 1 из 2, не проверить 1" in run.stdout
    evs = journal.load_journal(path)["records"][0]["options"][0]["evidence"]
    assert (evs[0]["found"], evs[0]["verdict"]) == (None, "не проверить: бинарный файл")
    assert evs[1]["found"] is True
    assert journal.validate_journal(journal.load_journal(path)) == []


def test_non_utf8_file_is_not_checked_too(tmp_path):
    (tmp_path / "a.txt").write_bytes("привет".encode("cp1251"))
    j = one_record_journal(path="a.txt", quote="привет")
    journal.check_evidence(j, {"": tmp_path})
    assert verdict_of(j) == (None, None, "не проверить: не UTF-8")


# --- сверка без нормализации (5.5) --------------------------------------------

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


# --- отступление от постановки без замка (7.4: F-55.E, F-08.A) --------------------

DEVIATION_FIX = FIX / "journal-deviation.json"
INTENT_DEMO = FIX / "intent-demo"


def intent_demo_roots(tmp_path) -> Path:
    """Корень улик fixture: путь `openspec/changes/intent-demo/…` — как в журнале изменения, от корня проекта."""
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"openspec/changes/intent-demo/": str(INTENT_DEMO)}), encoding="utf-8")
    return roots


def test_deviation_with_a_human_decision_against_the_setting_passes_check(tmp_path):
    """Сценарий «Отступление проходит check»: факт постановки, развилка, чей выбранный вариант несёт `deviation`
    на него, решение человека против факта со словом — `check` код 0 и с `--strict`, ни одной строки `[!!]`:
    пометка — видимость, не замок."""
    j = journal.load_journal(DEVIATION_FIX)
    fork = next(r for r in j["records"] if any(o.get("deviation") for o in r["options"]))
    chosen = next(o for o in fork["options"] if o["letter"] == fork["decision"]["option"])
    fact = next(r for r in j["records"] if r["id"] == chosen["deviation"])
    assert (fact["kind"], fact["addressee"]) == ("факт", "постановка")
    assert fork["kind"] == "развилка" and fork["status"] == "решён" and fork["decision"]["word"]
    assert chosen["text"].startswith("Наследование"), "решение против сценария факта постановки"
    assert fork["recommendation"]["option"] != chosen["letter"] and "deviation" not in fork
    run = run_check(DEVIATION_FIX, "--roots", intent_demo_roots(tmp_path), "--strict")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "[!!]" not in run.stdout + run.stderr and "[ok] улик сверено 3 из 3" in run.stdout


def test_deviation_stays_visible_in_the_renders():
    """Видимость: пометка у строки выбранного варианта в markdown и строка у решения в design."""
    j = journal.load_journal(DEVIATION_FIX)
    md = journal.render_md(j).split("\n## F-03")[1]
    assert "(отступление от F-01)" in next(line for line in md.splitlines() if line.startswith("  - B. "))
    assert "- **Отступление от постановки:** F-01" in journal.render_design(j)


# --- nodes: check смотрит только форму, со схемой не сверяет (F-24, F-114) -----

def check_output(tmp_path, record_nodes=None, scheme=None):
    """Вывод `check` журнала рядом со `scheme.md`: код и всё, что напечатано."""
    (tmp_path / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    j = one_record_journal("a.md", "дв")
    if record_nodes is not None:
        j["records"][0]["nodes"] = record_nodes
    src = tmp_path / "decisions.json"
    journal.save_journal(src, j)
    if scheme is not None:
        (tmp_path / "scheme.md").write_text(scheme, encoding="utf-8")
    run = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "journal.py"), "check", str(src), "--roots", str(roots)],
                         capture_output=True, text=True, encoding="utf-8")
    return run.returncode, run.stdout + run.stderr


SCHEME_WITHOUT_X = "```mermaid\nflowchart TD\n  A --> B\n```\n"


def test_check_does_not_compare_nodes_with_the_scheme(tmp_path):
    code, out = check_output(tmp_path, ["X"], SCHEME_WITHOUT_X)
    assert code == 0, out
    assert "nodes" not in out and "узел" not in out


def test_check_says_nothing_about_a_journal_without_nodes(tmp_path):
    code, out = check_output(tmp_path, None, SCHEME_WITHOUT_X)
    assert code == 0, out
    assert "nodes" not in out and "узел" not in out


# --- слово у выбора мимо рекомендации ---------------------------------------------

def word_fixture(tmp_path, choice, word="", added=False):
    j = one_record_journal(path="a.md", quote="раз")
    record = j["records"][0]
    other = dict(record["options"][0], letter="B", text="второй", added=added)
    record["options"].append(other)
    record["status"] = "решён"
    record["recommendation"] = {"option": "A", "why": "причина из рекомендации"}
    record["decision"] = {"option": choice, "word": word, "date": "2026-11-02"}
    record["reversibility"] = {"level": "обратимо", "why": "одна строка"}
    (tmp_path / "a.md").write_text("раз\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path)}), encoding="utf-8")
    path = tmp_path / "j.json"
    journal.save_journal(path, j)
    return path, roots


def test_choice_past_the_recommendation_without_a_word_is_a_signal(tmp_path):
    """Сценарий «Выбор мимо рекомендации без слова»: код 0, с --strict — 2."""
    path, roots = word_fixture(tmp_path, "B")
    run = run_check(path, "--roots", roots)
    assert run.returncode == 0, run.stderr
    assert "[!!] F-01: выбран не рекомендованный вариант B без слова" in run.stdout
    assert run_check(path, "--roots", roots, "--strict").returncode == 2


@pytest.mark.parametrize("choice, word, added", [("A", "", False), ("B", "потому что", False), ("B", "", True)])
def test_no_signal_for_recommended_worded_or_own_choice(tmp_path, choice, word, added):
    """Сценарии «Рекомендованный отказ без слова» и «Вариант, добавленный человеком»."""
    path, roots = word_fixture(tmp_path, choice, word, added)
    run = run_check(path, "--roots", roots, "--strict")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "не рекомендованный" not in run.stdout



# --- корни при инструментах вне проекта (F-93, F-104): раскладка по образцу research/F-93-probe/probe.py ---

import json
import re


def _copy_tools(into: Path) -> Path:
    """Инструменты в раскладке инсталлятора: `<into>/.symphysis/tools`, файл корней с `"": "<root>/.."`."""
    tools = into / ".symphysis" / "tools"
    tools.mkdir(parents=True)
    for f in (ROOT / "tools").glob("*"):
        if f.is_file() and re.match(r"journal.*\.py|step_help\.py|symphysis_config\.py|playground-template\.html|mermaid\.min\.js", f.name):
            shutil.copy(f, tools / f.name)
    (into / ".symphysis" / "docs").mkdir()
    shutil.copy(ROOT / "docs" / "journal.schema.json", into / ".symphysis" / "docs" / "journal.schema.json")
    (tools / "journal-roots.json").write_text('{"": "<root>/.."}\n', encoding="utf-8")
    return tools


def _layout(tmp_path: Path, tools_in_project: bool):
    """(tools, project): в проекте `only_project.py` и `both.py`, в установке `only_install.py` и `both.py`."""
    install = tmp_path / "установка с пробелом"
    project = install if tools_in_project else tmp_path / "проект"
    tools = _copy_tools(install)
    for base, names in ((install, ("both.py", "only_install.py")), (project, ("both.py", "only_project.py"))):
        (base / "src").mkdir(exist_ok=True, parents=True)
        for name in names:
            (base / "src" / name).write_text("в этом месте\n", encoding="utf-8")
    change = project / "openspec" / "changes" / "demo"
    change.mkdir(parents=True)
    j = one_record_journal("src/both.py", "в ")
    j["records"][0]["options"][0]["evidence"] = [
        {"path": f"src/{n}", "quote": "в "} for n in ("both.py", "only_project.py", "only_install.py")]
    journal.save_journal(change / "decisions.json", j)
    return tools, project


def _core(tools: Path, project: Path, *args):
    return subprocess.run([sys.executable, "-X", "utf8", str(tools / "journal.py"), *map(str, args)], cwd=project,
                          capture_output=True, encoding="utf-8", errors="replace")


JOURNAL_REL = "openspec/changes/demo/decisions.json"


def _verdicts(view_stdout: str) -> dict:
    return {e["path"]: e["verdict"] for e in json.loads(view_stdout)["records"][0]["options"][0]["evidence"]}


def test_scenario_root_with_tools_outside_the_project(tmp_path):
    """«Корень при инструментах вне проекта»: вердикт и карта считаются от проекта из пути журнала."""
    tools, project = _layout(tmp_path, tools_in_project=False)
    view = _core(tools, project, "view-json", JOURNAL_REL)
    assert view.returncode == 0, view.stderr
    assert _verdicts(view.stdout) == {"src/both.py": "сверено", "src/only_project.py": "сверено", "src/only_install.py": "файла нет"}


def test_scenario_all_core_commands_with_tools_outside_the_project(tmp_path):
    """«Все команды ядра»: `check` и `render-html` не читают корни установки."""
    tools, project = _layout(tmp_path, tools_in_project=False)
    out = _core(tools, project, "check", JOURNAL_REL)
    assert "улик сверено 2 из 3" in out.stdout and "only_install.py" in out.stdout and "файла нет" in out.stdout
    page = _core(tools, project, "render-html", JOURNAL_REL, "--out", "openspec/changes/demo/symphysis.html")
    assert page.returncode == 0, page.stderr
    assert "улик сверено 2 из 3" in page.stdout
    html = (project / "openspec" / "changes" / "demo" / "symphysis.html").read_text(encoding="utf-8")
    assert re.search(r'"src/only_project.py":\s*"[^"]*src/only_project.py"', html)
    assert not re.search(r'"src/only_install.py":\s*"', html)   # файл только в установке в карту не идёт


def test_scenario_ordinary_installation(tmp_path):
    """«Обычная установка»: инструменты в проекте, корни из файла корней; `--roots` важнее всего."""
    tools, project = _layout(tmp_path, tools_in_project=True)
    for command in ("view-json", "check", "render-html"):
        extra = ("--out", "openspec/changes/demo/symphysis.html") if command == "render-html" else ()
        run = _core(tools, project, command, JOURNAL_REL, *extra)
        assert run.returncode == 0, run.stderr
    view = _core(tools, project, "view-json", JOURNAL_REL)
    assert _verdicts(view.stdout)["src/only_install.py"] == "сверено"   # установка и проект — один каталог
    other = tmp_path / "другой"
    (other / "src").mkdir(parents=True)
    (other / "src" / "both.py").write_text("в другом\n", encoding="utf-8")
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(other)}), encoding="utf-8")
    forced = _core(tools, project, "view-json", JOURNAL_REL, "--roots", roots)
    assert _verdicts(forced.stdout) == {"src/both.py": "сверено", "src/only_project.py": "файла нет", "src/only_install.py": "файла нет"}


def test_explicit_roots_beat_the_project_root_with_tools_outside(tmp_path):
    tools, project = _layout(tmp_path, tools_in_project=False)
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(tmp_path / "установка с пробелом")}), encoding="utf-8")
    view = _core(tools, project, "view-json", JOURNAL_REL, "--roots", roots)
    assert _verdicts(view.stdout)["src/only_install.py"] == "сверено"


def test_default_roots_for_a_journal_outside_openspec_changes_keeps_the_roots_file(tmp_path):
    """Проект из пути не вывести — прежнее поведение: файл корней."""
    roots = tmp_path / "r.json"
    roots.write_text(json.dumps({"": str(tmp_path / "a")}), encoding="utf-8")
    assert journal.default_roots(roots)[""] == tmp_path / "a"
