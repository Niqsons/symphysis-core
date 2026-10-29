#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Журнал решений symphysis: источник — JSON, markdown и HTML — рендер (F-01.B).

Схема — `docs/journal.schema.json`. Ключи JSON английские, значения русские.

    py -3.13 tools/journal.py import-md docs/plan-implementation.journal.md \
        --out docs/plan-implementation.journal.json
    py -3.13 tools/journal.py check docs/plan-implementation.journal.json [--strict] [--write]
    py -3.13 tools/journal.py render-md docs/plan-implementation.journal.json \
        --out docs/plan-implementation.journal.md
    py -3.13 tools/journal.py render-html docs/plan-implementation.journal.json \
        --out docs/plan-implementation.html [--template tools/playground-template.html]

Markdown и HTML — производные от JSON: правится JSON, потом рендер. Корни путей
улик — свои префиксы symphysis плюс `tools/journal-roots.json`. Путь улики, не
подошедший ни под один префикс, получает вердикт «корня для пути нет»: отката
на корень symphysis нет.

Подкоманды добавляются по задачам плана (`docs/plan-implementation.tasks.md`,
часть A): apply, apply-md4h.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "docs" / "journal.schema.json"
ROOTS_PATH = ROOT / "tools" / "journal-roots.json"
TEMPLATE_PATH = ROOT / "tools" / "playground-template.html"
PLACEHOLDER = "__JOURNAL_JSON__"
# Префиксы путей улик, которые лежат в самом symphysis (остальные — в journal-roots.json).
OWN_PREFIXES = ("docs/", "upstream/", "CLAUDE.md")

RE_TITLE = re.compile(r"^# (.*\S)\s*$")
RE_REC = re.compile(r"^## (F-\d+)\s+(.*\S)\s*$")
RE_ANCHOR = re.compile(r"^<!-- journal:F-\d+ -->\s*$")
RE_GENERATED = re.compile(r"^> Рендер из .+, не править руками\.\s*$")
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
    """Снимает ровно одну внешнюю пару «» — слово человека и вопрос парковки хранятся
    без кавычек; «» внутри остаются."""
    if len(text) >= 2 and text.startswith("«") and text.endswith("»"):
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
    """Разбирает markdown-журнал в формате `plan-flexible-pipeline.md` в словарь по схеме."""
    journal = {"title": "", "source": source, "records": []}
    intro: list[str] = []
    rec: dict | None = None
    opt: dict | None = None
    mode = None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if RE_ANCHOR.match(line):
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
        journal["records"] = journal.pop("records")  # в файле вводный текст идёт до записей
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


def _evidence_of(rec: dict) -> list[dict]:
    """Улики записи: свои и у её вариантов."""
    return list(rec["evidence"]) + [ev for opt in rec["options"] for ev in opt["evidence"]]


def check_evidence(journal: dict, roots: dict[str, Path]) -> dict:
    """Сверяет каждую улику грепом по цитате в файле. Пишет в улики `line`, `found`
    (`False` — сверяли, не нашли) и `verdict`. Несверенная улика — сигнал, не ошибка."""
    total = found = 0
    missing: list[str] = []
    for rec in journal["records"]:
        for ev in _evidence_of(rec):
            total += 1
            line, verdict = find_quote(ev["path"], ev["quote"], roots)
            ev["line"], ev["found"], ev["verdict"] = line, line is not None, verdict
            if line is not None:
                found += 1
            else:
                missing.append(f"{rec['id']}: {ev['path']} «{ev['quote']}» — {verdict}")
    return {"total": total, "found": found, "missing": missing}


# --- рендер ----------------------------------------------------------------

def _evidence_line(ev: dict, indent: str) -> str:
    return f"{indent}- улика: `{ev['path']}` «{ev['quote']}»"


def _render_option(opt: dict) -> list[str]:
    text = opt["text"]
    if opt["added"] and ADDED_MARK not in text:
        text += f" {ADDED_MARK})"
    lines = [f"  - {opt['letter']}. {text}"]
    lines += [_evidence_line(ev, "    ") for ev in opt["evidence"]]
    if opt["unlikely"]:
        lines.append(f"    - маловероятно: {opt['unlikely']}")
    return lines


def _render_decision(decision: dict) -> str:
    if decision["option"] is None:  # строка не по форме — слово хранит её целиком
        return decision["word"]
    text = decision["option"]
    if decision["word"]:
        text += f" — «{decision['word']}»"
    if decision["date"]:
        text += f", {decision['date']}"
    return text


def _render_recommendation(rc: dict) -> str:
    """Сырая строка `text`; нет её (журнал собран не импортом) — `вариант — почему`."""
    return rc.get("text") or " — ".join(part for part in (rc["option"], rc["why"]) if part)


def _render_record(rec: dict) -> list[str]:
    """Поля в порядке формата; пустые необязательные — без строки. Варианты и антиподы
    пишутся только у развилки, как в импорте."""
    lines = [f"## {rec['id']} {rec['question']}", f"<!-- journal:{rec['id']} -->",
             f"- вид: {rec['kind']}", f"- статус: {rec['status']}"]
    if rec["addressee"]:
        lines.append(f"- адресат: {rec['addressee']}")
    lines.append(f"- зависит от: {', '.join(rec['depends_on']) or '—'}")
    if rec["delivery"]:
        lines.append(f"- поставка: {rec['delivery']}")
    if rec["kind"] == "развилка":
        lines.append("- варианты:")
        for opt in rec["options"]:
            lines += _render_option(opt)
        lines.append("- антиподы: " + ("; ".join(f"{a['option']} ↔ {a['other']}" for a in rec["antipodes"]) or "—"))
    if rec["recommendation"]:
        lines.append(f"- рекомендация: {_render_recommendation(rec['recommendation'])}")
    for park in rec["parking"]:
        who = f"{park['addressee']} — " if park["addressee"] else ""
        lines.append(f"- парковка: {who}«{park['text']}»")
        if "finding" in park:
            lines.append(f"- находка: {park['finding']}".rstrip())
    if rec["evidence"]:
        lines.append("- улики:")
        lines += [_evidence_line(ev, "  ") for ev in rec["evidence"]]
    if rec["dispute"]:
        lines.append(f"- спор: {rec['dispute']}")
    if rec["decision"]:
        lines.append(f"- решение: {_render_decision(rec['decision'])}")
    if rec["consequences"]:
        lines.append(f"- следствия: {rec['consequences']}")
    return lines


def render_md(journal: dict, json_name: str = "") -> str:
    """Журнал -> markdown в формате `plan-flexible-pipeline.md`; после заголовка каждой
    записи — якорь `<!-- journal:F-NN -->`. `json_name` попадает в шапку: «рендер из …,
    не править руками». В markdown нет `reversibility`, `outcome`, `comments` и полей сверки
    улик (`line/found/verdict`) — их источник только JSON."""
    source = f"`{json_name}`" if json_name else "JSON-журнала"
    lines = [f"# {journal['title']}", "", f"> Рендер из {source}, не править руками.", ""]
    if journal.get("intro"):
        lines += [journal["intro"], ""]
    for rec in journal["records"]:
        lines += _render_record(rec) + [""]
    return "\n".join(lines)


def _viewer_record(rec: dict) -> dict:
    """Запись в форме, которую читает шаблон: одна парковка журнала на запись
    (`parking` — объект или `null`) и `finding` на самой записи."""
    first = rec["parking"][0] if rec["parking"] else None
    view = dict(rec)
    view["parking"] = {"addressee": first["addressee"], "text": first["text"]} if first else None
    view["finding"] = first.get("finding", "") if first else ""
    return view


def render_html(journal: dict, template: Path) -> str:
    """Шаблон просмотрщика с журналом вместо `__JOURNAL_JSON__`. Улики берутся такими,
    какие в журнале (`check --write` или сверка в памяти); `</` экранируется как `<\\/`,
    чтобы текст записи не закрыл `<script>`. Шаблон показывает одну парковку на запись:
    у записи с несколькими — первую."""
    html = Path(template).read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        raise ValueError(f"в шаблоне нет метки {PLACEHOLDER}")
    records = journal["records"]
    forks = [r for r in records if r["kind"] == "развилка"]
    evidence = [ev for r in records for ev in _evidence_of(r)]
    payload = {
        "title": journal["title"],
        "source": journal["source"],
        "generated": dt.date.today().isoformat(),
        "stats": {"records": len(records), "forks": len(forks),
                  "facts": sum(1 for r in records if r["kind"] == "факт"),
                  "decided": sum(1 for r in forks if r["decision"]),
                  "parked": sum(1 for r in forks if r["parking"]),
                  "evidence_total": len(evidence),
                  "evidence_found": sum(1 for ev in evidence if ev.get("found"))},
        "records": [_viewer_record(r) for r in records],
    }
    js = json.dumps(payload, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return html.replace(PLACEHOLDER, js)


# --- командная строка ------------------------------------------------------

def _valid_journal(path: Path) -> dict | None:
    """Журнал из файла; негодный — ошибки в stderr и `None`."""
    journal = load_journal(path)
    errors = validate_journal(journal)
    for e in errors:
        print(f"[!!] {e}", file=sys.stderr)
    return None if errors else journal


def cmd_check(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
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


def cmd_render_md(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    Path(args.out).write_text(render_md(journal, json_name=args.json.name), encoding="utf-8", newline="\r\n")
    print(f"[ok] записей {len(journal['records'])}")
    print(f"[ok] {args.out}")
    return 0


def cmd_render_html(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    # Сверка идёт в памяти: просмотрщик получает вердикты, файл журнала не меняется.
    result = check_evidence(journal, default_roots(args.roots))
    try:
        html = render_html(journal, args.template)
    except ValueError as e:
        print(f"[!!] {e}", file=sys.stderr)
        return 1
    Path(args.out).write_text(html, encoding="utf-8", newline="\n")
    print(f"[ok] улик сверено {result['found']} из {result['total']}")
    for m in result["missing"]:
        print(f"[!!] не сверено — {m}")
    print(f"[ok] {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="journal", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("import-md", help="журнал в markdown -> JSON по схеме")
    p.add_argument("md", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_import_md)
    p = sub.add_parser("check", help="сверить улики грепом по цитате (сигнал, не стоп); "
                                     "негодный по схеме журнал — код 1")
    p.add_argument("json", type=Path)
    p.add_argument("--roots", type=Path, help="файл корней вместо tools/journal-roots.json")
    p.add_argument("--strict", action="store_true", help="код 2, если есть несверенные улики")
    p.add_argument("--write", action="store_true", help="сохранить line/found/verdict в JSON")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("render-md", help="JSON -> markdown (производный файл); негодный журнал — код 1")
    p.add_argument("json", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_render_md)
    p = sub.add_parser("render-html", help="JSON -> просмотрщик; улики сверяются в памяти; "
                                           "негодный журнал — код 1")
    p.add_argument("json", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--roots", type=Path, help="файл корней вместо tools/journal-roots.json")
    p.add_argument("--template", type=Path, default=TEMPLATE_PATH,
                   help="по умолчанию tools/playground-template.html")
    p.set_defaults(func=cmd_render_html)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
