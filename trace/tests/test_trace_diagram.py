"""Текст `requirementDiagram` по графу изменения (`trace-diagram`, F-54): конфиг видов, выбор части графа, типы связей."""
import json
import re

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import ROOT
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


def plain(name):
    """Имя без номера: `SCN_12 Есть поле` → `Есть поле` (F-68)."""
    return re.sub(r"^[A-Z]+_[\d.]+ ", "", name)


def titles(text):
    return [plain(name) for name in names(text)]


def links(text):
    return [(plain(a), t, plain(b)) for a, t, b in re.findall(r'^"([^"]+)" - (\w+) -> "([^"]+)"$', text, re.M)]


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
    got = titles(text)
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
    got = titles(diagram(root, "--requirement", "Первое"))
    assert {"Первое", "Есть поле", "Нет поля", "Соседнее"} <= set(got)
    assert any(n.startswith("Сделать") for n in got) and any("Вопрос F-19" in n for n in got)
    assert not {"Далёкое", "Соседний сценарий", "Чужое", "Чужой сценарий"} & set(got)
    assert any("Инъекции" in n for n in got) and any("Ветка отказа" in n for n in got)  # security и ветка сценария (решение к ревью U15)
    assert not any("Пункт про чужое" in n or "Чужая ветка" in n for n in got)


def test_neighbour_is_joined_by_copies_unlike_recorded_links(tmp_path):
    """`trace-diagram`: «Сосед на диаграмме» — связь с соседом идёт типом `copies`, которого нет у записанных связей."""
    text = diagram(project(tmp_path), "--requirement", "Первое")
    assert [t for a, t, b in links(text) if {a, b} == {"Первое", "Соседнее"}] == ["copies"]
    recorded = {t for _, t, _ in links(text) if t != "copies"}
    assert recorded and recorded <= {"contains", "verifies", "traces", "satisfies", "derives", "refines"}


def test_capability_selection_has_no_neighbour_links(tmp_path):
    """`trace-diagram`: «Выбрана capability» — кандидаты соседями идут только при выборе требования (F-71)."""
    assert "copies" not in diagram(project(tmp_path), "--capability", "demo")


def test_whole_change_has_no_copies_links(tmp_path):
    """`trace-diagram`: «Сосед на диаграмме» — без выбора кандидатов нет, связи `copies` в выдаче нет (мелочь ревью U15)."""
    text = diagram(project(tmp_path))
    assert links(text) and "copies" not in {t for _, t, _ in links(text)}


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
    zeta = titles(diagram(root, "--requirement", "zeta/Первое"))
    assert "Первое" in zeta and "Есть поле" not in zeta and "Чужой сценарий" in zeta
    assert "Есть поле" in titles(diagram(root, "--requirement", "demo/Первое"))


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
    assert {"Первое", "Чужое", "Чужой сценарий"} <= set(titles(diagram(root)))
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
    assert (plain(name), "refines", "Первое") in links(text)


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
    assert set(kinds) == {"cap", "req", "scn", "task", "rec", "sec", "branch", "component", "repo", "module", "file"} and len(set(classes)) == len(classes)
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
    declared = set(titles(text))
    assert links(text) and all(a in declared and b in declared for a, _, b in links(text))


def test_blocks_have_required_fields(tmp_path):
    for kind, _, body in blocks(diagram(project(tmp_path))):
        if kind in {"requirement", "designConstraint"}:
            assert re.search(r'^\s*id: "[^"]+"$', body, re.M) and re.search(r'^\s*text: "', body, re.M)
        else:
            assert re.search(r'^\s*type: "[^"]+"$', body, re.M) and "docref:" in body


# --- выбор требования: security и ветки (решение контроллера к ревью U15) --------------

def test_requirement_selection_takes_security_item_and_scenario_branch(tmp_path):
    """`trace-diagram`: «Выбрано требование» — пункт security по `refines` и ветка описи по `verifies` сценария входят."""
    root = project(tmp_path)
    text = diagram(root, "--requirement", "Первое")
    assert ("Инъекции через содержимое файлов", "refines", "Первое") in links(text)
    assert ("Ветка отказа", "verifies", "Есть поле") in links(text)
    far = titles(diagram(root, "--requirement", "Соседнее"))
    assert not any("Инъекции" in n or "Ветка отказа" in n for n in far)


# --- предел текста (5.2, F-66, F-104) ----------------------------------------------------

def big_spec(count):
    """Спека на `count` требований с длинными именами и тремя сценариями: заведомо больше предела."""
    out = ["## ADDED Requirements", ""]
    for i in range(count):
        out += [f"### Requirement: Требование номер {i:03d} " + "длинное " * 8, "Текст SHALL.", ""]
        for j in range(3):
            out += [f"#### Scenario: Сценарий {i:03d}-{j} " + "длинный " * 8, "- **WHEN** a", "- **THEN** b", ""]
    return "\n".join(out)


def big_project(tmp_path):
    return project(tmp_path, specs={"demo": DEMO, "huge": big_spec(70)})


def digits(line):
    return line.replace(" ", "").replace(" ", "")


def test_limit_value_is_config_number():
    assert trace_graph.DIAGRAM["предел"] == 50000


def test_limit_small_change_is_given_whole(tmp_path):
    """`trace-diagram`: «Небольшое изменение» — текст не больше предела выдан целиком, код 0."""
    text = diagram(project(tmp_path))
    assert 0 < len(text) <= 50000 and "Первое" in titles(text)


def test_limit_whole_change_over_limit_is_refused_with_capabilities(tmp_path):
    """`trace-diagram`: «Текст больше предела» — текста нет, код 1, подсказка называет capability, узлы и размер каждой."""
    root = big_project(tmp_path)
    done = run("build", CHANGE, "--format", "mermaid", cwd=root)
    assert done.returncode == 1 and done.stdout == "" and "Traceback" not in done.stderr
    assert "50000" in digits(done.stderr)
    for cap in ("huge", "demo"):
        line = next(l for l in done.stderr.splitlines() if re.search(rf"\b{cap}\b", l) and "узл" in l)
        assert re.search(r"\d{3,}", digits(line))  # число узлов и размер текста
    huge = next(l for l in done.stderr.splitlines() if re.search(r"\bhuge\b", l) and "узл" in l)
    assert str(70 * 4 + 1) in digits(huge)


def test_limit_capability_over_limit_is_refused_with_requirements(tmp_path):
    """`trace-diagram`: «Выбранная capability больше предела» — отказ с кодом, подсказка называет её требования с узлами и размером."""
    root = big_project(tmp_path)
    done = run("build", CHANGE, "--format", "mermaid", "--capability", "huge", cwd=root)
    assert done.returncode == 1 and done.stdout == "" and "Traceback" not in done.stderr
    lines = [l for l in done.stderr.splitlines() if "Требование номер" in l]
    assert len(lines) == 70 and all("узл" in l and re.search(r"\d{3,}", digits(l)) for l in lines)
    assert "--requirement" in done.stderr


def test_limit_does_not_hold_small_capability_next_to_huge_one(tmp_path):
    assert "Первое" in titles(diagram(big_project(tmp_path), "--capability", "demo"))


def test_limit_does_not_hold_requirement_selection(tmp_path):
    """`--requirement` предела не имеет: F-104 называет только целое и capability."""
    one = diagram(big_project(tmp_path), "--requirement", "huge/Требование номер 000 " + "длинное " * 7 + "длинное")
    assert any("Требование номер 000" in n for n in titles(one))


# --- номера (5.3, F-67, F-68, F-73, F-137) ---------------------------------------------

def node(kind, name, nid=None, **extra):
    return {"id": nid or f"{kind}:{name}", "kind": kind, "name": name, "at": "x.md:1", **extra}


def graph_of(nodes, edges=()):
    return {"nodes": list(nodes), "edges": list(edges), "candidates": []}


def hook_keys(text):
    """Находки шаблона `KEY` хука: тот же отбор, что в `gate_hook.py`."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("gate_hook_for_test", ROOT / "tools" / "hooks" / "gate_hook.py")
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    return [m.group(0) for m in hook.KEY.finditer(text) if m.group(1) not in hook.KEY_ALLOW]


def test_number_more_than_nine_nodes_do_not_trip_the_task_key():
    """`trace-diagram`: «Больше девяти узлов» — двенадцать сценариев, шаблон `KEY` из хука находок не даёт."""
    scenarios = [node("scn", f"Сценарий {i}", capability="c", requirement="req:c/R") for i in range(1, 13)]
    nodes = [node("cap", "c"), node("req", "R", "req:c/R", capability="c", section="ADDED")] + scenarios
    text = trace_graph.diagram_text(graph_of(nodes))
    assert "SCN_12 Сценарий 12" in names(text) and "SCN_1 Сценарий 1" in names(text)
    assert hook_keys(text) == []
    dashed = "SCN" + "-12"
    assert hook_keys(dashed) == [dashed]  # шаблон и правда ловит дефис: проверка не пустая


def test_number_record_and_task_take_it_from_themselves_others_count_in_diagram():
    nodes = [node("rec", "Вопрос?", "rec:F-19", number=19), node("task", "Сделать", "task:3.2"),
             node("req", "Первое", "req:c/Первое", capability="c", section="ADDED"),
             node("req", "Второе", "req:c/Второе", capability="c", section="ADDED"),
             node("cap", "c"), node("sec", "Пункт"), node("branch", "Ветка", "branch:a:1")]
    text = trace_graph.diagram_text(graph_of(nodes))
    assert names(text) == ["REC_19 Вопрос?", "TASK_3.2 Сделать", "REQ_1 Первое", "REQ_2 Второе", "CAP_1 c", "SEC_1 Пункт", "BR_1 Ветка"]
    ids = {plain(n): re.search(r'id: "([^"]+)"', body).group(1) for k, n, body in blocks(text) if k != "element"}
    assert ids == {"Первое": "REQ_1", "Второе": "REQ_2", "c": "CAP_1", "Пункт": "SEC_1"}
    assert hook_keys(text) == []


def test_number_equal_scenario_names_make_two_blocks():
    """`trace-diagram`: «Одинаковые имена сценариев» — два блока с разными именами, суффикс id не нужен."""
    nodes = [node("req", "R", "req:c/R", capability="c", section="ADDED"),
             node("scn", "Есть поле", "scn:c/R/Есть поле", capability="c", requirement="req:c/R"),
             node("req", "Q", "req:c/Q", capability="c", section="ADDED"),
             node("scn", "Есть поле", "scn:c/Q/Есть поле", capability="c", requirement="req:c/Q")]
    got = names(trace_graph.diagram_text(graph_of(nodes)))
    assert got.count("SCN_1 Есть поле") == 1 and got.count("SCN_2 Есть поле") == 1 and len(set(got)) == len(got)
    assert not any("scn:" in n or "·" in n for n in got)


def test_number_long_record_question_is_cut_to_90_with_number_kept():
    """`trace-diagram`: «Длинный вопрос записи» — номер и начало вопроса, вместе не длиннее 90 знаков."""
    question = "Как поступить с очень длинным вопросом записи журнала " * 4
    text = trace_graph.diagram_text(graph_of([node("rec", question, "rec:F-19", number=19)]))
    (name,) = names(text)
    assert name.startswith("REC_19 Как поступить") and 85 <= len(name) <= 90 and name == name.rstrip()
    assert f'class "{name}" rec' in text


def test_number_every_name_is_within_90():
    nodes = [node("req", "Т" * 300, "req:c/R", capability="c", section="ADDED"),
             node("scn", "С" * 300, "scn:c/R/С", capability="c", requirement="req:c/R"),
             node("task", "З" * 300, "task:12.34"), node("sec", "П" * 300)]
    assert all(len(n) <= 90 for n in names(trace_graph.diagram_text(graph_of(nodes))))


# --- текст (5.4, F-15, F-54, F-59) -------------------------------------------------------

def test_text_directive_and_markup_are_removed_from_names_and_text():
    """`trace-diagram`: «Директива и разметка в имени» — в тексте нет `%%` и угловых скобок из имени."""
    hostile = "Вход %%{init: {'theme':'forest'}}%% <img src=x> тут"
    nodes = [node("cap", "<b>c</b> %%x", capability="c"), node("req", hostile, "req:c/R", capability="c<i>", section="ADDED"),
             node("sec", "Пункт %% <script>", "sec:p")]
    text = trace_graph.diagram_text(graph_of(nodes))
    assert "%%" not in text
    for _, name, body in blocks(text):
        assert not re.search(r"[<>]", name + body), (name, body)
    joined = " ".join(names(text))
    assert "Вход" in joined and "img src=x" in joined  # слова остаются, снимается разметка


def test_text_double_quote_in_name_does_not_break_the_line():
    """`trace-diagram`: «Двойная кавычка в имени» — имя в одной строке, кавычка заменена на апостроф, блок цел."""
    nodes = [node("req", "R", "req:c/R", capability="c", section="ADDED"),
             node("scn", 'Поле "имя" пустое', "scn:c/R/x", capability="c", requirement="req:c/R", at='a"b.md:3')]
    edges = [{"from": "scn:c/R/x", "to": "req:c/R", "type": "verifies"}]
    text = trace_graph.diagram_text(graph_of(nodes, edges))
    kind, name, body = block_of(text, "Поле")
    assert kind == "element" and name == "SCN_1 Поле 'имя' пустое"
    assert f'class "{name}" scn' in text
    assert re.findall(r'^"([^"]+)" - (\w+) -> "([^"]+)"$', text, re.M) == [("SCN_1 Поле 'имя' пустое", "verifies", "REQ_1 R")]
    assert "docref: \"a'b.md:3\"" in body  # кавычка в docref (мелочь ревью U15)
    assert all(l.count('"') % 2 == 0 for l in text.splitlines())


def test_text_keyword_in_text_and_names_keeps_one_block():
    """`trace-diagram`: «Ключевое слово в тексте» — слово `element` в имени и тексте: блок один, строки целы."""
    nodes = [node("req", "element requirement", "req:c/R", capability="element", section="ADDED")]
    text = trace_graph.diagram_text(graph_of(nodes))
    assert len(blocks(text)) == 1
    assert 'text: "element, ADDED"' in text and names(text) == ["REQ_1 element requirement"]


def test_text_whitespace_and_newlines_in_names_are_collapsed():
    text = trace_graph.diagram_text(graph_of([node("sec", "Первая\nвторая\t строка")]))
    assert names(text) == ["SEC_1 Первая вторая строка"]


# --- обход очистки и уникальность имён (раунд 1 ревью U16) ---------------------------------

BYPASS = ["%<%{init: {'theme':'forest'}}%>%", "%>%{init: {}}%<%", "#37;#37;{init: {'theme':'forest'}}#37;#37;",
          "#lt;b#gt; #60;i#62; #x25;#x25;{init}", "%#37;%{init}%#37;%", "#percnt;#percnt;{init}"]


def _no_bad(text):
    assert "%%" not in text and not re.search(r"[<>]", text) and not re.search(r"#\w+;", text), text


@pytest.mark.parametrize("raw", BYPASS)
def test_text_bypass_forms_do_not_survive_clean_text(raw):
    """`trace-diagram`: «Директива и разметка в имени» — обходные формы директивы и разметки очищаются до неподвижной точки."""
    out = trace_graph.clean_text("a " + raw + " b")
    _no_bad(out)
    assert trace_graph.clean_text(out) == out


@pytest.mark.parametrize("raw", BYPASS)
def test_text_bypass_forms_are_gone_from_name_text_and_docref(raw):
    nodes = [node("req", raw, "req:c/R", capability=raw, section=raw, at=raw),
             node("scn", raw, "scn:c/R/s", capability="c", requirement="req:c/R", at=raw),
             node("sec", raw, "sec:p", at=raw)]
    text = trace_graph.diagram_text(graph_of(nodes))
    for _, name, body in blocks(text):
        _no_bad(name + body)
    assert "%%" not in text


def test_number_all_block_names_are_pairwise_different_with_common_long_start():
    common = "Очень длинное общее начало имени, которое занимает почти всю отведённую длину подписи узла "
    nodes = [node("scn", common + str(i), f"scn:c/R/{i}", capability="c", requirement="req:c/R") for i in range(5)]
    nodes += [node("rec", common + str(i), f"rec:F-{i}", number=i) for i in range(3)]
    nodes += [node("rec", "без числа", "rec:F-x", number=0), node("rec", "без числа", "rec:F-y")]
    got = names(trace_graph.diagram_text(graph_of(nodes)))
    assert len(got) == len(nodes) == len(set(got)) and all(len(n) <= 90 for n in got)
