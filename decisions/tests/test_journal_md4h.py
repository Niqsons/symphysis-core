import copy
import hashlib
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import FIX, ROOT, one_record_journal
import journal

FIXTURE = FIX / "md4h-feedback.md"
FEEDBACK_TEXT = {  # то, что лежит в фикстуре под `### Feedback`
    "F1": "Пример текста первого комментария.",
    "F2": "Пример текста второго комментария.",
    "F6": "Пример многострочного комментария:\nпервая строка-заглушка\n\nвторая строка после пустой.",
}


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "cli" / "journal.py"), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8")


def line_of(path, needle):
    """Номер (с единицы) первой строки файла, где есть needle; файл читается как лежит на диске."""
    for n, line in enumerate(Path(path).read_bytes().decode("utf-8").split("\n"), 1):
        if needle in line:
            return n
    raise AssertionError(f"{needle!r} в {path} не найдено")


def plan():
    return journal.import_md(FIX / "journal-plan.md")


def rendered(tmp_path, j, name="d.md"):
    """Рендер журнала на диске, как его пишет `render-md`: CRLF."""
    md = tmp_path / name
    md.write_text(journal.render_md(j), encoding="utf-8", newline="\r\n")
    return md


def fixture_text():
    """Фикстура как лежит на диске — с CRLF."""
    return FIXTURE.read_bytes().decode("utf-8")


def bundle_at(md, *spans):
    """Связка из фикстуры, привязанная к рендеру `md`: его SHA и строки комментариев `spans`."""
    b = journal.parse_md4h(fixture_text())
    b["source_sha256"] = journal.sha256_file(md)
    b["items"] = b["items"][:len(spans)]
    for item, span in zip(b["items"], spans):
        item["lines"] = span
    return b


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


def comments_of(j, rid):
    return next(r for r in j["records"] if r["id"] == rid)["comments"]


def all_comments(j):
    return [c for r in j["records"] for c in r["comments"]]


def refused(report):
    return [line for line in report if line.startswith(journal.REFUSED)]


# --- тесты из брифа ---------------------------------------------------------

def test_md4h_refuses_sha_mismatch(tmp_path):
    md = tmp_path / "d.md"; md.write_text("<!-- journal:F-01 -->\n# x\n", encoding="utf-8")
    b = journal.parse_md4h(FIX.joinpath("md4h-feedback.md").read_text(encoding="utf-8"))
    j = journal.import_md(FIX / "journal-plan.md")
    report = journal.apply_md4h(j, b, md)
    assert report and "sha256" in report[0] and all(not r["comments"] for r in j["records"])


def test_md4h_maps_comment_to_record(tmp_path):
    j = journal.import_md(FIX / "journal-plan.md")
    md = tmp_path / "d.md"; md.write_text(journal.render_md(j), encoding="utf-8")
    b = journal.parse_md4h(FIX.joinpath("md4h-feedback.md").read_text(encoding="utf-8"))
    b["source_sha256"] = journal.sha256_file(md); b["items"][0]["lines"] = (line_of(md, "<!-- journal:F-03 -->") + 2,) * 2
    journal.apply_md4h(j, b, md)
    assert next(r for r in j["records"] if r["id"] == "F-03")["comments"][0]["text"]


# --- разбор связки ----------------------------------------------------------

def test_parse_md4h_reads_the_fixture():
    b = journal.parse_md4h(fixture_text())
    assert {k: b[k] for k in ("schema", "state", "round", "source", "source_sha256")} == {
        "schema": "md4h-feedback/v2", "state": "sealed", "round": "20261028T201340Z-dfa6",
        "source": "docs/plan-implementation.journal.md",
        "source_sha256": "851326035e4670e223d4cdcd260a1d9a8aa1fe5953d0e29ee810857826638323"}
    assert [(i["id"], i["lines"], i["feedback"]) for i in b["items"]] == [
        ("F1", (363, 373), FEEDBACK_TEXT["F1"]),
        ("F2", (363, 373), FEEDBACK_TEXT["F2"]),
        ("F6", (377, 382), FEEDBACK_TEXT["F6"])]


def test_parse_md4h_single_line_number_is_a_one_line_span():
    text = fixture_text().replace("**Source lines:** 363-373", "**Source lines:** 363", 1)
    assert journal.parse_md4h(text)["items"][0]["lines"] == (363, 363)


def test_parse_md4h_reads_crlf_and_lf_alike():
    raw = FIXTURE.read_bytes().decode("utf-8")
    assert "\r\n" in raw                                   # фикстура на диске — CRLF
    assert journal.parse_md4h(raw) == journal.parse_md4h(raw.replace("\r\n", "\n"))
    assert journal.parse_md4h(raw)["items"][2]["feedback"] == FEEDBACK_TEXT["F6"]   # без \r внутри


def test_parse_md4h_reads_a_file_with_a_bom():
    assert journal.parse_md4h(chr(0xFEFF) + fixture_text()) == journal.parse_md4h(fixture_text())


def test_parse_md4h_takes_only_the_fenced_feedback():
    text = fixture_text()
    assert "Selected content" in text and "Пример выделенного" in text
    for item in journal.parse_md4h(text)["items"]:
        assert "Пример выделенного" not in item["feedback"] and "Source lines" not in item["feedback"]


def test_parse_md4h_ignores_headings_and_fences_inside_evidence():
    # Выделенный текст сам содержит `### Feedback`, чужой заголовок комментария и такую же рамку:
    # разбор идёт по рамкам, а не по первым попавшимся строкам.
    text = "\n".join([
        "---", "schema: md4h-feedback/v2", "state: sealed", "round: r1", "source: d.md",
        "source_sha256: abc", "line_numbering: one-based-inclusive", "---", "",
        "## F1 · text", "", "**Source lines:** 5-6", "", "### Selected content", "",
        "````text", "### Feedback", "```markdown", "подделка", "```", "## F9 · text", "````", "",
        "### Feedback", "", "```markdown", "настоящий", "```", ""])
    items = journal.parse_md4h(text)["items"]
    assert [(i["id"], i["lines"], i["feedback"]) for i in items] == [("F1", (5, 6), "настоящий")]


def test_parse_md4h_feedback_may_hold_a_shorter_fence_and_a_fake_heading():
    text = fixture_text().replace(
        "```markdown\r\nПример текста первого комментария.\r\n```",
        "````markdown\r\nкод:\r\n```python\r\nx = 1\r\n```\r\n## F9 · text\r\n````", 1)
    first = journal.parse_md4h(text)["items"][0]["feedback"]
    assert first == "код:\n```python\nx = 1\n```\n## F9 · text"


def test_parse_md4h_unknown_schema_is_refused():
    text = fixture_text().replace("md4h-feedback/v2", "md4h-feedback/v3")
    with pytest.raises(ValueError, match=r"md4h-feedback/v3"):
        journal.parse_md4h(text)


@pytest.mark.parametrize("field", ["schema", "state", "round", "source", "source_sha256"])
def test_parse_md4h_names_the_missing_frontmatter_field(field):
    text = re.sub(rf"(?m)^{field}: .*\r\n", "", fixture_text(), count=1)
    with pytest.raises(ValueError, match=field):
        journal.parse_md4h(text)


def test_parse_md4h_without_frontmatter_is_refused():
    with pytest.raises(ValueError, match="frontmatter"):
        journal.parse_md4h("## F1 · text\n")


def test_parse_md4h_refuses_line_numbering_other_than_one_based():
    text = fixture_text().replace("one-based-inclusive", "zero-based-exclusive")
    with pytest.raises(ValueError, match="zero-based-exclusive"):
        journal.parse_md4h(text)


def test_parse_md4h_names_the_item_without_lines_or_feedback():
    no_lines = fixture_text().replace("**Source lines:** 377-382\r\n", "")
    with pytest.raises(ValueError, match=r"F6.*Source lines"):
        journal.parse_md4h(no_lines)
    no_feedback = fixture_text()[:fixture_text().index("```markdown\r\nПример многострочного")]
    with pytest.raises(ValueError, match=r"F6.*Feedback"):
        journal.parse_md4h(no_feedback)


def test_parse_md4h_refuses_an_empty_feedback():
    text = fixture_text().replace("```markdown\r\nПример текста первого комментария.\r\n```",
                                  "```markdown\r\n  \r\n```", 1)
    with pytest.raises(ValueError, match=r"F1.*пуст"):
        journal.parse_md4h(text)


# --- якоря рендера ----------------------------------------------------------

def test_anchor_lines_numbers_lines_from_one_and_ignores_line_endings():
    lf = "# т\n\n## F-01 в\n<!-- journal:F-01 -->\n- вид: факт\n\n## F-02 в\n<!-- journal:F-02 -->\n"
    assert journal.anchor_lines(lf) == [(4, "F-01"), (8, "F-02")]
    assert journal.anchor_lines(lf.replace("\n", "\r\n")) == [(4, "F-01"), (8, "F-02")]


def test_anchor_lines_match_whole_lines_only():
    text = "см. <!-- journal:F-01 --> в тексте\n<!-- journal:F-02 -->\n    <!-- journal:F-03 -->\n"
    assert journal.anchor_lines(text) == [(2, "F-02")]


def test_anchor_lines_of_a_render_cover_every_record():
    j = plan()
    anchors = journal.anchor_lines(journal.render_md(j))
    assert [rid for _, rid in anchors] == [r["id"] for r in j["records"]]
    assert [n for n, _ in anchors] == sorted(n for n, _ in anchors)


# --- внесение ---------------------------------------------------------------

def test_sha256_file_hashes_the_bytes_on_disk(tmp_path):
    p = tmp_path / "a.md"
    data = "а\r\nб\n".encode("utf-8")
    p.write_bytes(data)
    assert journal.sha256_file(p) == hashlib.sha256(data).hexdigest()
    assert journal.sha256_file(p) != hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def test_comment_lands_on_the_record_with_round_lines_and_text(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-03 -->")
    b = bundle_at(md, (start + 2, start + 4))
    report = journal.apply_md4h(j, b, md)
    assert not refused(report), report
    assert comments_of(j, "F-03") == [{"round": "20261028T201340Z-dfa6", "lines": [start + 2, start + 4],
                                       "text": FEEDBACK_TEXT["F1"]}]
    assert all(not r["comments"] for r in j["records"] if r["id"] != "F-03")
    assert journal.validate_journal(j) == []
    assert "F1" in report[0] and "F-03" in report[0]


def test_comment_on_the_last_line_of_a_record_stays_with_it(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    next_heading = line_of(md, "<!-- journal:F-04 -->") - 1       # заголовок F-04
    journal.apply_md4h(j, bundle_at(md, (next_heading - 2, next_heading - 2)), md)
    assert [c["text"] for c in comments_of(j, "F-03")] == [FEEDBACK_TEXT["F1"]]


def test_comment_on_a_heading_belongs_to_that_record_not_the_one_above(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    heading = line_of(md, "<!-- journal:F-05 -->") - 1
    assert journal.anchor_lines(md.read_bytes().decode("utf-8"))[4] == (heading + 1, "F-05")
    journal.apply_md4h(j, bundle_at(md, (heading, heading)), md)
    assert len(comments_of(j, "F-05")) == 1 and not comments_of(j, "F-04")


def test_comment_on_the_first_heading_belongs_to_the_first_record(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    heading = line_of(md, "<!-- journal:F-01 -->") - 1
    report = journal.apply_md4h(j, bundle_at(md, (heading, heading)), md)
    assert not refused(report), report
    assert len(comments_of(j, "F-01")) == 1


def test_several_comments_go_to_their_records_in_document_order(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    f2, f3 = line_of(md, "<!-- journal:F-02 -->"), line_of(md, "<!-- journal:F-03 -->")
    journal.apply_md4h(j, bundle_at(md, (f2 + 1, f2 + 1), (f2 + 2, f2 + 3), (f3 + 1, f3 + 1)), md)
    assert [c["text"] for c in comments_of(j, "F-02")] == [FEEDBACK_TEXT["F1"], FEEDBACK_TEXT["F2"]]
    assert [c["text"] for c in comments_of(j, "F-03")] == [FEEDBACK_TEXT["F6"]]


def test_multiline_feedback_is_kept_as_written(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-02 -->")
    b = bundle_at(md, (start + 1, start + 1), (start + 1, start + 1), (start + 1, start + 1))
    journal.apply_md4h(j, b, md)
    assert comments_of(j, "F-02")[2]["text"] == FEEDBACK_TEXT["F6"]


def test_reapplying_the_same_bundle_adds_nothing(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-03 -->")
    b = bundle_at(md, (start + 1, start + 1), (start + 1, start + 1))
    journal.apply_md4h(j, b, md)
    once = copy.deepcopy(j)
    report = journal.apply_md4h(j, b, md)
    assert j == once and len(comments_of(j, "F-03")) == 2
    assert len(report) == 2 and all("уже внесён" in line for line in report)


def test_same_lines_with_other_text_is_a_new_comment(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-03 -->")
    b = bundle_at(md, (start + 1, start + 1))
    journal.apply_md4h(j, b, md)
    b["items"][0]["feedback"] = "другой текст"
    journal.apply_md4h(j, b, md)
    assert [c["text"] for c in comments_of(j, "F-03")] == [FEEDBACK_TEXT["F1"], "другой текст"]


def test_same_text_in_another_round_is_a_new_comment(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-03 -->")
    b = bundle_at(md, (start + 1, start + 1))
    journal.apply_md4h(j, b, md)
    b["round"] = "20261101T000000Z-aaaa"
    journal.apply_md4h(j, b, md)
    assert [c["round"] for c in comments_of(j, "F-03")] == ["20261028T201340Z-dfa6", "20261101T000000Z-aaaa"]


# --- отказы -----------------------------------------------------------------

def test_unsealed_bundle_is_refused_without_touching_the_journal(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-03 -->")
    b = bundle_at(md, (start + 1, start + 1))
    b["state"] = "draft"
    before = copy.deepcopy(j)
    report = journal.apply_md4h(j, b, md)
    assert "связка не запечатана" in report[0] and "draft" in report[0]
    assert "sha256" not in report[0]
    assert j == before


def test_unsealed_and_foreign_sha_both_named(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    b = bundle_at(md, (10, 10))
    b["state"], b["source_sha256"] = "open", "0" * 64
    text = "\n".join(journal.apply_md4h(j, b, md))
    assert "связка не запечатана" in text and "sha256 рендера не совпадает: связка к другой версии" in text
    assert all_comments(j) == []


def test_sha_of_another_render_version_is_refused(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-03 -->")
    b = bundle_at(md, (start + 1, start + 1))
    md.write_text(journal.render_md(j) + "\n- допись\n", encoding="utf-8", newline="\r\n")   # рендер изменился
    report = journal.apply_md4h(j, b, md)
    assert "sha256 рендера не совпадает: связка к другой версии" in report[0]
    assert all_comments(j) == []


def test_sha_compares_bytes_not_text(tmp_path):
    # Тот же текст, другие концы строк — другой файл: связка к нему не относится.
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-03 -->")
    b = bundle_at(md, (start + 1, start + 1))
    md.write_text(journal.render_md(j), encoding="utf-8", newline="\n")
    assert "sha256" in journal.apply_md4h(j, b, md)[0]


def test_sha_is_compared_case_insensitively(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-03 -->")
    b = bundle_at(md, (start + 1, start + 1))
    b["source_sha256"] = b["source_sha256"].upper()
    assert not refused(journal.apply_md4h(j, b, md))


def test_comment_above_the_first_record_is_refused_by_name(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    b = bundle_at(md, (1, 1))
    before = copy.deepcopy(j)
    report = journal.apply_md4h(j, b, md)
    assert "комментарий F1 выше первой записи" in report[0]
    assert j == before


def test_one_refusal_keeps_every_comment_out(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-03 -->")
    b = bundle_at(md, (start + 1, start + 1), (2, 2))       # первый годен, второй выше первой записи
    before = copy.deepcopy(j)
    report = journal.apply_md4h(j, b, md)
    assert "комментарий F2 выше первой записи" in report[0]
    assert "журнал не изменён" in report[-1]
    assert j == before


def test_anchor_of_a_record_missing_from_the_journal_is_refused(tmp_path):
    j = plan()
    md = rendered(tmp_path, j)
    start = line_of(md, "<!-- journal:F-03 -->")
    b = bundle_at(md, (start + 1, start + 1))
    del j["records"][2]                                      # журнал ушёл вперёд рендера
    before = copy.deepcopy(j)
    report = journal.apply_md4h(j, b, md)
    assert "F1" in report[0] and "F-03" in report[0] and "нет в журнале" in report[0]
    assert j == before


def test_invalid_result_is_refused(tmp_path):
    j = one_record_journal("a.md", "q")
    j["records"][0]["status"] = "готов"                      # журнал негоден уже до внесения
    md = tmp_path / "d.md"
    md.write_text("# т\n\n## F-01 вопрос?\n<!-- journal:F-01 -->\n", encoding="utf-8", newline="\r\n")
    b = bundle_at(md, (4, 4))
    before = copy.deepcopy(j)
    report = journal.apply_md4h(j, b, md)
    assert "журнал негоден" in report[0] and "F-01" in report[0]
    assert j == before


# --- командная строка -------------------------------------------------------

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


def test_cli_apply_md4h_help_tells_the_flow():
    run = run_cli("apply-md4h", "--help")
    assert run.returncode == 0
    text = " ".join(run.stdout.split())
    assert "render-md" in text and "md4h" in text and "comments[]" in text
    assert "не рендерит" in text
    assert "--render" in text


def test_cli_lists_apply_md4h_among_the_commands():
    run = run_cli("--help")
    assert run.returncode == 0 and "apply-md4h" in run.stdout
