"""Master-support freshness as consumed by journal check and the step page."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from conftest import journal_of
import attack_scope
import attack_table
import journal_cli
import step_help


MASTER = ("## Requirements\n\n"
          "### Requirement: Stable contract\n"
          "The contract SHALL remain usable.\n\n"
          "#### Scenario: Existing consumer\n"
          "- **WHEN** the input is kept\n"
          "- **THEN** the consumer succeeds\n\n"
          "### Requirement: Neighbor\n"
          "The neighbor SHALL be independent.\n")
BLOCK = ("#### Scenario: Existing consumer\n"
         "- **WHEN** the input is kept\n"
         "- **THEN** the consumer succeeds\n\n")
HEADER = ("| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |\n"
          "| --- | --- | --- | --- | --- | --- | --- |\n"
          "| чисто | design.md, 1 | scenario-run | — | справка | есть | — |\n")


def setup_report(tmp_path, support=None):
    root = tmp_path / "selected"
    change = root / "openspec/changes/demo"
    (change / "attack").mkdir(parents=True)
    (change / "design.md").write_bytes(b"Mechanism\n")
    (change / "decisions.json").write_text(json.dumps(journal_of()), encoding="utf-8")
    master = root / "openspec/specs/demo-cap/spec.md"
    master.parent.mkdir(parents=True)
    master.write_text(MASTER, encoding="utf-8")
    metadata = {"capability": "demo-cap", "requirement": "Stable contract", "scenario": "Existing consumer",
                "sha256": hashlib.sha256(BLOCK.encode()).hexdigest()}
    design_sha = hashlib.sha256(b"Mechanism\n").hexdigest()
    report = change / "attack/artifacts.md"
    report.write_text("---\nstatus: passed\ntargets:\n"
                      f"  - path: design.md\n    sha256: {design_sha}\n"
                      f"master_supports: {support if support is not None else json.dumps([metadata])}\n"
                      "---\n\n" + HEADER, encoding="utf-8")
    return root, change, master, report


def both_readers(root, change, report):
    checked, broken = journal_cli._scope_report(change)
    assert not broken
    prefix = "[..] атака артефактов: "
    scope = [line[len(prefix):] for line in checked if line.startswith(prefix)]
    status = {"planningHome": {"root": str(root)}, "changeRoot": str(change),
              "artifactPaths": {"attack-artifacts": {"existingOutputPaths": [str(report)]}}}
    helped = step_help._stale_scope({"id": "attack-artifacts"}, status)
    assert helped == scope
    return scope


def test_parser_keeps_master_supports_separate_from_local_targets(tmp_path):
    _, _, _, report = setup_report(tmp_path)
    fields = attack_table.parse_attack_md(report)["frontmatter"]
    assert fields["master_supports"] == [{
        "capability": "demo-cap", "requirement": "Stable contract", "scenario": "Existing consumer",
        "sha256": "2afc88712465ad11b8671730c38711b468193dd210c522157200dd1a30a5d050",
    }]
    assert len(fields["targets"]) == 1 and fields["targets"][0]["path"] == "design.md"


def test_both_readers_report_changed_master_while_local_target_is_unchanged(tmp_path):
    root, change, master, report = setup_report(tmp_path)
    assert both_readers(root, change, report) == []
    master.write_text(MASTER.replace("consumer succeeds", "consumer regresses"), encoding="utf-8")
    lines = both_readers(root, change, report)
    assert len(lines) == 1 and "openspec/specs/demo-cap/spec.md" in lines[0] and "измен" in lines[0]
    assert str(tmp_path) not in lines[0]


def test_neighbor_block_changes_leave_used_master_fresh(tmp_path):
    root, change, master, report = setup_report(tmp_path)
    master.write_text(MASTER.replace("independent", "changed"), encoding="utf-8")
    assert both_readers(root, change, report) == []


@pytest.mark.parametrize("damage,fragment", [
    ("missing", "блока нет"), ("unreadable", "не читается"), ("invalid-utf8", "не читается"),
    ("ambiguous", "неоднознач"), ("malformed", "неверный формат"),
])
def test_master_failures_have_the_same_safe_reason_in_both_readers(tmp_path, monkeypatch, damage, fragment):
    root, change, master, report = setup_report(tmp_path)
    if damage == "missing":
        master.unlink()
    elif damage == "invalid-utf8":
        master.write_bytes(b"\xff")
    elif damage == "ambiguous":
        master.write_text(MASTER.replace("### Requirement: Neighbor", BLOCK + "### Requirement: Neighbor"), encoding="utf-8")
    elif damage == "malformed":
        text = report.read_text(encoding="utf-8")
        line = next(line for line in text.splitlines() if line.startswith("master_supports:"))
        report.write_text(text.replace(line, 'master_supports: [{"do-not-echo-malformed-input":'), encoding="utf-8")
    else:
        read_bytes = Path.read_bytes

        def fail_after_path_check(path):
            if path == master:
                raise PermissionError("do-not-echo-read-error")
            return read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", fail_after_path_check)
    lines = both_readers(root, change, report)
    assert len(lines) == 1 and fragment in lines[0]
    assert "do-not-echo" not in lines[0] and str(tmp_path) not in lines[0]


@pytest.mark.parametrize("capability", ["../do-not-echo", "/do-not-echo", "C:\\do-not-echo"])
def test_unsafe_master_declarations_are_numbered_without_echoing_input(tmp_path, capability):
    support = [{"capability": capability, "requirement": "Stable contract", "sha256": "0" * 64}]
    root, change, _, report = setup_report(tmp_path, json.dumps(support))
    lines = both_readers(root, change, report)
    assert len(lines) == 1 and "master_supports[1]" in lines[0] and "вне" in lines[0]
    assert "do-not-echo" not in lines[0] and str(tmp_path) not in lines[0]


@pytest.mark.parametrize("field", [
    "master_supports: []\nmaster_supports: []",
    'master_supports:\n  - path: do-not-echo\n    sha256: attacker-digest',
    " master_supports: []",
    "master_supports : []",
    '"master_supports": []',
    r'"\u006daster_supports": []',
    r'"\x6daster_supports": []',
    r'"\U0000006daster_supports": []',
    "master_supports: []\n  ignored: payload",
])
def test_malformed_support_field_cannot_fall_back_to_legacy_or_extend_targets(tmp_path, field):
    root, change, _, report = setup_report(tmp_path)
    text = report.read_text(encoding="utf-8")
    line = next(line for line in text.splitlines() if line.startswith("master_supports:"))
    report.write_text(text.replace(line, field), encoding="utf-8")
    parsed = attack_table.parse_attack_md(report)
    assert len(parsed["frontmatter"]["targets"]) == 1
    lines = both_readers(root, change, report)
    assert len(lines) == 1 and "master_supports" in lines[0]
    assert "do-not-echo" not in lines[0] and "payload" not in lines[0]


@pytest.mark.parametrize("header", [
    '{"status":"passed","master_supports":[]}',
    r'{"status":"passed","\u006daster_supports":[]}',
    r'{status: passed, "\x6daster_supports": []}',
    '{status: passed, master_supports: [broken}',
])
def test_noncanonical_flow_frontmatter_cannot_hide_master_supports(tmp_path, header):
    root, change, _, report = setup_report(tmp_path)
    text = report.read_text(encoding="utf-8")
    body = text.split("---", 2)[2]
    report.write_text('---\n' + header + '\n---' + body, encoding="utf-8")
    lines = both_readers(root, change, report)
    assert len(lines) == 1 and "master_supports" in lines[0] and "неверный формат" in lines[0]
    assert "do-not-echo" not in lines[0] and str(tmp_path) not in lines[0]


@pytest.mark.parametrize("header", [
    '{"status":"passed","description":"master_supports: []"}',
    '{"status":"passed","description":"quoted value, \\"master_supports\\": []"}',
    '{"status":"passed","extra":{"master_supports":[]}}',
    '{"status":"passed","extra":["master_supports", "[]"]}',
    r'{"status":"passed","\\u006daster_supports":[]}',
    'status: passed\ndescription: |\n  master_supports: []',
    'status: passed\ndescription: >-\n  "master_supports": []',
])
def test_support_name_inside_flow_values_does_not_declare_master_field(tmp_path, header):
    root, change, _, report = setup_report(tmp_path)
    body = report.read_text(encoding="utf-8").split("---", 2)[2]
    report.write_text('---\n' + header + '\n---' + body, encoding="utf-8")
    assert both_readers(root, change, report) == []


def test_selected_store_is_used_instead_of_source_or_report_root(tmp_path, monkeypatch):
    root, change, master, report = setup_report(tmp_path)
    source = tmp_path / "source"
    source_master = source / "openspec/specs/demo-cap/spec.md"
    source_master.parent.mkdir(parents=True)
    source_master.write_text(MASTER, encoding="utf-8")
    monkeypatch.chdir(source)
    monkeypatch.setattr(journal_cli, "runtime_context", lambda: {"store": {"root": str(root)}})
    master.write_text(MASTER.replace("consumer succeeds", "consumer regresses"), encoding="utf-8")
    parsed = attack_table.parse_attack_md(report)
    parsed["frontmatter"]["planning_root"] = str(source)
    assert len(attack_scope.scope_lines(parsed, change, root)) == 1
    assert len(both_readers(root, change, report)) == 1
    lines = step_help._stale_scope({"id": "attack-artifacts"}, {
        "planningHome": {"root": str(source)}, "changeRoot": str(change),
        "artifactPaths": {"attack-artifacts": {"existingOutputPaths": [str(report)]}},
    })
    assert lines == []


def test_legacy_report_without_master_field_still_uses_only_local_targets(tmp_path):
    root, change, master, report = setup_report(tmp_path)
    lines = report.read_text(encoding="utf-8").splitlines(keepends=True)
    report.write_text("".join(line for line in lines if not line.startswith("master_supports:")), encoding="utf-8")
    master.unlink()
    assert both_readers(root, change, report) == []


@pytest.mark.parametrize("boundary", ["specs-root", "capability-dir", "master-file"])
def test_canonical_master_escape_is_rejected_before_external_file_is_read(tmp_path, monkeypatch, boundary):
    root, change, master, report = setup_report(tmp_path)
    outside = tmp_path / "do-not-echo-external"
    outside.mkdir()
    original = Path.read_bytes
    if boundary == "specs-root":
        master.unlink()
        master.parent.rmdir()
        master.parent.parent.rmdir()
        external = outside / "demo-cap/spec.md"
        external.parent.mkdir()
        external.write_text(MASTER, encoding="utf-8")
        link, target = root / "openspec/specs", outside
    elif boundary == "capability-dir":
        master.unlink()
        master.parent.rmdir()
        external = outside / "spec.md"
        external.write_text(MASTER, encoding="utf-8")
        link, target = master.parent, outside
    else:
        external = outside / "spec.md"
        external.write_text(MASTER, encoding="utf-8")
        master.unlink()
        link, target = master, external
    if os.name == "nt" and boundary in ("specs-root", "capability-dir"):
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    else:
        try:
            link.symlink_to(target, target_is_directory=boundary in ("specs-root", "capability-dir"))
        except OSError as error:
            pytest.skip(f"Symbolic links unavailable: {error}")

    def check_read(path):
        if path.resolve() == external:
            pytest.fail("External master content was opened before canonical containment was checked")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", check_read)
    lines = both_readers(root, change, report)
    assert len(lines) == 1 and "вне" in lines[0]
    assert "do-not-echo-external" not in lines[0] and str(tmp_path) not in lines[0]
