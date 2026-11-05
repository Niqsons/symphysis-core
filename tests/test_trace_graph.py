"""Скрипт графа трассируемости `tools/trace_graph.py`: каркас подкоманд, проверка имени, реестр артефактов."""
import copy
import hashlib
import json
import shutil
import subprocess
import sys

import pytest

import journal_model
import trace_graph
from conftest import ROOT, requires_fork
from test_schema import make_project, run_openspec

SCHEMA = ROOT / "openspec" / "schemas" / "symphysis" / "schema.yaml"
SCRIPT = ROOT / "tools" / "trace_graph.py"
CHANGE_COMMANDS = ["build", "report", "check", "freeze"]
STUB_COMMANDS = ["freeze"]


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
    done = run(command, name, *(["g.json"] if command == "check" else []), cwd=tmp_path)
    assert done.returncode == 1, done.stdout
    assert "не подходит" in done.stderr and "Traceback" not in done.stderr, done.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["openspec"]


def test_leading_dash_name_is_refused_after_double_dash(tmp_path):
    done = run("build", "--", "-x", cwd=tmp_path)
    assert done.returncode == 1 and "не подходит" in done.stderr, done.stderr


@pytest.mark.parametrize("command", STUB_COMMANDS)
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


# --- build: узлы (U04, F-70, F-80, F-81, F-125, F-131) ------------------------

CHANGE = "demo"


def make_change(tmp_path, journal=None, specs=None, tasks=None, security=None, consequences=None):
    """Проект с изменением `demo`: только `.openspec.yaml` и то, что передано."""
    root = tmp_path / "proj"
    base = root / "openspec" / "changes" / CHANGE
    base.mkdir(parents=True)
    (base / ".openspec.yaml").write_text("schema: symphysis\n", encoding="utf-8")
    if journal is not None:
        records = [journal_model._new_record(rid, f"Вопрос {rid}?") for rid in journal]
        data = {"title": "t", "source": "", "records": records}
        (base / "decisions.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for cap, text in (specs or {}).items():
        (base / "specs" / cap).mkdir(parents=True, exist_ok=True)
        (base / "specs" / cap / "spec.md").write_text(text, encoding="utf-8", newline="\n")
    for name, text in (("tasks.md", tasks), ("security.md", security), ("consequences.md", consequences)):
        if text is not None:
            (base / name).write_text(text, encoding="utf-8", newline="\n")
    return root, base


def build(root):
    return run("build", CHANGE, cwd=root)


def graph_of(root):
    done = build(root)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def ids(graph, kind=None):
    return [n["id"] for n in graph["nodes"] if kind is None or n["kind"] == kind]


SPEC = """## ADDED Requirements

### Requirement: Один
Текст SHALL.

#### Scenario: Первый
- **WHEN** a
- **THEN** b

#### Scenario: Второй
- **WHEN** c
- **THEN** d

## MODIFIED Requirements

### Requirement: Два
Текст SHALL.

#### Scenario: Третий
- **WHEN** e
- **THEN** f
"""


def test_build_of_fresh_change_is_empty_graph_with_code_zero(tmp_path):
    """`trace-graph`: «Только что созданное изменение» — граф пуст, код 0."""
    root, _ = make_change(tmp_path)
    assert graph_of(root) == {"format": 1, "sources": [], "nodes": [], "edges": [], "candidates": []}


def test_build_missing_change_is_refused_with_name(tmp_path):
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    done = run("build", "nope", cwd=tmp_path)
    assert done.returncode == 1 and "nope" in done.stderr and "Traceback" not in done.stderr, done.stderr


def test_graph_grows_with_artifacts_without_filling_step(tmp_path):
    """`trace-graph`: «Граф растёт вместе с артефактами» — журнал даёт записи, спека добавляет требования и сценарии."""
    root, base = make_change(tmp_path, journal=["F-01", "F-02"])
    assert ids(graph_of(root)) == ["rec:F-01", "rec:F-02"]
    (base / "specs" / "cap-a").mkdir(parents=True)
    (base / "specs" / "cap-a" / "spec.md").write_text(SPEC, encoding="utf-8", newline="\n")
    second = graph_of(root)
    assert ids(second, "req") == ["req:cap-a/Один", "req:cap-a/Два"]
    assert ids(second, "scn") == ["scn:cap-a/Один/Первый", "scn:cap-a/Один/Второй", "scn:cap-a/Два/Третий"]
    assert ids(second, "cap") == ["cap:cap-a"]
    assert ids(second, "rec") == ["rec:F-01", "rec:F-02"]


def test_node_shape_has_id_kind_name_and_at_from_change_dir(tmp_path):
    root, _ = make_change(tmp_path, journal=["F-07"], specs={"cap-a": SPEC})
    nodes = {n["id"]: n for n in graph_of(root)["nodes"]}
    req = nodes["req:cap-a/Два"]
    assert req["kind"] == "req" and req["name"] == "Два" and req["section"] == "MODIFIED"
    assert req["capability"] == "cap-a" and req["at"] == "specs/cap-a/spec.md:16"
    scn = nodes["scn:cap-a/Два/Третий"]
    assert scn["name"] == "Третий" and scn["at"] == "specs/cap-a/spec.md:19" and scn["requirement"] == "req:cap-a/Два"
    assert nodes["cap:cap-a"]["at"] == "specs/cap-a/spec.md:1"
    rec = nodes["rec:F-07"]
    assert rec["kind"] == "rec" and rec["name"] == "Вопрос F-07?" and rec["record_kind"] == "развилка"
    assert rec["number"] == 7 and rec["at"].startswith("decisions.json:")
    assert all("\\" not in n["at"] and not n["at"].startswith("/") for n in nodes.values())


def test_rec_at_points_to_the_line_of_the_record_id(tmp_path):
    root, base = make_change(tmp_path, journal=["F-01", "F-02"])
    lines = (base / "decisions.json").read_text(encoding="utf-8").split("\n")
    for node in graph_of(root)["nodes"]:
        line = int(node["at"].rsplit(":", 1)[1])
        assert f'"id": "{node["id"][4:]}"' in lines[line - 1]


def test_same_requirement_name_in_two_capabilities_is_two_nodes(tmp_path):
    """`trace-graph`: «Одно имя в двух capability» — два узла с разными id."""
    root, _ = make_change(tmp_path, specs={"cap-a": SPEC, "cap-b": SPEC})
    reqs = ids(graph_of(root), "req")
    assert sorted(reqs) == ["req:cap-a/Два", "req:cap-a/Один", "req:cap-b/Два", "req:cap-b/Один"]


def test_renamed_requirement_gives_new_id_and_no_old_one(tmp_path):
    """`trace-graph`: «Переименование меняет id» — новый id есть, старого нет."""
    root, base = make_change(tmp_path, specs={"cap-a": SPEC})
    assert "req:cap-a/Один" in ids(graph_of(root))
    renamed = SPEC.replace("Requirement: Один", "Requirement: Новое имя")
    (base / "specs" / "cap-a" / "spec.md").write_text(renamed, encoding="utf-8", newline="\n")
    after = ids(graph_of(root))
    assert "req:cap-a/Новое имя" in after and "req:cap-a/Один" not in after
    assert "scn:cap-a/Новое имя/Первый" in after and "scn:cap-a/Один/Первый" not in after


def test_task_nodes_take_checked_and_unchecked_lines_only(tmp_path):
    tasks = "# Tasks\n\n## 1. Группа\n\n- [ ] 1.1 Первая\n- [x] 1.2 Вторая (F-01)\n- [X] 2.10 Третья\n- 1.3 не задача\n- [ ] без номера\n"
    root, _ = make_change(tmp_path, tasks=tasks)
    nodes = {n["id"]: n for n in graph_of(root)["nodes"]}
    assert list(nodes) == ["task:1.1", "task:1.2", "task:2.10"]
    assert nodes["task:1.2"]["at"] == "tasks.md:6" and nodes["task:1.2"]["name"] == "Вторая (F-01)"
    assert nodes["task:1.2"]["done"] is True and nodes["task:1.1"]["done"] is False


SECURITY = """# Security

| Пункт | Применимо | Чем проверено |
| --- | --- | --- |
| Инъекции через содержимое файлов | применимо | сценарий |
| Права | применимо | сценарий |
"""


def test_security_nodes_take_first_column_of_table_rows(tmp_path):
    root, _ = make_change(tmp_path, security=SECURITY)
    nodes = graph_of(root)["nodes"]
    assert [n["id"] for n in nodes] == ["sec:Инъекции через содержимое файлов", "sec:Права"]
    assert nodes[1]["at"] == "security.md:6" and nodes[1]["name"] == "Права"


CONSEQ = """# Последствия

## Опись

- **Первая** — `tools/a.py:10` «строка один»
  - при отказе: x
- **Вторая** — `tools/a.py:20` «строка два»
- **Без места** — файл целиком, строки нет
- **Третья** — `tools/b.js:5` «строка три»
"""


def test_two_branches_of_one_mechanism_on_different_lines_are_two_nodes(tmp_path):
    """`trace-graph`: «Две ветки одного механизма» — два узла `branch:`; строка описи без места узла не даёт."""
    root, _ = make_change(tmp_path, consequences=CONSEQ)
    nodes = graph_of(root)["nodes"]
    assert [n["id"] for n in nodes] == ["branch:tools/a.py:10", "branch:tools/a.py:20", "branch:tools/b.js:5"]
    assert nodes[0]["at"] == "consequences.md:5" and nodes[0]["name"] == "Первая"


def test_two_builds_without_edits_are_byte_identical_and_sorted(tmp_path):
    """`trace-graph`: «Две сборки без правок» — выводы совпадают байт в байт, узлы идут по файлу и строке."""
    root, _ = make_change(tmp_path, journal=["F-02", "F-01"], specs={"cap-b": SPEC, "cap-a": SPEC},
                          tasks="- [ ] 1.1 a\n", security=SECURITY, consequences=CONSEQ)
    first, second = build(root), build(root)
    assert first.returncode == 0 and first.stdout == second.stdout
    nodes = json.loads(first.stdout)["nodes"]
    keys = [(n["at"].rsplit(":", 1)[0], int(n["at"].rsplit(":", 1)[1])) for n in nodes]
    assert keys == sorted(keys)
    assert [n["id"] for n in nodes if n["kind"] == "scn"][:3] == [
        "scn:cap-a/Один/Первый", "scn:cap-a/Один/Второй", "scn:cap-a/Два/Третий"]


def test_broken_journal_gives_no_graph_and_names_the_file(tmp_path):
    """`trace-graph`: «Журнал не разбирается» — графа нет, код ненулевой, сообщение называет файл."""
    root, base = make_change(tmp_path, specs={"cap-a": SPEC})
    (base / "decisions.json").write_text('{"records": [', encoding="utf-8")
    done = build(root)
    assert done.returncode == 1 and done.stdout == ""
    assert "decisions.json" in done.stderr and "Traceback" not in done.stderr, done.stderr


def test_journal_not_utf8_names_the_file(tmp_path):
    root, base = make_change(tmp_path)
    (base / "decisions.json").write_bytes("{}".encode("utf-16"))
    done = build(root)
    assert done.returncode == 1 and "decisions.json" in done.stderr and "Traceback" not in done.stderr, done.stderr


def test_journal_invalid_by_schema_names_records_as_check_does(tmp_path):
    """`trace-graph`: «Журнал негоден по схеме» — графа нет, код ненулевой, строки называют записи."""
    root, base = make_change(tmp_path, journal=["F-01", "F-02"])
    data = json.loads((base / "decisions.json").read_text(encoding="utf-8"))
    del data["records"][1]["depends_on"]
    (base / "decisions.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    done = build(root)
    assert done.returncode == 1 and done.stdout == ""
    assert "F-02" in done.stderr and "depends_on" in done.stderr and "decisions.json" in done.stderr, done.stderr
    assert "Traceback" not in done.stderr


def test_spec_not_utf8_names_the_file(tmp_path):
    root, base = make_change(tmp_path, specs={"cap-a": SPEC})
    (base / "specs" / "cap-a" / "spec.md").write_bytes("### Requirement: Ж\n".encode("cp1251"))
    done = build(root)
    assert done.returncode == 1 and done.stdout == ""
    assert "specs/cap-a/spec.md" in done.stderr.replace("\\", "/") and "Traceback" not in done.stderr, done.stderr


def test_nothing_artifact_is_not_opened_and_gives_no_nodes(tmp_path, monkeypatch):
    """`trace-graph`: «Артефакт, из которого брать нечего» — узлов из артефакта нет, файл не читается."""
    root, base = make_change(tmp_path, journal=["F-01"], specs={"cap-a": SPEC})
    (base / "decisions.json").write_text("не json вообще", encoding="utf-8")  # открыли бы — отказ
    registry = copy.deepcopy(trace_graph.REGISTRY)
    registry["decisions"] = {"берёт": trace_graph.NOTHING, "довод": "тест: журнал не нужен"}
    monkeypatch.setattr(trace_graph, "REGISTRY", registry)
    graph = trace_graph.build_graph(root, CHANGE)
    assert ids(graph, "rec") == [] and ids(graph, "req") == ["req:cap-a/Один", "req:cap-a/Два"]


def test_registry_row_without_reader_is_refused(tmp_path, monkeypatch):
    root, _ = make_change(tmp_path)
    registry = copy.deepcopy(trace_graph.REGISTRY)
    registry["intent"] = {"берёт": ["что-то"]}
    monkeypatch.setattr(trace_graph, "REGISTRY", registry)
    with pytest.raises(trace_graph.Refusal, match="intent"):
        trace_graph.build_graph(root, CHANGE)


def test_build_help_no_longer_says_not_implemented():
    done = run("build", "--help")
    assert done.returncode == 0 and "ещё не реализована" not in done.stdout and "Коды:" in done.stdout


def test_build_on_this_very_change_gives_nodes_of_every_kind():
    """Живой пример: изменение `trace-graph` из этого дерева."""
    if not (ROOT / "openspec" / "changes" / "trace-graph").is_dir():
        pytest.skip("изменение trace-graph заархивировано: каталога openspec/changes/trace-graph нет")
    graph = json.loads(run("build", "trace-graph", cwd=ROOT).stdout)
    assert {n["kind"] for n in graph["nodes"]} == {"cap", "req", "scn", "rec", "task", "sec", "branch"}
    assert len(set(ids(graph))) == len(graph["nodes"])


# --- дубли id: узел один, сигнал с обоими местами, код 0 (F-31, раунд 1) --------

DUP_REQ = """## ADDED Requirements

### Requirement: Один
Текст SHALL.

#### Scenario: Первый
- **WHEN** a
- **THEN** b

## REMOVED Requirements

### Requirement: Один
Причина.
"""

DUP_SCN = """## ADDED Requirements

### Requirement: Один
Текст SHALL.

#### Scenario: Первый
- **WHEN** a
- **THEN** b

#### Scenario: Первый
- **WHEN** c
- **THEN** d
"""


def assert_duplicate_signal(done, node_id, places):
    assert done.returncode == 0, done.stderr
    assert "Traceback" not in done.stderr
    line = next((row for row in done.stderr.splitlines() if node_id in row), None)
    assert line is not None, done.stderr
    assert all(place in line for place in places), line
    assert [n["id"] for n in json.loads(done.stdout)["nodes"]].count(node_id) == 1


def test_duplicate_requirement_in_one_capability_is_signalled_with_both_places(tmp_path):
    root, _ = make_change(tmp_path, specs={"cap-a": DUP_REQ})
    assert_duplicate_signal(build(root), "req:cap-a/Один", ["specs/cap-a/spec.md:3", "specs/cap-a/spec.md:12"])


def test_duplicate_scenario_in_one_requirement_is_signalled_with_both_places(tmp_path):
    root, _ = make_change(tmp_path, specs={"cap-a": DUP_SCN})
    assert_duplicate_signal(build(root), "scn:cap-a/Один/Первый", ["specs/cap-a/spec.md:6", "specs/cap-a/spec.md:10"])


def test_duplicate_security_item_is_signalled_with_both_places(tmp_path):
    root, _ = make_change(tmp_path, security=SECURITY + "| Права | применимо | ещё раз |\n")
    assert_duplicate_signal(build(root), "sec:Права", ["security.md:6", "security.md:7"])


def test_duplicates_are_returned_to_caller_and_not_put_into_graph_json(tmp_path):
    root, _ = make_change(tmp_path, specs={"cap-a": DUP_REQ})
    graph, dups = trace_graph.build_graph_with_duplicates(root, CHANGE)
    assert dups == [{"id": "req:cap-a/Один", "at": ["specs/cap-a/spec.md:3", "specs/cap-a/spec.md:12"]}]
    assert set(graph) == {"format", "sources", "nodes", "edges", "candidates"}
    assert [n for n in graph["nodes"] if n["id"] == "req:cap-a/Один"][0]["section"] == "ADDED"  # первый по файлу


def test_graph_without_duplicates_has_no_signal(tmp_path):
    root, _ = make_change(tmp_path, specs={"cap-a": SPEC}, security=SECURITY)
    assert build(root).stderr == ""


def test_schema_refusal_carries_error_lines_and_library_stays_quiet(tmp_path, capsys):
    root, base = make_change(tmp_path, journal=["F-01"])
    data = json.loads((base / "decisions.json").read_text(encoding="utf-8"))
    del data["records"][0]["depends_on"]
    (base / "decisions.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(trace_graph.Refusal) as caught:
        trace_graph.build_graph(root, CHANGE)
    assert capsys.readouterr().err == ""
    assert any("depends_on" in row for row in caught.value.lines)


# --- build: связи с местом at (U05, F-06, F-42, F-44, F-70, F-84, F-89, F-92) -----

def edges_of(graph, type_=None):
    return [(e["from"], e["to"], e["type"], e["at"]) for e in graph["edges"] if type_ is None or e["type"] == type_]


def spec_with(*body_lines, scenario="Первый"):
    """Спека с одним требованием `Один` в ADDED: строки тела идут с 4-й; сценарий после них."""
    return ("## ADDED Requirements\n\n### Requirement: Один\n" + "\n".join(body_lines) +
            f"\n\n#### Scenario: {scenario}\n- **WHEN** a\n- **THEN** b\n")


def test_link_names_its_place(tmp_path):
    """`trace-graph`: «Связь называет место» — `traces` к `rec:F-19` несёт `at` со строкой, где номер записан."""
    spec = ("## ADDED Requirements\n\n### Requirement: Один\nТекст SHALL.\n\nИз решения (F-19).\n\n"
            "#### Scenario: Первый\n- **WHEN** a\n")
    root, _ = make_change(tmp_path, journal=["F-19"], specs={"demo": spec})
    assert ("req:demo/Один", "rec:F-19", "traces", "specs/demo/spec.md:6") in edges_of(graph_of(root))


def test_link_is_fixed_by_editing_the_file(tmp_path):
    """`trace-graph`: «Связь правится через файл» — номер заменён в тексте, граф собран снова."""
    root, base = make_change(tmp_path, journal=["F-19", "F-20"], specs={"demo": spec_with("Из решения (F-19).")})
    assert ("req:demo/Один", "rec:F-19", "traces", "specs/demo/spec.md:4") in edges_of(graph_of(root), "traces")
    path = base / "specs" / "demo" / "spec.md"
    path.write_text(path.read_text(encoding="utf-8").replace("(F-19)", "(F-20)"), encoding="utf-8", newline="\n")
    assert [e[1] for e in edges_of(graph_of(root), "traces")] == ["rec:F-20"]


def test_capability_contains_requirement_and_scenario_verifies_it(tmp_path):
    root, _ = make_change(tmp_path, specs={"demo": SPEC})
    graph = graph_of(root)
    assert edges_of(graph, "contains") == [("cap:demo", "req:demo/Один", "contains", "specs/demo/spec.md:3"),
                                           ("cap:demo", "req:demo/Два", "contains", "specs/demo/spec.md:16")]
    assert ("scn:demo/Один/Второй", "req:demo/Один", "verifies", "specs/demo/spec.md:10") in edges_of(graph, "verifies")
    assert len(edges_of(graph, "verifies")) == 3
    assert all(set(e) == {"from", "to", "type", "at"} for e in graph["edges"])


def test_requirement_from_decision_takes_marker_at_word_boundary(tmp_path):
    """`trace-conventions`: «Требование из решения» — `(F-19)` даёт `traces`; `UTF-8` не даёт `F-8`, `F-07.A` идёт к `F-07`."""
    root, _ = make_change(tmp_path, journal=["F-07", "F-08", "F-19"],
                          specs={"demo": spec_with("Кодировка UTF-8 SHALL (F-07.A), (F-19, F-44).")})
    assert [e[1] for e in edges_of(graph_of(root), "traces")] == ["rec:F-07", "rec:F-19"]


def test_requirement_takes_numbers_from_its_text_only(tmp_path):
    """Номер из сценария и из комментария следа связи не даёт."""
    spec = ("## ADDED Requirements\n\n### Requirement: Один\nТекст (F-01) SHALL.\n<!-- проба краёв: F-02 -->\n"
            "<!--\nF-03\n-->\nХвост F-05.\n\n#### Scenario: Первый\n- **WHEN** F-04\n- **THEN** b\n")
    root, _ = make_change(tmp_path, journal=["F-01", "F-02", "F-03", "F-04", "F-05"], specs={"demo": spec})
    assert [e[1] for e in edges_of(graph_of(root), "traces")] == ["rec:F-01", "rec:F-05"]


def test_number_from_master_spec_gives_no_link(tmp_path):
    """`trace-conventions`: «Номер пришёл из мастер-спеки» — `(F-07.A)` уже в мастер-спеке, связи нет; новый номер связь даёт."""
    modified = ("## MODIFIED Requirements\n\n### Requirement: Один\nТекст (F-07.A) и новый (F-19).\n\n"
                "#### Scenario: Первый\n- **WHEN** a\n- **THEN** b\n")
    root, _ = make_change(tmp_path, journal=["F-07", "F-19"], specs={"demo": modified})
    master = root / "openspec" / "specs" / "demo"
    master.mkdir(parents=True)
    (master / "spec.md").write_text("# demo\n\n## Requirements\n\n### Requirement: Один\nТекст (F-07.A).\n\n"
                                    "#### Scenario: Первый\n- **WHEN** a\n- **THEN** b\n", encoding="utf-8", newline="\n")
    assert [e[1] for e in edges_of(graph_of(root), "traces")] == ["rec:F-19"]


def test_master_spec_filters_only_same_named_modified_requirement(tmp_path):
    added = spec_with("Текст (F-07).")  # ADDED с тем же именем: мастер-спека не мешает
    root, _ = make_change(tmp_path, journal=["F-07"], specs={"demo": added})
    master = root / "openspec" / "specs" / "demo"
    master.mkdir(parents=True)
    (master / "spec.md").write_text("## Requirements\n\n### Requirement: Один\nТекст (F-07).\n", encoding="utf-8")
    assert [e[1] for e in edges_of(graph_of(root), "traces")] == ["rec:F-07"]
    modified = added.replace("ADDED", "MODIFIED").replace("Один", "Другой")  # в мастер-спеке такого требования нет
    (root / "openspec" / "changes" / CHANGE / "specs" / "demo" / "spec.md").write_text(modified, encoding="utf-8")
    assert [e[1] for e in edges_of(graph_of(root), "traces")] == ["rec:F-07"]


TASKS = """## 1. Часть

- [ ] 1.1 Закрыть `demo`: «Первый» и (F-19)
- [ ] 1.2 Два имени: `demo`: «Первый», `demo`: «Второй» (F-06, F-99)
- [ ] 1.3 Вложенное: `demo`: «Фильтр «все»»
- [ ] 1.4 Неизвестное: `demo`: «Нет такого», `other`: «Первый»
- [ ] 1.5 Кодировка UTF-8 без номера
"""
TWO_SCN = """## ADDED Requirements

### Requirement: Один
Текст SHALL.

#### Scenario: Первый
- **WHEN** a

#### Scenario: Второй
- **WHEN** a

#### Scenario: Фильтр «все»
- **WHEN** a

#### Scenario: Фильтр
- **WHEN** a
"""


def test_task_names_scenario_with_own_capability_for_each_name(tmp_path):
    """`trace-conventions`: «Одно имя сценария в двух capability» — связь только с названной capability; без наследования."""
    other = TWO_SCN.replace("Один", "Иной")
    root, _ = make_change(tmp_path, journal=["F-19", "F-06"], specs={"demo": TWO_SCN, "z": other}, tasks=TASKS)
    graph = graph_of(root)
    sat = edges_of(graph, "satisfies")
    assert [(e[0], e[1]) for e in sat] == [
        ("task:1.1", "scn:demo/Один/Первый"), ("task:1.2", "scn:demo/Один/Второй"),
        ("task:1.2", "scn:demo/Один/Первый"), ("task:1.3", "scn:demo/Один/Фильтр «все»")]
    assert [e[3] for e in sat] == ["tasks.md:3", "tasks.md:4", "tasks.md:4", "tasks.md:5"]
    assert [(e[0], e[1]) for e in edges_of(graph, "traces") if e[0].startswith("task")] == [
        ("task:1.1", "rec:F-19"), ("task:1.2", "rec:F-06")]


def test_task_scenario_name_in_two_requirements_links_to_both(tmp_path):
    two_reqs = TWO_SCN + "\n### Requirement: Два\nТекст SHALL.\n\n#### Scenario: Первый\n- **WHEN** a\n"
    root, _ = make_change(tmp_path, specs={"demo": two_reqs}, tasks="- [ ] 1.1 `demo`: «Первый»\n")
    assert sorted(e[1] for e in edges_of(graph_of(root), "satisfies")) == ["scn:demo/Два/Первый", "scn:demo/Один/Первый"]


def test_unresolved_references_are_returned_with_what_where_why(tmp_path):
    root, _ = make_change(tmp_path, journal=["F-19", "F-06"], specs={"demo": TWO_SCN}, tasks=TASKS)
    graph, dups, unresolved = trace_graph.build_graph_with_signals(root, CHANGE)
    assert dups == [] and set(graph) == {"format", "sources", "nodes", "edges", "candidates"}
    assert {(u["from"], u["ref"], u["at"]) for u in unresolved} == {
        ("task:1.2", "F-99", "tasks.md:4"),
        ("task:1.4", "`demo`: «Нет такого»", "tasks.md:6"),
        ("task:1.4", "`other`: «Первый»", "tasks.md:6")}
    assert all(u["why"] for u in unresolved)
    assert trace_graph.build_graph_with_duplicates(root, CHANGE)[1] == []
    assert build(root).stderr == ""  # сигнал даст U10, не build


def test_name_without_own_capability_is_not_linked(tmp_path):
    """Имя «Б» в `` `demo`: «А», «Б» `` capability не наследует: связи нет, ссылка не разрешилась (F-89)."""
    root, _ = make_change(tmp_path, specs={"demo": TWO_SCN}, tasks="- [ ] 1.1 `demo`: «Первый», «Второй»\n")
    graph, _, unresolved = trace_graph.build_graph_with_signals(root, CHANGE)
    assert [e[1] for e in edges_of(graph, "satisfies")] == ["scn:demo/Один/Первый"]
    assert [(u["from"], u["ref"]) for u in unresolved] == [("task:1.1", "«Второй»")]


def test_longest_known_name_wins(tmp_path):
    root, _ = make_change(tmp_path, specs={"demo": TWO_SCN}, tasks="- [ ] 1.1 `demo`: «Фильтр «все»» и ещё\n")
    assert [e[1] for e in edges_of(graph_of(root), "satisfies")] == ["scn:demo/Один/Фильтр «все»"]


def test_satisfies_of_wrong_meaning_gives_no_signal(tmp_path):
    """`trace-graph`: «Настоящее имя, неверный смысл» — связь `satisfies` есть, сигнала о ней нет."""
    root, _ = make_change(tmp_path, specs={"demo": TWO_SCN}, tasks="- [ ] 1.1 Совсем другое `demo`: «Второй»\n")
    done = build(root)
    assert done.stderr == ""
    assert edges_of(json.loads(done.stdout), "satisfies")[0][:3] == ("task:1.1", "scn:demo/Один/Второй", "satisfies")


def test_edges_are_sorted_by_file_and_line_and_stable(tmp_path):
    root, _ = make_change(tmp_path, journal=["F-19", "F-06"], specs={"demo": TWO_SCN, "a": SPEC}, tasks=TASKS)
    first = build(root).stdout
    edges = json.loads(first)["edges"]
    keys = [(e["at"].rsplit(":", 1)[0], int(e["at"].rsplit(":", 1)[1])) for e in edges]
    assert keys == sorted(keys) and build(root).stdout == first


def test_duplicate_requirement_gives_links_of_first_only(tmp_path):
    spec = DUP_REQ.replace("Текст SHALL.", "Текст (F-01).").replace("Причина.", "Причина (F-02).")
    root, _ = make_change(tmp_path, journal=["F-01", "F-02"], specs={"cap-a": spec})
    assert [e[1] for e in edges_of(graph_of(root), "traces")] == ["rec:F-01"]


def test_this_very_change_has_links_of_every_kind_of_this_portion():
    """Живой пример: у изменения `trace-graph` есть связи всех видов этой порции."""
    if not (ROOT / "openspec" / "changes" / "trace-graph").is_dir():
        pytest.skip("изменение trace-graph заархивировано: каталога openspec/changes/trace-graph нет")
    graph, _, unresolved = trace_graph.build_graph_with_signals(ROOT, "trace-graph")
    assert {"contains", "verifies", "traces", "satisfies", "refines", "derives"} <= {e["type"] for e in graph["edges"]}


# --- build: связи пункта security, ветки описи и derives (U06, F-56, F-77, F-92, F-131, F-135) -------

def two_cap_specs():
    one = ("## ADDED Requirements\n\n### Requirement: Одно\nТекст SHALL.\n\n#### Scenario: Сцена\n- **WHEN** a\n"
           "\n### Requirement: Режим «атака» группирует строки\nТекст SHALL.\n\n#### Scenario: Сцена два\n- **WHEN** a\n")
    return {"demo": one}


SEC_HEAD = "| Пункт | Применимо | Чем проверено |\n| --- | --- | --- |\n"


def unresolved_of(root):
    return trace_graph.build_graph_with_signals(root, CHANGE)[2]


def master_spec(base, cap, text):
    folder = base.parents[1] / "specs" / cap
    folder.mkdir(parents=True)
    (folder / "spec.md").write_text(text, encoding="utf-8", newline="\n")


def test_security_row_links_to_named_requirement(tmp_path):
    """`trace-graph`: пункт security и требование — связь `refines` от пункта, место — строка таблицы (F-135)."""
    security = SEC_HEAD + "| Пункт А | применимо — закрывает требование `demo` «Одно», сценарий «Сцена» | тест |\n"
    root, _ = make_change(tmp_path, specs=two_cap_specs(), security=security)
    assert edges_of(graph_of(root), "refines") == [("sec:Пункт А", "req:demo/Одно", "refines", "security.md:3")]
    assert unresolved_of(root) == []


def test_security_form_with_colon_other_column_and_quoted_name(tmp_path):
    """Форма с двоеточием, имя в любой колонке, имя с кавычками целиком, два требования в строке."""
    security = SEC_HEAD + ("| Б | `demo`: «Режим «атака» группирует строки» | `demo` «Одно» и `demo`: «Одно» |\n"
                           "| В | сценарий «Сцена» без capability | нет |\n")
    root, _ = make_change(tmp_path, specs=two_cap_specs(), security=security)
    assert edges_of(graph_of(root), "refines") == [
        ("sec:Б", "req:demo/Одно", "refines", "security.md:3"),
        ("sec:Б", "req:demo/Режим «атака» группирует строки", "refines", "security.md:3")]
    assert unresolved_of(root) == []


def test_security_unknown_requirement_is_unresolved(tmp_path):
    """`trace-signals`: «Пункт security закрыт доводом» — неизвестное имя требования идёт в неразрешённые."""
    security = SEC_HEAD + "| Г | применимо — требование `demo` «Нет такого» | тест |\n| Д | без имени | нет |\n"
    root, _ = make_change(tmp_path, specs=two_cap_specs(), security=security)
    assert edges_of(graph_of(root), "refines") == []
    assert [(u["ref"], u["from"], u["at"]) for u in unresolved_of(root)] == [
        ("`demo`: «Нет такого»", "sec:Г", "security.md:3")]


CONSEQ_LINKS = ("## Опись\n\n- **Ветка** — `a/b.py:3` «код»\n  - при отказе: x\n  - сценарий: Сцена\n"
          "  - кандидат: F-1; ближайший сценарий: Одно\n"
          "- **Другая** — `a/b.py:9` «код»\n  - сценарий: Только в мастере\n"
          "- **Третья** — `a/b.py:12` «код»\n  - сценарий: Нигде нет\n")


def test_branch_links_to_scenario_by_name_in_all_capabilities(tmp_path):
    """Связь ветки со сценарием даёт только `сценарий: имя`; имя в двух capability — связи к обоим; мастер — без связи
    и без записи; «ближайший сценарий» связи не даёт."""
    other = "## ADDED Requirements\n\n### Requirement: Иное\nТекст SHALL.\n\n#### Scenario: Сцена\n- **WHEN** a\n"
    root, base = make_change(tmp_path, specs={**two_cap_specs(), "other": other}, consequences=CONSEQ_LINKS)
    master_spec(base, "old", "## Requirements\n\n### Requirement: Старое\nТекст SHALL.\n\n"
                             "#### Scenario: Только в мастере\n- **WHEN** a\n")
    branch = [e for e in edges_of(graph_of(root), "verifies") if e[0].startswith("branch:")]
    assert branch == [("branch:a/b.py:3", "scn:demo/Одно/Сцена", "verifies", "consequences.md:5"),
                      ("branch:a/b.py:3", "scn:other/Иное/Сцена", "verifies", "consequences.md:5")]
    assert [(u["ref"], u["from"], u["at"]) for u in unresolved_of(root)] == [
        ("сценарий: Нигде нет", "branch:a/b.py:12", "consequences.md:10")]


def test_derives_same_capability_other_capability_and_quoted_name(tmp_path):
    """`trace-conventions`: «Родитель в той же capability», «Родитель в другой capability», «Имя родителя с кавычками»."""
    child = ("## ADDED Requirements\n\n### Requirement: Дитя\nЧасть требования «Одно». Текст SHALL.\n\n"
             "### Requirement: Второе\nЧасть требования `demo`: «Одно».\n\n"
             "### Requirement: Третье\nЧасть требования `demo`: «Режим «атака» группирует строки». Текст SHALL.\n\n"
             "#### Scenario: Сцена\n- **WHEN** a\n")
    root, _ = make_change(tmp_path, specs={"demo": two_cap_specs()["demo"], "kid": child})
    got = edges_of(graph_of(root), "derives")
    assert ("req:kid/Второе", "req:demo/Одно", "derives", "specs/kid/spec.md:7") in got
    assert ("req:kid/Третье", "req:demo/Режим «атака» группирует строки", "derives", "specs/kid/spec.md:10") in got
    assert len(got) == 2  # «Одно» без capability ищется в `kid`, где такого нет
    assert [(u["ref"], u["from"]) for u in unresolved_of(root)] == [("«Одно»", "req:kid/Дитя")]


def test_derives_parent_in_same_spec_master_only_and_missing(tmp_path):
    """Родитель в той же спеке — связь; только в мастере — ни связи, ни сигнала; нигде — неразрешённая."""
    spec = ("## ADDED Requirements\n\n### Requirement: Одно\nТекст SHALL.\n\n### Requirement: Дитя\nЧасть требования «Одно».\n\n"
            "### Requirement: Сын мастера\nЧасть требования `old`: «Старое».\n\n"
            "### Requirement: Сирота\nЧасть требования «Такого родителя нет».\n\n#### Scenario: Сцена\n- **WHEN** a\n")
    root, base = make_change(tmp_path, specs={"demo": spec})
    master_spec(base, "old", "## Requirements\n\n### Requirement: Старое\nТекст SHALL.\n\n#### Scenario: С\n- **WHEN** a\n")
    assert edges_of(graph_of(root), "derives") == [("req:demo/Дитя", "req:demo/Одно", "derives", "specs/demo/spec.md:7")]
    assert [(u["ref"], u["from"]) for u in unresolved_of(root)] == [("«Такого родителя нет»", "req:demo/Сирота")]


def test_derives_phrase_inside_code_or_scenario_is_not_a_link(tmp_path):
    """Фраза в обратных кавычках и в сценарии связи не даёт."""
    spec = ("## ADDED Requirements\n\n### Requirement: Одно\nТекст SHALL.\n\n### Requirement: Два\n"
            "Фраза `Часть требования «Одно».` в кавычках.\n\n#### Scenario: Сцена\n- **GIVEN** Часть требования «Одно».\n")
    root, _ = make_change(tmp_path, specs={"demo": spec})
    assert edges_of(graph_of(root), "derives") == [] and unresolved_of(root) == []


def test_master_spec_with_crlf_is_read_like_lf(tmp_path):
    """Мастер-спека с CRLF (так лежит `openspec/specs/project-settings`) читается как с LF: сценарий из неё не неразрешённый."""
    spec = "## ADDED Requirements\n\n### Requirement: Одно\nТекст SHALL.\n\n#### Scenario: Сцена\n- **WHEN** a\n"
    root, base = make_change(tmp_path, specs={"demo": spec}, consequences=CONSEQ_LINKS)
    master_spec(base, "old", "## Requirements\n\n### Requirement: Старое\nТекст SHALL.\n\n"
                             "#### Scenario: Только в мастере\n- **WHEN** a\n".replace("\n", "\r\n"))
    names = [u["ref"] for u in unresolved_of(root)]
    assert "сценарий: Только в мастере, мастер-спека `old`" not in names and "сценарий: Только в мастере" not in names


# --- build: кандидаты связей и --out (U07, F-23, F-41, F-71) ---------------------------------------

def two_reqs_on(*numbers):
    """Два требования на одни и те же записи."""
    tail = " ".join(f"(F-{n})" for n in numbers)
    return ("## ADDED Requirements\n\n"
            f"### Requirement: Первое\nТекст {tail} SHALL.\n\n### Requirement: Второе\nТекст {tail} SHALL.\n\n"
            "### Requirement: Чужое\nТекст (F-99) SHALL.\n\n#### Scenario: Сцена\n- **WHEN** a\n")


def test_requirements_with_shared_record_are_candidates_not_edges(tmp_path):
    """`trace-graph`: «Вывод без файла» — граф несёт `candidates`; пара с общей записью (F-19) там есть, в `edges` её нет (F-23, F-71)."""
    root, _ = make_change(tmp_path, journal=["F-19", "F-99"], specs={"demo": two_reqs_on(19)})
    graph = graph_of(root)
    assert graph["candidates"] == [{"a": "req:demo/Второе", "b": "req:demo/Первое",
                                    "source": "общие записи журнала", "shared": ["rec:F-19"]}]
    pair = {"req:demo/Первое", "req:demo/Второе"}
    assert not [e for e in graph["edges"] if {e["from"], e["to"]} == pair]


def test_candidate_pair_is_unordered_once_with_all_shared_records_and_stable(tmp_path):
    root, _ = make_change(tmp_path, journal=["F-19", "F-20", "F-99"], specs={"demo": two_reqs_on(20, 19)})
    first = build(root).stdout
    got = json.loads(first)["candidates"]
    assert len(got) == 1 and got[0]["shared"] == ["rec:F-19", "rec:F-20"] and got[0]["a"] < got[0]["b"]
    assert build(root).stdout == first


def test_no_shared_record_gives_no_candidates_and_task_does_not_make_one(tmp_path):
    spec = ("## ADDED Requirements\n\n### Requirement: Один\nТекст (F-19).\n\n### Requirement: Два\nТекст (F-20).\n\n"
            "#### Scenario: Сцена\n- **WHEN** a\n")
    root, _ = make_change(tmp_path, journal=["F-19", "F-20"], specs={"demo": spec}, tasks="- [ ] 1.1 a (F-19)\n")
    assert graph_of(root)["candidates"] == []


def files_state(base):
    return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(base.rglob("*")) if p.is_file()}


def test_build_without_out_writes_no_file_in_change_dir(tmp_path):
    """`trace-graph`: «Вывод без файла» — список и хеши файлов каталога изменения те же, граф в stdout."""
    root, base = make_change(tmp_path, journal=["F-19"], specs={"demo": two_reqs_on(19)}, tasks="- [ ] 1.1 a\n")
    before = files_state(base)
    done = build(root)
    assert done.returncode == 0 and json.loads(done.stdout)["nodes"] and files_state(base) == before


def test_build_with_out_writes_graph_there_and_leaves_change_files(tmp_path):
    """`trace-graph`: «Запись в указанный файл» — по пути лежит граф, файлы изменения не изменены; путь от текущего каталога."""
    root, base = make_change(tmp_path, journal=["F-19"], specs={"demo": two_reqs_on(19)})
    before = files_state(base)
    done = run("build", CHANGE, "--out", "out/g.json", cwd=root)
    assert done.returncode == 0 and done.stdout == ""
    written = json.loads((root / "out" / "g.json").read_text(encoding="utf-8"))
    assert written == graph_of(root) and files_state(base) == before
    absolute = tmp_path / "abs.json"
    assert run("build", CHANGE, "--out", str(absolute), cwd=root).returncode == 0
    assert json.loads(absolute.read_text(encoding="utf-8")) == written


def test_duplicate_signal_goes_to_stderr_with_and_without_out(tmp_path):
    spec = DUP_REQ
    root, _ = make_change(tmp_path, specs={"cap-a": spec})
    assert "дубль id" in build(root).stderr
    done = run("build", CHANGE, "--out", "g.json", cwd=root)
    assert "дубль id" in done.stderr and done.stdout == ""


def test_out_that_cannot_be_written_is_a_refusal(tmp_path):
    root, _ = make_change(tmp_path)
    (root / "занято").write_text("x", encoding="utf-8")
    done = run("build", CHANGE, "--out", "занято/g.json", cwd=root)
    assert done.returncode == 1 and "Traceback" not in done.stderr and "занято" in done.stderr


def test_build_help_names_out():
    assert "--out" in run("build", "--help").stdout


def test_security_requirement_only_in_master_gives_no_link_and_no_record(tmp_path):
    """Требование, которое есть только в мастер-спеке, пункт security не связывает и неразрешённым не делает (как derives)."""
    security = SEC_HEAD + ("| Е | применимо — требование `old` «Старое» | тест |\n"
                           "| Ж | применимо — требование `old` «Нигде» | тест |\n")
    root, base = make_change(tmp_path, specs=two_cap_specs(), security=security)
    master_spec(base, "old", "## Requirements\n\n### Requirement: Старое\nТекст SHALL.\n\n#### Scenario: С\n- **WHEN** a\n")
    assert edges_of(graph_of(root), "refines") == []
    assert [(u["ref"], u["from"]) for u in unresolved_of(root)] == [("`old`: «Нигде»", "sec:Ж")]


def test_capitalized_nearest_scenario_gives_no_branch_link(tmp_path):
    """«Ближайший сценарий:» в начале строки связи не даёт, как и строчный."""
    conseq = ("## Опись\n\n- **Ветка** — `a/b.py:3` «код»\n  - при отказе: x\n"
              "  - Ближайший сценарий: Нигде нет\n  - ближайший сценарий: Нигде нет\n")
    root, _ = make_change(tmp_path, specs=two_cap_specs(), consequences=conseq)
    assert [e for e in edges_of(graph_of(root), "verifies") if e[0].startswith("branch:")] == []
    assert unresolved_of(root) == []


# --- check: сохранённый файл графа (U08, F-41, F-86, F-87, F-118) ---------------

def saved(root, name="g.json"):
    """Граф `demo`, записанный `build --out` в `name` от корня проекта."""
    assert run("build", CHANGE, "--out", name, cwd=root).returncode == 0
    return root / name


def check(root, name="g.json"):
    return run("check", CHANGE, name, cwd=root)


def checked_change(tmp_path):
    root, base = make_change(tmp_path, journal=["F-19"], specs={"demo": two_reqs_on(19)}, tasks="- [ ] 1.1 a (F-19)\n",
                             security=SEC_HEAD + "| Е | применимо | тест |\n")
    return root, base, saved(root)


def test_graph_sources_list_files_read_with_lf_hash_in_stable_order(tmp_path):
    """`trace-graph`: «Файл свежий» — `sources`: путь от каталога изменения и sha256 после приведения концов строк к LF (F-87)."""
    root, base, path = checked_change(tmp_path)
    got = json.loads(path.read_text(encoding="utf-8"))["sources"]
    assert [s["path"] for s in got] == ["decisions.json", "security.md", "specs/demo/spec.md", "tasks.md"]
    for s in got:
        text = (base / s["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert s["sha256"] == hashlib.sha256(text).hexdigest()
    assert set(got[0]) == {"path", "sha256"}


def test_check_fresh_file_gives_no_signals_and_code_zero(tmp_path):
    """`trace-graph`: «Файл свежий» — сигналов нет, код 0."""
    root, _, _ = checked_change(tmp_path)
    done = check(root)
    assert done.returncode == 0 and "[!!]" not in done.stdout and "сигналов нет" in done.stdout, done.stdout


def test_check_changed_source_names_the_file_with_code_zero(tmp_path):
    """`trace-graph`: «Исходник изменён» — сигнал «устарел» называет `tasks.md`, код 0."""
    root, base, _ = checked_change(tmp_path)
    (base / "tasks.md").write_text("- [ ] 1.1 b (F-19)\n", encoding="utf-8", newline="\n")
    done = check(root)
    lines = [l for l in done.stdout.splitlines() if l.startswith("[!!]")]
    assert done.returncode == 0 and len(lines) == 1 and "устарел" in lines[0] and "tasks.md" in lines[0], done.stdout


@pytest.mark.parametrize("mutate, expect", [
    (lambda d: d.pop("format"), "format"),
    (lambda d: d.pop("edges"), "edges"),
    (lambda d: d.pop("sources"), "sources"),
    (lambda d: d.update(nodes={}), "nodes"),
])
def test_check_wrong_shape_names_file_and_what_is_missing(tmp_path, mutate, expect):
    """`trace-graph`: «Форма не та» — сигнал называет файл и что в нём не так, код 0."""
    root, _, path = checked_change(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    done = check(root)
    lines = [l for l in done.stdout.splitlines() if l.startswith("[!!]")]
    assert done.returncode == 0 and len(lines) >= 1 and all("g.json" in l for l in lines), done.stdout
    assert expect in done.stdout and "устарел" not in done.stdout


def test_check_file_that_is_not_json_or_missing_is_a_shape_signal(tmp_path):
    """`trace-graph`: «Форма не та» — не JSON и нет файла: сигнал с именем файла, код 0."""
    root, _, path = checked_change(tmp_path)
    path.write_text("{не json", encoding="utf-8")
    done = check(root)
    assert done.returncode == 0 and "[!!]" in done.stdout and "g.json" in done.stdout and "Traceback" not in done.stderr
    done = check(root, "нет.json")
    assert done.returncode == 0 and "[!!]" in done.stdout and "нет.json" in done.stdout


def test_check_new_and_removed_source_are_named(tmp_path):
    """`trace-graph`: «Появился новый исходник» — «устарел» называет новый файл; удалённый исходник называется так же (F-86)."""
    root, base, _ = checked_change(tmp_path)
    (base / "specs" / "new").mkdir()
    (base / "specs" / "new" / "spec.md").write_text(two_reqs_on(19), encoding="utf-8", newline="\n")
    (base / "security.md").unlink()
    done = check(root)
    lines = [l for l in done.stdout.splitlines() if l.startswith("[!!]")]
    assert done.returncode == 0 and all("устарел" in l for l in lines), done.stdout
    assert any("specs/new/spec.md" in l for l in lines) and any("security.md" in l for l in lines)


def test_check_only_line_endings_changed_gives_no_signal(tmp_path):
    """`trace-graph`: «Изменились только концы строк» — сигнала «устарел» нет (F-87)."""
    root, base, _ = checked_change(tmp_path)
    for rel in ("tasks.md", "specs/demo/spec.md"):
        raw = (base / rel).read_bytes()
        (base / rel).write_bytes(raw.replace(b"\n", b"\r\n"))
    done = check(root)
    assert done.returncode == 0 and "[!!]" not in done.stdout and "сигналов нет" in done.stdout, done.stdout


def test_check_edited_node_in_fresh_file_names_file_and_difference(tmp_path):
    """`trace-graph`: «Узел поправлен в файле» — файл свежий по хешам, узел поправлен: сигнал называет файл и расхождение (F-118)."""
    root, _, path = checked_change(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    victim = data["nodes"][0]["id"]
    data["nodes"][0]["name"] = "Подделка"
    extra = {"id": "req:demo/Лишнее", "kind": "req", "name": "Лишнее", "at": "specs/demo/spec.md:1"}
    data["nodes"].append(extra)
    gone = data["edges"].pop()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    done = check(root)
    lines = [l for l in done.stdout.splitlines() if l.startswith("[!!]")]
    assert done.returncode == 0 and lines and all("g.json" in l for l in lines), done.stdout
    assert "устарел" not in done.stdout
    assert victim in done.stdout and "req:demo/Лишнее" in done.stdout and gone["from"] in done.stdout


def test_check_edited_candidates_are_a_signal(tmp_path):
    """`trace-graph`: «Узел поправлен в файле» — расхождение в `candidates` тоже замечено."""
    root, _, path = checked_change(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["candidates"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    assert "candidates" in check(root).stdout


def test_check_graph_signals_function_returns_list_and_prints_nothing(tmp_path, capsys):
    """Функция для заморозки: сигналы списком, ничего не печатает."""
    root, base, path = checked_change(tmp_path)
    assert trace_graph.check_graph_file(root, CHANGE, path) == []
    (base / "tasks.md").write_text("- [ ] 9.9 z\n", encoding="utf-8", newline="\n")
    signals = trace_graph.check_graph_file(root, CHANGE, path)
    assert len(signals) == 1 and "tasks.md" in signals[0] and capsys.readouterr().out == ""


def test_check_missing_change_and_bad_name_are_refusals(tmp_path):
    """`trace-graph`: «Имя изменения с символами оболочки» и нет изменения — код 1, без трассировки."""
    (tmp_path / "openspec").mkdir()
    done = run("check", CHANGE, "g.json", cwd=tmp_path)
    assert done.returncode == 1 and "Traceback" not in done.stderr and CHANGE in done.stderr
    done = run("check", "a/b", "g.json", cwd=tmp_path)
    assert done.returncode == 1 and "не подходит" in done.stderr


def test_check_help_names_arguments_and_codes():
    text = run("check", "--help").stdout
    assert "ФАЙЛ" in text and "ещё не реализована" not in text and "Коды:" in text
