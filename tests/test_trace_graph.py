"""Скрипт графа трассируемости `tools/trace_graph.py`: каркас подкоманд, проверка имени, реестр артефактов."""
import copy
import shutil
import subprocess
import sys

import pytest

import trace_graph
from conftest import ROOT, requires_fork
from test_schema import make_project, run_openspec

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


# --- разбор спек (F-40, F-85) --------------------------------------------------

TRACE = ROOT / "tests" / "fixtures" / "trace"
FIXTURES = sorted(p.name for p in TRACE.iterdir() if p.is_dir())


def parse_fixture(fixture: str, root=TRACE) -> dict:
    """Разбор всех `specs/<capability>/spec.md` фикстуры: capability -> `SpecParse`."""
    return {spec.parent.name: trace_graph.parse_spec(spec)
            for spec in sorted((root / fixture / "specs").glob("*/spec.md"))}


def own_counts(parsed: dict) -> dict:
    """Счётчики разбора скрипта: capability -> операция -> [(имя, число сценариев)]; RENAMED — пары имён."""
    result = {}
    for cap, spec in parsed.items():
        ops = result.setdefault(cap, {})
        for req in spec.requirements:
            ops.setdefault(req.section, []).append((req.name, len(req.scenarios)))
        for rename in spec.renames:
            ops.setdefault("RENAMED", []).append((rename.from_name, rename.to_name))
    return result


def shown_counts(project, change="demo") -> dict:
    """То же из `openspec show <изменение> --json --type change`: что OpenSpec видит в тех же спеках."""
    out = run_openspec(project, "show", change, "--json", "--type", "change", "--no-interactive")
    result = {}
    for delta in out["deltas"]:
        ops = result.setdefault(delta["spec"], {})
        if delta["operation"] == "RENAMED":
            ops.setdefault("RENAMED", []).append((delta["rename"]["from"], delta["rename"]["to"]))
        else:
            req = delta["requirement"]
            ops.setdefault(delta["operation"], []).append((req["name"], len(req["scenarios"])))
    return result


def assert_counts_match(fixture: str, own: dict, shown: dict) -> None:
    """Сверка по каждой capability и операции: число требований, число сценариев, имена. Красное называет фикстуру."""
    problems = []
    for cap in sorted(set(own) | set(shown)):
        mine, theirs = own.get(cap, {}), shown.get(cap, {})
        for op in sorted(set(mine) | set(theirs)):
            a, b = mine.get(op, []), theirs.get(op, [])
            if a == b:
                continue
            if op == "RENAMED":
                problems.append(f"{cap}/{op}: пары {a} против {b}")
            else:
                problems.append(f"{cap}/{op}: требований {len(a)} против {len(b)}, сценариев "
                                f"{sum(n for _, n in a)} против {sum(n for _, n in b)}, имена и счётчики {a} против {b}")
    assert not problems, (f"фикстура «{fixture}»: разбор скрипта разошёлся с `openspec show --json`: "
                          + "; ".join(problems))


def test_spec_parse_gives_section_name_line_text_for_every_requirement():
    """`trace-graph`: «Узел несёт пометку дельты» — секция дельты, имя, номер строки заголовка и текст у требования."""
    spec = trace_graph.parse_spec(TRACE / "plain" / "specs" / "alpha" / "spec.md")
    got = [(r.section, r.name, r.line) for r in spec.requirements]
    assert got == [("ADDED", "Первое требование", 3), ("ADDED", "Второе требование", 15),
                   ("MODIFIED", "Изменённое требование", 24)]
    assert spec.requirements[0].text == "Система SHALL делать первое."
    assert [(s.name, s.line) for s in spec.requirements[0].scenarios] == [("Первый сценарий", 6), ("Второй сценарий", 11)]
    assert spec.requirements[0].scenarios[1].text == "- **WHEN** d\n- **THEN** e"


def test_spec_parse_takes_text_and_path_alike():
    path = TRACE / "plain" / "specs" / "beta" / "spec.md"
    assert trace_graph.parse_spec(path.read_text(encoding="utf-8")) == trace_graph.parse_spec(path)


def test_spec_parse_skips_headers_inside_code_blocks():
    """Тест-страховка F-85: `### Requirement: x` в блоке кода, как у OpenSpec, не требование."""
    spec = trace_graph.parse_spec(TRACE / "fenced" / "specs" / "gamma" / "spec.md")
    assert [(r.section, r.name) for r in spec.requirements] == [("ADDED", "Требование с примерами"),
                                                                ("ADDED", "Реальное после блоков")]
    assert [len(r.scenarios) for r in spec.requirements] == [2, 1]


def test_spec_parse_lines_are_one_based_as_in_an_editor():
    spec = trace_graph.parse_spec("## ADDED Requirements\n### Requirement: a\n#### Scenario: s\n- x\n")
    assert (spec.requirements[0].line, spec.requirements[0].scenarios[0].line) == (2, 3)


def test_spec_parse_counts_lines_the_same_with_bom_and_crlf():
    raw = (TRACE / "plain" / "specs" / "alpha" / "spec.md").read_bytes().decode("utf-8").replace("\r\n", "\n")
    mixed = "﻿" + raw.replace("\n", "\r\n")
    a, b = trace_graph.parse_spec(raw), trace_graph.parse_spec(mixed)
    assert a == b and a.requirements[0].line == 3


def test_spec_parse_reads_removed_and_renamed_sections():
    spec = trace_graph.parse_spec(TRACE / "removed-renamed" / "specs" / "delta" / "spec.md")
    assert [(r.section, r.name, len(r.scenarios)) for r in spec.requirements] == [
        ("REMOVED", "Убранное заголовком", 1), ("REMOVED", "Убранное строкой", 0),
        ("REMOVED", "Убранное звёздочкой", 0), ("ADDED", "Добавленное рядом", 1)]
    assert [(r.from_name, r.to_name, r.line) for r in spec.renames] == [("Старое имя", "Новое имя", 16)]


def test_spec_parse_reads_odd_headers_as_openspec_does():
    """Что OpenSpec пропускает, пропускает и разбор: пустой сценарий, заголовок вне секций дельты, регистр секции."""
    spec = trace_graph.parse_spec(TRACE / "odd-headers" / "specs" / "omega" / "spec.md")
    got = [(r.section, r.name, [s.name for s in r.scenarios]) for r in spec.requirements]
    assert got == [
        ("ADDED", "С пустым сценарием", ["Сценарий с телом"]),
        ("ADDED", "Сценарий не Scenario", ["Edge case"]),
        ("ADDED", "Разделитель внутри", ["До разделителя"]),
        ("ADDED", "Без пробела после решёток", ["Закрывающие решётки"]),
        ("ADDED", "Имя с закрывающими решётками", ["Глубокий сразу под требованием"]),
        ("ADDED", "Из повторной секции", ["Сценарий повторной секции"]),
        ("MODIFIED", "Изменённое в нижнем регистре", ["Сценарий нижнего регистра"]),
    ]


def test_spec_parse_of_text_without_delta_sections_is_empty():
    spec = trace_graph.parse_spec("# Заголовок\n\n### Requirement: вне дельты\n")
    assert spec.requirements == [] and spec.renames == []


def test_spec_counts_check_names_the_fixture_on_an_extra_scenario():
    """`trace-graph`: «Счётчики разошлись с OpenSpec» — лишний сценарий даёт красную сверку с именем фикстуры."""
    parsed = parse_fixture("plain")
    shown = {cap: {op: list(rows) for op, rows in ops.items()} for cap, ops in own_counts(parsed).items()}
    assert_counts_match("plain", own_counts(parsed), shown)  # без подмены сходится
    parsed["alpha"].requirements[0].scenarios.append(trace_graph.SpecScenario("лишний", 99, "- x"))
    with pytest.raises(AssertionError, match=r"фикстура «plain».*alpha/ADDED.*сценариев 4 против 3"):
        assert_counts_match("plain", own_counts(parsed), shown)


@requires_fork
@pytest.mark.parametrize("fixture", FIXTURES)
def test_spec_counts_match_openspec_show_json(fixture, tmp_path):
    """`trace-graph`: «Счётчики разошлись с OpenSpec» — требования и сценарии по capability равны `openspec show --json`."""
    project = make_project(tmp_path, change_fixture=TRACE / fixture)
    assert_counts_match(fixture, own_counts(parse_fixture(fixture)), shown_counts(project))


@requires_fork
def test_spec_counts_match_openspec_show_json_with_bom_and_crlf(tmp_path):
    """BOM и CRLF OpenSpec снимает до счёта, как и скрипт."""
    copy_dir = tmp_path / "src" / "plain"
    shutil.copytree(TRACE / "plain", copy_dir)
    for spec in copy_dir.glob("specs/*/spec.md"):
        text = spec.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\n", "\r\n")
        spec.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    project = make_project(tmp_path, change_fixture=copy_dir)
    assert_counts_match("plain (BOM, CRLF)", own_counts(parse_fixture("plain", copy_dir.parent)), shown_counts(project))
