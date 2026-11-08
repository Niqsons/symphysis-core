"""Разбор таблицы атаки (`attack/attack_table.py`): `parse_attack_md`, экранирование, пустые и лишние ячейки;
отказы на странице и в командной строке называют файл и строку."""
import re

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import ATTACK_FIX, embedded_attack, FAKE_SHA, html_fixture, run_cli
import attack_table
import journal


ROW_KEYS = ["claim", "section", "lens", "invariant", "severity", "support", "fix"]


def test_parse_attack_md_decisions_form():
    att = journal.parse_attack_md(ATTACK_FIX / "decisions.md")
    assert att["path"] == str(ATTACK_FIX / "decisions.md")
    assert att["frontmatter"]["status"] == "gaps_found"
    # форма decisions (`target` / `target_sha256`) наружу отдаётся той же формой `targets[]`
    assert att["frontmatter"]["targets"] == [{"path": "decisions.json", "sha256": FAKE_SHA}]
    rows = att["rows"]
    assert len(rows) == 3 and all(list(r) == ROW_KEYS for r in rows)
    assert rows[0]["section"] == "F-02, следствия" and rows[0]["support"] == "по спеке не выводится"
    assert rows[1]["support"] == "нет" and rows[1]["severity"] == "блокер"
    cover = next(r for r in rows if r["claim"] == "чисто")
    assert cover["lens"] == "coverage" and cover["invariant"] == "—" and cover["fix"] == "—"


def test_parse_attack_md_artifacts_form():
    att = journal.parse_attack_md(ATTACK_FIX / "artifacts.md")
    targets = att["frontmatter"]["targets"]
    assert [t["path"] for t in targets] == ["decisions.json", "specs/demo-cap/spec.md"]   # журнал первым
    assert targets[0]["sha256"] == FAKE_SHA and targets[1]["sha256"] == "fedcba9876543210" * 4
    assert att["frontmatter"]["status"] == "gaps_found"
    assert [r["lens"] for r in att["rows"]] == ["requirement-coverage", "honest-verifier", "coverage"]
    assert att["rows"][0]["section"] == "specs/demo-cap/spec.md, Requirement: работа по схеме"
    assert att["rows"][0]["fix"] == "правка артефакта"


def test_parse_attack_md_skips_placeholders_and_rejects_missing_table(tmp_path):
    text = (ATTACK_FIX / "decisions.md").read_text(encoding="utf-8")
    assert "| <утверждение журнала> |" in text        # строка-подстановка шаблона в фикстуре оставлена
    rows = journal.parse_attack_md(ATTACK_FIX / "decisions.md")["rows"]
    assert not any(r["claim"].startswith("<") for r in rows)
    no_table = tmp_path / "broken.md"
    no_table.write_text("---\nstatus: gaps_found\ntarget: decisions.json\ntarget_sha256:\n---\n\n# Атака\n\n"
                        "таблицы нет\n", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.md"):
        journal.parse_attack_md(no_table)
    no_front = tmp_path / "nofront.md"
    no_front.write_text(text.split("---\n", 2)[2], encoding="utf-8")   # та же таблица, frontmatter снят
    with pytest.raises(ValueError, match="nofront.md"):
        journal.parse_attack_md(no_front)


ATTACK_HEAD = ("---\nstatus: gaps_found\ntarget: decisions.json\ntarget_sha256:\n---\n\n"
               "| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |\n"
               "| --- | --- | --- | --- | --- | --- | --- |\n")


def attack_file(tmp_path, *rows, name="attack.md"):
    path = tmp_path / name
    path.write_text(ATTACK_HEAD + "".join(row + "\n" for row in rows), encoding="utf-8")
    return path


def test_pipe_in_backticks_and_escaped_pipe(tmp_path):
    row = r"| `grep -c '| справка |'` | F-23 | coverage | а \| б | справка | нет | — |"
    cells = journal.parse_attack_md(attack_file(tmp_path, row))["rows"][0]
    assert cells["claim"] == "`grep -c '| справка |'`"      # черта в backticks — текст, backticks сохранены
    assert cells["invariant"] == "а | б"                    # \| — литеральная черта
    assert cells["support"] == "нет" and cells["fix"] == "—"


def test_escaped_backslash_and_unclosed_backtick(tmp_path):
    ok = r"| `\\|` | F-34 | coverage | x | справка | нет | — |"
    cells = journal.parse_attack_md(attack_file(tmp_path, ok))["rows"][0]
    assert cells["claim"] == r"`\|`"                        # в коде: \\ -> \, голая | — текст
    # вне кода \\| — литеральная косая и разделитель: ячейка «a\», следом «b»
    assert attack_table._split_row(r"|a\\|b |") == (["a\\", "b "], None)
    bad = attack_file(tmp_path, "| `открыт | F-01 | coverage | x | справка | нет | — |", name="bad.md")
    with pytest.raises(ValueError) as err:
        journal.parse_attack_md(bad)
    msg = str(err.value)
    assert "bad.md:9:" in msg and "«Утверждение»" in msg and "backtick" in msg


def test_escapes_inside_code_and_lone_backslash(tmp_path):
    r"""Триаж 5B: внутри backticks `\|` — `|`, `\\` — `\`; обратная косая перед иным символом литеральна;
    `\\|` вне кода через `parse_attack_md` — литеральная косая и разделитель."""
    row = r"| `a\|b` и `c:\\d` | F-23 | coverage | x\y и `\n` | справка | нет | — |"
    cells = journal.parse_attack_md(attack_file(tmp_path, row))["rows"][0]
    assert cells["claim"] == r"`a|b` и `c:\d`"
    assert cells["invariant"] == r"x\y и `\n`"
    outside = attack_file(tmp_path, r"| a\\| F-34 | coverage | x | справка | нет | — |", name="outside.md")
    cells = journal.parse_attack_md(outside)["rows"][0]
    assert cells["claim"] == "a\\" and cells["section"] == "F-34" and cells["fix"] == "—"


def test_empty_required_cell_names_the_column(tmp_path):
    path = attack_file(tmp_path, "| чисто | F-03 | coverage |  | справка | есть | — |", name="empty.md")
    with pytest.raises(ValueError) as err:
        journal.parse_attack_md(path)
    assert "empty.md:9:" in str(err.value) and "«Инвариант»" in str(err.value)


def test_wrong_cell_count_reports_the_number(tmp_path):
    path = attack_file(tmp_path, "| а | б | coverage | x | справка | нет |", name="six.md")
    with pytest.raises(ValueError, match=r"six.md:9: .*ячеек 6, нужно 7"):
        journal.parse_attack_md(path)


@pytest.mark.parametrize("line, stray", [
    ("| а | б | scenario-run | в | блокер | нет | чинить a|b |", "a|b"),
    ("| а | б a|b | scenario-run | в | блокер | нет | чинить |", "a|b"),
], ids=["в последней ячейке", "во второй ячейке"])
def test_bare_pipe_outside_backticks_names_file_line_and_columns(tmp_path, line, stray):
    """`artifact-attack`: «Черта вне backticks» — отказ называет файл, строку и столбцы, код 2. Какая черта лишняя,
    по тексту не узнать: названы столбцы всех черт вне backticks (без граничных), лишняя — одна из них; каждое
    названное число указывает на знак `|`."""
    path = attack_file(tmp_path, line, name="bare-pipe.md")
    stray_column = line.index(stray) + 2          # номер знака `|` внутри «a|b», с единицы
    def named(message):
        assert "bare-pipe.md:9:" in message and "ячеек 8" in message and "лишняя — одна из них" in message
        found = re.search(r"в столбцах ([\d, ]+);", message)
        assert found, message
        return [int(n) for n in found.group(1).split(",")]
    with pytest.raises(ValueError) as err:
        journal.parse_attack_md(path)
    columns = named(str(err.value))
    assert stray_column in columns and all(line[c - 1] == "|" for c in columns)
    assert len(columns) == 8 - 1                 # восемь ячеек — семь внутренних черт
    src, roots = html_fixture(tmp_path, "дв")
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots, "--attack", path)
    assert run.returncode == 2, run.stdout + run.stderr
    assert named(run.stderr) == columns
    assert not out.exists()


def test_cli_render_html_broken_attack_file_exits_2_with_position(tmp_path):
    src, roots = html_fixture(tmp_path, "дв")
    broken = attack_file(tmp_path, "| `открыт | F-01 | coverage | x | справка | нет | — |", name="broken-cell.md")
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots, "--attack", broken)
    assert run.returncode == 2, run.stdout + run.stderr
    assert "broken-cell.md:9:" in run.stderr and "Утверждение" in run.stderr
    assert not out.exists()


def test_pipe_in_backticks_in_last_cell_makes_seven_cells_and_shows_text(tmp_path):
    """`decision-viewer`: «Черта в backticks в последней ячейке» — семь ячеек, код 0, черта показана в ячейке текстом."""
    src, roots = html_fixture(tmp_path, "дв")
    path = attack_file(tmp_path, "| а | F-01 | coverage | x | справка | нет | закрыть `grep -c 'a|b'` |", name="last-cell.md")
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots, "--attack", path)
    assert run.returncode == 0, run.stdout + run.stderr
    row = embedded_attack(out.read_text(encoding="utf-8"))[0]["rows"][0]
    assert len(row) == 7 and row["fix"] == "закрыть `grep -c 'a|b'`"


def test_extra_cell_names_file_and_line_and_writes_no_html(tmp_path):
    """`decision-viewer`: «Лишняя ячейка» — строка из восьми ячеек: ошибка называет файл и номер строки, код 2, HTML нет."""
    src, roots = html_fixture(tmp_path, "дв")
    attack = tmp_path / "attack"
    attack.mkdir()
    path = attack_file(attack, "| а | F-01 | coverage | x | справка | нет | — | лишняя |", name="decisions.md")
    out = tmp_path / "view.html"
    run = run_cli("render-html", src, "--out", out, "--roots", roots, "--attack", path)
    assert run.returncode == 2, run.stdout + run.stderr
    assert "decisions.md:9:" in run.stderr and "ячеек 8" in run.stderr
    assert not out.exists()


# --- set_severity (`attack-severity-word`, F-17, F-18.B, F-19.A, F-28, F-29.B, F-31.B) ---

SEV_HEAD = ("---\nstatus: gaps_found\ntarget: decisions.json\ntarget_sha256: abc123\n---\n\n"
            "| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n")
ROW_BLOCK = "| а  | F-01 | scenario-run |  инв  | блокер (старая причина) |  нет | чинить |"
ROW_WARN = "| б | F-02 | honest-verifier | инв | предупреждение | по спеке не выводится | чинить |"
ROW_REF = "| в | F-03 | coverage | — | справка | нет | — |"


def sev_text(*rows, nl="\n"):
    return (SEV_HEAD + "".join(r + "\n" for r in rows) + "\nхвост\n").replace("\n", nl)


def test_set_severity_lowers_last_blocker_to_passed_keeping_other_bytes():
    text = sev_text(ROW_BLOCK, ROW_WARN)
    out = attack_table.set_severity(text, "a.md", "F-01", "а", "предупреждение", "решено человеком")
    assert out == text.replace("status: gaps_found", "status: passed").replace(
        "блокер (старая причина) |", "предупреждение (решено человеком) |")
    att = attack_table.parse_attack_text(out, "a.md")
    assert att["frontmatter"]["status"] == "passed"
    assert att["frontmatter"]["targets"][0]["sha256"] == "abc123"
    assert att["rows"][0]["severity"] == "предупреждение (решено человеком)"


@pytest.mark.parametrize("cell", ["Блокер", "блокер(причина)", "БЛОКЕР (причина)"])
def test_set_severity_status_counts_blockers_by_the_page_rule(cell):
    """Другая строка `Блокер` / `блокер(…)` не слово для хода, но блокер для status: после понижения единственной
    строчной `блокер` статус остаётся gaps_found."""
    other = ROW_WARN.replace("| предупреждение |", f"| {cell} |")
    out = attack_table.set_severity(sev_text(ROW_BLOCK, other), "a.md", "F-01", "а", "предупреждение", "слово")
    assert "status: gaps_found" in out and "предупреждение (слово) |" in out


def test_set_severity_raises_warning_to_gaps_found_other_rows_unchanged():
    text = sev_text(ROW_REF, ROW_WARN).replace("status: gaps_found", "status: passed")
    out = attack_table.set_severity(text, "a.md", "F-02", "б", "блокер", "не годится")
    assert out == text.replace("status: passed", "status: gaps_found").replace(
        "| предупреждение |", "| блокер (не годится) |")


def test_set_severity_same_claim_two_lenses_is_refused():
    twin = ROW_WARN.replace("honest-verifier", "scenario-run")
    with pytest.raises(ValueError, match="строк с этим ключом две"):
        attack_table.set_severity(sev_text(ROW_WARN, twin), "a.md", "F-02", "б", "блокер", "x")


def test_set_severity_flattens_why_and_escapes_pipe_and_backslash():
    out = attack_table.set_severity(sev_text(ROW_BLOCK), "a.md", "F-01", "а", "предупреждение",
                                    "см. сценарий (раздел B) | ок\nи c:\\d")
    line = next(ln for ln in out.split("\n") if ln.startswith("| а"))
    assert r"предупреждение (см. сценарий (раздел B) \| ок и c:\\d) |" in line
    assert attack_table.parse_attack_text(out, "a.md")["rows"][0]["severity"] == \
        "предупреждение (см. сценарий (раздел B) | ок и c:\\d)"


def test_set_severity_new_why_replaces_old_reason():
    text = sev_text(ROW_BLOCK.replace("блокер (старая причина)", "предупреждение (решено человеком в F-09)"))
    out = attack_table.set_severity(text, "a.md", "F-01", "а", "блокер", "кнопка")
    assert "блокер (кнопка)" in out and "F-09" not in out and "старая" not in out


@pytest.mark.parametrize("row, target, reason", [
    (ROW_BLOCK, "справка", "не ставится"),
    (ROW_REF, "блокер", "строка покрытия|вне хода"),
    (ROW_BLOCK, "блокер", "уже"),
    (ROW_BLOCK.replace("блокер (старая причина)", "Блокер"), "предупреждение", "вне хода"),
    (ROW_BLOCK.replace("блокер (старая причина)", "критично"), "предупреждение", "вне хода"),
    ("| не пройдено | F-01 | coverage | — | блокер | нет: не пройдено | — |", "предупреждение", "строка покрытия"),
    ("| а | F-01 | coverage | — | блокер | нет: файла нет | — |", "предупреждение", "строка покрытия"),
], ids=["цель справка", "справка в строке", "та же тяжесть", "заглавная", "слово вне трёх",
        "не пройдено", "файла нет"])
def test_set_severity_refusals_name_the_reason(row, target, reason):
    claim = "не пройдено" if row.startswith("| не пройдено") else "а" if row is not ROW_REF else "в"
    section = "F-03" if row is ROW_REF else "F-01"
    with pytest.raises(ValueError, match=reason):
        attack_table.set_severity(sev_text(row), "a.md", section, claim, target, "x")


def test_set_severity_missing_claim_after_rewrite_is_refused():
    with pytest.raises(ValueError, match="строки нет"):
        attack_table.set_severity(sev_text(ROW_BLOCK), "a.md", "F-01", "переписано", "предупреждение", "x")
    with pytest.raises(ValueError, match="строки нет"):
        attack_table.set_severity(sev_text(ROW_BLOCK), "a.md", "F-99", "а", "предупреждение", "x")


def test_set_severity_unclosed_backtick_is_unparsable():
    with pytest.raises(ValueError, match="ячейка не разбирается: .*backtick"):
        attack_table.set_severity(sev_text(ROW_BLOCK), "a.md", "F-01", "а", "предупреждение", "один ` знак")


def test_set_severity_keeps_crlf_bom_and_requires_status():
    text = "\ufeff" + sev_text(ROW_BLOCK, nl="\r\n")
    out = attack_table.set_severity(text, "a.md", "F-01", "а", "предупреждение", "ок")
    assert out.startswith("\ufeff---\r\nstatus: passed\r\n") and "\n" not in out.replace("\r\n", "")
    assert out == text.replace("gaps_found", "passed").replace(
        "блокер (старая причина)", "предупреждение (ок)")
    with pytest.raises(ValueError, match="status"):
        attack_table.set_severity(sev_text(ROW_BLOCK).replace("status: gaps_found\n", ""),
                                  "a.md", "F-01", "а", "предупреждение", "ок")
