"""Текст `requirementDiagram` по графу изменения (`trace-diagram`, F-54): конфиг видов, выбор части графа, типы связей."""
import json
import re

import pytest

import trace_graph
from test_trace_graph import CHANGE, make_change, run

DEMO = """## ADDED Requirements

### Requirement: Первое
Текст (F-19) SHALL.

#### Scenario: Есть поле
- **WHEN** a
- **THEN** b

#### Scenario: Нет поля
- **WHEN** c
- **THEN** d

### Requirement: Соседнее
Текст (F-19) SHALL.

#### Scenario: Соседний сценарий
- **WHEN** e

### Requirement: Далёкое
Текст (F-99) SHALL.

#### Scenario: Далёкий сценарий
- **WHEN** f
"""
ZETA = """## ADDED Requirements

### Requirement: Чужое
Текст SHALL.

#### Scenario: Чужой сценарий
- **WHEN** g
"""
TASKS = "## 1. Часть\n\n- [ ] 1.1 Сделать `demo`: «Есть поле» (F-19)\n- [ ] 1.2 Чужое `zeta`: «Чужой сценарий»\n"
SECURITY = ("# Security\n\n| Пункт | Применимо | Чем проверено |\n| --- | --- | --- |\n"
            "| Инъекции через содержимое файлов | применимо | `demo`: «Первое» |\n"
            "| Пункт про чужое | применимо | `zeta`: «Чужое» |\n")
CONSEQ = ("# Последствия\n\n- **Ветка отказа** — `tools/x.py:10` «цитата»\n  сценарий: Есть поле\n"
          "- **Чужая ветка** — `tools/y.py:5` «цитата»\n  сценарий: Чужой сценарий\n")


def project(tmp_path, specs=None):
    return make_change(tmp_path, journal=["F-19", "F-99"], specs=specs or {"demo": DEMO, "zeta": ZETA}, tasks=TASKS,
                       security=SECURITY, consequences=CONSEQ)[0]


def diagram(root, *selection, expect=0):
    done = run("build", CHANGE, "--format", "mermaid", *selection, cwd=root)
    assert done.returncode == expect, done.stderr
    return done.stdout


def blocks(text):
    """Блоки `<тип> "имя" {…}` текста: список `(тип, имя, тело)`."""
    return re.findall(r'^(requirement|designConstraint|element) "([^"]+)" \{\n(.*?)^\}', text, re.S | re.M)


def names(text):
    return [name for _, name, _ in blocks(text)]


def links(text):
    return re.findall(r'^"([^"]+)" - (\w+) -> "([^"]+)"$', text, re.M)


def block_of(text, name_part):
    return next((kind, name, body) for kind, name, body in blocks(text) if name_part in name)


def class_of(text, name):
    found = re.findall(r'^class "' + re.escape(name) + r'" (\w+)$', text, re.M)
    assert len(found) == 1, found
    return found[0]


# --- выбор ---------------------------------------------------------------------

def test_capability_selection_has_only_its_requirements_and_scenarios(tmp_path):
    """`trace-diagram`: «Выбрана capability» — в тексте требования и сценарии только `demo`, файла с рисунком нет."""
    root = project(tmp_path)
    before = sorted(p for p in root.rglob("*") if p.is_file())
    text = diagram(root, "--capability", "demo")
    got = names(text)
    assert text.startswith("requirementDiagram\n")
    assert {"Первое", "Соседнее", "Далёкое", "Есть поле", "Нет поля", "Соседний сценарий"} <= set(got)
    assert not {"Чужое", "Чужой сценарий"} & set(got)
    assert any("Инъекции" in n for n in got) and not any("чужое" in n for n in got)  # пункт security связан с demo
    assert any(n.startswith("Сделать") for n in got) and not any(n.startswith("Чужое `zeta`") for n in got)
    assert not any("Чужая ветка" in n for n in got) and any("Ветка отказа" in n for n in got)
    assert any("Вопрос F-19" in n for n in got)
    assert sorted(p for p in root.rglob("*") if p.is_file()) == before


def test_requirement_selection_has_scenarios_task_record_and_neighbour(tmp_path):
    """`trace-diagram`: «Выбрано требование» — требование, его сценарии, задача, запись и сосед."""
    root = project(tmp_path)
    got = names(diagram(root, "--requirement", "Первое"))
    assert {"Первое", "Есть поле", "Нет поля", "Соседнее"} <= set(got)
    assert any(n.startswith("Сделать") for n in got) and any("Вопрос F-19" in n for n in got)
    assert not {"Далёкое", "Соседний сценарий", "Чужое", "Чужой сценарий"} & set(got)
    assert not any("Инъекции" in n or "Ветка" in n for n in got)  # security и ветки в выборе требования не названы


def test_neighbour_is_joined_by_copies_unlike_recorded_links(tmp_path):
    """`trace-diagram`: «Сосед на диаграмме» — связь с соседом идёт типом `copies`, которого нет у записанных связей."""
    text = diagram(project(tmp_path), "--requirement", "Первое")
    assert [t for a, t, b in links(text) if {a, b} == {"Первое", "Соседнее"}] == ["copies"]
    recorded = {t for _, t, _ in links(text) if t != "copies"}
    assert recorded and recorded <= {"contains", "verifies", "traces", "satisfies", "derives", "refines"}


def test_capability_selection_has_no_neighbour_links(tmp_path):
    """`trace-diagram`: «Выбрана capability» — кандидаты соседями идут только при выборе требования (F-71)."""
    assert "copies" not in diagram(project(tmp_path), "--capability", "demo")


@pytest.mark.parametrize("arg", ["Первое", "demo/Первое"])
def test_requirement_takes_both_forms(tmp_path, arg):
    """`trace-diagram`: «Выбрано требование» — имя и форма `capability/имя` дают одно и то же."""
    root = project(tmp_path)
    assert diagram(root, "--requirement", arg) == diagram(root, "--requirement", "demo/Первое")


def test_same_name_in_two_capabilities_is_refused_with_both_forms(tmp_path):
    """`trace-diagram`: «Одно имя в двух capability» — отказ с кодом, подсказка называет обе формы, такая форма работает."""
    root = project(tmp_path, specs={"demo": DEMO, "zeta": ZETA.replace("Чужое", "Первое")})
    done = run("build", CHANGE, "--format", "mermaid", "--requirement", "Первое", cwd=root)
    assert done.returncode == 1 and done.stdout == ""
    assert "demo/Первое" in done.stderr and "zeta/Первое" in done.stderr and "Traceback" not in done.stderr
    zeta = names(diagram(root, "--requirement", "zeta/Первое"))
    assert "Первое" in zeta and "Есть поле" not in zeta and "Чужой сценарий" in zeta
    assert "Есть поле" in names(diagram(root, "--requirement", "demo/Первое"))


def test_unknown_selection_is_refused_with_known_names(tmp_path):
    root = project(tmp_path)
    for flag, value, hint in (("--capability", "нет", "demo"), ("--requirement", "Нет такого", "Первое")):
        done = run("build", CHANGE, "--format", "mermaid", flag, value, cwd=root)
        assert done.returncode == 1 and hint in done.stderr and done.stdout == ""


def test_selection_without_mermaid_is_refused_and_both_flags_are_usage_error(tmp_path):
    root = project(tmp_path)
    assert run("build", CHANGE, "--capability", "demo", cwd=root).returncode == 1
    assert run("build", CHANGE, "--format", "mermaid", "--capability", "demo", "--requirement", "Первое",
               cwd=root).returncode == 2


def test_no_selection_gives_whole_change_and_default_format_is_json(tmp_path):
    root = project(tmp_path)
    assert {"Первое", "Чужое", "Чужой сценарий"} <= set(names(diagram(root)))
    assert json.loads(run("build", CHANGE, cwd=root).stdout)["nodes"]


def test_empty_change_gives_header_without_blocks_and_links(tmp_path):
    root, _ = make_change(tmp_path)
    text = diagram(root)
    assert text.startswith("requirementDiagram") and blocks(text) == [] and links(text) == []


def test_out_writes_text_to_file_like_json(tmp_path):
    root = project(tmp_path)
    target = tmp_path / "out" / "d.mmd"
    done = run("build", CHANGE, "--format", "mermaid", "--capability", "demo", "--out", str(target), cwd=root)
    assert done.returncode == 0 and done.stdout == ""
    assert target.read_text(encoding="utf-8") == diagram(root, "--capability", "demo")
    assert b"\r" not in target.read_bytes()


def test_text_is_stable_between_runs(tmp_path):
    root = project(tmp_path)
    assert diagram(root, "--capability", "demo") == diagram(root, "--capability", "demo")


def test_build_help_names_format_and_selection():
    done = run("build", "--help")
    assert all(word in done.stdout for word in ("--format", "mermaid", "--capability", "--requirement"))


# --- виды ----------------------------------------------------------------------

def test_scenario_is_element_with_word_type_and_own_class(tmp_path):
    """`trace-diagram`: «Сценарий на диаграмме» — `element` с `type: "сценарий"` и классом своего вида."""
    text = diagram(project(tmp_path), "--requirement", "Первое")
    kind, name, body = block_of(text, "Есть поле")
    assert kind == "element" and 'type: "сценарий"' in body and "id:" not in body
    assert class_of(text, name) == trace_graph.DIAGRAM["виды"]["scn"]["класс"] == "scn"
    assert re.search(r"^classDef scn fill:#\w+,stroke:#\w+", text, re.M)


def test_security_item_is_design_constraint_with_class_and_refines(tmp_path):
    """`trace-diagram`: «Пункт security на диаграмме» — `designConstraint` с классом своего вида, связь `refines`."""
    text = diagram(project(tmp_path), "--capability", "demo")
    kind, name, body = block_of(text, "Инъекции")
    assert kind == "designConstraint" and 'id: "' in body
    assert class_of(text, name) == "sec"
    assert (name, "refines", "Первое") in links(text)


def test_all_kinds_have_sysml_word_and_class_per_config(tmp_path):
    text = diagram(project(tmp_path), "--capability", "demo")
    expect = {"Первое": ("requirement", "req"), "Есть поле": ("element", "scn"), "Сделать": ("element", "task"),
              "Вопрос F-19": ("element", "rec"), "Ветка отказа": ("element", "branch")}
    for part, (sysml, cls) in expect.items():
        kind, name, body = block_of(text, part)
        assert kind == sysml and class_of(text, name) == cls
    for key, word in {"scn": "сценарий", "task": "задача", "rec": "запись", "branch": "ветка"}.items():
        assert trace_graph.DIAGRAM["виды"][key]["type"] == word
        assert f'type: "{word}"' in text
    kind, name, _ = block_of(text, "demo")
    assert kind == "requirement" and class_of(text, name) == "cap"


def test_every_class_has_latin_name_without_hyphen_and_own_colour():
    kinds = trace_graph.DIAGRAM["виды"]
    classes = [row["класс"] for row in kinds.values()]
    assert set(kinds) == {"cap", "req", "scn", "task", "rec", "sec", "branch"} and len(set(classes)) == len(classes)
    assert all(re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", c) for c in classes)
    assert len({(row["заливка"], row["рамка"]) for row in kinds.values()}) == len(kinds)
    assert all(row["префикс"] for row in kinds.values())


def test_link_types_come_from_config():
    cfg = trace_graph.DIAGRAM["связи"]
    assert cfg["candidate"] == "copies" and cfg["refines"] == "refines"
    assert {"contains", "verifies", "traces", "satisfies", "derives"} <= set(cfg)
    assert cfg["candidate"] not in {v for k, v in cfg.items() if k != "candidate"}


# --- текст разбирается: ловушки F-54 ------------------------------------------------

def test_id_in_quotes_class_after_blocks_and_names_do_not_merge(tmp_path):
    spec = DEMO + "\n### Requirement: Повтор\nТекст SHALL.\n\n#### Scenario: Повтор\n- **WHEN** a\n"
    text = diagram(project(tmp_path, specs={"demo": spec, "zeta": ZETA}), "--capability", "demo")
    for _, _, body in blocks(text):
        assert not re.search(r"^\s*id: [^\"]", body, re.M)
    last_block = max(m.end() for m in re.finditer(r"^\}$", text, re.M))
    assert all(m.start() > last_block for m in re.finditer(r"^class ", text, re.M))
    assert len(names(text)) == len(set(names(text)))  # одинаковые имена в диаграмме не сливаются
    assert sum("Повтор" in n for n in names(text)) == 2


def test_every_link_end_is_a_declared_block(tmp_path):
    text = diagram(project(tmp_path))
    declared = set(names(text))
    assert links(text) and all(a in declared and b in declared for a, _, b in links(text))


def test_blocks_have_required_fields(tmp_path):
    for kind, _, body in blocks(diagram(project(tmp_path))):
        if kind in {"requirement", "designConstraint"}:
            assert re.search(r'^\s*id: "[^"]+"$', body, re.M) and re.search(r'^\s*text: "', body, re.M)
        else:
            assert re.search(r'^\s*type: "[^"]+"$', body, re.M) and "docref:" in body
