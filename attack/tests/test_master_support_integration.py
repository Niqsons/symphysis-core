"""One portable attack report is consumed by the real fork, journal and step help."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FORK_BIN, ROOT, fork_unavailable, journal_of


FIXTURE = ROOT / "attack/tests/fixtures/master-supports"
CHANGE = "sample"
SCHEMA = """name: support-flow
version: 1
description: Test freshness of a report's declared supports.
artifacts:
  - id: tasks
    generates: tasks.md
    description: Implementation tasks
    template: tasks.md
    requires: []
  - id: attack-artifacts
    generates: attack/artifacts.md
    description: Artifact attack
    template: attack.md
    requires: [tasks]
    optional: true
    verdict:
      frontmatter: status
      value: passed
apply:
  requires: [tasks, attack-artifacts]
  tracks: tasks.md
"""
CASES = (
    ("original", "ok", "ready", None),
    ("sibling", "ok", "ready", None),
    ("master", "stale", "blocked", "openspec/specs/shared-input/spec.md"),
    ("local", "stale", "blocked", "design.md"),
)


def fork_command():
    override = os.environ.get("SYMPHYSIS_TEST_OPENSPEC")
    binary = Path(override) if override else FORK_BIN
    if override:
        assert binary.is_file(), f"SYMPHYSIS_TEST_OPENSPEC does not name a file: {binary}"
    elif reason := fork_unavailable():
        pytest.skip(reason)
    if binary.suffix.lower() in (".js", ".mjs", ".cjs"):
        node = shutil.which("node")
        if node is None:
            pytest.skip("The real OpenSpec integration requires Node.js")
        return [node, str(binary.resolve())], str(binary.resolve())
    return [str(binary.resolve())], str(binary.resolve())


def project(tmp_path, label):
    root = tmp_path / label
    shutil.copytree(FIXTURE, root)
    change = root / "openspec/changes" / CHANGE
    schema = root / "openspec/schemas/support-flow"
    schema.mkdir(parents=True)
    (schema / "schema.yaml").write_text(SCHEMA, encoding="utf-8", newline="\n")
    (root / "openspec/config.yaml").write_text("schema: support-flow\n", encoding="utf-8", newline="\n")
    (change / ".openspec.yaml").write_text("schema: support-flow\n", encoding="utf-8", newline="\n")
    (change / "tasks.md").write_text("- [ ] 1.1 Verify behavior\n- [ ] 1.2 Verify compatibility\n",
                                    encoding="utf-8", newline="\n")
    (change / "decisions.json").write_text(json.dumps(journal_of()), encoding="utf-8", newline="\n")
    return root, change


def run(argv, root, env):
    done = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL, timeout=120)
    assert done.returncode == 0, f"{argv}\nstdout:\n{done.stdout}\nstderr:\n{done.stderr}"
    return done.stdout


def test_master_support_freshness_agrees_across_real_fork_check_and_help(tmp_path):
    command, binary = fork_command()
    report = (FIXTURE / "openspec/changes/sample/attack/artifacts.md").read_bytes()
    report_sha = hashlib.sha256(report).hexdigest()
    selected_support = json.loads(next(line.partition(":")[2] for line in report.decode("utf-8").splitlines()
                                      if line.startswith("master_supports:")))[0]
    assert selected_support["capability"] == "shared-input"
    env = {**os.environ, "SYMPHYSIS_OPENSPEC": binary, "OPENSPEC_TELEMETRY": "0", "OPENSPEC_NO_UPDATE_CHECK": "1",
           "OPENSPEC_NO_COMPLETIONS": "1", "NO_COLOR": "1",
           "XDG_CONFIG_HOME": str(tmp_path / "isolated-config"), "XDG_DATA_HOME": str(tmp_path / "isolated-data")}
    env.pop("SYMPHYSIS_RUNTIME_CONTEXT", None)
    version = run([*command, "--version"], tmp_path, env).strip()
    assert "symphysis" in version, f"Expected a built Symphysis fork, received {version}"
    for label, verdict, apply_state, stale_place in CASES:
        root, change = project(tmp_path, label)
        master = root / "openspec/specs/shared-input/spec.md"
        if label == "sibling":
            master.write_bytes(master.read_bytes().replace(b"independent value", b"different value"))
        elif label == "master":
            master.write_bytes(master.read_bytes().replace(b"original value", b"changed value"))
        elif label == "local":
            with (change / "design.md").open("ab") as output:
                output.write(b"\nChanged local target.\n")
        assert hashlib.sha256((change / "attack/artifacts.md").read_bytes()).hexdigest() == report_sha
        status = json.loads(run([*command, "status", "--change", CHANGE, "--json"], root, env))
        attack = next(artifact for artifact in status["artifacts"] if artifact["id"] == "attack-artifacts")
        assert attack["verdict"] == verdict, (label, status)
        apply = json.loads(run([*command, "instructions", "apply", "--change", CHANGE, "--json"], root, env))
        assert apply["state"] == apply_state, (label, apply)
        blocked_attacks = apply.get("artifactsWithoutPassingVerdict", [])
        assert any(item["id"] == "attack-artifacts" for item in blocked_attacks) == (apply_state == "blocked")
        check = run([sys.executable, "-X", "utf8", str(ROOT / "cli/journal.py"), "check",
                     str(change / "decisions.json")], root, env)
        prefix = "[..] атака артефактов: "
        checked = [line.removeprefix(prefix) for line in check.splitlines() if line.startswith(prefix)]
        helped = json.loads(run([sys.executable, str(ROOT / "step-help/step_help.py"), "--change", CHANGE], root, env))
        assert helped["error"] is None, helped
        page = next(step for step in helped["steps"] if step["id"] == "attack-artifacts")
        assert page["verdict"] == verdict
        assert page["stale_scope"] == checked
        if stale_place is None:
            assert checked == [], (label, checked)
        else:
            assert len(checked) == 1 and stale_place in checked[0], (label, checked)
            assert str(root) not in checked[0]
        assert hashlib.sha256((change / "attack/artifacts.md").read_bytes()).hexdigest() == report_sha
