#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Рендер журнала решений в просмотрщик playground. СПАЙК.

Читает журнал в формате `plan-flexible-pipeline.md` (раздел «Журнал
решений» с добавками `маловероятно:`, `антиподы:`, `улики:`, `парковка:`,
`находка:`, `спор:`), сверяет каждую улику грепом по цитате в файле,
встраивает JSON в HTML-шаблон и пишет просмотрщик. Журнал не меняет.
Несверенная улика — сигнал в выводе и пометка в HTML, не стоп (F-12).

    py -3.13 tools/journal_render.py docs/plan-implementation.journal.md \
        --out docs/plan-implementation.html

Корни путей улик: `docs/…`, `upstream/…`, `CLAUDE.md` — symphysis;
`store/…` — X:\\skills-store; `playground/…` — скилл playground в плагине;
`md4h/…` — расширение Markdown Editor for Humans.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

SYMPHYSIS = pathlib.Path(__file__).resolve().parent.parent
HOME = pathlib.Path.home()
ROOTS = [
    ("store/", pathlib.Path(r"X:\skills-store")),
    ("playground/", HOME / ".claude" / "plugins" / "marketplaces" / "claude-plugins-official"
     / "plugins" / "playground" / "skills" / "playground"),
    ("md4h/", HOME / ".vscode" / "extensions" / "concretio.markdown-for-humans-0.4.5"),
]

RE_REC = re.compile(r"^## (F-\d+)\s+(.*\S)\s*$")
RE_FIELD = re.compile(r"^- ([^:]+):\s*(.*)$")
RE_OPT = re.compile(r"^  - ([A-ZА-Я])\.\s+(.*\S)\s*$")
RE_EVID = re.compile(r"^\s+- улика:\s*`([^`]+)`\s*«(.+)»\s*$")
RE_UNLIKELY = re.compile(r"^\s+- маловероятно:\s*(.*\S)\s*$")
RE_ANTIPODE = re.compile(r"^([A-ZА-Я])\s*↔\s*(F-\d+\.[A-ZА-Я])$")
RE_DECISION = re.compile(r"^([A-ZА-Я])\b\s*(?:—\s*(.*?))?,?\s*(\d{4}-\d{2}-\d{2})?$")
DASH = {"—", "-", ""}
ADDED_MARK = "(добавлен человеком"


def resolve(path: str) -> pathlib.Path:
    for prefix, root in ROOTS:
        if path.startswith(prefix):
            return root / path[len(prefix):]
    return SYMPHYSIS / path


def _map_pos(text: str, flat_pos: int) -> int:
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


def find_quote(path: str, quote: str) -> tuple[int | None, str]:
    file = resolve(path)
    if not file.is_file():
        return None, "файла нет"
    text = file.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        if quote in line:
            return i, "сверено"
    flat = re.sub(r"\s+", " ", text)
    q = re.sub(r"\s+", " ", quote)
    pos = flat.find(q)
    if pos >= 0:
        return text[: _map_pos(text, pos)].count("\n") + 1, "сверено через перенос"
    return None, "цитаты нет дословно"


def parse_decision(val: str) -> dict | None:
    if val in DASH:
        return None
    m = RE_DECISION.match(val)
    if not m:
        return {"option": None, "text": val}
    return {"option": m.group(1), "word": (m.group(2) or "").strip(), "date": m.group(3), "text": val}


def parse_parking(val: str) -> dict | None:
    if val in DASH:
        return None
    addressee, sep, text = val.partition(" — ")
    return {"addressee": addressee.strip() if sep else "", "text": text.strip() if sep else val}


def new_record(rid: str, question: str) -> dict:
    return {"id": rid, "question": question, "kind": "развилка", "status": "открыт",
            "addressee": "", "depends_on": [], "delivery": "", "options": [], "evidence": [],
            "antipodes": [], "recommendation": None, "decision": None, "consequences": "",
            "parking": None, "finding": "", "dispute": ""}


def parse(journal: pathlib.Path) -> list[dict]:
    records: list[dict] = []
    rec: dict | None = None
    opt: dict | None = None
    mode = None
    for raw in journal.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\r")
        m = RE_REC.match(line)
        if m:
            rec = new_record(m.group(1), m.group(2))
            records.append(rec)
            opt, mode = None, None
            continue
        if rec is None:
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
            text = m.group(2)
            opt = {"letter": m.group(1), "text": text, "evidence": [], "unlikely": None,
                   "added": ADDED_MARK in text}
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
                if val not in DASH:
                    letter, _, why = val.partition(" — ")
                    rec["recommendation"] = {"option": letter.strip(), "why": why.strip()}
            elif key == "решение":
                rec["decision"] = parse_decision(val)
            elif key == "парковка":
                rec["parking"] = parse_parking(val)
            elif key == "находка":
                rec["finding"] = val
            elif key == "спор":
                rec["dispute"] = val
            elif key == "следствия":
                rec["consequences"] = val
            else:
                print(f"[..] {rec['id']}: поле «{key}» просмотрщику неизвестно", file=sys.stderr)
    return records


def verify(records: list[dict]) -> dict:
    total = found = 0
    missing: list[str] = []
    for rec in records:
        evs = list(rec["evidence"])
        for o in rec["options"]:
            evs.extend(o["evidence"])
        for ev in evs:
            total += 1
            line, verdict = find_quote(ev["path"], ev["quote"])
            ev["line"], ev["verdict"], ev["found"] = line, verdict, line is not None
            if line is not None:
                found += 1
            else:
                missing.append(f"{rec['id']}: `{ev['path']}` «{ev['quote']}» — {verdict}")
    return {"evidence_total": total, "evidence_found": found, "missing": missing}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("journal", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--template", type=pathlib.Path,
                    default=SYMPHYSIS / "tools" / "playground-template.html")
    args = ap.parse_args()

    records = parse(args.journal)
    stats = verify(records)
    forks = [r for r in records if r["kind"] == "развилка"]
    facts = [r for r in records if r["kind"] == "факт"]
    decided = [r for r in forks if r["decision"]]
    parked = [r for r in forks if r["parking"]]
    payload = {
        "title": "symphysis — журнал решений плана реализации",
        "source": args.journal.name,
        "generated": dt.date.today().isoformat(),
        "stats": {"records": len(records), "forks": len(forks), "facts": len(facts),
                  "decided": len(decided), "parked": len(parked),
                  "evidence_total": stats["evidence_total"], "evidence_found": stats["evidence_found"]},
        "records": records,
    }
    js = json.dumps(payload, ensure_ascii=False, indent=1).replace("</", "<\\/")
    html = args.template.read_text(encoding="utf-8")
    if "__JOURNAL_JSON__" not in html:
        print("[!!] в шаблоне нет метки __JOURNAL_JSON__", file=sys.stderr)
        return 1
    args.out.write_text(html.replace("__JOURNAL_JSON__", js), encoding="utf-8")

    print(f"[ok] записей {len(records)}: развилок {len(forks)} (решено {len(decided)}, "
          f"припарковано {len(parked)}), фактов {len(facts)}")
    print(f"[ok] улик сверено {stats['evidence_found']} из {stats['evidence_total']}")
    for m in stats["missing"]:
        print(f"[!!] не сверено — {m}")
    print(f"[ok] {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
