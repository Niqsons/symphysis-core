"""Скрипт графа трассируемости `tools/trace_graph.py`: каркас подкоманд, проверка имени, реестр артефактов."""
import copy
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
STUB_COMMANDS = ["report", "check", "freeze"]


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
    assert graph_of(root) == {"format": 1, "nodes": [], "edges": [], "candidates": []}


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
    assert set(graph) == {"format", "nodes", "edges", "candidates"}
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
