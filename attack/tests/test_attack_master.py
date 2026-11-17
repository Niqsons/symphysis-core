"""Exact master-block metadata shared by the attack writer and freshness readers."""
import hashlib
import importlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from conftest import ROOT


FIXTURE = ROOT / "attack/tests/fixtures/master-supports"
MASTER_RELATIVE = Path("openspec/specs/shared-input/spec.md")
REPORT_RELATIVE = Path("openspec/changes/sample/attack/artifacts.md")
CAPABILITY = "shared-input"
REQUIREMENT = "Stable input"
SCENARIO = "Input remains usable"
SCENARIO_BLOCK = (
    "#### Scenario: Input remains usable\n"
    "- **WHEN** a consumer reads the input\n"
    "- **THEN** it receives the original value — без потери данных\n\n"
)
REQUIREMENT_BLOCK = (
    "### Requirement: Stable input\n"
    "The input SHALL preserve its public shape.\n\n"
    + SCENARIO_BLOCK
    + "#### Scenario: Unused sibling\n"
    "- **WHEN** another consumer reads the input\n"
    "- **THEN** it receives an independent value\n\n"
)


def attack_master():
    return importlib.import_module("attack_master")


def test_selects_exact_requirement_and_scenario_blocks():
    module = attack_master()
    assert module.master_block(FIXTURE, CAPABILITY, REQUIREMENT) == REQUIREMENT_BLOCK
    assert module.master_block(FIXTURE, CAPABILITY, REQUIREMENT, SCENARIO) == SCENARIO_BLOCK


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_support_digest_normalizes_only_line_endings(tmp_path, ending):
    module = attack_master()
    path = tmp_path / MASTER_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_bytes((FIXTURE / MASTER_RELATIVE).read_text(encoding="utf-8").replace("\n", ending).encode("utf-8"))
    requirement = module.master_support(tmp_path, CAPABILITY, REQUIREMENT)
    scenario = module.master_support(tmp_path, CAPABILITY, REQUIREMENT, SCENARIO)
    assert requirement == {
        "capability": CAPABILITY, "requirement": REQUIREMENT,
        "sha256": hashlib.sha256(REQUIREMENT_BLOCK.encode("utf-8")).hexdigest(),
    }
    assert scenario == {
        "capability": CAPABILITY, "requirement": REQUIREMENT, "scenario": SCENARIO,
        "sha256": hashlib.sha256(SCENARIO_BLOCK.encode("utf-8")).hexdigest(),
    }
    assert requirement["sha256"] != scenario["sha256"]


def test_writer_preserves_local_targets_body_and_line_endings():
    module = attack_master()
    text = "\ufeff---\r\nstatus: passed\r\ntargets:\r\n  - path: design.md\r\n    sha256: local\r\n---\r\n\r\n# Report\r\n"
    support = module.master_support(FIXTURE, CAPABILITY, REQUIREMENT, SCENARIO)
    updated = module.set_master_supports(text, [support])
    field = next(line for line in updated.splitlines() if line.startswith("master_supports:"))
    assert module.parse_master_supports(field.split(":", 1)[1].strip()) == [support]
    assert updated.replace(field + "\r\n", "") == text
    assert module.set_master_supports(updated, [support]) == updated
    assert len(json.loads(field.split(":", 1)[1])) == 1
    assert "THEN" not in field and "openspec" not in field


def test_writer_replaces_used_blocks_without_adding_neighbors():
    module = attack_master()
    scenario = module.master_support(FIXTURE, CAPABILITY, REQUIREMENT, SCENARIO)
    requirement = module.master_support(FIXTURE, CAPABILITY, REQUIREMENT)
    text = module.set_master_supports("---\nstatus: passed\n---\n", [requirement])
    updated = module.set_master_supports(text, [scenario])
    field = next(line for line in updated.splitlines() if line.startswith("master_supports:"))
    assert module.parse_master_supports(field.split(":", 1)[1].strip()) == [scenario]
    assert "Unused sibling" not in updated and requirement["sha256"] not in updated


def test_shared_fixture_has_portable_bytes_and_reproducible_metadata():
    module = attack_master()
    report = (FIXTURE / REPORT_RELATIVE).read_bytes()
    master = (FIXTURE / MASTER_RELATIVE).read_bytes()
    design = (FIXTURE / "openspec/changes/sample/design.md").read_bytes()
    assert b"\r" not in report + master + design
    report_text = report.decode("utf-8")
    field = next(line for line in report_text.splitlines() if line.startswith("master_supports:"))
    assert module.parse_master_supports(field.split(":", 1)[1].strip()) == [
        module.master_support(FIXTURE, CAPABILITY, REQUIREMENT, SCENARIO)
    ]
    assert "    sha256: " + hashlib.sha256(design).hexdigest() in report_text


def write_master(root, text):
    path = root / MASTER_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def test_block_preserves_heading_comments_spaces_and_last_newline(tmp_path):
    module = attack_master()
    text = (
        "\ufeff# Example\n\n## Requirements ##\n\n"
        "###Requirement: Stable input ###\nBody  with  spaces.  \n\n"
        "#### Input remains usable ####\n<!-- evidence -->\n  keep  these spaces  \n"
        "##### Detail\nNested text.\n\n"
        "#### Other\nOther text."
    )
    write_master(tmp_path, text)
    expected = (
        "#### Input remains usable ####\n<!-- evidence -->\n  keep  these spaces  \n"
        "##### Detail\nNested text.\n\n"
    )
    assert module.master_block(tmp_path, CAPABILITY, REQUIREMENT, SCENARIO) == expected
    assert module.master_block(tmp_path, CAPABILITY, REQUIREMENT).endswith("Other text.")


def test_fenced_headers_remain_data_inside_raw_block(tmp_path):
    module = attack_master()
    block = (
        "#### Scenario: Input remains usable\n"
        "```markdown\n### Requirement: Stable input\n#### Scenario: Input remains usable\n```\n"
        "```inline```\nThe final line remains inside the selected block.\n\n"
    )
    write_master(tmp_path, "## Requirements\n### Requirement: Stable input\nBody.\n" + block
                 + "#### Scenario: Other\nOther text.\n")
    assert module.master_block(tmp_path, CAPABILITY, REQUIREMENT, SCENARIO) == block


@pytest.mark.parametrize("text, reason", [
    ("## Requirements\n### Requirement: Stable input\nBody.\n### Requirement: Stable input\nAgain.\n", "ambiguous"),
    ("## Requirements\n### Requirement: Stable input\nBody.\n#### Scenario: Input remains usable\nA.\n"
     "#### Scenario: Input remains usable\nB.\n", "ambiguous"),
    ("## Requirements\n### Requirement: Stable input\nBody.\n## Requirements\n### Requirement: Other\nBody.\n", "ambiguous"),
    ("### Requirement: Stable input\nBody.\n#### Scenario: Input remains usable\nBody.\n", "invalid"),
    ("## Requirements\n### Requirement: Stable input\nBody.\n#### Scenario: Input remains usable\n", "invalid"),
    ("## Requirements\n### Requirement: Stable input\nBody.\n#### Scenario: Input remains usable\n```\nbody\n", "invalid"),
    ("## Requirements\n### Requirement: Other\nBody.\n", "missing"),
])
def test_rejects_missing_ambiguous_and_malformed_scoped_blocks(tmp_path, text, reason):
    module = attack_master()
    write_master(tmp_path, text)
    with pytest.raises(module.MasterSupportError) as error:
        module.master_block(tmp_path, CAPABILITY, REQUIREMENT, SCENARIO)
    assert error.value.reason == reason
    assert "Stable input" not in str(error.value)


def test_rejects_non_utf8_without_echoing_bytes(tmp_path):
    module = attack_master()
    path = write_master(tmp_path, "## Requirements\n")
    path.write_bytes(b"private-token\xff")
    with pytest.raises(module.MasterSupportError) as error:
        module.master_support(tmp_path, CAPABILITY, REQUIREMENT)
    assert error.value.reason == "unreadable"
    assert "private-token" not in str(error.value) and str(tmp_path) not in str(error.value)


@pytest.mark.parametrize("capability", ["../private-token", "/private-token", r"C:\private-token",
                                        r"C:private-token", r"\\host\private-token", "..", "shared-input/../secret"])
def test_rejects_unsafe_identifiers_before_reading(tmp_path, monkeypatch, capability):
    module = attack_master()
    def fail_if_read(path):
        pytest.fail("an unsafe support reached file reading")
    monkeypatch.setattr(Path, "read_bytes", fail_if_read)
    with pytest.raises(module.MasterSupportError) as error:
        module.master_support(tmp_path, capability, REQUIREMENT)
    assert error.value.reason == "outside"
    assert capability not in str(error.value)


@pytest.mark.parametrize("capability", ["identity/shared-input", r"identity\shared-input"])
def test_resolves_nested_capabilities_and_writes_canonical_identifier(tmp_path, capability):
    module = attack_master()
    path = tmp_path / "openspec/specs/identity/shared-input/spec.md"
    path.parent.mkdir(parents=True)
    path.write_bytes((FIXTURE / MASTER_RELATIVE).read_bytes())
    support = module.master_support(tmp_path, capability, REQUIREMENT, SCENARIO)
    assert support["capability"] == "identity/shared-input"
    assert support["sha256"] == "21e0ae402bb9b519e1eaf2fedf8dec0fd1177ab0275f83fd9f990f5a8f180063"


@pytest.mark.parametrize("capability", ["identity//shared-input", "identity/./shared-input", "identity/../shared-input",
                                        "identity/", r"identity\..\shared-input"])
def test_rejects_noncanonical_nested_components_before_reading(tmp_path, monkeypatch, capability):
    module = attack_master()
    def fail_if_read(path):
        pytest.fail("an invalid nested capability reached file reading")
    monkeypatch.setattr(Path, "read_bytes", fail_if_read)
    with pytest.raises(module.MasterSupportError) as error:
        module.master_support(tmp_path, capability, REQUIREMENT)
    assert error.value.reason == "outside"


@pytest.mark.parametrize("location", ["specs", "capability", "file"])
def test_rejects_symlink_escape_before_opening_external_file(tmp_path, monkeypatch, location):
    module = attack_master()
    planning = tmp_path / "planning"
    external = tmp_path / "external"
    outside_file = write_master(external, "private-token")
    master = planning / MASTER_RELATIVE
    if location == "specs":
        link, target = planning / "openspec/specs", external / "openspec/specs"
    elif location == "capability":
        link, target = master.parent, outside_file.parent
    else:
        link, target = master, outside_file
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(target, target_is_directory=location != "file")
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error.winerror or error.errno}")
    def fail_if_read(path):
        pytest.fail("an external file reached file reading")
    monkeypatch.setattr(Path, "read_bytes", fail_if_read)
    with pytest.raises(module.MasterSupportError) as error:
        module.master_support(planning, CAPABILITY, REQUIREMENT)
    assert error.value.reason == "outside"
    assert "private-token" not in str(error.value) and str(external) not in str(error.value)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction")
@pytest.mark.parametrize("location", ["specs", "capability"])
def test_rejects_windows_junction_escape_before_opening_external_file(tmp_path, monkeypatch, location):
    module = attack_master()
    planning = tmp_path / "planning"
    external = tmp_path / "external"
    outside_file = write_master(external, "private-token")
    if location == "specs":
        link, target = planning / "openspec/specs", external / "openspec/specs"
    else:
        link, target = planning / MASTER_RELATIVE.parent, outside_file.parent
    link.parent.mkdir(parents=True)
    created = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
                             capture_output=True)
    assert created.returncode == 0, "junction creation failed"
    def fail_if_read(path):
        pytest.fail("a junction target reached file reading")
    monkeypatch.setattr(Path, "read_bytes", fail_if_read)
    try:
        with pytest.raises(module.MasterSupportError) as error:
            module.master_support(planning, CAPABILITY, REQUIREMENT)
        assert error.value.reason == "outside"
        assert str(external) not in str(error.value)
    finally:
        os.rmdir(link)


def test_reports_missing_file_and_read_failure_without_paths(tmp_path, monkeypatch):
    module = attack_master()
    with pytest.raises(module.MasterSupportError) as error:
        module.master_support(tmp_path, CAPABILITY, REQUIREMENT)
    assert error.value.reason == "missing"
    write_master(tmp_path, "## Requirements\n### Requirement: Stable input\nBody.\n")
    def denied(path):
        raise PermissionError("private-token " + str(path))
    monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises(module.MasterSupportError) as error:
        module.master_support(tmp_path, CAPABILITY, REQUIREMENT)
    assert error.value.reason == "unreadable"
    assert "private-token" not in str(error.value) and str(tmp_path) not in str(error.value)


def test_metadata_digest_changes_when_only_block_whitespace_changes(tmp_path):
    module = attack_master()
    path = write_master(tmp_path, (FIXTURE / MASTER_RELATIVE).read_text(encoding="utf-8"))
    before = module.master_support(tmp_path, CAPABILITY, REQUIREMENT, SCENARIO)
    path.write_bytes(path.read_bytes().replace(b"the original value", b"the  original value"))
    after = module.master_support(tmp_path, CAPABILITY, REQUIREMENT, SCENARIO)
    assert before["sha256"] != after["sha256"]


def test_metadata_digest_ignores_neighboring_requirement_and_scenario(tmp_path):
    module = attack_master()
    path = write_master(tmp_path, (FIXTURE / MASTER_RELATIVE).read_text(encoding="utf-8"))
    before = module.master_support(tmp_path, CAPABILITY, REQUIREMENT, SCENARIO)
    path.write_bytes(path.read_bytes().replace(b"an independent value", b"another independent value")
                     .replace(b"its own behavior", b"different behavior"))
    assert module.master_support(tmp_path, CAPABILITY, REQUIREMENT, SCENARIO) == before


@pytest.mark.parametrize("payload", [
    "null", "{}", '["private-token"]', '[{"capability":"private-token"}]',
    '[{"capability":"shared-input","requirement":"Stable input","sha256":"bad-private-token"}]',
    '[{"capability":"shared-input","requirement":"Stable input","scenario":null,"sha256":"' + "a" * 64 + '"}]',
    '[{"capability":"shared-input","capability":"private-token","requirement":"Stable input","sha256":"' + "a" * 64 + '"}]',
    '[\n{"capability":"shared-input"}]',
])
def test_rejects_invalid_metadata_without_raw_diagnostics(payload):
    module = attack_master()
    with pytest.raises(module.MasterSupportError) as error:
        module.parse_master_supports(payload)
    assert error.value.reason == "invalid"
    assert "private-token" not in str(error.value) and payload not in str(error.value)


def test_rejects_duplicate_supports_and_retains_record_number():
    module = attack_master()
    support = {"capability": CAPABILITY, "requirement": REQUIREMENT, "sha256": "a" * 64}
    with pytest.raises(module.MasterSupportError) as error:
        module.parse_master_supports(json.dumps([support, support]))
    assert error.value.reason == "ambiguous" and error.value.index == 2


@pytest.mark.parametrize("text", ["# No frontmatter\n", "---\nstatus: passed\n",
    "---\nmaster_supports: []\nmaster_supports: []\n---\n",
    "---\nmaster_supports:\n  - private-token\n---\n"])
def test_writer_refuses_ambiguous_frontmatter_without_raw_diagnostics(text):
    module = attack_master()
    with pytest.raises(module.MasterSupportError) as error:
        module.set_master_supports(text, [])
    assert error.value.reason in ("invalid", "ambiguous")
    assert "private-token" not in str(error.value)


def test_validates_metadata_and_normalizes_digest_without_mutating_input():
    module = attack_master()
    support = {"capability": CAPABILITY, "requirement": REQUIREMENT, "sha256": "A" * 64}
    assert module.validate_master_support(support) == {**support, "sha256": "a" * 64}
    assert support["sha256"] == "A" * 64
    assert module.parse_master_supports("[]") == []
