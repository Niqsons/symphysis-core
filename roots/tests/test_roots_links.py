"""Карта «путь — файл от корня проекта» (`file_links`, `project_href` из `roots/roots.py`)."""
import copy
from urllib.parse import quote

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import journal_of, one_record_journal
import journal


def link_project(tmp_path):
    root = tmp_path / "проект"
    change = root / "openspec" / "changes" / "x"
    change.mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "docs" / "план работ.md").write_text("раз\n", encoding="utf-8")
    (change / "tasks.md").write_text("- [ ] 1\n", encoding="utf-8")
    return change, {"": root}


PLAN_HREF = "../../../docs/" + quote("план работ.md")


def test_file_links_only_for_existing_files(tmp_path):
    """Сценарии «Файл в теле вопроса» и «Файла нет»: каталог, команда, чужое дерево и пропавший файл ссылки не дают."""
    change, roots = link_project(tmp_path)
    (tmp_path / "secret.txt").write_text("s", encoding="utf-8")
    j = one_record_journal("docs/план работ.md", "раз")
    j["records"][0]["question"] = "см. `tasks.md:3`, `tasks.md:3-5`, `docs`, `нет.md`, `../../../../secret.txt`, `tasks.md --help`"
    assert journal.file_links(j, roots, change, change / "symphysis.html") == {"docs/план работ.md": PLAN_HREF, "tasks.md": "tasks.md"}


def test_file_links_cover_attacks_and_help(tmp_path):
    change, roots = link_project(tmp_path)
    attacks = [{"path": "attack/none.md", "rows": [{"support": "`tasks.md:2`"}]}]
    snapshot = {"steps": [{"files": [{"path": "docs/план работ.md", "exists": True}]}]}
    links = journal.file_links(journal_of(), roots, change, change / "symphysis.html", attacks, snapshot)
    assert links == {"docs/план работ.md": PLAN_HREF, "tasks.md": "tasks.md"}


def test_file_links_hold_no_absolute_path_and_are_stable(tmp_path):
    change, roots = link_project(tmp_path)
    j = one_record_journal("docs/план работ.md", "раз")
    first = journal.file_links(j, roots, change, change / "symphysis.html")
    assert first == journal.file_links(copy.deepcopy(j), roots, change, change / "symphysis.html")
    assert list(first) == sorted(first) and not any(":" in href or href.startswith("/") for href in first.values())


def test_project_href_falls_back_to_the_tools_parent():
    """У ядра в файле корней нет пустого префикса: без этой опоры вариант IDEA / GIGA IDE на его страницах молча терял значок."""
    out = journal.ROOT / "docs" / "x.html"
    assert journal.project_href({}, out) == "../"
    assert journal.project_href({"": journal.ROOT / "docs"}, out) == "./"
