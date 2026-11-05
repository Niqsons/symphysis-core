"""Скрипт графа трассируемости `tools/trace_graph.py`: каркас подкоманд, проверка имени, реестр артефактов."""
import copy
import subprocess
import sys

import pytest

import trace_graph
from conftest import ROOT

SCHEMA = ROOT / "openspec" / "schemas" / "symphysis" / "schema.yaml"
SCRIPT = ROOT / "tools" / "trace_graph.py"
CHANGE_COMMANDS = ["build", "report", "check", "freeze"]


def run(*args, cwd=None):
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), *args], capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd)


# --- реестр -------------------------------------------------------------------

def test_registry_matches_real_schema():
    """`trace-graph`: «Артефакт без строки реестра» — на настоящей схеме тест реестра зелёный."""
    assert trace_graph.check_registry(SCHEMA) == []


def test_registry_covers_exactly_the_schema_artifacts():
    assert set(trace_graph.REGISTRY) == set(trace_graph.schema_artifacts(SCHEMA))


def test_registry_takes_from_specs_decisions_tasks_security_consequences():
    taken = {name: row["берёт"] for name, row in trace_graph.REGISTRY.items() if row["берёт"] != trace_graph.NOTHING}
    assert set(taken) == {"specs", "decisions", "tasks", "security", "consequences"}
    assert {"требования", "сценарии", "capability"} <= set(taken["specs"])


def test_extra_schema_artifact_without_registry_row_is_named(tmp_path):
    """`trace-graph`: «Артефакт без строки реестра» — копия схемы с лишним артефактом, тест называет его."""
    copy_of_schema = tmp_path / "schema.yaml"
    copy_of_schema.write_text(SCHEMA.read_text(encoding="utf-8").replace(
        "\napply:", "\n  - id: new-artifact-xyz\n    generates: x.md\n    requires: []\n\napply:", 1), encoding="utf-8")
    problems = trace_graph.check_registry(copy_of_schema)
    assert len(problems) == 1 and "new-artifact-xyz" in problems[0], problems


def test_nothing_with_empty_reason_is_named():
    """`trace-graph`: «`ничего` без довода» — реестр с `ничего` и пустой причиной, тест называет артефакт."""
    registry = copy.deepcopy(trace_graph.REGISTRY)
    registry["design"]["довод"] = "   "
    problems = trace_graph.check_registry(SCHEMA, registry)
    assert len(problems) == 1 and "design" in problems[0], problems
    del registry["design"]["довод"]
    assert "design" in trace_graph.check_registry(SCHEMA, registry)[0]


def test_every_nothing_row_has_its_own_reason():
    reasons = [row["довод"] for row in trace_graph.REGISTRY.values() if row["берёт"] == trace_graph.NOTHING]
    assert reasons and all(r.strip() for r in reasons) and len(set(reasons)) == len(reasons)


def test_registry_row_without_schema_artifact_is_named():
    registry = {**trace_graph.REGISTRY, "ghost": {"берёт": ["что-то"]}}
    problems = trace_graph.check_registry(SCHEMA, registry)
    assert len(problems) == 1 and "ghost" in problems[0], problems


def test_empty_takes_list_is_named():
    registry = copy.deepcopy(trace_graph.REGISTRY)
    registry["tasks"]["берёт"] = []
    assert "tasks" in trace_graph.check_registry(SCHEMA, registry)[0]


# --- имя изменения ------------------------------------------------------------

@pytest.mark.parametrize("command", CHANGE_COMMANDS)
@pytest.mark.parametrize("name", ["..", "a/b", "a\\b", "a&echo.>f"])
def test_bad_change_name_is_refused_before_any_path(command, name, tmp_path):
    """`trace-graph`: «Имя изменения с символами оболочки» — отказ в stderr, код 1, без трассировки и без файлов."""
    (tmp_path / "openspec").mkdir()
    done = run(command, name, cwd=tmp_path)
    assert done.returncode == 1, done.stdout
    assert "не подходит" in done.stderr and "Traceback" not in done.stderr, done.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["openspec"]


def test_leading_dash_name_is_refused_after_double_dash(tmp_path):
    done = run("build", "--", "-x", cwd=tmp_path)
    assert done.returncode == 1 and "не подходит" in done.stderr, done.stderr


@pytest.mark.parametrize("command", CHANGE_COMMANDS)
def test_good_name_reaches_not_implemented_refusal(command, tmp_path):
    done = run(command, "trace-graph", cwd=tmp_path)
    assert done.returncode == 1
    assert "ещё не реализована" in done.stderr and "Traceback" not in done.stderr, done.stderr


def test_archive_gaps_takes_a_directory_and_refuses_for_now(tmp_path):
    done = run("archive-gaps", str(tmp_path))
    assert done.returncode == 1 and "ещё не реализована" in done.stderr, done.stderr


def test_missing_arguments_is_a_usage_error():
    assert run("build").returncode == 2
    assert run().returncode == 2


def test_find_root_is_nearest_openspec_dir(tmp_path):
    (tmp_path / "openspec").mkdir()
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert trace_graph.find_root(deep) == tmp_path
    assert trace_graph.find_root(tmp_path / "a") == tmp_path
