#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Журнал решений symphysis: источник — JSON, markdown и HTML — рендер (F-01.B).

Схема — `docs/journal.schema.json`. Ключи JSON английские, значения русские.

    py -3.13 tools/journal.py import-md docs/plan-implementation.journal.md \
        --out docs/plan-implementation.journal.json
    py -3.13 tools/journal.py check docs/plan-implementation.journal.json [--strict] [--write]

Подкоманды добавляются по задачам плана (`docs/plan-implementation.tasks.md`,
часть A): render-md, render-html, apply, apply-md4h.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "docs" / "journal.schema.json"
ROOTS_PATH = ROOT / "tools" / "journal-roots.json"
# Префиксы путей улик, которые лежат в самом symphysis (остальные — в journal-roots.json).
OWN_PREFIXES = ("docs/", "upstream/", "CLAUDE.md")

RE_TITLE = re.compile(r"^# (.*\S)\s*$")
RE_REC = re.compile(r"^## (F-\d+)\s+(.*\S)\s*$")
RE_FIELD = re.compile(r"^- ([^:]+):\s*(.*)$")
RE_OPT = re.compile(r"^  - ([A-ZА-Я])\.\s+(.*\S)\s*$")
RE_EVID = re.compile(r"^\s+- улика:\s*`([^`]+)`\s*«(.+)»\s*$")
RE_UNLIKELY = re.compile(r"^\s+- маловероятно:\s*(.*\S)\s*$")
RE_ANTIPODE = re.compile(r"^([A-ZА-Я])\s*↔\s*(F-\d+\.[A-ZА-Я])$")
RE_DECISION = re.compile(r"^([A-ZА-Я])(?!\w)\s*(?:—\s*(.*?))?\s*(?:,\s*(\d{4}-\d{2}-\d{2}))?$")
RE_RECOMMENDATION = re.compile(r"^([A-ZА-Я])(?!\w)[;,]?\s*(?:—\s*)?(.*)$")
DASH = {"—", "-", ""}
ADDED_MARK = "(добавлен человеком"


# --- импорт из markdown ----------------------------------------------------

def _unquote(text: str) -> str:
    """Снимает одну внешнюю пару «» — слово человека хранится без кавычек."""
    if text.startswith("«") and text.endswith("»") and text.count("«") == 1 and text.count("»") == 1:
        return text[1:-1]
    return text


def _parse_decision(val: str) -> dict | None:
    if val in DASH:
        return None
    m = RE_DECISION.match(val)
    if not m:
        return {"option": None, "word": val, "date": None}
    return {"option": m.group(1), "word": _unquote((m.group(2) or "").strip()), "date": m.group(3)}


def _parse_recommendation(val: str) -> dict | None:
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
    """Разбирает markdown-журнал в формате `plan-flexible-pipeline.md` в словарь по схеме."""
    journal = {"title": "", "source": source, "records": []}
    rec: dict | None = None
    opt: dict | None = None
    mode = None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
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
    return errors


def validate_journal(journal: dict) -> list[str]:
    """Ошибки по схеме и правилам между записями; пустой список — журнал годен.

    Правила проверяются, только если схема соблюдена: на разбитой структуре
    они дали бы ошибки-следствия вместо причины.
    """
    errors = _schema_errors(journal)
    return errors or _rule_errors(journal)


# --- сверка улик -----------------------------------------------------------

def _expand_home(value: str) -> Path:
    if value.startswith("<home>"):
        value = str(Path.home()) + value[len("<home>"):]
    return Path(value).expanduser()


def default_roots(roots_file: Path | None = None) -> dict[str, Path]:
    """Префикс пути улики -> каталог. Свои префиксы symphysis плюс файл корней
    (`tools/journal-roots.json` или `roots_file`); `~` и `<home>` — домашний каталог."""
    roots = {prefix: ROOT / prefix for prefix in OWN_PREFIXES}
    raw = json.loads(Path(roots_file or ROOTS_PATH).read_text(encoding="utf-8"))
    roots.update({prefix: _expand_home(value) for prefix, value in raw.items()})
    return roots


def _resolve(path: str, roots: dict[str, Path]) -> Path | None:
    """Файл улики по самому длинному подходящему префиксу; `None` — корня для пути нет."""
    for prefix in sorted(roots, key=len, reverse=True):
        if path.startswith(prefix):
            return roots[prefix] / path[len(prefix):]
    return None


def _map_pos(text: str, flat_pos: int) -> int:
    """Позиция в `text` для позиции в тексте со схлопнутыми пробелами."""
    i = j = 0
    n = len(text)
    while i < n and j < flat_pos:
        if text[i].isspace():
            while i < n and text[i].isspace():
                i += 1
        else:
            i += 1
        j += 1
    return i


def find_quote(path: str, quote: str, roots: dict[str, Path]) -> tuple[int | None, str]:
    """(строка, вердикт): построчно, затем со схлопнутыми пробелами — цитата может
    переходить через перенос строки. Нет строки — вердикт называет причину."""
    file = _resolve(path, roots)
    if file is None:
        return None, "корня для пути нет"
    if not file.is_file():
        return None, "файла нет"
    text = file.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        if quote in line:
            return i, "сверено"
    flat = re.sub(r"\s+", " ", text)
    pos = flat.find(re.sub(r"\s+", " ", quote))
    if pos >= 0:
        return text[: _map_pos(text, pos)].count("\n") + 1, "сверено через перенос"
    return None, "цитаты нет дословно"


def check_evidence(journal: dict, roots: dict[str, Path]) -> dict:
    """Сверяет каждую улику грепом по цитате в файле. Пишет в улики `line`, `found`
    (`False` — сверяли, не нашли) и `verdict`. Несверенная улика — сигнал, не ошибка."""
    total = found = 0
    missing: list[str] = []
    for rec in journal["records"]:
        evidence = list(rec["evidence"])
        for opt in rec["options"]:
            evidence.extend(opt["evidence"])
        for ev in evidence:
            total += 1
            line, verdict = find_quote(ev["path"], ev["quote"], roots)
            ev["line"], ev["found"], ev["verdict"] = line, line is not None, verdict
            if line is not None:
                found += 1
            else:
                missing.append(f"{rec['id']}: {ev['path']} «{ev['quote']}» — {verdict}")
    return {"total": total, "found": found, "missing": missing}


# --- командная строка ------------------------------------------------------

def cmd_check(args: argparse.Namespace) -> int:
    journal = load_journal(args.json)
    errors = validate_journal(journal)
    for e in errors:
        print(f"[!!] {e}", file=sys.stderr)
    if errors:
        return 1
    result = check_evidence(journal, default_roots(args.roots))
    print(f"[ok] улик сверено {result['found']} из {result['total']}")
    for m in result["missing"]:
        print(f"[!!] {m}")
    if args.write:
        save_journal(args.json, journal)
        print(f"[ok] {args.json}")
    return 2 if args.strict and result["missing"] else 0


def cmd_import_md(args: argparse.Namespace) -> int:
    journal = import_md(args.md)
    save_journal(args.out, journal)
    recs = journal["records"]
    forks = sum(1 for r in recs if r["kind"] == "развилка")
    print(f"[ok] записей {len(recs)}: развилок {forks}, фактов {sum(1 for r in recs if r['kind'] == 'факт')}")
    print(f"[ok] {args.out}")
    errors = validate_journal(journal)
    for e in errors:
        print(f"[!!] {e}", file=sys.stderr)
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="journal", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("import-md", help="журнал в markdown -> JSON по схеме")
    p.add_argument("md", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_import_md)
    p = sub.add_parser("check", help="сверить улики грепом по цитате (сигнал, не стоп)")
    p.add_argument("json", type=Path)
    p.add_argument("--roots", type=Path, help="файл корней вместо tools/journal-roots.json")
    p.add_argument("--strict", action="store_true", help="код 2, если есть несверенные улики")
    p.add_argument("--write", action="store_true", help="сохранить line/found/verdict в JSON")
    p.set_defaults(func=cmd_check)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
