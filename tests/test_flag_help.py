"""Правило справки: у каждого входа `tools/*.py` `--help` отвечает, что делает, когда звать и что значат коды;
у каждого аргумента своя строка помощи."""
import ast
import subprocess
import sys

import pytest

import journal
from conftest import ROOT

TOOLS = sorted((ROOT / "tools").glob("*.py"))
WHEN = "Звать, когда"
CODES = "Коды:"
SUBCOMMANDS = journal.build_parser()._subparsers._group_actions[0].choices


def add_argument_calls(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"]


def is_entry(path):
    return "__main__" in path.read_text(encoding="utf-8")


def run_help(path, *args):
    return subprocess.run([sys.executable, "-X", "utf8", str(path), *args, "--help"], capture_output=True, text=True,
                          encoding="utf-8")


@pytest.mark.parametrize("path", TOOLS, ids=[p.name for p in TOOLS])
def test_every_argument_has_help(path):
    no_help = [node.lineno for node in add_argument_calls(path)
               if not any(keyword.arg == "help" for keyword in node.keywords)]
    assert not no_help, f"{path.name}: add_argument без help, строки {no_help}"


def test_entries_exist():
    assert {p.name for p in TOOLS if is_entry(p)} == {"journal.py", "symphysis_config.py", "step_help.py"}


@pytest.mark.parametrize("path", [p for p in TOOLS if is_entry(p)], ids=[p.name for p in TOOLS if is_entry(p)])
def test_entry_help_names_when_and_codes(path):
    done = run_help(path)
    assert done.returncode == 0, done.stderr
    assert WHEN in done.stdout and CODES in done.stdout, done.stdout
    assert "Маркеры:" in done.stdout and "Порядок:" in done.stdout, done.stdout


@pytest.mark.parametrize("name", sorted(SUBCOMMANDS))
def test_subcommand_help_names_when_and_codes(name):
    done = run_help(ROOT / "tools" / "journal.py", name)
    assert done.returncode == 0, done.stderr
    assert WHEN in done.stdout and CODES in done.stdout, done.stdout


def test_subcommands_are_the_expected_ones():
    assert set(SUBCOMMANDS) == {"import-md", "check", "apply", "apply-md4h", "render-md", "render-html", "view-json",
                                "render-design", "code-sites"}


def help_of(*args):
    return " ".join(run_help(ROOT / "tools" / "journal.py", *args).stdout.split())


def test_code_one_names_all_its_causes():
    """С9: код 1 у `check` и `code-sites` называет и негодную схему, и нет файла, и битый JSON."""
    for sub in ("check", "code-sites"):
        assert "1 — нет файла, битый JSON или негодный по схеме журнал" in help_of(sub), sub


def test_check_help_names_the_forms_it_recognises():
    text = help_of("check")
    assert "**Причина:** считается только в начале строки" in text
    assert "цитата сверяется только в форме путь:строка «цитата»" in text


def test_config_help_says_what_no_project_means():
    text = " ".join(run_help(ROOT / "tools" / "symphysis_config.py").stdout.split())
    assert "без него — проект над .symphysis/" in text
    assert "пустой префикс" not in text
