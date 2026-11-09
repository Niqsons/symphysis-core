"""Installed-copy execution contexts and the early global bootstrap, without personal profiles."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import shlex
from pathlib import Path

import pytest

from conftest import ROOT, core_files, one_record_journal
import runtime_context

SOURCES = {"journal": "cli/journal.py", "trace": "trace/trace_graph.py", "anchors": "anchors/anchor_refs.py",
           "help": "step-help/step_help.py", "config": "settings/symphysis_config.py"}


def write_json(file, value):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def isolated_env(base):
    names = {"HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "CODEX_HOME",
             "CLAUDE_CONFIG_DIR", "OPENCODE_CONFIG_DIR", "TEMP", "TMP", "TMPDIR"}
    env = {key: value for key, value in os.environ.items() if key.upper() not in names | {"SYMPHYSIS_RUNTIME_CONTEXT"}}
    for name in names:
        folder = base / "profiles" / name.lower()
        folder.mkdir(parents=True, exist_ok=True)
        env[name] = str(folder)
    env.update(OPENSPEC_TELEMETRY="0", OPENSPEC_NO_UPDATE_CHECK="1", PYTHONDONTWRITEBYTECODE="1")
    return env


def installed(base, scope="global", *, legacy=False):
    store = base / "store"
    (store / "openspec" / "changes").mkdir(parents=True)
    runtime = base / "user" / "runtime" if scope == "global" else store / ".symphysis"
    tools = runtime / "tools"
    tools.mkdir(parents=True)
    for source in core_files():
        shutil.copyfile(source, tools / source.name)
    docs = runtime / "docs"
    docs.mkdir()
    (docs / "terms.md").write_text("# Synthetic terms\n", encoding="utf-8")
    schema = (runtime if scope == "global" else store) / "openspec" / "schemas" / "symphysis"
    schema.mkdir(parents=True)
    (schema / "schema.yaml").write_text("name: symphysis\nversion: 1\nartifacts: []\n", encoding="utf-8")
    manifest_file = runtime.parent / "install-manifest.json" if scope == "global" else runtime / "install-manifest.json"
    files = [{"source": "tools/" + file.name, "path": str(file), "purpose": "tool", "sha256": digest(file)} for file in tools.iterdir()]
    files += [{"source": "docs/terms.md", "path": str(docs / "terms.md"), "purpose": "doc", "sha256": digest(docs / "terms.md")},
              {"source": "openspec/schemas/symphysis/schema.yaml", "path": str(schema / "schema.yaml"), "purpose": "schema", "sha256": digest(schema / "schema.yaml")}]
    manifest = {"format": 1, "scope": scope, "generation": "generation-a", "sourceVersion": "0.1.0-fixture",
                "bootstrapApi": 1, "runtimeApi": 1, "schemaApi": 1, "files": files, "clients": []}
    if not legacy:
        write_json(manifest_file, manifest)
    management = manifest_file.parent if not legacy else runtime
    lease_file = management / ".leases" / "fixture-lease.json"
    descriptor = {"file": str(lease_file), "id": "fixture-id", "generation": "legacy-local" if legacy else "generation-a",
                  "token": "c" * 64, "pid": os.getpid(), "startedAt": int(time.time() * 1000), "instance": "fixture-process"}
    record = {"format": 1, "kind": "reader", **{key: value for key, value in descriptor.items() if key != "file"}}
    write_json(lease_file, record)
    context = {"format": 1, "scope": scope, "store": {"root": str(store), "sourceCwd": str(store), "id": None},
               "runtime": {"root": str(runtime), "toolsRoot": str(tools), "docsRoot": str(docs), "schemaRoot": str(schema),
                           "manifestPath": None if legacy else str(manifest_file), "legacy": legacy,
                           "generation": "legacy-local" if legacy else "generation-a", "bootstrapApi": 1, "runtimeApi": 1, "schemaApi": 1},
               "resources": {"tools": {name: str(tools / Path(source).name) for name, source in SOURCES.items()},
                             "docs": {"terms.md": str(docs / "terms.md")}, "skills": {}, "templates": {},
                             "schema": {"name": "symphysis", "path": str(schema)}}, "lease": descriptor}
    return context, manifest, manifest_file, isolated_env(base)


def run_entry(context, env, tool="journal", args=("--help",), *, leased=True):
    env = dict(env)
    if leased:
        env["SYMPHYSIS_RUNTIME_CONTEXT"] = json.dumps(context, ensure_ascii=False)
    return subprocess.run([sys.executable, "-X", "utf8", context["resources"]["tools"][tool], *args],
                          cwd=context["store"]["root"], env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)


@pytest.mark.parametrize("scope,legacy", [("global", False), ("local", False), ("local", True)])
def test_installed_copy_consumes_parent_reader_context_before_runtime_imports(tmp_path, scope, legacy):
    context, _, _, env = installed(tmp_path, scope, legacy=legacy)
    for tool in SOURCES:
        result = run_entry(context, env, tool)
        assert result.returncode == 0, result.stderr
        assert "Коды:" in result.stdout
    assert not list(tmp_path.rglob("__pycache__"))


@pytest.mark.parametrize("bad", ["format", "relative-store", "generation", "token", "pid", "kind", "lease-path", "resource-path", "runtime-api"])
def test_corrupt_context_is_refused_before_imports_or_data_writes(tmp_path, bad):
    context, _, manifest_file, env = installed(tmp_path)
    if bad == "format":
        context["format"] = True
    elif bad == "relative-store":
        context["store"]["root"] = "relative"
    elif bad == "generation":
        context["runtime"]["generation"] = "other-generation"
    elif bad == "token":
        context["lease"]["token"] = "d" * 64
    elif bad == "pid":
        context["lease"]["pid"] += 1
    elif bad == "kind":
        lease_file = Path(context["lease"]["file"])
        record = json.loads(lease_file.read_text(encoding="utf-8"))
        record["kind"] = "writer"
        write_json(lease_file, record)
    elif bad == "lease-path":
        context["lease"]["file"] = str(manifest_file)
    elif bad == "resource-path":
        foreign = tmp_path / "foreign.py"
        foreign.write_text("raise Exception('must not import')\n", encoding="utf-8")
        context["resources"]["tools"]["journal"] = str(foreign)
    elif bad == "runtime-api":
        context["runtime"]["runtimeApi"] = 2
    # Invoke the actual entry even when a forged resource map points elsewhere.
    env["SYMPHYSIS_RUNTIME_CONTEXT"] = json.dumps(context)
    result = subprocess.run([sys.executable, "-X", "utf8", str(Path(context["runtime"]["toolsRoot"]) / "journal.py"), "--help"],
                            cwd=tmp_path / "store", env=env, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2, result.stderr
    assert "symphysis:" in result.stderr and "Traceback" not in result.stderr
    assert not list(tmp_path.rglob("__pycache__"))


@pytest.mark.parametrize("tool", SOURCES)
def test_direct_global_delegates_original_argv_before_runtime_imports(tmp_path, tool):
    node = shutil.which("node")
    assert node, "node required for the installed bootstrap acceptance"
    runtime = tmp_path / "user" / "runtime"
    tools = runtime / "tools"
    tools.mkdir(parents=True)
    entry = tools / Path(SOURCES[tool]).name
    shutil.copyfile(ROOT / SOURCES[tool], entry)
    shutil.copyfile(ROOT / "runtime" / "runtime_context.py", tools / "runtime_context.py")
    capture = tmp_path / "captured.json"
    bootstrap = tmp_path / "bootstrap.mjs"
    bootstrap.write_text('import fs from "node:fs";\nfs.writeFileSync(' + json.dumps(str(capture)) + ', JSON.stringify({args:process.argv.slice(2),cwd:process.cwd()}));\nprocess.exit(7);\n', encoding="utf-8")
    manifest = {"format": 1, "scope": "global", "generation": "fixture", "files": [{"source": "tools/" + entry.name, "path": str(entry), "sha256": digest(entry)}],
                "bootstrap": {"command": node, "args": [str(bootstrap)]}}
    write_json(runtime.parent / "install-manifest.json", manifest)
    write_json(runtime / ".symphysis-runtime.json", {"format": 1, "scope": "global"})
    cwd = tmp_path / "source"
    cwd.mkdir()
    args = ["--arg", "spaces and кириллица", "x&y", "%PATH%", "trailing" + chr(92)]
    result = subprocess.run([sys.executable, "-X", "utf8", str(entry), *args], cwd=cwd, env=isolated_env(tmp_path),
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 7, result.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {"args": ["--project", str(cwd), tool, *args], "cwd": str(cwd)}
    assert not list(tmp_path.rglob("__pycache__"))


@pytest.mark.parametrize("broken", ["missing-manifest", "invalid-manifest", "missing-bootstrap", "relative-bootstrap", "malformed-context"])
def test_direct_global_refuses_broken_managed_installation(tmp_path, broken):
    context, manifest, file, env = installed(tmp_path)
    runtime = Path(context["runtime"]["root"])
    write_json(runtime / ".symphysis-runtime.json", {"format": 1, "scope": "global"})
    if broken == "missing-manifest":
        file.unlink()
    elif broken == "invalid-manifest":
        file.write_text("{broken", encoding="utf-8")
    elif broken == "relative-bootstrap":
        manifest["bootstrap"] = {"command": "node", "args": ["relative.js"]}
        write_json(file, manifest)
    elif broken == "malformed-context":
        env["SYMPHYSIS_RUNTIME_CONTEXT"] = "{broken"
    result = run_entry(context, env, leased=False)
    assert result.returncode == 2, result.stderr
    assert "symphysis:" in result.stderr and "Traceback" not in result.stderr


def test_valid_context_does_not_delegate_again_and_actual_node_owns_the_lease(tmp_path):
    node = shutil.which("node")
    assert node
    context, manifest, manifest_file, env = installed(tmp_path)
    trap = tmp_path / "never-run.mjs"
    trap.write_text("process.exit(91);\n", encoding="utf-8")
    manifest["bootstrap"] = {"command": node, "args": [str(trap)]}
    write_json(manifest_file, manifest)
    source = tmp_path / "node-parent.mjs"
    source.write_text('import {acquireReader} from ' + json.dumps((ROOT / "installer/lib/runtime-leases.js").as_uri()) + ';\n'
                      'import {spawnSync} from "node:child_process";\n'
                      'const context=JSON.parse(process.env.FIXTURE_CONTEXT);context.status="ready";\n'
                      'const lease=acquireReader(context);\n'
                      'try { context.lease=lease.descriptor;\n'
                      'const r=spawnSync(process.env.FIXTURE_PYTHON,["-X","utf8",context.resources.tools.journal,"--help"],'
                      '{cwd:context.store.root,encoding:"utf8",env:{...process.env,SYMPHYSIS_RUNTIME_CONTEXT:JSON.stringify(context)}});\n'
                      'process.stdout.write(JSON.stringify({status:r.status,stdout:r.stdout,stderr:r.stderr}));\n'
                      '} finally {lease.release();}\n', encoding="utf-8")
    env.update(FIXTURE_CONTEXT=json.dumps(context), FIXTURE_PYTHON=sys.executable)
    result = subprocess.run([node, str(source)], cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["status"] == 0, data["stderr"]
    assert "Коды:" in data["stdout"]
    assert len(list(Path(context["lease"]["file"]).parent.iterdir())) == 1, "only the preexisting fixture lease remains"


def test_source_entry_without_context_keeps_existing_mode(tmp_path):
    result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "cli/journal.py"), "--help"], cwd=tmp_path,
                            env=isolated_env(tmp_path), capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("allowlisted", [True, False])
def test_local_absolute_skills_override_requires_owned_manifest_client_root(tmp_path, allowlisted):
    context, manifest, manifest_file, env = installed(tmp_path, "local")
    skills_root = tmp_path / "explicit-skills"
    skill = skills_root / "symphysis-brainstorm" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Synthetic skill\n", encoding="utf-8")
    manifest["files"].append({"source": "skills/symphysis-brainstorm/SKILL.md", "path": str(skill),
                              "purpose": "skill", "sha256": digest(skill), "clientId": "claude"})
    if allowlisted:
        manifest["clients"].append({"id": "claude", "skillsRoot": str(skills_root)})
    write_json(manifest_file, manifest)
    context["resources"]["skills"]["symphysis-brainstorm"] = str(skill)
    result = run_entry(context, env)
    assert result.returncode == (0 if allowlisted else 2), result.stderr


def context_expression(context, env, expression, *, cwd=None):
    child_env = {**env, "SYMPHYSIS_RUNTIME_CONTEXT": json.dumps(context)}
    code = "import sys,json;sys.path.insert(0,sys.argv[1]);import roots,trace_graph;" + expression
    return subprocess.run([sys.executable, "-X", "utf8", "-c", code, context["runtime"]["toolsRoot"]],
                          cwd=cwd or context["store"]["root"], env=child_env, capture_output=True, text=True,
                          encoding="utf-8", timeout=30)


def test_shared_runtime_preserves_two_store_maps_and_root_tokens(tmp_path):
    context, _, _, env = installed(tmp_path)
    runtime = Path(context["runtime"]["root"])
    shared_lease = context["lease"]["file"]
    for index, word in enumerate(("первый", "второй")):
        store = Path(context["store"]["root"]) if index == 0 else tmp_path / "second-store"
        change = store / "openspec" / "changes" / "same-change"
        change.mkdir(parents=True, exist_ok=True)
        source = store / "source"
        source.mkdir()
        (source / "proof.md").write_text(word, encoding="utf-8")
        write_json(store / ".symphysis" / "tools" / "journal-roots.json", {"": "<root>/..", "src/": "<root>/../source"})
        journal = change / "decisions.json"
        write_json(journal, one_record_journal("src/proof.md", word))
        selected = json.loads(json.dumps(context))
        selected["store"] = {"root": str(store), "sourceCwd": str(store), "id": None}
        result = context_expression(selected, env, "print(json.dumps({'root':str(roots.ROOT),'map':{k:str(v) for k,v in roots.default_roots().items()},'trace':str(trace_graph.find_root(roots.Path.cwd()))}))")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert Path(data["root"]) == store / ".symphysis"
        assert Path(data["map"][""]) == store
        assert Path(data["map"]["src/"]) == source
        assert Path(data["trace"]) == store
        assert selected["lease"]["file"] == shared_lease
        checked = run_entry(selected, env, args=("check", str(journal)))
        assert checked.returncode == 0, checked.stderr
        assert "улик сверено 1 из 1" in checked.stdout
    assert not (runtime / "tools" / "journal-roots.json").exists()


def test_context_default_roots_do_not_invent_prefixes_or_use_runtime_parent(tmp_path):
    context, _, _, env = installed(tmp_path)
    store = Path(context["store"]["root"])
    result = context_expression(context, env, "print(json.dumps({k:str(v) for k,v in roots.default_roots().items()}))")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"": str(store)}


def test_explicit_roots_file_uses_the_selected_store_base(tmp_path):
    context, _, _, env = installed(tmp_path)
    store = Path(context["store"]["root"])
    external = tmp_path / "explicit-map.json"
    write_json(external, {"": "<root>/..", "src/": "<root>/../source"})
    result = context_expression(context, env, "print(json.dumps({k:str(v) for k,v in roots.default_roots(roots.Path(" + json.dumps(str(external)) + ")).items()}))")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"": str(store), "src/": str(store / "source")}


@pytest.mark.parametrize("bad", ["invalid-json", "wrong-shape"])
def test_bad_store_map_is_a_visible_refusal_without_runtime_fallback(tmp_path, bad):
    context, _, _, env = installed(tmp_path)
    store = Path(context["store"]["root"])
    change = store / "openspec" / "changes" / "same-change"
    change.mkdir()
    journal = change / "decisions.json"
    write_json(journal, one_record_journal("proof.md", "word"))
    map_file = store / ".symphysis" / "tools" / "journal-roots.json"
    map_file.parent.mkdir(parents=True)
    map_file.write_text("{broken" if bad == "invalid-json" else "[]", encoding="utf-8")
    checked = run_entry(context, env, args=("check", str(journal)))
    assert checked.returncode == 1
    assert "journal-roots.json" in checked.stderr and "Traceback" not in checked.stderr
    assert not (Path(context["runtime"]["root"]) / "tools" / "journal-roots.json").exists()


def test_context_settings_default_project_is_store_even_when_map_has_an_external_default(tmp_path):
    context, _, _, env = installed(tmp_path)
    yaml = pytest.importorskip("yaml", reason="the actual settings read requires PyYAML")
    dependencies = tmp_path / "dependencies"
    shutil.copytree(Path(yaml.__file__).parent, dependencies / "yaml", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    env["PYTHONPATH"] = str(dependencies)
    store = Path(context["store"]["root"])
    other = tmp_path / "other"
    other.mkdir()
    (store / "symphysis.yaml").write_text("edge_probe:\n  enabled: false\n", encoding="utf-8")
    (other / "symphysis.yaml").write_text("edge_probe:\n  enabled: true\n", encoding="utf-8")
    write_json(store / ".symphysis" / "tools" / "journal-roots.json", {"": str(other)})
    result = run_entry(context, env, tool="config", args=())
    assert result.returncode == 0, result.stderr
    assert "краёв выкл" in result.stdout
    refused = run_entry(context, env, tool="config", args=("--project", str(other)))
    assert refused.returncode == 2 and "не совпадает" in refused.stderr


def add_owned_fixture_file(context, manifest, manifest_file, relative, text):
    file = Path(context["runtime"]["root"]) / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")
    manifest["files"].append({"source": relative, "path": str(file), "purpose": "fixture-resource", "sha256": digest(file)})
    write_json(manifest_file, manifest)
    return file


def help_fixture(tmp_path):
    context, manifest, manifest_file, env = installed(tmp_path)
    fork = ROOT / "upstream" / "openspec" / "bin" / "openspec.js"
    assert fork.is_file(), "the pinned fork is required for the global help fixture"
    env["SYMPHYSIS_OPENSPEC"] = str(fork)
    add_owned_fixture_file(context, manifest, manifest_file, "openspec/schemas/symphysis/steps.md",
                           "## intent\nSelected runtime intent\n### Зачем\nRead `symphysis-brainstorm`.\n")
    add_owned_fixture_file(context, manifest, manifest_file, "tools/symphysis-version.txt", "0.1.0+fixture-runtime\n")
    skill = add_owned_fixture_file(context, manifest, manifest_file, "skills/symphysis-brainstorm/SKILL.md", "# Selected skill\n")
    context["resources"]["skills"]["symphysis-brainstorm"] = str(skill)
    return context, manifest, manifest_file, env


def test_global_help_uses_selected_text_version_and_skill_without_project_runtime(tmp_path):
    context, _, _, env = help_fixture(tmp_path)
    result = run_entry(context, env, tool="help", args=())
    assert result.returncode == 0, result.stderr
    help_data = json.loads(result.stdout)
    page = next(page for page in help_data["steps"] if page["id"] == "intent")
    assert page["texts"]["title"] == "Selected runtime intent"
    assert help_data["versions"]["symphysis"] == "0.1.0+fixture-runtime"
    assert page["skills"] == [{"name": "symphysis-brainstorm", "path": "skills/symphysis-brainstorm/SKILL.md", "base": "install"}]
    assert context["runtime"]["root"] not in result.stdout
    assert not (Path(context["store"]["root"]) / ".symphysis" / "tools" / "journal.py").exists()


def test_project_skill_wins_and_explicit_install_dir_only_changes_links(tmp_path):
    context, _, _, env = help_fixture(tmp_path)
    explicit = tmp_path / "explicit-install"
    external_skill = explicit / ".agents" / "skills" / "symphysis-brainstorm" / "SKILL.md"
    external_skill.parent.mkdir(parents=True)
    external_skill.write_text("# Explicit link\n", encoding="utf-8")
    first = run_entry(context, env, tool="help", args=("--install-dir", str(explicit)))
    assert first.returncode == 0, first.stderr
    data = json.loads(first.stdout)
    page = next(page for page in data["steps"] if page["id"] == "intent")
    assert page["skills"] == [{"name": "symphysis-brainstorm", "path": ".agents/skills/symphysis-brainstorm/SKILL.md", "base": "install"}]
    assert page["texts"]["title"] == "Selected runtime intent"
    project_skill = Path(context["store"]["root"]) / ".claude" / "skills" / "symphysis-brainstorm" / "SKILL.md"
    project_skill.parent.mkdir(parents=True)
    project_skill.write_text("# Project link\n", encoding="utf-8")
    second = run_entry(context, env, tool="help", args=("--install-dir", str(explicit)))
    assert second.returncode == 0, second.stderr
    data = json.loads(second.stdout)
    page = next(page for page in data["steps"] if page["id"] == "intent")
    assert page["skills"][0]["base"] == "project"
    assert page["texts"]["title"] == "Selected runtime intent"
    assert data["versions"]["symphysis"] == "0.1.0+fixture-runtime"


def test_global_help_names_a_bad_map_in_visible_current_text(tmp_path):
    context, _, _, env = help_fixture(tmp_path)
    map_file = Path(context["store"]["root"]) / ".symphysis" / "tools" / "journal-roots.json"
    map_file.parent.mkdir(parents=True)
    map_file.write_text("[]", encoding="utf-8")
    result = run_entry(context, env, tool="help", args=())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "journal-roots.json" in data["current_text"]
    assert data["signals"] and data["error"] is None


def html_help(html):
    start = html.index("const HELP = ") + len("const HELP = ")
    return json.JSONDecoder().raw_decode(html[start:])[0]


def test_global_page_rebuild_uses_dispatcher_and_store_even_from_other_cwd(tmp_path):
    context, _, _, env = help_fixture(tmp_path)
    store = Path(context["store"]["root"])
    change = store / "openspec" / "changes" / "same-change"
    change.mkdir()
    journal, out = change / "decisions.json", change / "page.html"
    write_json(journal, one_record_journal("proof.md", "word"))
    unrelated = tmp_path / "other-store"
    (unrelated / "openspec" / "changes" / "same-change").mkdir(parents=True)
    env["SYMPHYSIS_RUNTIME_CONTEXT"] = json.dumps(context)
    result = subprocess.run([sys.executable, "-X", "utf8", context["resources"]["tools"]["journal"],
                             "render-html", str(journal), "--out", str(out)], cwd=unrelated,
                            env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    page = out.read_text(encoding="utf-8")
    snapshot = html_help(page)
    assert shlex.split(snapshot["rebuild"]) == ["symphysis", "--project", ".", "journal", "render-html",
                                               "openspec/changes/same-change/decisions.json", "--out",
                                               "openspec/changes/same-change/page.html"]
    assert str(Path(context["runtime"]["root"])) not in page
    assert not list(unrelated.rglob("page.html"))


def test_unverified_optional_helper_is_not_imported_for_page(tmp_path):
    context, _, _, env = installed(tmp_path, "local")
    helper = Path(context["resources"]["tools"].pop("help"))
    sentinel = tmp_path / "executed.txt"
    helper.write_text("from pathlib import Path\nPath(" + repr(str(sentinel)) + ").write_text('unsafe')\n", encoding="utf-8")
    change = Path(context["store"]["root"]) / "openspec" / "changes" / "same-change"
    journal, out = change / "decisions.json", change / "page.html"
    write_json(journal, one_record_journal("proof.md", "word"))
    result = run_entry(context, env, args=("render-html", str(journal), "--out", str(out)))
    assert result.returncode == 0, result.stderr
    assert "step_help.py" in html_help(out.read_text(encoding="utf-8"))["error"]
    assert not sentinel.exists()


def test_unknown_or_modified_asset_is_rejected_by_python_context(tmp_path):
    context, _, _, env = installed(tmp_path, "local")
    file = Path(context["runtime"]["toolsRoot"]) / "mermaid.min.js"
    file.write_text("// unregistered executable", encoding="utf-8")
    context["resources"]["assets"] = {"mermaid": str(file)}
    result = run_entry(context, env)
    assert result.returncode == 2 and "manifest" in result.stderr


def test_shared_runtime_freeze_and_anchors_use_addressed_store_not_cwd(tmp_path):
    context, _, _, env = installed(tmp_path)
    env["SYMPHYSIS_OPENSPEC"] = str(ROOT / "upstream/openspec/bin/openspec.js")
    first = Path(context["store"]["root"])
    second = tmp_path / "another-store"
    first_master = None
    for store in (first, second):
        change = store / "openspec/changes/same-change"
        (change / "specs/demo").mkdir(parents=True)
        (change / "intent.md").write_text("Synthetic change\n", encoding="utf-8")
        (change / "tasks.md").write_text("- [x] 1.1 `demo`: «First»\n", encoding="utf-8")
        write_json(change / "decisions.json", one_record_journal("src/proof.md", "word"))
        (store / "source").mkdir()
        (store / "source/proof.md").write_text("word\n", encoding="utf-8")
        write_json(store / ".symphysis/tools/journal-roots.json", {"": "<root>/..", "src/": "<root>/../source"})
        block = "### Requirement: Example\nThe tool SHALL work (F-01).\n\n#### Scenario: First\n- **WHEN** used\n- **THEN** it works\n"
        (change / "specs/demo/spec.md").write_text("## ADDED Requirements\n\n" + block, encoding="utf-8")
        master = store / "openspec/specs/demo/spec.md"
        master.parent.mkdir(parents=True)
        master.write_text("# demo\n\n## Requirements\n\n" + block, encoding="utf-8")
        selected = {**context, "store": {"root": str(store), "sourceCwd": str(store), "id": None}}
        child_env = {**env, "SYMPHYSIS_RUNTIME_CONTEXT": json.dumps(selected)}
        other_cwd = second if store == first else first
        other_cwd.mkdir(exist_ok=True)
        frozen = subprocess.run([sys.executable, "-X", "utf8", selected["resources"]["tools"]["trace"], "freeze", "same-change"],
                                cwd=other_cwd, env=child_env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert frozen.returncode == 0, frozen.stderr
        graph = json.loads((change / "graph/req-graph.json").read_text(encoding="utf-8"))
        assert {entry["prefix"] for entry in graph["roots"]} == {"", "src/"}
        anchored = subprocess.run([sys.executable, "-X", "utf8", selected["resources"]["tools"]["anchors"], "same-change"],
                                  cwd=other_cwd, env=child_env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert anchored.returncode == 0, anchored.stderr
        assert "same-change/F-01" in master.read_text(encoding="utf-8")
        if store == first:
            first_master = master.read_bytes()
        else:
            assert (first / "openspec/specs/demo/spec.md").read_bytes() == first_master
    assert not (Path(context["runtime"]["root"]) / "openspec/changes").exists()


@pytest.mark.skipif(os.name != "nt", reason="CPython Windows venv redirector")
@pytest.mark.parametrize("bad", [None, "parent-pid", "parent-image", "owner-image", "reused-pid", "birth-order", "missing-launcher", "missing-venv"])
def test_only_declared_live_windows_venv_redirector_can_be_between_child_and_lease(tmp_path, monkeypatch, bad):
    executable = tmp_path / "venv/Scripts/python.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"fixture executable path")
    config = tmp_path / "venv/pyvenv.cfg"
    config.write_text("home = fixture\n", encoding="utf-8")
    dispatcher = tmp_path / "node.exe"
    dispatcher.write_bytes(b"fixture dispatcher path")
    owner_pid = os.getppid() + 100000
    lease = {"pid": owner_pid, "startedAt": 10000}
    selected = {"launcher": {"kind": "python", "executable": str(executable), "dispatcherExecutable": str(dispatcher)}}
    records = {owner_pid: {"parent": 0, "image": str(dispatcher), "created": 10000},
               os.getppid(): {"parent": owner_pid, "image": str(executable), "created": 11000},
               os.getpid(): {"parent": os.getppid(), "image": "base interpreter", "created": 12000}}
    if bad == "parent-pid":
        records[os.getppid()]["parent"] += 1
    elif bad == "parent-image":
        records[os.getppid()]["image"] = str(dispatcher)
    elif bad == "owner-image":
        records[owner_pid]["image"] = str(executable)
    elif bad == "reused-pid":
        records[owner_pid]["created"] = 12000
    elif bad == "birth-order":
        records[os.getppid()]["created"] = 13000
    elif bad == "missing-launcher":
        selected.clear()
    elif bad == "missing-venv":
        config.unlink()
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(runtime_context, "_windows_process", records.__getitem__)
    assert runtime_context._leased_parent(selected, lease) is (bad is None)


def test_global_context_preserves_retired_flat_map_and_its_root_token(tmp_path):
    context, _, _, env = installed(tmp_path)
    store = Path(context["store"]["root"])
    flat_map = store / "tools/journal-roots.json"
    write_json(flat_map, {"": "<root>", "src/": "<root>/source"})
    before = flat_map.read_bytes()
    source = store / "source/proof.md"
    source.parent.mkdir()
    source.write_text("flat proof\n", encoding="utf-8")
    journal = store / "openspec/changes/same-change/decisions.json"
    write_json(journal, one_record_journal("src/proof.md", "flat proof"))
    checked = run_entry(context, env, args=("check", str(journal)))
    assert checked.returncode == 0, checked.stderr
    assert "улик сверено 1 из 1" in checked.stdout
    roots = context_expression(context, env, "print(json.dumps({'root':str(roots.ROOT),'path':str(roots.ROOTS_PATH)}))")
    assert roots.returncode == 0, roots.stderr
    assert json.loads(roots.stdout) == {"root": str(store), "path": str(flat_map)}
    assert flat_map.read_bytes() == before
    assert not (store / ".symphysis/tools/journal-roots.json").exists()


def test_bad_canonical_map_does_not_fall_back_to_valid_retired_flat_map(tmp_path):
    context, _, _, env = installed(tmp_path)
    store = Path(context["store"]["root"])
    write_json(store / "tools/journal-roots.json", {"": "<root>"})
    write_json(store / ".symphysis/tools/journal-roots.json", [])
    journal = store / "openspec/changes/same-change/decisions.json"
    write_json(journal, one_record_journal("proof.md", "word"))
    checked = run_entry(context, env, args=("check", str(journal)))
    assert checked.returncode == 1 and "journal-roots.json" in checked.stderr
    assert "Traceback" not in checked.stderr
