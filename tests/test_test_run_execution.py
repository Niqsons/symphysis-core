import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_test_runs import TOOL, commit, git, module, repo, tool, write


def invoke(*args, cwd=None, env=None):
    return subprocess.run([sys.executable, "-X", "utf8", "-B", str(TOOL), *map(str, args)],
                          capture_output=True, encoding="utf-8", timeout=180, cwd=cwd, env=env)


def test_missing_real_core_input_is_incomplete_before_vscode_build(execution_trees, tmp_path):
    core, _, plugin, _, log = execution_trees
    write(plugin, {
        "test/unit/contract.test.ts": "",
        "test/core-files.mjs": "export function checkCoreFiles() { throw Error('missing core module'); }",
    })
    base = commit(plugin)
    write(plugin, {"test/unit/contract.test.ts": "// change"})
    summary = tmp_path / "report.json"
    result = invoke("run", "change", "--core-root", core, "--vscode-root", plugin,
                    "--vscode-base", base, "--summary", summary)
    assert result.returncode == 2, result.stderr + result.stdout
    assert "missing core module" in result.stderr
    assert not log.exists()
    assert json.loads(summary.read_text(encoding="utf-8"))["groups"][0]["status"] == "incomplete"


def test_missing_e2e_runner_is_incomplete_before_build(execution_trees, tmp_path):
    core, _, plugin, _, log = execution_trees
    write(plugin, {
        "test/e2e/req-graph.mjs": "",
        "test/core-files.mjs": "export function checkCoreFiles() {}",
        "test/worktree-paths.mjs": "",
        "test/e2e/paths.mjs": (
            "import fs from 'node:fs';"
            "export function checkE2ePaths(){"
            "if(!fs.existsSync('test/e2e/req-graph.mjs')) throw Error('test/e2e/req-graph.mjs');}"
        ),
        "package.json": "{}",
    })
    base = commit(plugin)
    (plugin / "test/e2e/req-graph.mjs").unlink()
    summary = tmp_path / "report.json"
    result = invoke("run", "change", "--core-root", core, "--vscode-root", plugin,
                    "--vscode-base", base, "--summary", summary,
                    env={**os.environ, "SYMPHYSIS_CODE": sys.executable})
    assert result.returncode == 2, result.stderr + result.stdout
    assert "test/e2e/req-graph.mjs" in result.stderr
    assert not log.exists()
    assert json.loads(summary.read_text(encoding="utf-8"))["groups"][0]["status"] == "incomplete"


@pytest.fixture
def execution_trees(tmp_path):
    log = tmp_path / "order.jsonl"
    core, core_base = repo(tmp_path / "chosen-core", {
        "a/README.md": module("a"),
        "a/main.py": "before\n",
        "a/tests/test_main.py": f"from pathlib import Path\n\ndef test_main():\n    with Path({str(log)!r}).open('a', encoding='utf-8') as log:\n        log.write('{{\"group\": \"core\"}}\\n')\n",
        "pytest.ini": "[pytest]\nmarkers =\n    browser: Chrome\ntestpaths = a/tests\n",
        "conftest.py": (
            "import json\n"
            "from pathlib import Path\n"
            "def pytest_configure(config):\n"
            "    if hasattr(config, 'workerinput'):\n"
            "        return\n"
            f"    with Path({str(log)!r}).open('a', encoding='utf-8') as log:\n"
            "        log.write(json.dumps({'group':'pytest', 'workers':config.option.numprocesses, "
            "'marker':config.option.markexpr})+'\\n')\n"
            "    config.option.numprocesses = 1\n"
        ),
        "cli/journal.py": "",
        "installer/package.json": json.dumps({"scripts": {"pretest": "node prepare.cjs", "test": "node --test sample.test.cjs"}}),
        "installer/prepare.cjs": f"require('node:fs').appendFileSync({json.dumps(str(log))}, '{{\"group\":\"pretest\"}}\\n');\n",
        "installer/sample.test.cjs": (
            "const {test}=require('node:test');\n"
            "test('installer',()=>{\n"
            "  const p=require('node:child_process').spawnSync('python',['-c','import sys; print(sys.executable)'],{encoding:'utf8'});\n"
            "  if(p.status!==0) throw Error(p.stderr);\n"
            f"  require('node:fs').appendFileSync({json.dumps(str(log))},JSON.stringify({{group:'installer',python:p.stdout.trim()}})+'\\n');\n"
            "});\n"
        ),
    })
    plugin, plugin_base = repo(tmp_path / "vscode", {
        "src/a/README.md": module("a"),
        "src/a/main.ts": "before\n",
        "src/a/test/one.test.ts": "",
        "test/worktree-paths.mjs": "",
        "build.mjs": (
            "import fs from 'node:fs';\n"
            "import path from 'node:path';\n"
            "const args=process.argv.slice(process.argv.indexOf('--')+1);\n"
            "fs.mkdirSync('out/test',{recursive:true});\n"
            "for(const input of args){\n"
            " const name=path.basename(input).replace(/\\.tsx?$/,'.js');\n"
            " fs.writeFileSync(path.join('out/test',name),"
            f" \"require('node:test').test('vscode',()=>require('node:fs').appendFileSync(\"+JSON.stringify({json.dumps(str(log))})+\",JSON.stringify({{group:'vscode',core:process.env.SYMPHYSIS_ROOT}})+'\\\\n'));\");\n"
            "}\n"
        ),
    })
    return core, core_base, plugin, plugin_base, log


def test_run_uses_normal_entry_in_order_and_selected_core(execution_trees, tmp_path):
    core, base, plugin, plugin_base, log = execution_trees
    write(core, {"a/main.py": "after\n", "installer/README.md": "changed\n"})
    write(plugin, {"src/a/main.ts": "after\n"})
    summary = tmp_path / "report.json"
    result = invoke("run", "change", "--core-root", core, "--core-base", base,
                    "--vscode-root", plugin, "--vscode-base", plugin_base, "--summary", summary)
    assert result.returncode == 0, result.stderr + result.stdout
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [event["group"] for event in events] == ["pytest", "core", "pretest", "installer", "vscode"]
    assert events[0] == {"group": "pytest", "workers": 12, "marker": "not browser"}
    assert Path(events[3]["python"]) == Path(sys.executable)
    assert Path(events[4]["core"]) == core
    report = json.loads(summary.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert str(tmp_path) not in summary.read_text(encoding="utf-8")


@pytest.mark.parametrize("browser_status", ["passed", "incomplete", "failed"])
def test_run_browser_starts_after_core_and_before_plugin_without_installer(execution_trees, browser_status):
    core, base, plugin, plugin_base, log = execution_trees
    write(core, {"viewer/README.md": module("viewer"), "viewer/tests/test_viewer_browser.py": (
                     "from pathlib import Path\nimport pytest\n"
                     "@pytest.mark.browser\ndef test_browser():\n"
                     f"    with Path({str(log)!r}).open('a', encoding='utf-8') as log:\n"
                     "        log.write('{\"group\": \"browser\"}\\n')\n"
                 )})
    base = commit(core)
    outcomes = {
        "passed": "# changed\n",
        "incomplete": "    pytest.skip('browser stand unavailable')\n",
        "failed": "    pytest.fail('browser profile cleanup failed')\n",
    }
    write(core, {"a/main.py": "after\n", "viewer/tests/test_viewer_browser.py":
                 (core / "viewer/tests/test_viewer_browser.py").read_text(encoding="utf-8") + outcomes[browser_status]})
    write(plugin, {"src/a/main.ts": "after\n"})
    summary = core.parent / "browser-report.json"
    result = invoke("run", "change", "--core-root", core, "--core-base", base,
                    "--vscode-root", plugin, "--vscode-base", plugin_base, "--summary", summary)
    assert result.returncode == {"passed": 0, "incomplete": 2, "failed": 1}[browser_status], result.stderr + result.stdout
    report = json.loads(summary.read_text(encoding="utf-8"))
    assert report["groups"][1]["status"] == browser_status
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    expected = ["pytest", "core", "pytest", "browser"]
    assert [event["group"] for event in events] == expected + (["vscode"] if browser_status == "passed" else [])
    assert [(event["workers"], event["marker"]) for event in events if event["group"] == "pytest"] == [
        (12, "not browser"), (2, "browser"),
    ]


def test_installer_pretest_failure_stops_before_vscode(execution_trees):
    core, base, plugin, plugin_base, log = execution_trees
    write(core, {"a/main.py": "after\n", "installer/prepare.cjs":
                 (core / "installer/prepare.cjs").read_text(encoding="utf-8") + "process.exit(7);"})
    write(plugin, {"src/a/main.ts": "after\n"})
    summary = core.parent / "report.json"
    result = invoke("run", "change", "--core-root", core, "--core-base", base,
                    "--vscode-root", plugin, "--vscode-base", plugin_base, "--summary", summary)
    assert result.returncode == 1, result.stderr + result.stdout
    report = json.loads(summary.read_text(encoding="utf-8"))
    assert [(group["name"], group["status"]) for group in report["groups"]] == [
        ("core", "passed"), ("installer", "failed"), ("vscode", "not_run"),
    ]
    assert [json.loads(line)["group"] for line in log.read_text(encoding="utf-8").splitlines()] == ["pytest", "core", "pretest"]


@pytest.mark.parametrize("problem", ["test", "skip", "no-tests"])
def test_run_distinguishes_core_failure_skip_and_zero_then_stops(execution_trees, problem):
    core, base, plugin, plugin_base, log = execution_trees
    content = {
        "test": "def test_main():\n    print('PRIVATE_STDOUT')\n    raise RuntimeError('PRIVATE_ERROR')\n",
        "skip": "import pytest\ndef test_main(): pytest.skip('PRIVATE_SKIP')\n",
        "no-tests": "",
    }
    write(core, {"a/tests/test_main.py": content[problem], "installer/README.md": "changed\n"})
    summary = core.parent / "report.json"
    result = invoke("run", "change", "--core-root", core, "--core-base", base, "--summary", summary)
    assert result.returncode != 0
    assert [json.loads(line)["group"] for line in log.read_text(encoding="utf-8").splitlines()] == ["pytest"]
    raw = summary.read_text(encoding="utf-8")
    status = {"test": "failed", "skip": "incomplete", "no-tests": "zero"}[problem]
    assert json.loads(raw)["groups"][0]["status"] == status
    assert "PRIVATE_" not in raw
    assert "PRIVATE_" in result.stdout + result.stderr or problem == "no-tests"


@pytest.mark.parametrize(("has_journal", "reason", "skipped"), [
    (False, "got empty parameter set for (path)", 0),
    (True, "got empty parameter set for (path)", 1),
    (False, "validator dependency unavailable", 1),
])
def test_empty_active_journal_inventory_is_not_a_missing_check(tmp_path, has_journal, reason, skipped):
    changes = tmp_path / "openspec/changes"
    (changes / "archive/example").mkdir(parents=True)
    (changes / "archive/example/decisions.json").write_text("{}", encoding="utf-8")
    if has_journal:
        (changes / "active").mkdir()
        (changes / "active/decisions.json").write_text("{}", encoding="utf-8")
    xml = tmp_path / "result.xml"
    xml.write_text(
        '<testsuite><testcase classname="decisions.tests.test_journal_validator" '
        'name="test_no_journal_of_this_tree_breaks_on_the_new_rule[NOTSET]">'
        f'<skipped message="{reason}" type="pytest.skip" /></testcase></testsuite>',
        encoding="utf-8",
    )
    sys.path.insert(0, str(TOOL.parent))
    try:
        from run_execution import _pytest_counts

        result = _pytest_counts(xml, tmp_path)
    finally:
        sys.path.remove(str(TOOL.parent))

    assert (result.passed, result.failed, result.skipped, result.not_applicable) == (0, 0, skipped, 1 - skipped)


def test_run_reports_worktree_changed_after_the_selection_commit(execution_trees):
    core, _, plugin, _, log = execution_trees
    write(core, {"a/main.py": "selected commit\n"})
    selected = commit(core)
    write(core, {"untracked with spaces": "actual working tree\n"})
    summary = core.parent / "report.json"
    result = invoke("run", "commit", "--core-root", core, "--core-commit", selected, "--summary", summary)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "рабочее дерево с правками" in result.stdout
    report = json.loads(summary.read_text(encoding="utf-8"))
    assert report["repositories"][0]["selected_commit"] == selected
    assert report["repositories"][0]["dirty"]
    assert "untracked with spaces" not in summary.read_text(encoding="utf-8")


def test_run_refuses_existing_output_before_any_test(execution_trees):
    core, base, _, _, log = execution_trees
    write(core, {"a/main.py": "after\n"})
    summary = core.parent / "report.json"
    summary.write_text("other run\n", encoding="utf-8")
    result = invoke("run", "change", "--core-root", core, "--core-base", base, "--summary", summary)
    assert result.returncode == 2
    assert summary.read_text(encoding="utf-8") == "other run\n"
    assert not log.exists()
    existing_logs = core.parent / "existing-logs"
    existing_logs.mkdir()
    result = invoke("run", "change", "--core-root", core, "--core-base", base, "--log-dir", existing_logs)
    assert result.returncode == 2 and not log.exists()


def test_selected_vscode_input_gone_after_planning_is_incomplete(execution_trees):
    core, _, plugin, base, log = execution_trees
    runs = tool()
    write(plugin, {"src/a/main.ts": "after\n", "src/a/test/two.test.ts": ""})
    planned = runs.plan("change", [runs.Repository(runs.CORE, core), runs.Repository(runs.VSCODE, plugin, base)])
    assert len(planned.groups[0].inputs) == 2
    (plugin / "src/a/test/two.test.ts").unlink()
    sys.path.insert(0, str(TOOL.parent))
    try:
        from run_execution import execute

        summary = core.parent / "report.json"
        assert execute(planned, summary) == 2
    finally:
        sys.path.remove(str(TOOL.parent))
    assert not log.exists()
    assert json.loads(summary.read_text(encoding="utf-8"))["groups"][0]["status"] == "incomplete"


def test_full_plan_and_release_require_explicit_worktrees(execution_trees):
    core, _, plugin, _, _ = execution_trees
    result = invoke("plan", "full", "--core-root", core, "--vscode-root", plugin, "--release")
    assert result.returncode == 0, result.stderr + result.stdout
    assert all(f"{name}: полный набор" in result.stdout for name in ("core", "browser", "installer", "vscode"))
    assert "e2e:vsix" in result.stdout
    git(core, "switch", "-qc", "feature")
    result = invoke("plan", "full", "--core-root", core, "--vscode-root", plugin, "--release")
    assert result.returncode == 1 and "main ядра" in result.stdout
    result = invoke("plan", "full", "--vscode-root", plugin)
    assert result.returncode == 1 and "корень symphysis-core" in result.stdout


def test_native_hook_is_an_explicit_manual_check(execution_trees):
    core, _, plugin, base, log = execution_trees
    write(plugin, {"test/e2e/hook-clients.mjs": "throw Error('must not run');"})
    result = invoke("run", "change", "--core-root", core, "--vscode-root", plugin, "--vscode-base", base)
    assert result.returncode == 2 and "ручная проверка npm run e2e:hook" in result.stdout
    assert not log.exists()


def test_full_scope_ignores_inherited_pytest_filter_and_saves_local_logs(execution_trees):
    core, _, _, _, log = execution_trees
    caller = core.parent
    env = {**os.environ, "PYTEST_ADDOPTS": "-k never_matches", "PYTEST_PLUGINS": "no_such_module"}
    result = invoke("run", "full", "--core-root", core, "--log-dir", "logs", "--summary", "report.json",
                    cwd=caller, env=env)
    # The fixture has no browser tests: core still ran and browser reports zero.
    assert result.returncode == 3, result.stdout + result.stderr
    assert [json.loads(line)["group"] for line in log.read_text(encoding="utf-8").splitlines()] == ["pytest", "core", "pytest"]
    assert (caller / "logs/core/pytest.xml").is_file()
    assert (caller / "logs/core/logs/stdout.log").is_file()
    assert not (core / "logs").exists()
    assert json.loads((caller / "report.json").read_text(encoding="utf-8"))["groups"][1]["status"] == "zero"


def test_vscode_report_captures_actual_core_revision_after_prior_group(execution_trees):
    core, base, plugin, plugin_base, _ = execution_trees
    path = core / "a/tests/test_main.py"
    path.write_text(
        path.read_text(encoding="utf-8")
        + f"    (Path({str(core)!r}) / 'created-while-testing').write_text('drift')\n", encoding="utf-8",
    )
    selected = commit(core)
    write(plugin, {"src/a/main.ts": "after\n"})
    plugin_selected = commit(plugin)
    summary = core.parent / "report.json"
    result = invoke("run", "commit", "--core-root", core, "--core-commit", selected,
                    "--vscode-root", plugin, "--vscode-commit", plugin_selected, "--summary", summary)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(summary.read_text(encoding="utf-8"))
    assert report["groups"][0]["repositories"][0]["dirty"] is False
    assert report["groups"][-1]["repositories"][0]["dirty"] is True
    assert "изменился после начала прогона" in result.stdout
