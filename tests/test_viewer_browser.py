"""Панель схемы на странице в настоящем Chrome: вёрстку, рисунок, CSP и сеть `viewer-smoke.js` без браузера не проверит.
Chrome нет — пропуск с причиной; заданный `SYMPHYSIS_CHROME` без файла — падение, а не пропуск."""
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

import journal
from conftest import FIX, ROOT, one_record_journal

MERMAID = ROOT / "installer" / "node_modules" / "mermaid" / "dist" / "mermaid.min.js"
DRIVER = FIX / "viewer-browser.mjs"
WIDE = (FIX / "scheme" / "wide.md").read_text(encoding="utf-8")
SIMPLE = "# Схема\n\n```mermaid\nflowchart TD\n  A[начало] --> B[конец]\n```\n"
node = shutil.which("node")


def find_chrome():
    named = os.environ.get("SYMPHYSIS_CHROME")
    if named:
        assert Path(named).is_file(), f"SYMPHYSIS_CHROME={named}: файла нет"
        return named
    for path in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if Path(path).is_file():
            return path
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")


chrome = find_chrome()
pytestmark = [pytest.mark.skipif(node is None, reason="нет node: драйвер браузера не запустить"),
              pytest.mark.skipif(chrome is None, reason="нет Chrome; путь задаётся SYMPHYSIS_CHROME"),
              pytest.mark.skipif(not MERMAID.is_file(), reason="нет файла mermaid: npm ci в installer")]


def page(tmp_path, scheme=SIMPLE, with_mermaid=True, j=None):
    """Страница журнала в установленном проекте: `.symphysis/tools/` на месте, файл mermaid по заказу."""
    change = tmp_path / "проект с пробелами" / "openspec" / "changes" / "изменение"
    change.mkdir(parents=True)
    tools = change.parent.parent.parent / ".symphysis" / "tools"
    tools.mkdir(parents=True)
    if with_mermaid:
        shutil.copy(MERMAID, tools / "mermaid.min.js")
    (change / "a.md").write_text("раз\nдва\n", encoding="utf-8")
    src = change / "decisions.json"
    journal.save_journal(src, j or one_record_journal("a.md", "дв"))
    if scheme is not None:
        (change / "scheme.md").write_bytes(scheme.encode("utf-8"))
    out = change / "decisions.html"
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "journal.py"), "render-html", str(src), "--out", str(out)],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    return out


def browser(html, *actions, size=(1400, 900)):
    run = subprocess.run([node, str(DRIVER), chrome, str(html), str(size[0]), str(size[1]), *actions],
                         capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_panel_is_off_on_first_open_and_cards_take_the_width(tmp_path):
    r = browser(page(tmp_path))
    assert r["shown"] is False
    assert r["cards"]["right"] == pytest.approx(1400, abs=20)


def test_drawing_stands_beside_the_cards(tmp_path):
    r = browser(page(tmp_path), "panel")
    assert r["state"] == "svg" and r["hasSvg"] and r["total"] == 2
    assert r["cards"]["right"] <= r["panel"]["left"] + 1
    assert r["errors"] == []


def test_wide_scheme_reads_and_starts_at_the_top_node(tmp_path):
    r = browser(page(tmp_path, WIDE), "panel")
    assert r["state"] == "svg" and r["total"] == 20
    assert r["panel"]["width"] == pytest.approx(560, abs=2)
    assert r["labelPx"] >= 14
    assert r["topVisible"] is True
    assert r["cards"]["width"] > 400


def test_panel_starts_below_a_wrapped_header(tmp_path):
    """Длинное имя журнала переносит шапку на вторую строку: панель не должна уходить под неё, иначе верх рисунка срезан."""
    j = one_record_journal("a.md", "дв")
    j["title"] = "Журнал решений: изменение с очень длинным именем, которое не помещается в шапку страницы"
    r = browser(page(tmp_path, j=j), "panel", size=(1100, 900))
    assert r["headerBottom"] > 60, "шапка не перенеслась, тест ничего не проверяет"
    assert r["panel"]["top"] >= r["headerBottom"] - 1
    assert r["panel"]["bottom"] == pytest.approx(900, abs=1)


def test_without_the_mermaid_file_the_text_shows_and_the_page_works(tmp_path):
    r = browser(page(tmp_path, with_mermaid=False), "panel", "mode:check", "mode:decisions")
    assert r["state"] == "text" and not r["hasSvg"]
    assert "A[начало] --> B[конец]" in r["text"]
    assert "Решения по журналу" in r["out"]
    assert r["http"] == [] and r["errors"] == []


def test_unparsable_text_shows_with_the_file_line(tmp_path):
    scheme = "# Схема\n\nтекст\n\n```mermaid\nflowchart TD\n  A[незакрытая --> B\n  B --> C\n```\n"
    r = browser(page(tmp_path, scheme), "panel")
    assert r["state"] == "text" and "A[незакрытая" in r["text"]
    assert any("строка 7" in m for m in r["messages"]), r["messages"]


def test_bom_and_crlf_keep_the_drawing_and_the_file_line(tmp_path):
    good = browser(page(tmp_path / "1", "\ufeff# С\r\n\r\n```mermaid\r\nflowchart TD\r\n  A --> B\r\n```\r\n"), "panel")
    assert good["state"] == "svg" and good["total"] == 2
    bad = browser(page(tmp_path / "2", "\ufeff# С\r\n\r\n```mermaid\r\nflowchart TD\r\n  A[незакрытая --> B\r\n```\r\n"), "panel")
    assert bad["state"] == "text" and any("строка 5" in m for m in bad["messages"]), bad["messages"]


def test_no_scheme_file_says_so(tmp_path):
    r = browser(page(tmp_path, None), "panel")
    assert r["state"] == "missing" and any("Схема не создана" in m for m in r["messages"])


def test_file_without_a_block_says_so(tmp_path):
    r = browser(page(tmp_path, "# Только текст\n"), "panel")
    assert r["state"] == "empty" and any("В scheme.md нет схемы" in m for m in r["messages"])


def test_two_blocks_draw_the_first_and_say_so(tmp_path):
    scheme = "```mermaid\nflowchart TD\n  A --> B\n```\n\n```mermaid\nflowchart TD\n  C --> D --> E\n```\n"
    r = browser(page(tmp_path, scheme), "panel")
    assert r["state"] == "svg" and r["total"] == 2
    assert any("в файле 2 блока, показан первый" in m for m in r["messages"]), r["messages"]


def test_panel_stays_on_in_the_check_mode(tmp_path):
    r = browser(page(tmp_path), "panel", "mode:check")
    assert r["shown"] is True and r["state"] == "svg"
    assert r["view"] <= 1400 - r["panel"]["width"] + 1


def test_dragged_border_is_remembered(tmp_path):
    html = page(tmp_path)
    r = browser(html, "panel", "drag:-100", "reload")
    assert r["shown"] is True
    assert r["panel"]["width"] == pytest.approx(660, abs=3)
    assert r["cards"]["right"] <= r["panel"]["left"] + 1


def test_narrow_window_puts_the_panel_above_the_cards(tmp_path):
    r = browser(page(tmp_path), "panel", size=(800, 900))
    assert r["shown"] is True
    assert r["panel"]["bottom"] <= r["cards"]["top"] + 1
    assert r["panel"]["width"] >= 700


def test_image_from_a_label_does_not_reach_the_network(tmp_path):
    """Настоящий слушающий порт: к нему никто не подключился. Журнал сети один не довод: Chrome пишет туда и заблокированную попытку."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.setblocking(False)
        url = f"http://127.0.0.1:{listener.getsockname()[1]}/pixel.png"
        scheme = f"```mermaid\nflowchart TD\n  A[\"<img src='{url}'>\"] --> B\n```\n"
        r = browser(page(tmp_path, scheme), "panel")
        with pytest.raises(BlockingIOError):
            listener.accept()
    assert r["state"] == "svg"
    assert r["http"] == [] and url in r["blocked"]
    assert any("img-src" in v for v in r["csp"]), r["csp"]


def test_buttons_work_under_csp(tmp_path):
    r = browser(page(tmp_path), "panel", "buttons")
    assert r["buttons"] == {"exported": True, "imported": "проба импорта", "copied": "скопировано"}
    assert r["csp"] == [] and r["errors"] == []


@pytest.mark.parametrize("with_mermaid", [True, False], ids=["с файлом", "без файла"])
def test_no_network_requests_at_all(tmp_path, with_mermaid):
    r = browser(page(tmp_path, WIDE, with_mermaid), "panel", "mode:attack", "mode:check", "mode:decisions")
    assert r["http"] == []


def test_choosing_the_second_antipode_goes_through_with_a_warning(tmp_path):
    j = one_record_journal("a.md", "дв")
    fork = j["records"][0]
    option = dict(fork["options"][0], letter="B", text="второй", evidence=[])
    fork["options"].append(option)
    other = json.loads(json.dumps(fork))
    other["id"] = "F-02"
    other["antipodes"] = [{"option": "B", "other": "F-01.A"}]
    j["records"].append(other)
    r = browser(page(tmp_path, j=j), "choose:F-01:A", "choose:F-02:B")
    assert sorted(r["chosen"]) == ["F-01.A", "F-02.B"]
    assert sorted(r["warnings"]) == ["F-01.A", "F-02.B"]
    assert "- F-01: A" in r["out"] and "- F-02: B" in r["out"]
