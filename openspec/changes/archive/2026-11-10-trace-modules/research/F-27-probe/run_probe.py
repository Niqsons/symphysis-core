"""F-27: read-only source imports; all mutations are in TemporaryDirectory.

Run from the repository: python -I -X utf8 openspec/changes/trace-modules/research/F-27-probe/run_probe.py
The report's OpenSpec validation is replaced in memory, not in product files.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "trace/trace_graph.py").is_file())
sys.path.insert(0, str(ROOT / "trace"))
import trace_graph as tg

OUT = Path(__file__).parent
lines = []


def emit(label, value):
    lines.append(label + ": " + json.dumps(value, ensure_ascii=False, sort_keys=True))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def clean(value, temporary):
    return str(value).replace(str(temporary), "<TEMP>").replace(str(ROOT), "<SOURCE>")


emit("isolation", "Only temporary fixture changed; no install/network/config discovery. validate_findings replaced with [] in memory.")
original_validate = tg.validate_findings
tg.validate_findings = lambda root, change: []
try:
    with tempfile.TemporaryDirectory(prefix="symphysis-f27-") as td:
        temp = Path(td)
        root = temp / "project"
        base = root / "openspec/changes/demo"
        spec = base / "specs/demo/spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("## ADDED Requirements\n\n### Requirement: Requirement\nThe system SHALL work.\n\n#### Scenario: Works\n- **WHEN** invoked\n- **THEN** works\n", encoding="utf-8")
        module = root / "src/module-a"
        module.mkdir(parents=True)
        readme = module / "README.md"
        readme.write_text("---\nname: module-a\nkind: доменный\n---\n", encoding="utf-8")
        (module / "runtime.py").write_text("VALUE = 1\n", encoding="utf-8")
        roots = temp / "fixture-roots.json"
        dump(roots, {"core/": str(root), "external/": str(temp / "absent-external-clone")})
        first = tg.freeze_change(root, "demo", roots)
        snap = base / "graph/req-graph.json"
        baseline = json.loads(snap.read_text(encoding="utf-8"))
        report = (base / "graph/report.md").read_text(encoding="utf-8")
        emit("baseline", {"action": first.action, "format": baseline["format"], "sources": baseline["sources"], "kinds": sorted({n["kind"] for n in baseline["nodes"]}), "check": tg.check_graph_file(root, "demo", snap)})
        emit("missing_external_clone", {"roots": baseline["roots"], "unnamed": first.unnamed, "report_mentions_missing": "Корень `external/` вне git или без каталога: коммит не записан." in report})
        readme.write_text("---\nname: renamed-module\nkind: технический\n---\n", encoding="utf-8")
        emit("README_after_freeze", {"check": tg.check_graph_file(root, "demo", snap), "freeze_action": tg.freeze_change(root, "demo", roots).action, "graph_nodes_unchanged": json.loads(snap.read_text(encoding="utf-8"))["nodes"] == baseline["nodes"], "report_unchanged": (base / "graph/report.md").read_text(encoding="utf-8") == report})
        module.rename(root / "src/moved-module")
        emit("module_move_after_freeze", {"check": tg.check_graph_file(root, "demo", snap), "freeze_action": tg.freeze_change(root, "demo", roots).action, "graph_nodes_unchanged": json.loads(snap.read_text(encoding="utf-8"))["nodes"] == baseline["nodes"]})
        extended = copy.deepcopy(baseline)
        extended["structure_schema"] = {"version": 1, "required": True}
        dump(snap, extended)
        emit("unknown_top_level_field_format2", {"shape": tg._shape_problems(extended), "check": tg.check_graph_file(root, "demo", snap), "freeze_action": tg.freeze_change(root, "demo", roots).action, "field_preserved": "structure_schema" in json.loads(snap.read_text(encoding="utf-8"))})
        extended = copy.deepcopy(baseline)
        extended["nodes"].append({"id": "module:demo", "kind": "module", "name": "module-a", "at": "src/module-a/README.md:1"})
        req = next(n["id"] for n in extended["nodes"] if n["kind"] == "req")
        extended["edges"].append({"from": req, "to": "module:demo", "type": "implements", "at": "fixture:1"})
        dump(snap, extended)
        try:
            tg.diagram_text(extended)
            full = "unexpected success"
        except Exception as exc:
            full = type(exc).__name__ + ": " + str(exc)
        filtered = tg.select_diagram(extended, requirement="demo/Requirement")[0]
        cap_filtered = tg.select_diagram(extended, capability="demo")[0]
        emit("new_kind_format2", {"shape": tg._shape_problems(extended), "check": [clean(s, temp) for s in tg.check_graph_file(root, "demo", snap)], "full_diagram": full, "requirement_kinds": [n["kind"] for n in filtered], "capability_kinds": [n["kind"] for n in cap_filtered]})
        edge_only = copy.deepcopy(baseline)
        edge_only["edges"].append({"from": req, "to": req, "type": "implements", "at": "fixture:1"})
        try:
            tg.diagram_text(edge_only)
        except Exception as exc:
            emit("new_edge_type", type(exc).__name__ + ": " + str(exc))
        formats = {}
        for original in sorted((ROOT / "openspec/changes/archive").glob("*/graph/req-graph.json")):
            data = json.loads(original.read_bytes().decode("utf-8-sig"))
            fmt = str(data.get("format"))
            formats.setdefault(fmt, []).append(original.relative_to(ROOT).as_posix())
        emit("archive_formats", formats)
        for fmt in (1, 2):
            original = ROOT / formats[str(fmt)][0]
            data = json.loads(original.read_bytes().decode("utf-8-sig"))
            archive_copy = temp / ("archive-format-" + str(fmt))
            dump(archive_copy / "graph/req-graph.json", data)
            emit("archive_reader_format" + str(fmt), {"source": original.relative_to(ROOT).as_posix(), "shape": tg._shape_problems(data), "base_capabilities": sorted(tg.saved_base(archive_copy)), "kinds": sorted({n["kind"] for n in data["nodes"]})})
        old = copy.deepcopy(baseline)
        old["format"] = 1
        old["base"] = {"demo": {"Requirement": {"numbers": [99], "scenarios": {}, "text": "x", "traces": []}}}
        dump(snap, old)
        emit("format1_current_check", [clean(s, temp) for s in tg.check_graph_file(root, "demo", snap)])
        rebuilt = tg.freeze_change(root, "demo", roots)
        emit("format1_temporary_freeze", {"action": rebuilt.action, "reason": clean(rebuilt.reason, temp), "result_format": json.loads(snap.read_text(encoding="utf-8"))["format"]})
        emit("module_new_requirement_format2_check", "Current reader rejects extra structural nodes as differing from fresh build; optional unknown top-level fields are silently accepted.")
        sys.path.insert(0, str(ROOT / "viewer"))
        import viewer_render
        import roots as roots_module
        from journal_model import _new_record
        external = temp / "external-fixture"
        external.mkdir()
        (external / "runtime.py").write_text("VALUE = 2\n", encoding="utf-8")
        (root / "local.py").write_text("VALUE = 1\n", encoding="utf-8")
        journal = {"title": "dogfood fixture", "source": "", "records": [_new_record("F-01", "Files `local.py:1` and `external/runtime.py:1`")]}
        mapping = {"": root, "external/": external}
        links = roots_module.file_links(journal, mapping, base, base / "viewer.html")
        template = temp / "template.html"
        template.write_text(" ".join([viewer_render.PLACEHOLDER, viewer_render.PLACEHOLDER_ATTACK, viewer_render.PLACEHOLDER_SCHEME, viewer_render.PLACEHOLDER_HELP, viewer_render.PLACEHOLDER_LINKS]), encoding="utf-8")
        html = viewer_render.render_html(journal, template, links={"root": None, "files": links})
        external.rename(temp / "external-gone")
        missing_links = roots_module.file_links(journal, mapping, base, base / "viewer.html")
        emit("real_requirement_partial_dogfood", {"requirement": "decision-viewer/Файлы на странице показаны ссылками", "modules": ["roots", "viewer"], "links": links, "both_embedded": all(value in html for value in links.values()), "absolute_paths_absent": str(temp) not in html, "missing_external_links": missing_links, "limits": "Uses real file_links/render_html and a synthetic five-marker template; CLI wiring and browser DOM are outside the allowed source area. This is partial implementation evidence, not a new graph relation."})
        captured = {line.split(": ", 1)[0]: json.loads(line.split(": ", 1)[1]) for line in lines}
        emit("compatibility_summary", {"unknown_field_format2": captured["unknown_top_level_field_format2"], "new_kind_shape": captured["new_kind_format2"]["shape"], "new_kind_check_signals": len(captured["new_kind_format2"]["check"]), "full_diagram": full, "requirement_filter": captured["new_kind_format2"]["requirement_kinds"], "capability_filter": captured["new_kind_format2"]["capability_kinds"], "new_edge": captured["new_edge_type"]})
        emit("snapshot_bounds_summary", {"README": captured["README_after_freeze"], "move": captured["module_move_after_freeze"], "missing_external": captured["missing_external_clone"]})
        emit("archive_compatibility_summary", {"counts": {fmt: len(paths) for fmt, paths in formats.items()}, "format1_shape": captured["archive_reader_format1"]["shape"], "format1_base": captured["archive_reader_format1"]["base_capabilities"], "format2_shape": captured["archive_reader_format2"]["shape"], "format2_base": captured["archive_reader_format2"]["base_capabilities"], "temporary_freeze": captured["format1_temporary_freeze"]})
finally:
    tg.validate_findings = original_validate
lines.append("probe_exit: 0")
(OUT / "results.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
