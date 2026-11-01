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
    assert {p.name for p in TOOLS if is_entry(p)} == {"journal.py", "symphysis_config.py"}


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
