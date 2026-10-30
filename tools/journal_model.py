# -*- coding: utf-8 -*-
"""Модель журнала: загрузка и сохранение JSON, проверка по схеме и по правилам между
записями, разбор markdown-журнала в словарь (`import_md`). От соседних модулей не зависит."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

__all__ = [
    "ROOT", "SCHEMA_PATH", "RE_ANCHOR", "RE_REC", "ADDED_MARK", "PROBE_OUTCOMES",
    "load_journal", "save_journal", "validate_journal", "import_md", "import_md_text",
    "_unquote", "_flat", "_new_record", "_evidence_of",
]


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "docs" / "journal.schema.json"

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
# Исходы кандидата пробы — слова GSD (F-09.C): `Dismiss` только с причиной (`edge-probe.md:89`).
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
    """`text` — строка как написана: у составной рекомендации («B для процедур и A для
    коротких правил; …») `option`/`why` — лишь приближение, источником служит `text`."""
    if val in DASH:
        return None
    m = RE_RECOMMENDATION.match(val)
    if not m:
        return {"option": None, "why": val, "text": val}
    return {"option": m.group(1), "why": m.group(2).strip(), "text": val}


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
    с пометкой в stderr). Раздел `## Заметки` в конце файла — в `notes[]`: строка
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
            opt = {"letter": m.group(1), "text": m.group(2), "added": ADDED_MARK in m.group(2),
                   "unlikely": None, "evidence": []}
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

def _schema_errors(journal) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = []
    for err in sorted(Draft202012Validator(schema).iter_errors(journal),
                      key=lambda e: [str(p) for p in e.absolute_path]):
        path = list(err.absolute_path)
        if len(path) >= 2 and path[0] == "records" and isinstance(path[1], int):
            rec = journal["records"][path[1]]
            who = rec.get("id") if isinstance(rec, dict) and rec.get("id") else f"records[{path[1]}]"
            where = "/".join(str(p) for p in path[2:])
        else:
            who, where = "журнал", "/".join(str(p) for p in path)
        errors.append(f"{who}: {where + ': ' if where else ''}{err.message[:300]}")
    return errors


def _rule_errors(journal: dict) -> list[str]:
    errors = []
    letters = {r["id"]: {o["letter"] for o in r["options"]} for r in journal["records"]}
    for r in journal["records"]:
        rid, own = r["id"], letters[r["id"]]
        if r["kind"] == "факт" and r["options"]:
            errors.append(f"{rid}: у факта нет вариантов, найдено {len(r['options'])}")
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
            if a["option"] not in own:
                errors.append(f"{rid}: антипод {a['option']} ↔ {a['other']}: у записи нет варианта {a['option']}")
            if target not in letters:
                errors.append(f"{rid}: антипод {a['option']} ↔ {a['other']}: записи {target} нет")
            elif letter not in letters[target]:
                errors.append(f"{rid}: антипод {a['option']} ↔ {a['other']}: у {target} нет варианта {letter}")
        if r["decision"] and r["decision"]["option"] not in own:
            errors.append(f"{rid}: решение {r['decision']['option']} — такого варианта нет среди {sorted(own)}")
        outcome = r["outcome"]
        if outcome and outcome["kind"] == "проба":   # лексика «вопрос» — у своего скилла
            if outcome["value"] not in PROBE_OUTCOMES:
                errors.append(f"{rid}: исход пробы «{outcome['value']}» — не из {', '.join(PROBE_OUTCOMES)}")
            elif outcome["value"] == "Dismiss" and not outcome["reason"].strip():
                errors.append(f"{rid}: исход Dismiss без причины")
    return errors


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
