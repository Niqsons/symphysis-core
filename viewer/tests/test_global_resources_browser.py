"""Global pages remain autonomous under the existing CSP in an isolated headless browser."""
import copy
import json
import os
import subprocess
from pathlib import Path

import pytest
from conftest import one_record_journal
import viewer_render
from test_global_resources import HOSTILE, SIMPLE, TEMPLATE, resource_fixture
from test_viewer_browser import MERMAID, browser, pytestmark


def write_global_page(state, hostile=False):
    journal = one_record_journal("a.md", "fixture")
    if hostile:
        journal["intro"] = HOSTILE
        journal["records"][0]["question"] = HOSTILE
    html = viewer_render.render_html(journal, TEMPLATE, scheme=SIMPLE, help_snapshot=state["snapshot"],
                                     resource_context=state["selected"])
    out = state["store"] / "openspec" / "changes" / "demo" / "symphysis.html"
    out.parent.mkdir(parents=True)
    out.write_text(html, encoding="utf-8")
    return out


def test_global_base64_loader_uses_utf8_and_needs_no_runtime_files_during_browser_load(tmp_path):
    prefix = "if ('кир' !== String.fromCharCode(1082,1080,1088)) throw new Error('UTF8_RESOURCE_FAILED');\n"
    state = resource_fixture(tmp_path, prefix.encode("utf-8") + MERMAID.read_bytes())
    out = write_global_page(state, hostile=True)
    # The diagram and skill body must work after their original files have gone away.
    state["js"].unlink()
    state["license"].unlink()
    state["skill"].unlink()
    result = browser(out, "panel", "theme:light", "tab:help")
    assert result["state"] == "svg" and result["total"] == 2
    assert result["errors"] == [] and result["csp"] == []
    assert result["http"] == [] and result["blocked"] == []
    assert all("mermaid.min.js" not in url for url in result["files"])
    assert HOSTILE in result["help"]["text"]
    assert result["help"]["foreign"] == 0


def test_global_missing_asset_has_explicit_fallback_text_and_cannot_load_local_library(tmp_path):
    state = resource_fixture(tmp_path, MERMAID.read_bytes())
    state["js"].unlink()
    local = state["store"] / ".symphysis" / "tools" / "mermaid.min.js"
    local.parent.mkdir(parents=True)
    local.write_text("throw new Error('LOCAL_LIBRARY_EXECUTED');\n", encoding="utf-8")
    result = browser(write_global_page(state), "panel", "layout:snapshot", "layout:journal")
    assert result["state"] == "text" and result["hasSvg"] is False
    assert "начало" in result["text"]
    assert any("выбранной global-поставки" in message for message in result["messages"])
    assert result["errors"] == [] and result["http"] == []
    assert all("mermaid.min.js" not in url for url in result["files"])


def test_same_change_in_two_stores_does_not_share_unsubmitted_words(tmp_path):
    first = resource_fixture(tmp_path / "first", MERMAID.read_bytes())
    second = resource_fixture(tmp_path / "second", MERMAID.read_bytes())
    # Both stores use the very same selected generation and resources.
    second["selected"] = {**copy.deepcopy(first["selected"]), "store": {"root": str(second["store"])}}
    one, two = write_global_page(first), write_global_page(second)
    hidden = browser(one, "choose:F-01:A", "word:F-01:первое невнесённое слово", f"open:{two}")
    assert "первое невнесённое слово" not in hidden["out"]
    assert hidden["chosen"] == []
    restored = browser(one, "choose:F-01:A", "word:F-01:первое невнесённое слово", f"open:{two}", f"open:{one}")
    assert "первое невнесённое слово" in restored["out"]
    assert restored["errors"] == []


def test_rebuilt_page_preserves_word_after_global_generation_update(tmp_path):
    state = resource_fixture(tmp_path, MERMAID.read_bytes())
    out = write_global_page(state)
    before = out.read_bytes()
    state["manifest"]["generation"] = "updated-fixture-generation"
    state["manifest_path"].write_text(json.dumps(state["manifest"]), encoding="utf-8")
    state["selected"]["runtime"]["generation"] = "updated-fixture-generation"
    state["snapshot"]["versions"]["symphysis"] = "updated-fixture-version"
    write_global_page({**state, "store": tmp_path / "updated-page"})
    updated = tmp_path / "updated-page" / "openspec" / "changes" / "demo" / "symphysis.html"
    assert out.read_bytes() == before
    result = browser(out, "choose:F-01:A", "word:F-01:сохранить мой черновик", f"rebuilt:{updated}", "panel", "tab:help")
    assert "сохранить мой черновик" in result["out"]
    assert "updated-fixture-version" in result["help"]["versions"]
    assert result["errors"] == []


@pytest.mark.skipif(os.name != "nt", reason="Windows drive-letter acceptance")
def test_store_and_runtime_on_distinct_drive_letters(tmp_path):
    state = resource_fixture(tmp_path, MERMAID.read_bytes())
    storage = state["runtime"].parent
    subst = str(Path(os.environ["SystemRoot"]) / "System32" / "subst.exe")
    drive = None
    for letter in "ZYXWVUTSRQP":
        candidate = letter + ":"
        if Path(candidate + "/").exists():
            continue
        result = subprocess.run([subst, candidate, str(storage)], capture_output=True)
        if result.returncode == 0:
            drive = candidate
            break
    assert drive is not None, "a free drive alias is required for the acceptance fixture"
    try:
        alias = Path(drive + "/")
        runtime = alias / "runtime"
        for entry in state["manifest"]["files"]:
            entry["path"] = str(runtime / entry["source"])
        manifest_file = alias / "install-manifest.json"
        manifest_file.write_text(json.dumps(state["manifest"]), encoding="utf-8")
        state["selected"]["runtime"].update(root=str(runtime), toolsRoot=str(runtime / "tools"), manifestPath=str(manifest_file))
        state["selected"]["resources"]["skills"]["symphysis-brainstorm"] = str(runtime / "skills/symphysis-brainstorm/SKILL.md")
        assert Path(state["selected"]["runtime"]["root"]).drive != state["store"].drive
        out = write_global_page(state)
        html = out.read_text(encoding="utf-8")
        assert drive + "/" not in html and drive + chr(92) not in html
        result = browser(out, "panel", "tab:help")
        assert result["state"] == "svg" and result["total"] == 2
        assert HOSTILE in result["help"]["text"]
        assert result["http"] == [] and result["errors"] == []
    finally:
        mapped = subprocess.run([subst], capture_output=True, text=True, encoding="utf-8")
        own = [line for line in mapped.stdout.splitlines() if line.upper().startswith(drive + chr(92))]
        assert len(own) == 1 and str(storage).casefold() in own[0].casefold()
        removed = subprocess.run([subst, drive, "/D"], capture_output=True)
        assert removed.returncode == 0
