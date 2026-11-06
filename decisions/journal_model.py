# -*- coding: utf-8 -*-
"""Модель журнала: загрузка и сохранение JSON, проверка по схеме и по правилам между
записями, разбор markdown-журнала в словарь (`import_md`). От соседних файлов не зависит, внешних пакетов
не требует: код журнала работает на голом Python. Схема журнала лежит рядом с кодом в обеих раскладках (F-41):
в исходнике — в каталоге модуля `decisions/`, в установке — в `.symphysis/tools/`."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

__all__ = [
    "SCHEMA_PATH", "RE_ANCHOR", "RE_REC", "ADDED_MARK", "PROBE_OUTCOMES", "DEVIATION_LABEL",
    "DEVIATION_TAIL", "SETTING",
    "load_journal", "save_journal", "validate_journal", "import_md", "import_md_text",
    "_unquote", "_flat", "_new_record", "_evidence_of",
]


SCHEMA_PATH = Path(__file__).resolve().with_name("journal.schema.json")   # рядом с кодом (F-41)

RE_TITLE = re.compile(r"^# (.*\S)\s*$")
RE_REC = re.compile(r"^## (F-\d+)\s+(.*\S)\s*$")
RE_ANCHOR = re.compile(r"^<!-- journal:(F-\d+) -->\s*$")
RE_GENERATED = re.compile(r"^> Рендер из .+, не править руками\.\s*$")
RE_FIELD = re.compile(r"^- ([^:]+):\s*(.*)$")
RE_OPT = re.compile(r"^  - ([A-ZА-Я])\.\s+(.*\S)\s*$")
RE_EVID = re.compile(r"^\s+- улика:\s*`([^`]+)`\s*«(.+)»\s*$")
RE_UNLIKELY = re.compile(r"^\s+- маловероятно:\s*(.*\S)\s*$")
RE_ANTIPODE = re.compile(r"^([A-ZА-Я])\s*↔\s*(F-\d+\.[A-ZА-Я])$")
RE_DECISION = re.compile(r"^([A-ZА-Я])(?!\w)\s*(?:—\s*(.*?))?\s*(?:,\s*(\d{4}-\d{2}-\d{2}))?$")
RE_RECOMMENDATION = re.compile(r"^([A-ZА-Я])(?!\w)[;,]?\s*(?:—\s*)?(.*)$")
RE_NOTES_HEAD = re.compile(r"^## Заметки\s*$")
RE_NOTE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) — (.*)$")
# `<вид> — <значение>[ — <причина>]`: вид — из двух списков схемы, значение — до первого « — »,
# причина — всё после него (сама может содержать « — »).
RE_OUTCOME = re.compile(r"^(проба|вопрос)\s*—\s*(.*?)(?:\s+—\s+(.*))?$")
DASH = {"—", "-", ""}
ADDED_MARK = "(добавлен человеком"
# Пометка «отступление от постановки» (F-08.A, F-28.E): поле `deviation` варианта развилки — номер факта
# постановки, сценарию которого противоречит поведение варианта. В markdown — хвост строки варианта
# `(отступление от F-NN)` после пометки «добавлен человеком»; импорт разбирает его обратно в поле варианта.
DEVIATION_LABEL = "отступление от постановки"
DEVIATION_TAIL = "(отступление от {})"
RE_DEVIATION_TAIL = re.compile(r"^(.*\S)\s+\(отступление от (F-\d+)\)$")
SETTING = "постановка"   # адресат факта из intent.md (F-17.A)
# Исходы кандидата пробы — слова GSD (F-09.C). Причины исход не требует: слово нужно у выбора мимо рекомендации.
PROBE_OUTCOMES = ("Specify", "Dismiss", "Backstop", "Defer")


# --- импорт из markdown ----------------------------------------------------

def _unquote(text: str) -> str:
    """Снимает ровно одну внешнюю пару «» — слово человека и вопрос парковки хранятся
    без кавычек; «» внутри остаются. Пара внешняя, только если первая « закрыта
    последней »: у `«а» и «б»` глубина вернулась в ноль раньше конца — это два слова
    в кавычках, и строка остаётся как есть."""
    if len(text) < 2 or not (text.startswith("«") and text.endswith("»")):
        return text
    depth = 0
    for i, ch in enumerate(text):
        if ch == "«":
            depth += 1
        elif ch == "»":
            depth -= 1
            if depth == 0 and i < len(text) - 1:
                return text
    return text[1:-1]


def _parse_decision(val: str) -> dict | None:
    if val in DASH:
        return None
    m = RE_DECISION.match(val)
    if not m:
        return {"option": None, "word": val, "date": None}
    return {"option": m.group(1), "word": _unquote((m.group(2) or "").strip()), "date": m.group(3)}


def _parse_recommendation(val: str) -> dict | None:
    """Только вариант и причина: «B для процедур и A для коротких правил» даёт `B` и остаток строки."""
    if val in DASH:
        return None
    m = RE_RECOMMENDATION.match(val)
    if not m:
        return {"option": None, "why": val}
    return {"option": m.group(1), "why": m.group(2).strip()}


def _parse_parking(val: str) -> dict | None:
    if val in DASH:
        return None
    addressee, sep, text = val.partition(" — ")
    if not sep:
        addressee, text = "", val
    return {"addressee": addressee.strip(), "text": _unquote(text.strip())}


def _new_record(rid: str, question: str) -> dict:
    return {"id": rid, "question": question, "kind": "развилка", "status": "открыт",
            "addressee": "", "depends_on": [], "delivery": "", "options": [], "antipodes": [],
            "recommendation": None, "decision": None, "reversibility": None, "outcome": None,
            "parking": [], "dispute": "", "consequences": "", "evidence": [], "comments": []}


def import_md_text(text: str, source: str = "") -> dict:
    """Разбирает markdown-журнал в формате `plan-flexible-pipeline.md` в словарь по схеме.
    Строка `- исход: <вид> — <значение>[ — <причина>]` — в `outcome` (не по форме — пропуск
    с пометкой в stderr). Хвост строки варианта `(отступление от F-NN)` — в `deviation` варианта;
    нет хвоста — нет поля. Раздел `## Заметки` в конце файла — в `notes[]`: строка
    `- <дата> — <текст>`, строки с отступом в два пробела — продолжение текста заметки."""
    journal = {"title": "", "source": source, "records": []}
    intro: list[str] = []
    rec: dict | None = None
    opt: dict | None = None
    mode = None
    notes: list[dict] | None = None  # после «## Заметки» записей нет — только заметки
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if RE_ANCHOR.match(line):
            continue
        if RE_NOTES_HEAD.match(line):
            notes, rec, opt, mode = [], None, None, None
            continue
        if notes is not None:
            m = RE_NOTE.match(line)
            if m:
                notes.append({"date": m.group(1), "text": m.group(2).strip()})
            elif line.startswith("  ") and notes:
                notes[-1]["text"] += "\n" + line[2:]
            elif line.strip():
                print(f"[..] заметки: строка не по форме: {line}", file=sys.stderr)
            continue
        m = RE_REC.match(line)
        if m:
            rec = _new_record(m.group(1), m.group(2))
            journal["records"].append(rec)
            opt, mode = None, None
            continue
        if rec is None:
            m = RE_TITLE.match(line)
            if m and not journal["title"]:
                journal["title"] = m.group(1)
            elif not RE_GENERATED.match(line):
                intro.append(line)
            continue
        m = RE_EVID.match(line)
        if m:
            ev = {"path": m.group(1), "quote": m.group(2)}
            (opt["evidence"] if (mode == "options" and opt) else rec["evidence"]).append(ev)
            continue
        m = RE_UNLIKELY.match(line)
        if m and opt is not None:
            opt["unlikely"] = m.group(1)
            continue
        m = RE_OPT.match(line)
        if m and mode == "options":
            text, deviation = m.group(2), None
            if (tail := RE_DEVIATION_TAIL.match(text)):
                text, deviation = tail.group(1), tail.group(2)
            opt = {"letter": m.group(1), "text": text, "added": ADDED_MARK in text,
                   "unlikely": None, "evidence": []}
            if deviation:
                opt["deviation"] = deviation
            rec["options"].append(opt)
            continue
        m = RE_FIELD.match(line)
        if m and not line.startswith("  "):
            key, val = m.group(1).strip(), m.group(2).strip()
            opt, mode = None, None
            if key == "варианты":
                mode = "options"
            elif key == "улики":
                mode = "evidence"
            elif key == "вид":
                rec["kind"] = val
            elif key == "статус":
                rec["status"] = val
            elif key == "адресат":
                rec["addressee"] = val
            elif key == "поставка":
                rec["delivery"] = val
            elif key == "зависит от":
                rec["depends_on"] = [] if val in DASH else [v.strip() for v in val.split(",") if v.strip()]
            elif key == "антиподы":
                for p in ([] if val in DASH else [p.strip() for p in val.split(";") if p.strip()]):
                    mm = RE_ANTIPODE.match(p)
                    if not mm:
                        print(f"[!!] {rec['id']}: антипод не по форме: {p}", file=sys.stderr)
                        continue
                    rec["antipodes"].append({"option": mm.group(1), "other": mm.group(2)})
            elif key == "рекомендация":
                rec["recommendation"] = _parse_recommendation(val)
            elif key == "решение":
                rec["decision"] = _parse_decision(val)
            elif key == "исход":
                mm = RE_OUTCOME.match(val)
                if val in DASH:
                    rec["outcome"] = None
                elif not mm:
                    print(f"[!!] {rec['id']}: исход не по форме: {val}", file=sys.stderr)
                else:
                    rec["outcome"] = {"kind": mm.group(1), "value": mm.group(2).strip(),
                                      "reason": (mm.group(3) or "").strip()}
            elif key == "парковка":
                parking = _parse_parking(val)
                if parking:
                    rec["parking"].append(parking)
            elif key == "находка":
                if not rec["parking"]:
                    print(f"[!!] {rec['id']}: находка без парковки", file=sys.stderr)
                    rec["parking"].append({"addressee": "", "text": ""})
                rec["parking"][-1]["finding"] = val
            elif key == "спор":
                rec["dispute"] = val
            elif key == "следствия":
                rec["consequences"] = val
            else:
                print(f"[..] {rec['id']}: поле «{key}» журналу неизвестно", file=sys.stderr)
    while intro and not intro[0].strip():
        intro.pop(0)
    while intro and not intro[-1].strip():
        intro.pop()
    if intro:
        journal["intro"] = "\n".join(intro)
    if notes:
        journal["notes"] = notes
    if intro or notes:
        journal["records"] = journal.pop("records")  # порядок ключей как в схеме: записи последними
    return journal


def import_md(path: Path) -> dict:
    path = Path(path)
    return import_md_text(path.read_text(encoding="utf-8"), source=path.name)


# --- файл журнала ----------------------------------------------------------

def load_journal(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_journal(path: Path, journal: dict) -> None:
    text = json.dumps(journal, ensure_ascii=False, indent=1) + "\n"
    Path(path).write_text(text, encoding="utf-8", newline="\n")


# --- проверка --------------------------------------------------------------

# Подмножество JSON Schema 2020-12, которым написан `docs/journal.schema.json`; сообщения — как у `jsonschema`,
# он остался эталоном сверки в тестах (`tests/test_journal_validator.py`).
SCHEMA_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "integer": lambda v: (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer()),
}
SCHEMA_KEYWORDS = {"$schema", "$defs", "$ref", "title", "description", "type", "enum", "pattern", "minLength",
                   "required", "properties", "additionalProperties", "items", "minItems", "maxItems"}
REF_PREFIX = "#/$defs/"


def _refuse_unknown_schema(node: dict, root: dict) -> None:
    """Вся схема до первой проверки: правило, которого проверщик не знает, — `ValueError`, а не молчаливый пропуск,
    в том числе там, куда значение не дойдёт."""
    for keyword, arg in node.items():
        if keyword not in SCHEMA_KEYWORDS:
            raise ValueError(f"схема журнала: правила {keyword} проверщик не знает")
        if keyword in ("properties", "$defs"):
            for sub in arg.values():
                _refuse_unknown_schema(sub, root)
        elif keyword == "items":
            _refuse_unknown_schema(arg, root)
        elif keyword == "type":
            for name in arg if isinstance(arg, list) else [arg]:
                if name not in SCHEMA_TYPES:
                    raise ValueError(f"схема журнала: типа {name} проверщик не знает")
        elif keyword == "additionalProperties" and arg is not False:
            raise ValueError("схема журнала: additionalProperties проверщик знает только как false")
        elif keyword == "$ref" and not (arg.startswith(REF_PREFIX) and arg[len(REF_PREFIX):] in root.get("$defs", {})):
            raise ValueError(f"схема журнала: ссылка {arg} никуда не ведёт")


def _walk_schema(node: dict, root: dict, value, path: list, out: list) -> None:
    for keyword, arg in node.items():
        if keyword == "$ref":
            _walk_schema(root["$defs"][arg[len(REF_PREFIX):]], root, value, path, out)
        elif keyword == "type":
            names = arg if isinstance(arg, list) else [arg]
            if not any(SCHEMA_TYPES[name](value) for name in names):
                out.append((path, keyword, f"{value!r} is not of type {', '.join(map(repr, names))}"))
        elif keyword == "enum":
            if value not in arg:
                out.append((path, keyword, f"{value!r} is not one of {arg!r}"))
        elif keyword == "pattern":
            if isinstance(value, str) and not re.search(arg, value):
                out.append((path, keyword, f"{value!r} does not match {arg!r}"))
        elif keyword == "minLength":
            if isinstance(value, str) and len(value) < arg:
                out.append((path, keyword, f"{value!r} {'should be non-empty' if arg == 1 else 'is too short'}"))
        elif keyword == "minItems":
            if isinstance(value, list) and len(value) < arg:
                out.append((path, keyword, f"{value!r} {'should be non-empty' if arg == 1 else 'is too short'}"))
        elif keyword == "maxItems":
            if isinstance(value, list) and len(value) > arg:
                out.append((path, keyword, f"{value!r} {'is expected to be empty' if arg == 0 else 'is too long'}"))
        elif keyword == "required":
            if isinstance(value, dict):
                out += [(path, keyword, f"{name!r} is a required property") for name in arg if name not in value]
        elif keyword == "additionalProperties":
            extras = sorted((k for k in value if k not in node.get("properties", {})), key=str) \
                if isinstance(value, dict) else []
            if extras:
                names, verb = ", ".join(map(repr, extras)), "was" if len(extras) == 1 else "were"
                out.append((path, keyword, f"Additional properties are not allowed ({names} {verb} unexpected)"))
        elif keyword == "properties":
            if isinstance(value, dict):
                for name, sub in arg.items():
                    if name in value:
                        _walk_schema(sub, root, value[name], [*path, name], out)
        elif keyword == "items":
            if isinstance(value, list):
                for i, item in enumerate(value):
                    _walk_schema(arg, root, item, [*path, i], out)


def _schema_violations(schema: dict, value) -> list[tuple[list, str, str]]:
    """Нарушения схемы: `(путь, ключевое слово, сообщение)`. Схема, в которой есть незнакомое правило, — `ValueError`."""
    _refuse_unknown_schema(schema, schema)
    out: list = []
    _walk_schema(schema, schema, value, [], out)
    return out


def _schema_errors(journal) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = []
    for path, _, message in sorted(_schema_violations(schema, journal), key=lambda v: [str(p) for p in v[0]]):
        if len(path) >= 2 and path[0] == "records" and isinstance(path[1], int):
            rec = journal["records"][path[1]]
            who = rec.get("id") if isinstance(rec, dict) and rec.get("id") else f"records[{path[1]}]"
            where = "/".join(str(p) for p in path[2:])
        else:
            who, where = "журнал", "/".join(str(p) for p in path)
        errors.append(f"{who}: {where + ': ' if where else ''}{message[:300]}")
    return errors


def _deviation_errors(rec: dict, by_id: dict[str, dict]) -> list[str]:
    """`options[].deviation` — только у варианта развилки и только на существующий факт `addressee: постановка`.
    Выбор такого варианта ошибкой не считается: пометка — видимость, не замок (F-55.E). Текст варианта без поля,
    сам оканчивающийся хвостом `(отступление от F-NN)`, — ошибка: импорт рендера принял бы хвост за поле
    и усёк текст."""
    errors = []
    for opt in rec["options"]:
        target = opt.get("deviation")
        if target is None:
            if RE_DEVIATION_TAIL.match(opt["text"].rstrip()):
                errors.append(f"{rec['id']}: вариант {opt['letter']} — текст варианта оканчивается пометкой"
                              " отступления без поля")
            continue
        where = f"{rec['id']}: вариант {opt['letter']} — {DEVIATION_LABEL}"
        fact = by_id.get(target)
        if rec["kind"] != "развилка":
            errors.append(f"{where} у факта — пометка ставится только у варианта развилки")
        elif fact is None:
            errors.append(f"{where} {target} — такой записи нет")
        elif fact["kind"] != "факт" or fact["addressee"] != SETTING:
            what = "развилка" if fact["kind"] == "развилка" else f"факт с адресатом «{fact['addressee']}»"
            errors.append(f"{where} {target} — запись не факт `addressee: {SETTING}`: {what}")
    return errors


def _rule_errors(journal: dict) -> list[str]:
    # Вне схемы: уникальность значения поля в JSON Schema не выражается, а вторую запись с тем же
    # номером молча съели бы словари ниже (F-138.A).
    ids = Counter(r["id"] for r in journal["records"])
    errors = [f"{rid}: номер записи повторяется" for rid, count in ids.items() if count > 1]
    letters = {r["id"]: {o["letter"] for o in r["options"]} for r in journal["records"]}
    by_id = {r["id"]: r for r in journal["records"]}
    for r in journal["records"]:
        rid, own = r["id"], letters[r["id"]]
        if r["kind"] == "факт" and r["options"]:
            errors.append(f"{rid}: у факта нет вариантов, найдено {len(r['options'])}")
        if r["kind"] == "факт" and not r["evidence"] and not r["parking"] and r["status"] != "припаркован":
            errors.append(f"{rid}: факт без улики")
        if r["recommendation"] and not r["recommendation"]["why"].strip():
            errors.append(f"{rid}: рекомендация без why")
        for o in r["options"]:
            if o["unlikely"] is not None and not o["unlikely"].strip():
                errors.append(f"{rid}: вариант {o['letter']} помечен «маловероятно» без причины")
        for dep in r["depends_on"]:
            if dep == rid:
                errors.append(f"{rid}: зависит от самого себя")
            elif dep not in letters:
                errors.append(f"{rid}: зависит от {dep}, такой записи нет")
        for a in r["antipodes"]:
            target, _, letter = a["other"].partition(".")
            if target == rid:
                errors.append(f"{rid}: антипод {a['option']} ↔ {a['other']}: вариант той же записи, варианты одной развилки и так исключают друг друга")
            if a["option"] not in own:
                errors.append(f"{rid}: антипод {a['option']} ↔ {a['other']}: у записи нет варианта {a['option']}")
            if target not in letters:
                errors.append(f"{rid}: антипод {a['option']} ↔ {a['other']}: записи {target} нет")
            elif letter not in letters[target]:
                errors.append(f"{rid}: антипод {a['option']} ↔ {a['other']}: у {target} нет варианта {letter}")
        if r["decision"] and r["decision"]["option"] not in own:
            errors.append(f"{rid}: решение {r['decision']['option']} — такого варианта нет среди {sorted(own)}")
        errors += _deviation_errors(r, by_id)
        outcome = r["outcome"]
        if outcome and outcome["kind"] == "проба":   # лексика «вопрос» — у своего скилла
            if outcome["value"] not in PROBE_OUTCOMES:
                errors.append(f"{rid}: исход пробы «{outcome['value']}» — не из {', '.join(PROBE_OUTCOMES)}")
    return errors


def unexplained_choices(journal: dict) -> list[str]:
    """Решения мимо рекомендации без слова: без него читатель журнала не поймёт выбор. Рекомендованному
    варианту слово не нужно, его причина стоит в `why`; вариант, добавленный человеком, и есть его слова."""
    signals = []
    for r in journal["records"]:
        decision, rec = r["decision"], r["recommendation"]
        if not (decision and rec and rec["option"]) or decision["option"] == rec["option"] or decision["word"].strip():
            continue
        if not any(o["letter"] == decision["option"] and o["added"] for o in r["options"]):
            signals.append(f"{r['id']}: выбран не рекомендованный вариант {decision['option']} без слова")
    return signals


def dependency_cycles(journal: dict) -> list[str]:
    """Циклы в `depends_on`: зависимости идут в одну сторону, а цикл говорит, что каждая запись ждёт другую. Сигнал, а не
    ошибка: журнал с циклом читается и рендерится. Зависимости уже проверены `validate_journal`: ссылки ведут на записи."""
    graph = {r["id"]: r["depends_on"] for r in journal["records"]}
    done, signals = set(), []

    def walk(rid: str, path: list[str]) -> None:
        if rid in path:
            cycle = [*path[path.index(rid):], rid]
            signals.append(f"{rid}: цикл зависимостей {' → '.join(cycle)}")
        elif rid not in done:
            for dep in graph[rid]:
                walk(dep, [*path, rid])
            done.add(rid)

    for rid in graph:
        walk(rid, [])
    return signals


def validate_journal(journal: dict) -> list[str]:
    """Ошибки по схеме и правилам между записями; пустой список — журнал годен.

    Правила проверяются, только если схема соблюдена: на разбитой структуре
    они дали бы ошибки-следствия вместо причины.
    """
    errors = _schema_errors(journal)
    return errors or _rule_errors(journal)


# --- общие хелперы записи --------------------------------------------------

def _flat(text: str) -> str:
    """Текст в одну строку: markdown-формат журнала однострочный (так же слово F-07 лежит в журнале)."""
    return " ".join(text.split())


def _evidence_of(rec: dict) -> list[dict]:
    """Улики записи: свои и у её вариантов."""
    return list(rec["evidence"]) + [ev for opt in rec["options"] for ev in opt["evidence"]]
