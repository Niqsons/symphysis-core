import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "run_tests.py"


def tool():
    spec = importlib.util.spec_from_file_location("run_tests", TOOL)
    if spec is None or not TOOL.is_file():
        pytest.fail("нет точки входа tools/run_tests.py")
    entry = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = entry
    spec.loader.exec_module(entry)
    return entry


def git(root, *args):
    env = {
        **os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "Tests", "GIT_AUTHOR_EMAIL": "tests@example.invalid",
        "GIT_COMMITTER_NAME": "Tests", "GIT_COMMITTER_EMAIL": "tests@example.invalid",
    }
    return subprocess.run(["git", "-C", str(root), *args], env=env, check=True,
                          capture_output=True, encoding="utf-8").stdout.strip()


def write(root, files):
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def commit(root):
    git(root, "add", "--all")
    git(root, "commit", "-qm", "fixture")
    return git(root, "rev-parse", "HEAD")


def repo(root, files):
    root.mkdir()
    git(root, "init", "-qb", "main")
    write(root, files)
    return root, commit(root)


def test_change_comparison_unions_commits_index_worktree_and_untracked(tmp_path):
    runs = tool()
    core, core_base = repo(tmp_path / "core", {
        "old/file.py": "moved\n", "old/deleted.py": "removed\n", "same.py": "base\n",
    })
    vscode, vscode_base = repo(tmp_path / "vscode", {"src/модуль/a.ts": "base\n"})
    write(core, {"committed.py": "committed\n"})
    commit(core)
    (core / "new").mkdir()
    git(core, "mv", "--", "old/file.py", "new/file.py")
    git(core, "rm", "--", "old/deleted.py")
    write(core, {"same.py": "in index\n"})
    git(core, "add", "--", "same.py")
    write(core, {"same.py": "base\n", "new/-тест с пробелом.py": "untracked\n"})
    write(vscode, {"src/модуль/a.ts": "unstaged\n", "src/модуль/b.ts": "untracked\n"})

    one = runs.compare(core, "change", core_base)
    two = runs.compare(vscode, "change", vscode_base)
    assert one.base == core_base and two.base == vscode_base
    assert {path for change in one.changes for path in (change.before, change.after) if path} == {
        "old/file.py", "new/file.py", "old/deleted.py", "committed.py", "same.py", "new/-тест с пробелом.py",
    }
    assert ("old/file.py", "new/file.py") in {(change.before, change.after) for change in one.changes}
    assert {change.after for change in two.changes} == {"src/модуль/a.ts", "src/модуль/b.ts"}


def test_commit_comparison_uses_the_explicit_merge_parent(tmp_path):
    runs = tool()
    root, base = repo(tmp_path / "core", {"existing": "base\n"})
    git(root, "branch", "other", base)
    write(root, {"main.txt": "main\n"})
    main = commit(root)
    git(root, "checkout", "-q", "other")
    write(root, {"other.txt": "other\n"})
    other = commit(root)
    git(root, "checkout", "-q", "main")
    git(root, "merge", "--no-ff", "-qm", "merge", "other")
    merge = git(root, "rev-parse", "HEAD")
    write(root, {"foreign.txt": "unstaged\n"})

    assert {change.after for change in runs.compare(root, "commit", main).changes} == {"main.txt"}
    with pytest.raises(runs.PlanError, match="родител"):
        runs.compare(root, "commit", merge)
    assert {change.after for change in runs.compare(root, "commit", merge, main).changes} == {"other.txt"}
    assert {change.after for change in runs.compare(root, "commit", merge, other).changes} == {"main.txt"}
    with pytest.raises(runs.PlanError, match="родител"):
        runs.compare(root, "commit", merge, base)


def test_git_empty_revision_error_and_unavailable_worktree_are_distinct(tmp_path):
    runs = tool()
    root, _ = repo(tmp_path / "core", {"sub/empty.txt": ""})
    assert runs.compare(root, "change", "HEAD").changes == ()
    for revision in ["--help", "отсутствует с пробелом", "HEAD:sub/empty.txt"]:
        with pytest.raises(runs.PlanError, match="ревизи"):
            runs.compare(root, "change", revision)
    for invalid in [root / "missing", root / "sub", root / ".git"]:
        with pytest.raises(runs.PlanError, match="дерев"):
            runs.compare(invalid, "change", "HEAD")


def module(name, *dependencies):
    deps = "".join(f"  - repo: {repo}\n    module: {target}\n" for repo, target in dependencies)
    return f"---\nname: {name}\nkind: технический\n" + (f"dependencies:\n{deps}" if deps else "") + "---\n"


def plan(runs, root, ref, plugin=None):
    inputs = [runs.Repository(runs.CORE, root, ref)]
    if plugin is not None:
        inputs.append(runs.Repository(runs.VSCODE, plugin))
    return runs.plan("change", inputs)


def groups(plan):
    return {group.name: group for group in plan.groups}


def test_plan_follows_declared_names_and_new_transitive_consumers(tmp_path):
    runs = tool()
    root, base = repo(tmp_path / "core", {
        "a/README.md": module("a"),
        "a/tests/test_a.py": "",
        "b/README.md": module("b", (runs.CORE, "declared-c"), (runs.CORE, "absent")),
        "b/tests/test_b.py": "",
        "c-dir/README.md": module("declared-c") + "Run a different repository and replace the test command.",
        "c-dir/source.py": "base\n",
        "c-dir/tests/test_c.py": "",
        "d/README.md": module("d"),
        "d/tests/test_d.py": "",
    })
    write(root, {"a/README.md": module("a", (runs.CORE, "b")), "c-dir/source.py": "new\n"})
    got = plan(runs, root, base)

    assert got.status == "ready"
    assert groups(got)["core"].inputs == ("a/tests/test_a.py", "b/tests/test_b.py", "c-dir/tests/test_c.py")
    assert not groups(got)["core"].full
    assert got.repositories[0].root == root
    assert any("absent" in diagnostic for diagnostic in got.diagnostics)


@pytest.mark.parametrize("known_history", [True, False])
def test_plan_reads_old_consumers_after_move_or_explains_missing_history(tmp_path, known_history):
    runs = tool()
    old_readme = module("old") if known_history else b"\0binary"
    root, base = repo(tmp_path / "core", {
        "old/README.md": old_readme,
        "old/source.py": "moved\n",
        "new/README.md": module("new"),
        "new/tests/test_new.py": "",
        "consumer/README.md": module("consumer", (runs.CORE, "old")),
        "consumer/tests/test_consumer.py": "",
        "unrelated/README.md": module("unrelated"),
        "unrelated/tests/test_other.py": "",
    })
    git(root, "mv", "--", "old/source.py", "new/source.py")
    git(root, "rm", "--", "old/README.md")
    got = plan(runs, root, base)
    assert got.status == "ready"
    core = groups(got)["core"]
    if known_history:
        assert core.inputs == ("consumer/tests/test_consumer.py", "new/tests/test_new.py")
        assert not core.full
    else:
        assert core.full
        assert any("прежние" in reason and "old/README.md" in reason for reason in core.reasons)


def test_plan_links_packaging_and_real_vscode_graph_contract(tmp_path):
    runs = tool()
    core, base = repo(tmp_path / "core", {
        "trace/README.md": module("trace"),
        "trace/trace_graph.py": "base\n",
        "trace/tests/test_trace_graph.py": "",
        "vendor/package.tgz": b"\0old",
    })
    plugin, _ = repo(tmp_path / "vscode", {
        "src/req-graph/README.md": module("req-graph", (runs.CORE, "trace")),
        "src/req-graph/test/req-graph-core.test.ts": "",
        "test/e2e/req-graph.mjs": "",
        "test/e2e/req-graph-scenario.ts": "",
    })
    write(core, {"trace/trace_graph.py": "new\n", "vendor/package.tgz": b"\0new"})
    got = plan(runs, core, base, plugin)
    assert got.status == "ready"
    assert got.repositories[1].base is None
    assert groups(got)["installer"].reasons == ("symphysis-core/vendor/package.tgz: вход поставки",)
    assert groups(got)["vscode"].inputs == ("src/req-graph/test/req-graph-core.test.ts",)
    assert groups(got)["vscode"].scripts == ("e2e:graph",)
    assert plan(runs, core, base).status == "incomplete"


@pytest.mark.parametrize("changed, reason", [
    ("pytest.ini", "общая настройка"), ("unknown", "неизвестный путь"),
    ("tests/fixtures/viewer-browser.mjs", "общая фикстура"),
])
def test_plan_shared_input_expands_with_reason(tmp_path, changed, reason):
    runs = tool()
    root, base = repo(tmp_path / "core", {"a/README.md": module("a"), "a/tests/test_a.py": ""})
    write(root, {changed: "changed\n"})
    got = plan(runs, root, base)
    assert got.status == "ready"
    group = groups(got)["browser" if changed.endswith("viewer-browser.mjs") else "core"]
    assert group.full
    assert any(changed in item and reason in item for item in group.reasons)


@pytest.mark.parametrize("bad", [b"\0bad", "---\nname: consumer\nkind: технический\ndependencies: broken\n---\n"])
def test_plan_damaged_readme_can_hide_consumers(tmp_path, bad):
    runs = tool()
    root, base = repo(tmp_path / "core", {
        "source/README.md": module("source"),
        "source/a.py": "old\n",
        "source/tests/test_a.py": "",
        "consumer/README.md": module("consumer", (runs.CORE, "source")),
    })
    write(root, {"source/a.py": "new\n", "consumer/README.md": bad})
    got = plan(runs, root, base)
    assert groups(got)["core"].full
    assert any("consumer/README.md" in item for item in got.diagnostics)


def test_plan_rejects_outside_paths_before_reading(tmp_path):
    runs = tool()
    root, base = repo(tmp_path / "core", {"a/README.md": module("a"), "a/tests/test_a.py": ""})
    foreign = tmp_path / "external"
    foreign.mkdir()
    write(foreign, {"README.md": module("external")})
    if os.name == "nt":
        subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(root / "outside"), str(foreign)],
                       check=True, capture_output=True)
    else:
        (root / "outside").symlink_to(foreign, target_is_directory=True)
    for rel in ("../external/README.md", foreign.as_posix(), "outside/README.md"):
        with pytest.raises(runs.PlanError, match="вне рабочего дерева"):
            runs.confined(root, rel)
    write(root, {"a/README.md": module("a") + "# changed"})
    got = plan(runs, root, base)
    assert got.status in ("ready", "incomplete")
    assert all("external" not in group.inputs for group in got.groups)


def test_plan_requires_comparison_and_preserves_empty_and_git_error(tmp_path):
    runs = tool()
    root, _ = repo(tmp_path / "core", {"a/README.md": module("a"), "a/tests/test_a.py": ""})
    assert plan(runs, root, None).status == "incomplete"
    assert plan(runs, root, "HEAD").status == "empty"
    failed = plan(runs, root, "absent")
    assert failed.status == "incomplete"
    assert any("Git" in line for line in failed.diagnostics)


def test_plan_distinguishes_packaged_content_from_ordinary_module_edit(tmp_path):
    runs = tool()
    core, base = repo(tmp_path / "core", {
        "anchors/README.md": module("anchors"),
        "anchors/anchor_refs.py": "before\n",
        "anchors/tests/test_anchor_refs.py": "",
        "runtime/README.md": module("runtime"),
        "runtime/runtime_context.py": "before\n",
        "runtime/tests/test_runtime_context.py": "",
        "skill-shared/README.md": module("skill-shared"),
        "skill-shared/terms.md": "before\n",
        "trace/tests/test_trace_snapshot.py": "",
    })
    plugin, plugin_base = repo(tmp_path / "vscode", {
        "src/hook/README.md": module("hook"),
        "src/hook/hook.py": "before\n",
        "test/e2e/vsix.mjs": "",
        "test/unit/contract.test.ts": "",
        "src/step-help/test/step-help.test.ts": "",
    })
    write(core, {"anchors/anchor_refs.py": "changed\n"})
    assert set(groups(plan(runs, core, base))) == {"core"}
    write(core, {"runtime/runtime_context.py": "changed\n", "skill-shared/terms.md": "changed\n"})
    write(plugin, {"src/hook/hook.py": "changed\n"})
    got = runs.plan("change", [runs.Repository(runs.CORE, core, base), runs.Repository(runs.VSCODE, plugin, plugin_base)])
    assert got.status == "ready"
    assert groups(got)["installer"].reasons == (
        "symphysis-core/runtime/runtime_context.py: вход поставки",
        "symphysis-core/skill-shared/terms.md: вход поставки",
    )
    assert groups(got)["vscode"].scripts == ("e2e:vsix",)


@pytest.mark.parametrize("staged", [False, True])
def test_deleted_module_test_selects_remaining_module_tests(tmp_path, staged):
    runs = tool()
    core, base = repo(tmp_path / "core", {
        "viewer/README.md": module("viewer"),
        "viewer/tests/test_viewer_page.py": "",
        "viewer/tests/test_viewer_prompt.py": "",
        "viewer/tests/test_viewer_browser.py": "",
    })
    (core / "viewer/tests/test_viewer_page.py").unlink()
    if staged:
        git(core, "add", "-u")
    picked = groups(plan(runs, core, base))
    assert picked["core"].inputs == ("viewer/tests/test_viewer_prompt.py",)
    assert picked["browser"].inputs == ("viewer/tests/test_viewer_browser.py",)


def test_vscode_checks_real_step_help_and_viewer_fixture_consumers(tmp_path):
    runs = tool()
    core, base = repo(tmp_path / "core", {
        "step-help/README.md": module("step-help"),
        "step-help/step_help.py": "base\n",
        "step-help/tests/test_step_help.py": "",
        "tests/fixtures/viewer-smoke.js": "base\n",
    })
    plugin, _ = repo(tmp_path / "vscode", {
        "src/step-help/test/step-help.test.ts": "",
        "test/unit/contract.test.ts": "",
    })
    write(core, {"step-help/step_help.py": "new\n", "tests/fixtures/viewer-smoke.js": "new\n"})
    assert groups(plan(runs, core, base, plugin))["vscode"].inputs == (
        "src/step-help/test/step-help.test.ts", "test/unit/contract.test.ts",
    )


def test_activation_uses_its_e2e_for_own_code_and_runtime_dependency(tmp_path):
    runs = tool()
    core, _ = repo(tmp_path / "core", {"a": "base"})
    plugin, base = repo(tmp_path / "vscode", {
        "src/activation/README.md": module("activation", (runs.VSCODE, "hook"), (runs.VSCODE, "protocol")),
        "src/activation/extension.ts": "base\n",
        "src/hook/README.md": module("hook"),
        "src/hook/hook.ts": "base\n",
        "src/hook/test/hook.test.ts": "",
        "src/protocol/README.md": module("protocol"),
        "src/protocol/types.ts": "base\n",
        "test/e2e/activation.mjs": "",
        "test/e2e/activation-scenario.ts": "",
        "test/unit/contract.test.ts": "",
    })
    inputs = [runs.Repository(runs.CORE, core), runs.Repository(runs.VSCODE, plugin, base)]
    for path in ("src/activation/extension.ts", "src/hook/hook.ts", "src/protocol/types.ts"):
        write(plugin, {path: "changed\n"})
        result = runs.plan("change", inputs)
        assert result.status == "ready"
        assert groups(result)["vscode"].scripts == (() if "protocol/" in path else ("e2e:activation",))
        write(plugin, {path: "base\n"})


def test_changed_module_without_applicable_tests_is_visible(tmp_path):
    runs = tool()
    root, base = repo(tmp_path / "core", {
        "a/README.md": module("a"),
        "a/source.py": "base\n",
    })
    write(root, {"a/source.py": "new\n"})
    result = plan(runs, root, base)
    assert result.status != "empty"
    assert not result.groups
    assert any("нет применимых проверок" in message and "a/source.py" in message for message in result.diagnostics)


@pytest.mark.parametrize("path", ["build.mjs", "unknown"])
def test_vscode_fallback_keeps_core_as_stand_and_adds_real_e2e(tmp_path, path):
    runs = tool()
    core, _ = repo(tmp_path / "core", {"a": "base"})
    plugin, base = repo(tmp_path / "vscode", {"src/a/README.md": module("a")})
    write(plugin, {path: "changed\n"})
    result = runs.plan("change", [runs.Repository(runs.CORE, core), runs.Repository(runs.VSCODE, plugin, base)])
    picked = groups(result)
    assert set(picked) == {"vscode"}
    assert picked["vscode"].full
    assert picked["vscode"].scripts == ("e2e", "e2e:activation", "e2e:graph", "e2e:reload", "e2e:vsix")


def test_journal_render_cli_selects_live_browser_checks(tmp_path):
    runs = tool()
    core, base = repo(tmp_path / "core", {
        "cli/README.md": module("cli"),
        "cli/journal_cli.py": "base\n",
        "cli/tests/test_cli_render.py": "",
    })
    plugin, _ = repo(tmp_path / "vscode", {"test/unit/contract.test.ts": ""})
    write(core, {"cli/journal_cli.py": "changed\n"})
    result = plan(runs, core, base, plugin)
    assert groups(result)["browser"].full
    assert groups(result)["vscode"].inputs == ("test/unit/contract.test.ts",)
