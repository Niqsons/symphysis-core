"""Проверка журнала по схеме без внешних пакетов (слово владельца 2026-11-01): `tools/journal*.py`
работают на голом Python. `jsonschema` остаётся только здесь — эталоном сверки; без него сверка
показывается пропуском и пройденной не считается."""
import copy
import json
import subprocess
import sys

import pytest

import journal
import journal_model
from conftest import FIX, ROOT

SCHEMA = json.loads(journal_model.SCHEMA_PATH.read_text(encoding="utf-8"))
TOOLS = ROOT / "tools"


# --- без пакета ------------------------------------------------------------

def without_jsonschema(*args: str) -> subprocess.CompletedProcess:
    """CLI журнала при `sys.modules[имя] = None`: импорт падает так же, как у интерпретатора без пакета."""
    code = ("import runpy, sys; sys.modules['jsonschema'] = None; sys.argv = ['journal.py'] + sys.argv[1:]; "
            f"sys.path.insert(0, {str(TOOLS)!r}); runpy.run_path({str(TOOLS / 'journal.py')!r}, run_name='__main__')")
    return subprocess.run([sys.executable, "-X", "utf8", "-c", code, *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_good_journal_passes_without_jsonschema():
    done = without_jsonschema("check", str(FIX / "journal-deviation.json"))
    assert done.returncode == 0, done.stderr


def test_broken_journal_refused_without_jsonschema(tmp_path):
    """Проверка по схеме не пропускается: без пакета негодный журнал по-прежнему код 1."""
    broken = tmp_path / "decisions.json"
    broken.write_text('{"title": "т", "source": "s.md"}', encoding="utf-8")
    done = without_jsonschema("check", str(broken))
    assert done.returncode == 1
    assert "журнал: 'records' is a required property" in done.stderr


# --- сверка с эталоном ------------------------------------------------------

def ours(doc) -> list:
    return sorted((tuple(map(str, path)), keyword) for path, keyword, _ in journal_model._schema_violations(SCHEMA, doc))


@pytest.fixture
def reference():
    validator = pytest.importorskip("jsonschema").Draft202012Validator(SCHEMA)
    return lambda doc: sorted((tuple(map(str, e.absolute_path)), e.validator) for e in validator.iter_errors(doc))


def rich() -> dict:
    """Журнал, где заполнено каждое поле схемы: мутации доходят до всех ключевых слов."""
    evidence = {"path": "docs/x.md", "quote": "цитата", "line": 3, "found": True, "verdict": "сверено"}
    fork = {
        "id": "F-01", "question": "вопрос?", "kind": "развилка", "status": "решён", "addressee": "человек",
        "depends_on": ["F-02"], "delivery": "П1",
        "options": [{"letter": "A", "text": "вариант", "added": False, "unlikely": None, "evidence": [evidence],
                     "deviation": "F-02"}],
        "antipodes": [{"option": "A", "other": "F-02.A"}],
        "recommendation": {"option": "A", "why": "потому", "text": "A — потому"},
        "decision": {"option": "A", "word": "слово", "date": "2026-11-01"},
        "reversibility": {"level": "дорого", "why": "потому"},
        "outcome": {"kind": "проба", "value": "Specify", "reason": ""},
        "parking": [{"addressee": "ИБ", "text": "вопрос", "finding": "находка"}],
        "dispute": "спор", "consequences": "следствия", "evidence": [evidence],
        "comments": [{"round": "1", "lines": [1, 2], "text": "замечание"}],
    }
    fact = {**fork, "id": "F-02", "kind": "факт", "addressee": "постановка", "options": [], "antipodes": [],
            "recommendation": None, "decision": None, "reversibility": None, "outcome": None, "depends_on": []}
    return {"title": "т", "source": "s.md", "intro": "вступление", "generated": "2026-11-01",
            "notes": [{"date": "2026-11-01", "text": "заметка"}], "records": [fork, fact]}


WRONG = [None, True, 1, 2.0, 1.5, "", "строка", "F-1", "F-1.A", "2026-11-01", [], [1], {}, {"лишнее": 1}]


def spots(node, path=()):
    yield path
    items = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()
    for key, value in items:
        yield from spots(value, (*path, key))


def at(doc, path):
    for key in path:
        doc = doc[key]
    return doc


def mutations(base: dict):
    """На каждом месте документа: подмена значения, удаление, лишние ключи, чужой элемент списка."""
    yield from WRONG
    for path in spots(base):
        node = at(base, path)
        if path:
            for value in WRONG:
                doc = copy.deepcopy(base)
                at(doc, path[:-1])[path[-1]] = value
                yield doc
            doc = copy.deepcopy(base)
            del at(doc, path[:-1])[path[-1]]
            yield doc
        if isinstance(node, dict):
            doc = copy.deepcopy(base)
            at(doc, path).update({"лишнее": 1, "ещё": 2})
            yield doc
        if isinstance(node, list):
            for value in WRONG:
                doc = copy.deepcopy(base)
                at(doc, path).append(value)
                yield doc


def test_rich_journal_is_valid(reference):
    """Основа мутаций годна, иначе сверка мутаций сверяла бы одну и ту же ошибку."""
    assert reference(rich()) == []
    assert ours(rich()) == []


def test_mutations_match_reference(reference):
    checked = 0
    for doc in mutations(rich()):
        assert ours(doc) == reference(doc), doc
        checked += 1
    assert checked > 1000


REAL = [*sorted(ROOT.glob("openspec/changes/*/decisions.json")), ROOT / "docs" / "plan-implementation.journal.json",
        ROOT / "openspec" / "schemas" / "symphysis" / "templates" / "decisions.json", FIX / "journal-deviation.json"]


@pytest.mark.parametrize("path", REAL, ids=lambda p: str(p.relative_to(ROOT)))
def test_real_journals_match_reference(reference, path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert ours(doc) == reference(doc)


def test_imported_markdown_matches_reference(reference):
    doc = journal.import_md(FIX / "journal-plan.md")
    assert ours(doc) == reference(doc)


# --- сообщения --------------------------------------------------------------

@pytest.mark.parametrize("schema, value, message", [
    ({"type": "string"}, 5, "5 is not of type 'string'"),
    ({"type": ["object", "null"]}, 5, "5 is not of type 'object', 'null'"),
    ({"enum": ["а", "б"]}, "в", "'в' is not one of ['а', 'б']"),
    ({"pattern": "^F-\\d+$"}, "x", "'x' does not match '^F-\\\\d+$'"),
    ({"minLength": 1}, "", "'' should be non-empty"),
    ({"minLength": 2}, "x", "'x' is too short"),
    ({"minItems": 1}, [], "[] should be non-empty"),
    ({"minItems": 2}, [1], "[1] is too short"),
    ({"maxItems": 0}, [1], "[1] is expected to be empty"),
    ({"maxItems": 2}, [1, 2, 3], "[1, 2, 3] is too long"),
    ({"required": ["a"]}, {}, "'a' is a required property"),
    ({"additionalProperties": False, "properties": {"a": {}}}, {"b": 1},
     "Additional properties are not allowed ('b' was unexpected)"),
    ({"additionalProperties": False}, {"c": 2, "b": 1},
     "Additional properties are not allowed ('b', 'c' were unexpected)"),
])
def test_message_wording(schema, value, message):
    assert [m for _, _, m in journal_model._schema_violations(schema, value)] == [message]


def test_violation_path_goes_through_refs():
    schema = {"$defs": {"item": {"properties": {"a": {"type": "string"}}}},
              "properties": {"list": {"items": {"$ref": "#/$defs/item"}}}}
    assert journal_model._schema_violations(schema, {"list": [{"a": "да"}, {"a": 5}]}) == \
        [(["list", 1, "a"], "type", "5 is not of type 'string'")]


def test_record_error_named_by_id():
    """Форма строки ошибки прежняя: номер записи, путь внутри неё, сообщение."""
    doc = rich()
    doc["records"][0]["kind"] = "нечто"
    assert journal.validate_journal(doc) == \
        ["F-01: kind: 'нечто' is not one of ['развилка', 'факт']"]


# --- чего проверщик не знает --------------------------------------------------

@pytest.mark.parametrize("schema", [
    {"minimum": 1},
    {"type": "number"},
    {"$ref": "other.json#/x"},
    {"$ref": "#/$defs/нет"},
    {"additionalProperties": {"type": "string"}},
    {"properties": {"a": {"format": "date"}}},
    {"$defs": {"b": {"oneOf": []}}},
    {"items": {"contains": {}}},
], ids=lambda s: json.dumps(s, ensure_ascii=False))
def test_unknown_schema_refused(schema):
    """Новое правило в схеме не игнорируется молча, даже там, куда значение не дойдёт."""
    with pytest.raises(ValueError):
        journal_model._schema_violations(schema, "значение")


# --- антипод внутри одной записи (F-97) ----------------------------------------

def inner_antipode_journal():
    j = journal.import_md(FIX / "journal-plan.md")
    fork = next(r for r in j["records"] if r["kind"] == "развилка" and len(r["options"]) >= 2)
    fork["antipodes"].append({"option": fork["options"][0]["letter"], "other": f"{fork['id']}.{fork['options'][1]['letter']}"})
    return j, fork["id"]


def test_antipode_to_a_variant_of_the_same_record_is_rejected():
    j, rid = inner_antipode_journal()
    errors = journal.validate_journal(j)
    assert any(e.startswith(rid) and "той же записи" in e for e in errors)


def test_antipode_inside_a_record_fails_check_with_the_record_name(tmp_path):
    j, rid = inner_antipode_journal()
    src = tmp_path / "decisions.json"
    src.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    run = subprocess.run([sys.executable, "-X", "utf8", str(TOOLS / "journal.py"), "check", str(src)],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 1 and rid in run.stdout + run.stderr


@pytest.mark.parametrize("path", sorted(ROOT.glob("openspec/changes/*/decisions.json")), ids=lambda p: p.parent.name)
def test_no_journal_of_this_tree_breaks_on_the_new_rule(path):
    assert journal.validate_journal(journal.load_journal(path)) == []
