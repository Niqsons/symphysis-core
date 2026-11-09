"""Autonomous global HTML resources: trusted library bytes and untrusted skill text are separate."""
import base64
import copy
import hashlib
import json
from pathlib import Path

import pytest

from conftest import ROOT, one_record_journal
import viewer_render

TEMPLATE = ROOT / "viewer" / "playground-template.html"
SIMPLE = {"exists": True, "text": "flowchart TD\n A[начало] --> B[конец]\n", "blocks": 1, "first_line": 2, "mermaid": "local-must-not-be-used.js"}
HOSTILE = '</script><script>throw new Error("SKILL_EXECUTED")</script><img src="https://example.com/skill">'


def resource_fixture(tmp_path, library=b"/* trusted UTF-8: \xd0\xba\xd0\xb8\xd1\x80 */\nwindow.mermaid={};\n"):
    store = tmp_path / "store"
    (store / "openspec").mkdir(parents=True)
    runtime = tmp_path / "user-data" / "runtime"
    tools = runtime / "tools"
    tools.mkdir(parents=True)
    manifest_path = runtime.parent / "install-manifest.json"
    entries = []

    def owned(source, content):
        file = runtime / source
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content)
        entries.append({"path": str(file), "source": source, "purpose": "tool", "sha256": hashlib.sha256(content).hexdigest()})
        return file

    js = owned("tools/mermaid.min.js", library)
    license_file = owned("tools/mermaid.LICENSE", b"MIT License\nCopyright fixture\n")
    skill = owned("skills/symphysis-brainstorm/SKILL.md", ("# Skill fixture\n" + HOSTILE).encode("utf-8"))
    manifest = {"format": 1, "scope": "global", "generation": "fixture-generation", "files": entries}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    selected = {"scope": "global", "store": {"root": str(store)}, "runtime": {"root": str(runtime), "toolsRoot": str(tools), "manifestPath": str(manifest_path), "generation": "fixture-generation"},
                "resources": {"skills": {"symphysis-brainstorm": str(skill)}}}
    snapshot = viewer_render.no_help_snapshot("unused")
    snapshot.update(error=None, current_step="decisions", steps=[{
        "id": "decisions", "state": "ready", "turn": "model", "optional": False, "files": [], "blocks": [],
        "waits_for": [], "stops_apply": False, "prev": None, "next": None,
        "texts": {"title": "Решения", "why": "Учебная справка", "mechanics": "", "how_to_prepare": "", "if_skipped": "", "what_to_check": "", "command": ""},
        "skills": [{"name": "symphysis-brainstorm", "base": "install", "path": "skills/symphysis-brainstorm/SKILL.md"}],
    }])
    return {"selected": selected, "store": store, "runtime": runtime, "js": js, "license": license_file,
            "skill": skill, "snapshot": snapshot, "manifest": manifest, "manifest_path": manifest_path}


def embed(html, field):
    start = html.index(f"const {field} = ") + len(f"const {field} = ")
    return json.JSONDecoder().raw_decode(html[start:])[0]


def render(state, **kwargs):
    return viewer_render.render_html(one_record_journal("a.md", "fixture"), TEMPLATE, scheme=SIMPLE,
                                     help_snapshot=state["snapshot"], resource_context=state["selected"], **kwargs)


def test_global_library_is_base64_of_verified_bytes_with_license_and_no_runtime_path(tmp_path):
    state = resource_fixture(tmp_path)
    html = render(state)
    diagram = embed(html, "SCHEME")
    assert diagram["mermaid"] is None
    asset = diagram["mermaidData"]
    assert base64.b64decode(asset["data"]) == state["js"].read_bytes()
    assert asset["encoding"] == "base64"
    assert asset["license"] == state["license"].read_text(encoding="utf-8")
    assert str(state["runtime"]) not in html and state["runtime"].as_posix() not in html
    assert "local-must-not-be-used.js" not in html


@pytest.mark.parametrize("bad", ["missing-js", "changed-js", "missing-license", "changed-license", "invalid-utf8", "generation", "foreign-path"])
def test_missing_or_corrupt_selected_resource_has_a_diagnostic_without_other_installation_fallback(tmp_path, bad):
    state = resource_fixture(tmp_path)
    fallback = state["store"] / ".symphysis" / "tools" / "mermaid.min.js"
    fallback.parent.mkdir(parents=True)
    fallback.write_bytes(b"throw new Error('LOCAL_FALLBACK_EXECUTED');\n")
    if bad.startswith("missing-"):
        state["js" if bad.endswith("js") else "license"].unlink()
    elif bad.startswith("changed-"):
        state["js" if bad.endswith("js") else "license"].write_bytes(b"changed bytes")
    elif bad == "invalid-utf8":
        state["js"].write_bytes(b"\xff")
        state["manifest"]["files"][0]["sha256"] = hashlib.sha256(b"\xff").hexdigest()
    elif bad == "generation":
        state["manifest"]["generation"] = "another-generation"
    else:
        state["manifest"]["files"][0]["path"] = str(fallback)
    state["manifest_path"].write_text(json.dumps(state["manifest"]), encoding="utf-8")
    html = render(state)
    asset = embed(html, "SCHEME")["mermaidData"]
    assert asset["data"] is None and "выбранной global-поставки" in asset["error"]
    assert "LOCAL_FALLBACK_EXECUTED" not in html and "local-must-not-be-used.js" not in html


def test_skill_bodies_are_copied_as_data_without_mutating_snapshot_or_borrowing_by_name(tmp_path):
    state = resource_fixture(tmp_path)
    before = copy.deepcopy(state["snapshot"])
    html = render(state)
    payload = embed(html, "HELP")
    body = payload["skill_bodies"][payload["steps"][0]["skills"][0]["body_id"]]
    assert body["text"] == state["skill"].read_text(encoding="utf-8")
    assert HOSTILE in body["text"] and HOSTILE not in html
    assert state["snapshot"] == before
    state["snapshot"]["steps"][0]["skills"][0]["path"] = ".agents/skills/symphysis-brainstorm/SKILL.md"
    unavailable = embed(render(state), "HELP")["skill_bodies"]["skill-0"]
    assert unavailable["text"] is None and unavailable["error"]


def test_project_skill_keeps_priority_and_explicit_install_lookup_only_reads_that_source(tmp_path):
    state = resource_fixture(tmp_path)
    metadata = state["snapshot"]["steps"][0]["skills"][0]
    project_skill = state["store"] / ".claude" / "skills" / "symphysis-brainstorm" / "SKILL.md"
    project_skill.parent.mkdir(parents=True)
    project_skill.write_text("# Project body\n", encoding="utf-8")
    metadata.update(base="project", path=".claude/skills/symphysis-brainstorm/SKILL.md")
    assert embed(render(state), "HELP")["skill_bodies"]["skill-0"]["text"] == "# Project body\n"
    explicit = tmp_path / "explicit-install"
    other_skill = explicit / "other" / "skills" / "symphysis-brainstorm" / "SKILL.md"
    other_skill.parent.mkdir(parents=True)
    other_skill.write_text("# Explicit body\n", encoding="utf-8")
    metadata.update(base="install", path="other/skills/symphysis-brainstorm/SKILL.md")
    assert embed(render(state, skill_install_dir=explicit), "HELP")["skill_bodies"]["skill-0"]["text"] == "# Explicit body\n"


def test_untrusted_scheme_cannot_supply_the_executable_slot_in_local_or_global_mode(tmp_path):
    state = resource_fixture(tmp_path)
    scheme = {**SIMPLE, "mermaidData": {"encoding": "base64", "data": base64.b64encode(b"throw new Error('UNTRUSTED_EXECUTED')").decode()}}
    html = viewer_render.render_html(one_record_journal("a.md", "fixture"), TEMPLATE, scheme=scheme, resource_context=state["selected"])
    assert base64.b64decode(embed(html, "SCHEME")["mermaidData"]["data"]) == state["js"].read_bytes()
    local = viewer_render.render_html(one_record_journal("a.md", "fixture"), TEMPLATE, scheme=scheme, resource_context={"scope": "local"})
    assert "mermaidData" not in embed(local, "SCHEME")
    assert embed(local, "SCHEME")["mermaid"] == SIMPLE["mermaid"]
    malicious = {**SIMPLE, "__proto__": {"mermaidData": scheme["mermaidData"]}}
    prototype = viewer_render.render_html(one_record_journal("a.md", "fixture"), TEMPLATE, scheme=malicious, resource_context={"scope": "local"})
    assert "__proto__" not in embed(prototype, "SCHEME")
