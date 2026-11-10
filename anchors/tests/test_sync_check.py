"""Результат sync: проверяемые расхождения и области, где требуется суждение о семантике/происхождении."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from conftest import ROOT
import sync_check
import trace_graph
from test_anchor_refs import block, project, snapshot_with_base, tree_hashes

PURPOSE = "# demo\n\n## Purpose\nЭкспорт позволяет получить данные и проверить совместимость клиента с контрактом сервиса.\n\n"
DELTA = "## MODIFIED Requirements\n\n" + block("Один", "Система SHALL вернуть данные (F-20, F-21).")
MASTER = PURPOSE + "## Requirements\n\n" + block("Один", "Система SHALL вернуть данные (F-20, demo/F-21).")


def prepared(tmp_path, *, delta=DELTA, master=MASTER):
    root, base, path = project(tmp_path, delta=delta, master=master)
    snapshot_with_base(base, ["F-20"])
    return root, base, path


def test_matching_anchored_result_is_repeatable_and_read_only(tmp_path):
    root, _, _ = prepared(tmp_path)
    before = tree_hashes(root)
    assert sync_check.check_sync(root, "demo")["status"] == "match"
    assert sync_check.check_sync(root, "demo")["status"] == "match"
    assert tree_hashes(root) == before


@pytest.mark.parametrize("old,new", [
    ("F-20, demo/F-21", "demo/F-20, demo/F-21"),
    ("demo/F-21", "foreign/F-21"),
    ("demo/F-21", "F-21"),
])
def test_equal_numbers_do_not_hide_wrong_origin_or_missing_anchor(tmp_path, old, new):
    root, _, _ = prepared(tmp_path, master=MASTER.replace(old, new))
    result = sync_check.check_sync(root, "demo")
    assert result["status"] == "mismatch"
    assert any("происхождение" in item["message"] for item in result["findings"])


def test_missing_base_requires_review_instead_of_guessing_own_origin(tmp_path):
    root, _, _ = project(tmp_path, delta=DELTA, master=MASTER)
    result = sync_check.check_sync(root, "demo")
    assert result["status"] == "review"
    assert all(item["level"] == "review" for item in result["findings"])


def test_base_taken_from_already_anchored_master_does_not_prove_old_origin(tmp_path):
    root, base, _ = prepared(tmp_path, master=MASTER.replace("F-20, demo/F-21", "demo/F-20, demo/F-21"))
    snapshot_path = base / "graph/req-graph.json"
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    data["base"]["demo"]["Один"]["numbers"] = ["demo/F-20", "demo/F-21"]
    snapshot_path.write_text(json.dumps(data), encoding="utf-8")
    assert sync_check.check_sync(root, "demo")["status"] == "review"


def test_textual_semantic_merge_is_review_not_a_fabricated_exact_match(tmp_path):
    root, _, _ = prepared(tmp_path, master=MASTER.replace("вернуть данные", "выдать данные"))
    assert sync_check.check_sync(root, "demo")["status"] == "review"


def test_whitespace_inside_a_literal_is_not_silently_normalized(tmp_path):
    delta = DELTA.replace("вернуть данные", "вернуть строку `a  b`")
    master = MASTER.replace("вернуть данные", "вернуть строку `a b`")
    root, _, _ = prepared(tmp_path, delta=delta, master=master)
    assert sync_check.check_sync(root, "demo")["status"] == "review"


def test_foreign_journal_and_option_letter_remain_part_of_the_reference(tmp_path):
    text = 'Система SHALL хранить (журнал `old`: F-20.A) и новый (F-20).'
    delta = "## MODIFIED Requirements\n\n" + block("Один", text)
    master = PURPOSE + "## Requirements\n\n" + block("Один", text.replace("новый (F-20)", "новый (demo/F-20)"))
    root, base, path = prepared(tmp_path, delta=delta, master=master)
    snapshot = base / "graph/req-graph.json"
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    data["base"]["demo"]["Один"]["numbers"] = ["old/F-20.A"]
    snapshot.write_text(json.dumps(data), encoding="utf-8")
    assert sync_check.check_sync(root, "demo")["status"] == "match"
    path.write_text(master.replace("F-20.A", "F-20.B"), encoding="utf-8")
    assert sync_check.check_sync(root, "demo")["status"] == "mismatch"


def test_new_and_modified_requirements_and_renames_are_verified_together(tmp_path):
    rename = '\n## RENAMED Requirements\n- FROM: `### Requirement: Один`\n- TO: `### Requirement: Новое`\n'
    added = block("Добавлено", "Система SHALL вернуть номер (F-26).")
    delta = DELTA.replace("Requirement: Один", "Requirement: Новое") + "\n## ADDED Requirements\n" + added + rename
    master = MASTER.replace("Requirement: Один", "Requirement: Новое") + "\n" + added.replace("F-26", "demo/F-26")
    root, _, path = prepared(tmp_path, delta=delta, master=master)
    assert sync_check.check_sync(root, "demo")["status"] == "match"  # база ещё под FROM
    path.write_text(master + "\n" + block("Один", "Система SHALL вернуть данные."), encoding="utf-8")
    assert sync_check.check_sync(root, "demo")["status"] == "mismatch"


def test_removed_requirement_still_present_is_a_mismatch(tmp_path):
    delta = "## REMOVED Requirements\n\n### Requirement: Один\n**Reason**: заменено\n**Migration**: другое\n"
    root, _, path = prepared(tmp_path, delta=delta)
    assert sync_check.check_sync(root, "demo")["status"] == "mismatch"
    path.unlink()
    assert sync_check.check_sync(root, "demo")["status"] == "review"  # политика retire — отдельная проверка


def test_missing_delta_and_old_scenarios_are_reported(tmp_path):
    root, base, path = prepared(tmp_path)
    snapshot_path = base / "graph/req-graph.json"
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    data["base"]["demo"]["Один"]["scenarios"] = {"Старый": "x"}
    snapshot_path.write_text(json.dumps(data), encoding="utf-8")
    result = sync_check.check_sync(root, "demo")
    assert result["status"] == "mismatch" and any("Старый" in f["message"] for f in result["findings"])
    path.write_text(MASTER.replace("#### Scenario: Сц", "#### Scenario: Другое"), encoding="utf-8")
    assert any("Сц" in f["message"] for f in sync_check.check_sync(root, "demo")["findings"])


def test_only_probe_trails_are_omitted_and_multiline_positions_stay_valid(tmp_path):
    probe = "<!-- проба краёв:\nформа=io, исходы: F-21 Specify\n-->\n"
    delta = DELTA + probe
    root, _, path = prepared(tmp_path, delta=delta)
    assert sync_check.check_sync(root, "demo")["status"] == "match"
    path.write_text(MASTER + probe, encoding="utf-8")
    assert sync_check.check_sync(root, "demo")["status"] == "mismatch"
    samples = '``<!-- проба краёв: образец -->``\n```md\n<!-- проба запретов: образец -->\n```\n'
    assert sync_check.strip_probe_trails(samples) == samples
    assert sync_check.strip_probe_trails("<!-- другая пометка -->") == "<!-- другая пометка -->"
    open_example = "```html\n<!--\n```\n"
    assert sync_check.strip_probe_trails(open_example + "<!-- проба краёв: след -->") == open_example


def test_selected_capability_does_not_require_excluded_delta_to_be_synced(tmp_path):
    root, base, _ = prepared(tmp_path)
    excluded = base / "specs/excluded/spec.md"
    excluded.parent.mkdir()
    excluded.write_text("## ADDED Requirements\n\n" + block("Новое", "Система SHALL работать (F-21)."), encoding="utf-8")
    assert sync_check.check_sync(root, "demo", capabilities=["demo"])["status"] == "match"
    assert sync_check.check_sync(root, "demo")["status"] == "mismatch"
    with pytest.raises(trace_graph.Refusal):
        sync_check.check_sync(root, "demo", capabilities=["missing"])


def test_duplicate_names_and_delta_headings_in_master_are_mismatches(tmp_path):
    root, _, path = prepared(tmp_path, master=MASTER + MASTER)
    assert sync_check.check_sync(root, "demo")["status"] == "mismatch"
    path.write_text(MASTER.replace("## Requirements", "## ADDED Requirements"), encoding="utf-8")
    assert sync_check.check_sync(root, "demo")["status"] == "mismatch"


def test_cli_json_codes_and_working_directory(tmp_path):
    root, _, _ = prepared(tmp_path)
    done = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "anchors/sync_check.py"), "demo", "--json"],
                          cwd=root, capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["status"] == "match"
    assert Path(json.loads(done.stdout)["root"]) == root.resolve()


def test_json_is_utf8_even_with_legacy_windows_output_encoding(tmp_path):
    root, _, _ = project(tmp_path, delta=DELTA.replace("Один", "导出"), master=MASTER.replace("Один", "导出"))
    done = subprocess.run([sys.executable, str(ROOT / "anchors/sync_check.py"), "demo", "--json"],
                          cwd=root, env=dict(os.environ, PYTHONIOENCODING="cp1251"), capture_output=True)
    assert done.returncode == 2, done.stderr.decode("utf-8")
    data = json.loads(done.stdout.decode("utf-8"))
    assert data["status"] == "review" and data["findings"][0]["requirement"] == "导出"
