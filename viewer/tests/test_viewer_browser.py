"""Панель схемы на странице в настоящем Chrome: вёрстку, рисунок, CSP и сеть `viewer-smoke.js` без браузера не проверит.
Chrome нет — пропуск с причиной; заданный `SYMPHYSIS_CHROME` без файла — падение, а не пропуск."""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import (ALL_STEPS, FIX, FORK_VERSION, ROOT, fake_apply, fake_status, fork_env, fork_record, fork_reply,
                      install_fork_shim, journal_of, one_record_journal, steps_text)
from browser_driver import run_browser_driver
import journal

MERMAID = ROOT / "installer" / "node_modules" / "mermaid" / "dist" / "mermaid.min.js"
DRIVER = FIX / "viewer-browser.mjs"
BROWSER_TIMEOUT = 120
WIDE = (FIX / "scheme" / "wide.md").read_text(encoding="utf-8")
SIMPLE = "# Схема\n\n```mermaid\nflowchart TD\n  A[начало] --> B[конец]\n```\n"
node = shutil.which("node")


def find_chrome():
    named = os.environ.get("SYMPHYSIS_CHROME")
    if named:
        return named
    for path in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if Path(path).is_file():
            return path
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")


chrome = find_chrome()
pytestmark = [pytest.mark.browser,
              pytest.mark.skipif(node is None, reason="нет node: драйвер браузера не запустить"),
              pytest.mark.skipif(chrome is None, reason="нет Chrome; путь задаётся SYMPHYSIS_CHROME"),
              pytest.mark.skipif(not MERMAID.is_file(), reason="нет файла mermaid: npm ci в installer")]


def page(tmp_path, scheme=SIMPLE, with_mermaid=True, j=None, env=None):
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
    out = change / "symphysis.html"
    run = subprocess.run([sys.executable, str(ROOT / "cli" / "journal.py"), "render-html", str(src), "--out", str(out)],
                         capture_output=True, text=True, encoding="utf-8", env=env)
    assert run.returncode == 0, run.stderr
    return out


def browser(html, *actions, size=(1400, 900), temp_dir=None):
    assert Path(chrome).is_file(), f"SYMPHYSIS_CHROME={chrome}: файла нет"
    args = [node, str(DRIVER), chrome, str(html), str(size[0]), str(size[1]), *actions]
    return json.loads(run_browser_driver(args, timeout=BROWSER_TIMEOUT, temp_dir=temp_dir))


def test_driver_removes_its_profile_under_load(tmp_path):
    """Процессы Chrome переживают kill главного и держат файлы профиля, под `-n 12` дольше: одна попытка снятия оставляла в системном каталоге по 5,5 МБ на запуск."""
    html = page(tmp_path)
    temp = tmp_path / "temp"
    temp.mkdir()
    with ThreadPoolExecutor(max_workers=6) as pool:
        runs = [pool.submit(browser, html, temp_dir=temp) for _ in range(6)]
        assert all(run.result() for run in runs)
    assert list(temp.iterdir()) == []


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
    r = browser(page(tmp_path, with_mermaid=False), "panel", "layout:snapshot", "layout:journal")
    assert r["state"] == "text" and not r["hasSvg"]
    assert r["layout"] == "по журналу"
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


def test_panel_stays_on_in_the_snapshot_layout(tmp_path):
    r = browser(page(tmp_path), "panel", "layout:snapshot")
    assert r["shown"] is True and r["state"] == "svg"
    assert r["layout"] == "снимок"
    assert r["cards"]["width"] <= 1400 - r["panel"]["width"] + 1


@pytest.mark.parametrize("width", [1397, 800])
@pytest.mark.parametrize("layout", ["snapshot", "journal"])
def test_option_text_uses_the_row_width(tmp_path, width, layout):
    r = browser(page(tmp_path), "layout:" + layout, size=(width, 966))
    assert r["optionWidths"]
    for option in r["optionWidths"]:
        assert option["text"] >= option["row"] - 45, option
        assert option["radio"] == (layout == "journal")
    assert r["errors"] == []


def test_dragged_border_is_remembered(tmp_path):
    html = page(tmp_path)
    r = browser(html, "panel", "drag:-100", "reload")
    assert r["shown"] is True
    assert r["panel"]["width"] == pytest.approx(660, abs=3)
    assert r["cards"]["right"] <= r["panel"]["left"] + 1


def test_toc_width_can_be_dragged_and_is_remembered(tmp_path):
    html = page(tmp_path)
    first = browser(html)
    assert first["toc"]["width"] == pytest.approx(250, abs=1)
    changed = browser(html, "tocdrag:120", "reload")
    assert changed["toc"]["width"] == pytest.approx(370, abs=1)
    assert changed["cards"]["left"] >= changed["toc"]["right"]
    assert changed["errors"] == []


def test_light_theme_can_be_selected_and_is_remembered(tmp_path):
    html = page(tmp_path)
    dark = browser(html)
    assert dark["theme"] == "dark" and dark["background"] == "rgb(15, 17, 21)"
    light = browser(html, "theme:light", "reload")
    assert light["theme"] == "light" and light["themePick"] == "light"
    assert light["background"] == "rgb(245, 247, 250)"
    assert light["errors"] == []
    assert light["themeButtons"] == [
        {"theme": "light", "label": "Светлая тема", "pressed": "true"},
        {"theme": "dark", "label": "Тёмная тема", "pressed": "false"},
    ]
    dark_again = browser(html, "theme:light", "theme:dark", "reload")
    assert dark_again["theme"] == dark_again["themePick"] == "dark"
    assert dark_again["errors"] == []


@pytest.mark.parametrize("width", [1431, 1100, 800])
def test_header_controls_do_not_overlap(tmp_path, width):
    r = browser(page(tmp_path), size=(width, 900))
    assert r["headerOverlaps"] == []
    assert len(r["themeButtons"]) == 2


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
    r = browser(page(tmp_path, WIDE, with_mermaid), "panel", "mode:attack", "mode:decisions", "layout:snapshot", "layout:journal")
    assert r["http"] == [] and r["layout"] == "по журналу"


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


def recommended_journal():
    j = one_record_journal("a.md", "дв")
    fork = j["records"][0]
    fork["options"].append(dict(fork["options"][0], letter="B", text="второй", evidence=[]))
    fork["recommendation"] = {"option": "A", "why": "причина"}
    return j


def test_choice_past_the_recommendation_asks_for_a_word_and_does_not_block(tmp_path):
    """Сценарий «Выбор мимо рекомендации»: просьба видна, выбор и промпт идут."""
    r = browser(page(tmp_path, j=recommended_journal()), "choose:F-01:B")
    assert r["wordNeeded"] == ["F-01"]
    assert r["chosen"] == ["F-01.B"] and "- F-01: B" in r["out"]


def test_written_word_removes_the_request(tmp_path):
    """Сценарий «Слово написано»: просьбы нет, слово ушло в промпт."""
    r = browser(page(tmp_path, j=recommended_journal()), "choose:F-01:B", "word:F-01:потому что")
    assert r["wordNeeded"] == []
    assert "- F-01: B — «потому что»" in r["out"]


def test_own_variant_asks_for_nothing(tmp_path):
    """Сценарий «Вариант человека»."""
    j = recommended_journal()
    j["records"][0]["options"][1]["added"] = True
    r = browser(page(tmp_path, j=j), "choose:F-01:B")
    assert r["wordNeeded"] == [] and r["chosen"] == ["F-01.B"]


def test_recommended_choice_asks_for_nothing(tmp_path):
    """Сценарий «Рекомендованный вариант»."""
    r = browser(page(tmp_path, j=recommended_journal()), "choose:F-01:A")
    assert r["wordNeeded"] == [] and r["chosen"] == ["F-01.A"]


def test_card_shows_the_reason_when_text_is_present(tmp_path):
    """Сценарий «Есть поле `text`»: под вариантами причина, строки `text` нет."""
    j = recommended_journal()
    j["records"][0]["recommendation"] = {"option": "A", "why": "дешевле откатить", "text": "A — кратко"}
    assert browser(page(tmp_path, j=j))["recommendations"] == ["рекомендация: A — дешевле откатить"]


# --- панель: схема или справка ------------------------------------------------

BEFORE_SPECS = ("intent", "decisions", "research", "proposal")
HOSTILE = "</script><img src=x onerror=\"document.title='взлом'\"><svg onload=alert(1)>"


def help_page(tmp_path, done=BEFORE_SPECS, ready=("specs",), apply=None, scheme=SIMPLE, steps=None, j=None, version=FORK_VERSION,
              **replies):
    """Страница в проекте с `steps.md`, форк подменён шимом с ответами по сценарию; текущий шаг по умолчанию `specs`."""
    project = tmp_path / "проект с пробелами"
    schema = project / "openspec" / "schemas" / "symphysis"
    schema.mkdir(parents=True)
    (schema / "steps.md").write_text(steps_text() if steps is None else steps, encoding="utf-8")
    status = fake_status(project, change="изменение", done=done, ready=ready)
    install_fork_shim(tmp_path / "bin", version=version, **{"status": fork_reply(status), "apply": fork_reply(apply or fake_apply()), **replies})
    no_open_forks = j or journal_of(fork_record("F-01", "A", A=[]))
    return page(tmp_path, scheme, j=no_open_forks, env=fork_env(tmp_path / "bin"))


def snapshot_of(html) -> dict:
    text = Path(html).read_text(encoding="utf-8")
    start = text.index("const HELP = ") + len("const HELP = ")
    return json.JSONDecoder().raw_decode(text[start:].replace("<\\/", "</"))[0]


def with_snapshot(html, **fields):
    """Та же страница с полями снимка, которых шимом не получить: страницу пересобирает рендер из памяти."""
    src = Path(html).with_name("decisions.json")
    snapshot = {**snapshot_of(html), **fields}
    Path(html).write_text(journal.render_html(journal.load_journal(src), ROOT / "viewer" / "playground-template.html",
                                              help_snapshot=snapshot), encoding="utf-8", newline="\n")
    return html


def test_panel_button_says_both(tmp_path):
    """Сценарий «Подпись кнопки панели»."""
    r = browser(page(tmp_path))
    assert r["shown"] is False and r["panelLabel"] == "схема · справка"


def test_first_open_shows_the_scheme(tmp_path):
    """Сценарий «Первое открытие панели»."""
    r = browser(help_page(tmp_path), "panel")
    assert r["tabs"] == ["схема", "справка"] and r["activeTab"] == "схема"
    assert r["help"]["schemeShown"] is True and r["help"]["shown"] is False
    assert r["state"] == "svg" and r["hasSvg"]


def test_switching_keeps_the_place(tmp_path):
    """Сценарий «Переключение»: на месте схемы справка, ширина прежняя, карточки рядом."""
    html = help_page(tmp_path)
    scheme = browser(html, "panel")
    r = browser(html, "panel", "tab:help")
    assert r["help"]["shown"] is True and r["help"]["schemeShown"] is False and r["activeTab"] == "справка"
    assert r["panel"]["width"] == pytest.approx(scheme["panel"]["width"], abs=1)
    assert r["panel"]["left"] == pytest.approx(scheme["panel"]["left"], abs=1)
    assert r["cards"]["right"] <= r["panel"]["left"] + 1
    assert r["errors"] == [] and r["csp"] == []


def test_choice_is_remembered(tmp_path):
    """Сценарий «Выбор сохранился»: и панель, и справка в ней после нового открытия."""
    r = browser(help_page(tmp_path), "panel", "tab:help", "reload")
    assert r["shown"] is True and r["help"]["shown"] is True and r["activeTab"] == "справка"


def test_modes_are_not_touched(tmp_path):
    """Сценарий «Режимы страницы не тронуты»: кнопок режимов две, панель показывает справку в другой раскладке."""
    r = browser(help_page(tmp_path), "panel", "tab:help", "layout:snapshot")
    assert r["help"]["shown"] is True and r["modeButtons"] == 2
    assert r["layout"] == "снимок"
    assert r["cards"]["width"] <= 1400 - r["panel"]["width"] + 1


def test_no_scheme_says_so_on_its_tab(tmp_path):
    """Сценарий «Схемы нет»."""
    html = help_page(tmp_path, scheme=None)
    r = browser(html, "panel", "tab:help")
    assert r["help"]["shown"] is True and "why specs" in r["help"]["text"]
    r = browser(html, "panel", "tab:scheme")
    assert r["state"] == "missing" and any("Схема не создана" in m for m in r["messages"])


def test_drawing_does_not_take_the_help_away(tmp_path):
    """Предположение «е», F-63: у справки свой контейнер. Рисунок готов раньше выбора справки, и справка цела."""
    html = help_page(tmp_path, scheme=WIDE)
    r = browser(html, "panel", "tab:help", "tab:scheme", "tab:help")
    assert r["help"]["shown"] is True and r["hasSvg"] and "why specs" in r["help"]["text"]


def test_scheme_first_shown_after_help_starts_at_the_top_node(tmp_path):
    """Рисунок считает прокрутку на видимом контейнере: при открытой справке он не рисуется, иначе верхний узел ушёл бы (F-35)."""
    html = help_page(tmp_path, scheme=WIDE)
    r = browser(html, "panel", "tab:help", "reload", "tab:scheme")
    assert r["state"] == "svg" and r["topVisible"] is True


def test_narrow_window_keeps_the_help_above_the_cards(tmp_path):
    r = browser(help_page(tmp_path), "panel", "tab:help", size=(800, 900))
    assert r["help"]["shown"] is True and r["panel"]["bottom"] <= r["cards"]["top"] + 1


def test_opens_on_the_current_step(tmp_path):
    """Сценарий «Открытие на текущем шаге»."""
    r = browser(help_page(tmp_path), "panel", "tab:help")["help"]
    assert r["opened"] == "specs" and r["current"] == ["specs"]
    assert r["steps"] == ALL_STEPS
    assert "выполняется" not in r["text"] and "по файлам" in r["text"]
    assert "модель" in r["text"] and "человек" in r["text"], "у пунктов виден чей ход"


def test_choosing_an_item_keeps_the_mark(tmp_path):
    """Сценарий «Выбор пункта»."""
    r = browser(help_page(tmp_path), "panel", "tab:help", "step:archive")["help"]
    assert r["opened"] == "archive" and r["current"] == ["specs"]
    assert "why archive" in r["text"] and "why specs" not in r["text"]


def test_paging_to_the_end_of_the_list(tmp_path):
    """Сценарий «Листание до конца списка»."""
    html = help_page(tmp_path)
    r = browser(html, "panel", "tab:help", "step:archive")["help"]
    assert r["nextDisabled"] is True and r["prevDisabled"] is False
    r = browser(html, "panel", "tab:help", "step:archive", "helpprev")["help"]
    assert r["opened"] == "sync" and r["current"] == ["specs"]


def test_paging_from_the_start_of_the_list(tmp_path):
    html = help_page(tmp_path)
    r = browser(html, "panel", "tab:help", "step:intent")["help"]
    assert r["prevDisabled"] is True and r["nextDisabled"] is False
    assert browser(html, "panel", "tab:help", "step:intent", "helpnext")["help"]["opened"] == "decisions"


def test_step_page_answers_the_questions_of_the_intent(tmp_path):
    """Требование «Страница шага отвечает на вопросы намерения» на показе: тексты, файлы, что держит граф, команда."""
    r = browser(help_page(tmp_path, done=(*BEFORE_SPECS, "specs"), ready=("consequences", "security")), "panel", "tab:help",
                "step:security")["help"]
    for word in ("why security", "mechanics security", "if_skipped security", "what_to_check security", "command security",
                 "openspec/changes/изменение/security.md", "файла ещё нет", "Без него не начнутся: attack-artifacts",
                 "Без него не начнётся apply"):
        assert word in r["text"], word


def test_optional_step_is_marked(tmp_path):
    r = browser(help_page(tmp_path, done=("intent", "decisions", "research"), ready=("attack-decisions", "proposal")), "panel",
                "tab:help", "step:attack-decisions")["help"]
    assert "необязательный" in r["text"]


def test_empty_file_of_a_step(tmp_path):
    """Сценарий «Пустой файл шага»: статус считает шаг готовым, показан готовым с пометкой."""
    r = browser(help_page(tmp_path, done=(*BEFORE_SPECS, "specs", "consequences", "design"), ready=("security",)), "panel",
                "tab:help", "step:design")["help"]
    assert "готов" in r["text"] and "файл есть, содержание не проверялось" in r["text"]


def test_snapshot_stays_until_the_page_is_rebuilt(tmp_path):
    """Сценарий «Файлы изменились после снимка»."""
    html = help_page(tmp_path)
    first = browser(html, "panel", "tab:help")["help"]
    assert first["time"] and first["current"] == ["specs"]
    project = tmp_path / "проект с пробелами"
    (Path(html).parent / "design.md").write_text("дизайн\n", encoding="utf-8")
    again = browser(html, "panel", "tab:help")["help"]
    assert (again["current"], again["time"]) == (first["current"], first["time"])
    scenario = tmp_path / "bin" / "scenario.json"
    replies = json.loads(scenario.read_text(encoding="utf-8"))
    replies["status"] = fork_reply(fake_status(project, change="изменение", done=(*BEFORE_SPECS, "specs", "consequences", "design"),
                                               ready=("security",)))
    scenario.write_text(json.dumps(replies, ensure_ascii=False), encoding="utf-8")
    time.sleep(1.1)
    run = subprocess.run([sys.executable, str(ROOT / "cli" / "journal.py"), "render-html", str(Path(html).with_name("decisions.json")),
                          "--out", str(html)], capture_output=True, text=True, encoding="utf-8", env=fork_env(tmp_path / "bin"))
    assert run.returncode == 0, run.stderr
    rebuilt = browser(html, "panel", "tab:help")["help"]
    assert rebuilt["current"] == ["security"] and rebuilt["time"] != first["time"]


def test_rebuild_command_stands_by_the_time(tmp_path):
    """Сценарий «Команда пересборки рядом со снимком», показ."""
    html = help_page(tmp_path)
    r = browser(html, "panel", "tab:help")["help"]
    assert r["rebuild"] == snapshot_of(html)["rebuild"] and "render-html" in r["rebuild"]
    assert r["time"] == snapshot_of(html)["taken_at"]
    assert "проект с пробелами" not in r["rebuild"]


def test_versions_differ_with_no_warning(tmp_path):
    """Сценарий «Версии разошлись»: показаны обе, предупреждения нет."""
    html = with_snapshot(help_page(tmp_path), versions={"openspec": "9.9.9-symphysis.9", "symphysis": "0.1.0+aa50e8f"})
    r = browser(html, "panel", "tab:help")["help"]
    assert "9.9.9-symphysis.9" in r["versions"] and "0.1.0+aa50e8f" in r["versions"]
    assert r["error"] is None
    for word in ("предупрежд", "расход", "не совпад", "обнови"):
        assert word not in r["text"].lower(), word


def test_unknown_symphysis_version(tmp_path):
    """Сценарий «Файла версии нет», показ."""
    r = browser(help_page(tmp_path), "panel", "tab:help")["help"]
    assert "symphysis неизвестно" in r["versions"] and FORK_VERSION in r["versions"] and r["error"] is None


def test_unreadable_journal_is_said_in_words(tmp_path):
    """Сценарий «Журнал не читается», показ: слова вместо числа. Такой журнал страницу не собирает, поэтому снимок задан."""
    text = "Следующий шаг по файлам — `research`, ход модели. Открытые развилки не посчитаны: журнал не читается."
    html = with_snapshot(help_page(tmp_path), current_step="research", current_text=text,
                         forks={"open": "журнал не читается", "parked": "журнал не читается"})
    r = browser(html, "panel", "tab:help")["help"]
    assert r["opened"] == "research" and "журнал не читается" in r["text"]


def test_open_forks_and_tasks_are_counted(tmp_path):
    html = help_page(tmp_path, done=("intent", "decisions", "research", "proposal", "specs", "consequences", "design", "security", "tasks"),
                     ready=(), apply=fake_apply("ready", total=5, complete=2))
    result = browser(html, "panel", "tab:help")
    assert result["help"]["current"] == ["apply"] and "Задач закрыто 2 из 5" in " ".join(result["stats"].split())


def test_tasks_in_the_header(tmp_path):
    """Сценарий «Задачи идут на странице»."""
    html = with_snapshot(help_page(tmp_path), tasks={"state": "ready", "total": 5, "complete": 2, "remaining": 3})
    assert "Задач закрыто 2 из 5" in " ".join(browser(html)["stats"].split())


@pytest.mark.parametrize("fields", [{"tasks": {"state": "ready", "total": 0, "complete": 0, "remaining": 0}}, {"tasks": None},
                                    {"error": "сбой расчёта", "tasks": {"state": "ready", "total": 5, "complete": 2, "remaining": 3}}])
def test_no_tasks_in_the_snapshot(tmp_path, fields):
    """Сценарий «Задач в снимке нет»: нет задач или сбой расчёта, части в шапке нет."""
    html = with_snapshot(help_page(tmp_path), **fields)
    assert "Задач закрыто" not in browser(html)["stats"]


def test_panel_has_no_fork_counters(tmp_path):
    """Сценарий «Чисел развилок на панели нет»: в шапке они прежние."""
    html = with_snapshot(help_page(tmp_path), forks={"open": 1, "parked": 1})
    r = browser(html, "panel", "tab:help")
    for word in ("открытых развилок", "припарковано"):
        assert word not in r["help"]["text"], word
    assert "открыто" in r["stats"] and "с парковкой" in r["stats"]


def test_hostile_step_text_makes_no_element(tmp_path):
    """Канон F-53: `<img onerror=…>` в тексте шага элемента не создаёт, скрипт не исполняется, страница цела."""
    html = help_page(tmp_path, steps=f"## specs\n\n{HOSTILE}\n\n### Зачем\n\n{HOSTILE}\n\n### Механики\n\n- {HOSTILE}\n")
    r = browser(html, "panel", "tab:help")
    assert r["help"]["foreign"] == 0 and r["errors"] == []
    assert "<img src=x" in r["help"]["text"]


def test_hostile_failure_reason_makes_no_element(tmp_path):
    """Канон F-53: то же в причине сбоя."""
    html = help_page(tmp_path, status=fork_reply(code=1, stderr=HOSTILE + "\n"))
    r = browser(html, "panel", "tab:help")
    assert r["help"]["foreign"] == 0 and r["errors"] == []
    assert "<img src=x" in r["help"]["error"]


def test_how_to_prepare_on_any_step(tmp_path):
    """Сценарий «Кнопка на любом шаге»."""
    r = browser(help_page(tmp_path), "panel", "tab:help", "howto")["help"]
    assert r["opened"] == "intent" and r["current"] == ["specs"]
    assert "Как готовить" in r["text"] and "где искать материалы" in r["text"]


def test_how_to_prepare_when_the_calculation_failed(tmp_path):
    """Сценарий «Кнопка при сбое расчёта»: при сбое панель даёт причину и кнопку, списка нет (F-47)."""
    project = tmp_path / "проект с пробелами"
    (project / "openspec" / "schemas" / "symphysis").mkdir(parents=True)
    (project / "openspec" / "schemas" / "symphysis" / "steps.md").write_text(steps_text(), encoding="utf-8")
    html = page(tmp_path, env=fork_env())
    r = browser(html, "panel", "tab:help")["help"]
    assert "openspec не найден" in r["error"] and r["steps"] == [] and r["opened"] is None
    r = browser(html, "panel", "tab:help", "howto")["help"]
    assert r["opened"] == "intent" and "где искать материалы" in r["text"]
    assert "openspec не найден" in r["error"]


def test_how_to_prepare_without_the_section(tmp_path):
    """Сценарий «Раздела нет»: текста нет, остальное работает."""
    html = help_page(tmp_path, steps=steps_text([step for step in ALL_STEPS if step != "intent"]))
    r = browser(html, "panel", "tab:help", "howto")["help"]
    assert r["opened"] == "intent" and "текста нет" in r["text"].lower() and r["current"] == ["specs"]
    assert browser(html, "panel", "tab:help", "howto", "step:specs")["help"]["opened"] == "specs"


def test_how_to_prepare_when_the_journal_is_outside_changes(tmp_path):
    """Снимка нет совсем: кнопка всё равно отвечает, что текста нет."""
    html = with_snapshot(page(tmp_path, env=fork_env()), steps=[], error="Журнал лежит вне openspec/changes/")
    r = browser(html, "panel", "tab:help", "howto")["help"]
    assert r["opened"] == "intent" and "текста нет" in r["text"].lower() and "Журнал лежит вне" in r["error"]
    assert r["versions"] and "неизвестно" in r["versions"]


def test_files_are_links(tmp_path):
    """Сценарии «Файл в теле вопроса» и «Файла нет»: ссылка берётся из карты, клик внутри варианта выбор не меняет."""
    j = one_record_journal("a.md", "дв")
    record = j["records"][0]
    record["question"] = "см. `a.md:2`, `нет-такого.md`, `constructor`, `<img src=x onerror=alert(1)>`"
    record["options"][0]["text"] = "вариант про `a.md`"
    html = page(tmp_path, j=j)
    r = browser(html, "clicklink")
    target = html.with_name("a.md").as_uri()
    assert {link["href"] for link in r["links"] if link["text"] != "↗"} == {target}
    assert "file" + target[len("file:") + 2:] + ":2" in [link["href"][len("vscode://"):] for link in r["links"] if link["text"] == "↗"]
    assert {"нет-такого.md", "constructor", "<img src=x onerror=alert(1)>"} <= set(r["codes"])
    assert not any(link["text"] in ("нет-такого.md", "constructor") for link in r["links"])
    assert r["chosen"] == [] and r["errors"] == [] and r["csp"] == []


def editor_arrows(result):
    return [link["href"] for link in result["links"] if link["text"] == "↗"]


def test_editor_choice_lives_in_the_browser(tmp_path):
    """Сценарий «Выбор редактора»: выбор один на браузер, его видит и другая страница, а в файл страницы он не попадает."""
    j = one_record_journal("a.md", "дв")
    html, other = page(tmp_path / "один", j=j), page(tmp_path / "два", j=j)
    before = html.read_bytes()
    file_part = html.with_name("a.md").as_uri()[len("file:///"):]
    other_part = other.with_name("a.md").as_uri()[len("file:///"):]

    assert browser(html)["editor"] == "vscode"
    r = browser(html, "editor:cursor", "reload")
    assert r["editor"] == "cursor" and editor_arrows(r) == [f"cursor://file/{file_part}:1"]
    r = browser(html, "editor:cursor", f"open:{other}")
    assert r["editor"] == "cursor" and editor_arrows(r) == [f"cursor://file/{other_part}:1"]
    assert editor_arrows(browser(html, "editor:none")) == []
    r = browser(html, "editor:custom:idea://open?file={path}&line={line}", "reload")
    assert editor_arrows(r) == [f"idea://open?file={file_part}&line=1"] and r["editorMask"] == "idea://open?file={path}&line={line}"
    assert html.read_bytes() == before


def test_editor_mask_must_be_usable(tmp_path):
    """Сценарий «Негодная маска»: значка нет, обычная ссылка на файл на месте, ошибок нет."""
    html = page(tmp_path, j=one_record_journal("a.md", "дв"))
    for mask in ("javascript:alert({path})", "data:text/html,{path}", "vscode://file/без-пути"):
        r = browser(html, "editor:custom:" + mask)
        assert editor_arrows(r) == [] and r["links"] and r["errors"] == [] and r["csp"] == []


def test_jetbrains_preset_needs_the_project_root(tmp_path):
    """Форма команды проверена на GIGA IDE: проект и путь от корня, строка с нуля. Файл вне корня значка не даёт."""
    j = one_record_journal("a.md", "дв")
    j["records"][0]["question"] = "см. `a.md:2`"
    html = page(tmp_path, j=j)
    project = html.parent.parent.parent.parent
    arrow = "jetbrains://idea/navigate/reference?project=" + quote(project.name) + "&path=" + quote("openspec/changes/изменение/a.md") + ":1"
    assert arrow in editor_arrows(browser(html, "editor:jetbrains")), "инструменты вне проекта: корень это проект из пути журнала"

    def render_with_root(root):
        roots = tmp_path / "roots.json"
        roots.write_text(json.dumps({"": str(root)}), encoding="utf-8")
        run = subprocess.run([sys.executable, str(ROOT / "cli" / "journal.py"), "render-html", str(html.with_name("decisions.json")), "--out", str(html), "--roots", str(roots)],
                             capture_output=True, text=True, encoding="utf-8")
        assert run.returncode == 0, run.stderr

    other = tmp_path / "другой проект"
    other.mkdir()
    render_with_root(other)
    assert editor_arrows(browser(html, "editor:jetbrains")) == []
    render_with_root(project)
    r = browser(html, "editor:jetbrains")
    assert arrow in editor_arrows(r)
    assert r["errors"] == []


# --- режим «атака»: фильтр по линзе (decision-viewer) ---------------------------------------------

def test_attack_filter_all_shows_every_lens_again(tmp_path):
    """`decision-viewer`: «Фильтр «все»» — выбрана одна линза, человек нажимает «все»: видны строки всех линз файла."""
    def row(lens):
        return {"claim": f"утверждение {lens}", "section": "F-01, decision", "lens": lens, "invariant": "и",
                "severity": "блокер", "support": "нет", "fix": "правка записи"}
    lenses = ["context-compliance", "claim-authority", "coverage"]
    attack = {"path": "attack/decisions.md", "frontmatter": {"status": "gaps_found", "targets": [{"path": "decisions.json", "sha256": ""}]},
              "rows": [row(lens) for lens in lenses]}
    html = tmp_path / "attack.html"
    html.write_text(journal.render_html(one_record_journal("a.md", "дв"), ROOT / "viewer" / "playground-template.html", attacks=[attack],
                                        journal_sha256="0" * 64), encoding="utf-8", newline="\n")
    one = browser(html, "mode:attack", "lens:claim-authority")["attack"]
    assert one == {"groups": ["claim-authority"], "active": "claim-authority"}
    everything = browser(html, "mode:attack", "lens:claim-authority", "lens:all")["attack"]
    assert everything == {"groups": lenses, "active": "all"}


# --- режим «атака»: флаг «прочитано» (decision-viewer, warning-read-flag) ----------------------------

READ = "предупреждение прочитано: "


def warning_row(section, claim, severity="предупреждение", fix="вопрос человеку"):
    return {"claim": claim, "section": section, "lens": "claim-authority", "invariant": "и", "severity": severity,
            "support": "по спеке не выводится", "fix": fix}


def attack_page(tmp_path, rows, notes=(), path="attack/decisions.md"):
    """Страница с одним файлом атаки из строк `rows`; `notes` — тексты заметок журнала."""
    j = one_record_journal("a.md", "дв")
    j["notes"] = [{"date": "2026-11-07", "text": text} for text in notes]
    attack = {"path": path, "frontmatter": {"status": "passed", "targets": [{"path": "decisions.json", "sha256": ""}]}, "rows": rows}
    html = tmp_path / "attack.html"
    html.write_text(journal.render_html(j, ROOT / "viewer" / "playground-template.html", attacks=[attack], journal_sha256="0" * 64),
                    encoding="utf-8", newline="\n")
    return html


def test_read_toggle_on_one_row_marks_the_whole_section(tmp_path):
    """`decision-viewer`: «Две строки одного раздела — одна отметка»."""
    rows = [warning_row("design.md, Decisions", "первое"), warning_row("design.md, Decisions", "второе"), warning_row("F-02, options.A", "третье")]
    r = browser(attack_page(tmp_path, rows, path="attack/artifacts.md"), "mode:attack", "read:attack/artifacts.md:design.md, Decisions")
    by = {x["claim"]: x for x in r["attackRows"]}
    assert by["первое"]["checked"] and by["второе"]["checked"] and not by["третье"]["checked"]
    assert r["attackState"]["read"] == ["attack/artifacts.md|design.md, Decisions"]
    assert r["out"].count(READ + "design.md, Decisions") == 1
    assert r["errors"] == []


def test_old_storage_without_read_field_keeps_disputes(tmp_path):
    """`decision-viewer`: «Старое хранилище без поля отметок»."""
    html = attack_page(tmp_path, [warning_row("F-02, options.A", "первое")])
    old = json.dumps({"disputes": {"attack/decisions.md|F-02, options.A|первое": "опора есть"}}, ensure_ascii=False)
    r = browser(html, "attackstate:" + old, "reload", "mode:attack")
    assert r["attackState"] == {"read": [], "disputes": ["attack/decisions.md|F-02, options.A|первое"]}
    assert "спор: опора есть" in r["out"]
    assert r["errors"] == []


def test_ingested_mark_leaves_the_state_and_shows_the_journal_badge(tmp_path):
    """`decision-viewer`: «Внесённая отметка уходит из состояния», «Переключатель у внесённого флага неактивен»."""
    html = attack_page(tmp_path, [warning_row("F-02, options.A", "первое")], notes=[READ + "F-02, options.A"])
    preset = json.dumps({"disputes": {}, "read": {"attack/decisions.md|F-02, options.A": True}}, ensure_ascii=False)
    r = browser(html, "attackstate:" + preset, "reload", "mode:attack")
    assert r["attackState"]["read"] == []
    assert READ not in r["out"]
    row = r["attackRows"][0]
    assert row["checked"] and row["disabled"] and "в журнале" in row["badge"]


def test_mark_before_apply_shows_the_draft_badge(tmp_path):
    """`decision-viewer`: «Отметка до внесения», «Две подписи»."""
    rows = [warning_row("F-02, options.A", "первое"), warning_row("F-03, options.A", "второе")]
    r = browser(attack_page(tmp_path, rows, notes=[READ + "F-03, options.A"]), "mode:attack", "read:attack/decisions.md:F-02, options.A")
    by = {x["claim"]: x for x in r["attackRows"]}
    assert "не внесено" in by["первое"]["badge"] and by["первое"]["checked"] and not by["первое"]["disabled"]
    assert "в журнале" in by["второе"]["badge"] and by["второе"]["disabled"]
    assert READ + "F-02, options.A" in r["out"] and READ + "F-03, options.A" not in r["out"]


def test_flagged_rows_stay_in_place_with_the_same_counters(tmp_path):
    """`decision-viewer`: «Число карточек при заметках»."""
    rows = [warning_row("F-02, options.A", "первое"), warning_row("F-03, options.A", "второе"),
            warning_row("F-01, decision", "блок", severity="блокер", fix="правка записи")]
    plain = browser(attack_page(tmp_path, rows), "mode:attack")
    flagged = browser(attack_page(tmp_path, rows, notes=[READ + "F-02, options.A"]), "mode:attack")
    assert len(flagged["attackRows"]) == len(plain["attackRows"]) == 3
    assert [x["claim"] for x in flagged["attackRows"]] == [x["claim"] for x in plain["attackRows"]]
    assert flagged["attackCounters"] == plain["attackCounters"]
    assert "предупреждений 2" in flagged["attackCounters"][0]
    assert {x["claim"]: x["toggle"] for x in flagged["attackRows"]} == {"первое": True, "второе": True, "блок": False}


def test_flagged_question_row_keeps_its_dispute_field(tmp_path):
    """`warning-read-flag`: «Прочитанный вопрос человеку»."""
    html = attack_page(tmp_path, [warning_row("F-02, options.A", "первое", fix="вопрос человеку")], notes=[READ + "F-02, options.A"])
    row = browser(html, "mode:attack")["attackRows"][0]
    assert row["dispute"] and "в журнале" in row["badge"]
    assert row["undecidedNote"] is not None


# --- режим «атака»: кнопка тяжести и поле обоснования (decision-viewer) ------------------------------

def test_severity_button_keeps_text_typed_before_the_press_and_warns_live(tmp_path):
    """`decision-viewer`: «Нажатие без текста»: текст, набранный до нажатия, остаётся; очистка возвращает пометку и убирает строку
    о тяжести, отметка живёт; повторное нажатие её снимает; фокус при вводе не теряется (ruling 11)."""
    html = attack_page(tmp_path, [warning_row("F-02, options.A", "первое", severity="блокер")])
    sev = lambda r: r["attackRows"][0]["sev"]
    r = browser(html, "mode:attack", "sevwhy:0:0:причина человека")
    assert sev(r)["focused"] and not sev(r)["active"] and not r["attackSev"]        # ввод без нажатия отметку не создаёт
    r = browser(html, "mode:attack", "sevwhy:0:0:причина человека", "sev:0:0")
    assert sev(r)["active"] and sev(r)["text"] == "причина человека" and not sev(r)["note"] and sev(r)["open"]
    assert "- тяжесть: attack/decisions.md · F-02, options.A · «первое» → предупреждение — «причина человека»" in r["out"]
    r = browser(html, "mode:attack", "sevwhy:0:0:причина человека", "sev:0:0", "sevwhy:0:0:")
    assert sev(r)["note"] and sev(r)["focused"] and sev(r)["text"] == "" and "- тяжесть:" not in r["out"]
    assert list(r["attackSev"].values()) == [{"to": "предупреждение", "why": ""}]
    r = browser(html, "mode:attack", "sevwhy:0:0:причина человека", "sev:0:0", "sev:0:0")
    assert r["attackSev"] == {} and not sev(r)["active"] and "- тяжесть:" not in r["out"]
    assert r["errors"] == []


def test_pressed_severity_button_looks_different(tmp_path):
    """Нажатая кнопка тяжести отличается от ненажатой цветом текста, при свёрнутом поле тоже."""
    html = attack_page(tmp_path, [warning_row("F-02, options.A", "первое", severity="блокер")])
    off = browser(html, "mode:attack")["attackRows"][0]["sev"]
    on = browser(html, "mode:attack", "sevwhy:0:0:причина", "sev:0:0")["attackRows"][0]["sev"]
    assert on["active"] and not off["active"]
    assert on["color"] != off["color"]            # указатель уведён с кнопки: :hover рамку не красит, цвет текста меняет только .active
