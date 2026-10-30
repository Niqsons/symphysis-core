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
    py -3.13 tools/journal.py render-design docs/plan-implementation.journal.json \
        --out design.md
    py -3.13 tools/journal.py apply docs/plan-implementation.journal.json answers.md \
        [--date YYYY-MM-DD] [--dry-run]

Markdown, HTML и design.md — производные от JSON: правится JSON, потом рендер. Корни путей
улик — свои префиксы symphysis плюс `tools/journal-roots.json`. Путь улики, не
подошедший ни под один префикс, получает вердикт «корня для пути нет»: отката
на корень symphysis нет.

`apply` вносит промпт возврата просмотрщика (кнопка «Скопировать промпт») в JSON: всё или
ничего, отказ называет запись; сам он не рендерит — после него `render-md` и `render-html`.

Подкоманды добавляются по задачам плана (`docs/plan-implementation.tasks.md`,
часть A): apply-md4h.
"""
from __future__ import annotations

import argparse
import copy
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
    не править руками». В markdown нет `reversibility`, `outcome`, `comments`, `notes`,
    `generated` и полей сверки улик (`line/found/verdict`) — их источник только JSON."""
    source = f"`{json_name}`" if json_name else "JSON-журнала"
    lines = [f"# {journal['title']}", "", f"> Рендер из {source}, не править руками.", ""]
    if journal.get("intro"):
        lines += [journal["intro"], ""]
    for rec in journal["records"]:
        lines += _render_record(rec) + [""]
    return "\n".join(lines)


def _viewer_record(rec: dict) -> dict:
    """Запись в форме, которую читает шаблон: `parking` — весь список журнала (пустой,
    если парковки нет) и `finding` на самой записи — находки парковок через « · »."""
    view = dict(rec)
    view["parking"] = [dict(p) for p in rec["parking"]]
    view["finding"] = " · ".join(p["finding"] for p in rec["parking"] if p.get("finding"))
    return view


def render_html(journal: dict, template: Path) -> str:
    """Шаблон просмотрщика с журналом вместо `__JOURNAL_JSON__`. Улики берутся такими,
    какие в журнале (`check --write` или сверка в памяти); `</` экранируется как `<\\/`,
    чтобы текст записи не закрыл `<script>`. Дата сборки `generated` — из журнала, если она
    там есть; своей даты рендер не ставит, и два рендера одного журнала совпадают."""
    html = Path(template).read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        raise ValueError(f"в шаблоне нет метки {PLACEHOLDER}")
    records = journal["records"]
    forks = [r for r in records if r["kind"] == "развилка"]
    evidence = [ev for r in records for ev in _evidence_of(r)]
    payload = {
        "title": journal["title"],
        "source": journal["source"],
        **({"generated": journal["generated"]} if journal.get("generated") else {}),
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


# --- design.md из журнала --------------------------------------------------

ONE_WAY = "в одну сторону"
EMPTY_SECTION = "—"
GOALS_STUB = "Цели и не-цели — из proposal; здесь только решения."
MIGRATION_STUB = "Не применимо к журналу решений; см. tasks.md."


def _ref(ev: dict) -> str:
    """`путь:строка`; строка известна после сверки (`check --write`), без неё — один путь."""
    return f"{ev['path']}:{ev['line']}" if ev.get("line") is not None else ev["path"]


def _unmatched(ev: dict) -> str:
    """Улика, которую сверяли и не нашли, несёт вердикт: цитата без пометки читалась бы
    как проверенная. Несверенная (`found` нет или `null`) пишется как есть."""
    return f" — {ev.get('verdict') or 'цитаты нет'}" if ev.get("found") is False else ""


def _design_context(facts: list[dict]) -> list[str]:
    lines: list[str] = []
    for fact in facts:
        lines.append(f"- {fact['id']} {fact['question']}")
        lines += [f"  - {_ref(ev)} «{ev['quote']}»{_unmatched(ev)}" for ev in fact["evidence"]]
    return lines


def _design_decision(rec: dict) -> list[str]:
    decision, chosen = rec["decision"], rec["decision"]["option"]
    picked = next(o for o in rec["options"] if o["letter"] == chosen)
    lines = [f"### {rec['id']} {rec['question']}", "", f"- **Выбрано:** {chosen}. {picked['text']}"]
    if decision["word"]:
        lines.append(f"- **Слово человека ({decision['date']}):** «{decision['word']}»")
    if rec["reversibility"]:
        level, why = rec["reversibility"]["level"], rec["reversibility"]["why"]
        lines.append(f"- **Обратимость:** {level}" + (f" — {why}" if why else ""))
    lines += [f"- **Улики выбранного:** {_ref(ev)} «{ev['quote']}»{_unmatched(ev)}" for ev in picked["evidence"]]
    for opt in rec["options"]:
        if opt["letter"] != chosen:
            lines.append(f"- **Отвергнуто:** {opt['letter']}. {opt['text']}"
                         + (f" — маловероятно: {opt['unlikely']}" if opt["unlikely"] else ""))
    return lines


def _design_risks(rec: dict) -> list[str]:
    """Улика за отвергнутую опцию — довод против выбранной: в Decisions она читается как
    обоснование, здесь — как то, чем плох выбранный путь (`fork-form.md`, «Разделы постановки»)."""
    chosen = rec["decision"]["option"]
    return [f"- [Risk] {ev['quote']} ({rec['id']}, отвергнут {opt['letter']}: {_ref(ev)}{_unmatched(ev)})"
            f" → Mitigation: решение {chosen}"
            for opt in rec["options"] if opt["letter"] != chosen for ev in opt["evidence"]]


def _design_open_questions(records: list[dict]) -> list[str]:
    lines = [f"- {r['id']} {r['question']} — открыта"
             for r in records if r["kind"] == "развилка" and not r["decision"]]
    for r in records:
        for park in r["parking"]:
            who = f" → {park['addressee']}" if park["addressee"] else ""
            finding = f" — находка: {park['finding']}" if park.get("finding") else ""
            lines.append(f"- {r['id']}{who}: «{park['text']}»{finding}")
    lines += [f"- {r['id']} — спор: {r['dispute']}" for r in records if r["dispute"]]
    return lines


def render_design(journal: dict) -> str:
    """Журнал -> `design.md` по шаблону spec-driven (Context, Goals / Non-Goals, Decisions,
    Risks / Trade-offs, Migration Plan, Open Questions). Чистая функция: ничего не читает
    с диска, журнал не меняет; журнал предполагается годным (`validate_journal`).

    Context — факты с уликами. Decisions — развилки со словом человека: сначала «в одну
    сторону», затем остальные, внутри групп по номеру. Risks / Trade-offs — улики отвергнутых
    опций решённых развилок, в порядке Decisions. Open Questions — развилки без решения,
    парковка с адресатом и спорные факты. Номер строки в уликах и вердикт несверенной улики
    есть, только если журнал сверен (`check --write`); сама функция улик не сверяет."""
    records = journal["records"]
    decided = sorted((r for r in records if r["kind"] == "развилка" and r["decision"]),
                     key=lambda r: ((r["reversibility"] or {}).get("level") != ONE_WAY, int(r["id"][2:])))
    decisions: list[str] = []
    for rec in decided:
        decisions += ([""] if decisions else []) + _design_decision(rec)
    sections = [
        ("Context", _design_context([r for r in records if r["kind"] == "факт"])),
        ("Goals / Non-Goals", [GOALS_STUB]),
        ("Decisions", decisions),
        ("Risks / Trade-offs", [line for rec in decided for line in _design_risks(rec)]),
        ("Migration Plan", [MIGRATION_STUB]),
        ("Open Questions", _design_open_questions(records)),
    ]
    lines = ["# Design", ""]
    for title, body in sections:
        lines += [f"## {title}", "", *(body or [EMPTY_SECTION]), ""]
    return "\n".join(lines)


# --- внесение промпта возврата ---------------------------------------------

PARKING_ADDRESSEES = ("материалы", "человек", "ИБ")
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
REFUSED = "отказ"

# Строки промпта — те, что пишет `updateOut()` в `tools/playground-template.html`.
RE_ITEM = re.compile(r"^- (F-N?\d+):[ \t]*(.*)$")
RE_NEW_FORKS = re.compile(r"^Новые развилки:\s*$")
RE_NOTES = re.compile(r"^Замечания к схеме:[ \t]*(.*)$")
RE_ADD_OPTION = re.compile(r"^добавлен вариант ([A-ZА-Я])\.\s*(.*)$", re.S)
RE_DEP = re.compile(r"^зависимость (добавлена|снята)\s+(F-\d+)$")
RE_PARK = re.compile(r"^припарковано\s*→\s*([^\s—]+)\s*—\s*(.*)$", re.S)
RE_DISPUTE = re.compile(r"^факт оспорен\s*—\s*(.*)$", re.S)
RE_WORD = re.compile(r"^(?:к решению ([A-ZА-Я])|без выбора)\s*—\s*(.*)$", re.S)
RE_CHOICE = re.compile(r"^([A-ZА-Я])(?!\w)(?:\s*\(было ([A-ZА-Я])\))?\s*(?:—\s*(.*))?$", re.S)
RE_NEW_FORK = re.compile(r"^(.*?)\s+—\s+варианты:\s*(.*?)(?:\s+—\s+(«.*»))?\s*$", re.S)


def _human_word(rest: str | None) -> str:
    """Слово человека из `«…»` или `(без слова)` -> пусто. Кавычки снимает `_unquote` —
    единственное место, которое знает, какая пара «» внешняя."""
    rest = (rest or "").strip()
    return "" if rest == "(без слова)" else _unquote(rest)


def _parse_item(rid: str, body: str) -> dict:
    if rid.startswith("F-N"):
        m = RE_NEW_FORK.match(body)
        if m:
            options = [o.strip() for o in m.group(2).split(" | ") if o.strip()]
            return {"id": rid, "op": "new_fork", "question": m.group(1).strip(),
                    "options": options, "word": _human_word(m.group(3))}
    else:
        m = RE_ADD_OPTION.match(body)
        if m:
            return {"id": rid, "op": "add_option", "letter": m.group(1), "text": m.group(2).strip()}
        m = RE_DEP.match(body)
        if m:
            return {"id": rid, "op": "dep_add" if m.group(1) == "добавлена" else "dep_remove", "dep": m.group(2)}
        m = RE_PARK.match(body)
        if m:
            return {"id": rid, "op": "park", "addressee": m.group(1), "text": _human_word(m.group(2))}
        m = RE_DISPUTE.match(body)
        if m:
            return {"id": rid, "op": "dispute", "word": _human_word(m.group(1))}
        m = RE_WORD.match(body)
        if m:
            return {"id": rid, "op": "word", "option": m.group(1), "word": _human_word(m.group(2))}
        m = RE_CHOICE.match(body)
        if m:
            return {"id": rid, "op": "decide", "option": m.group(1), "was": m.group(2),
                    "word": _human_word(m.group(3))}
    return {"id": rid, "op": "unknown", "raw": body}


def parse_answers(text: str) -> list[dict]:
    """Промпт возврата просмотрщика -> список `{"id", "op", ...}` в порядке строк.

    Строка начинается с `- F-NN: ` (новая развилка — `- F-N1: `) и продолжается до следующей
    такой строки: слово человека бывает многострочным. Всё до первой такой строки (шапка
    `Решения по журналу …:` в простой и в markdown-ссылочной форме) пропускается;
    `Замечания к схеме:` идут последними и забирают текст до конца. Строка не по форме
    даёт `op: unknown` — `apply_answers` откажет по ней поимённо."""
    items: list[list[str]] = []
    cur: list[str] | None = None
    notes: list[str] | None = None
    for line in re.split(r"\r\n|\r|\n", text.lstrip("﻿")):
        if notes is not None:
            notes.append(line)
            continue
        m = RE_NOTES.match(line)
        if m:
            cur, notes = None, [m.group(1)]
            continue
        if RE_NEW_FORKS.match(line):
            cur = None
            continue
        m = RE_ITEM.match(line)
        if m:
            cur = [m.group(1), m.group(2)]
            items.append(cur)
        elif cur is not None:
            cur[1] += "\n" + line
    ops = [_parse_item(rid, body.strip()) for rid, body in items]
    if notes is not None and "\n".join(notes).strip():
        ops.append({"id": None, "op": "note", "text": "\n".join(notes).strip()})
    return ops


class _Refusal(Exception):
    """Строка промпта не вносится; текст — причина, названная по записи."""


def _flat(text: str) -> str:
    """Текст в одну строку: markdown-формат журнала однострочный (так же слово F-07 лежит в журнале)."""
    return " ".join(text.split())


def _merge(old: str, new: str) -> str:
    """Слово дописывается к прежнему; уже сказанное не повторяется."""
    if not new or new in old:
        return old
    return f"{old} {new}" if old else new


def _rec(by_id: dict, a: dict) -> dict:
    rec = by_id.get(a["id"])
    if rec is None:
        raise _Refusal(f"{a['id']}: такой записи нет")
    return rec


def _fork(by_id: dict, a: dict) -> dict:
    rec = _rec(by_id, a)
    if rec["kind"] != "развилка":
        raise _Refusal(f"{rec['id']}: это факт — у него нет вариантов, решения, слова и парковки; "
                       "факт оспаривается строкой «факт оспорен»")
    return rec


def _do_decide(work: dict, by_id: dict, a: dict, date: str) -> str:
    rec = _fork(by_id, a)
    rid, letter, was = rec["id"], a["option"], a["was"]
    letters = [o["letter"] for o in rec["options"]]
    if letter not in letters:
        raise _Refusal(f"{rid}: варианта {letter} нет среди {', '.join(letters) or '—'}")
    current = (rec["decision"] or {}).get("option")
    if was is not None and was != current:
        raise _Refusal(f"{rid}: в журнале решено {current}, а не {was}" if current
                       else f"{rid}: в журнале решения нет, а промпт ждёт {was}")
    if was is None and current not in (None, letter):
        raise _Refusal(f"{rid}: в журнале уже решено {current}; смена решения пишется строкой «{letter} (было {current})»")
    word = _flat(a["word"])
    rec["status"] = "решён"
    if current == letter:
        rec["decision"]["word"] = _merge(rec["decision"]["word"], word)
        return f"{rid}: решение {letter} подтверждено"
    rec["decision"] = {"option": letter, "word": word, "date": date}
    return f"{rid}: решено {letter}" + (f" (было {current})" if current else "")


def _do_word(work: dict, by_id: dict, a: dict, date: str) -> str:
    rec = _fork(by_id, a)
    rid, decision = rec["id"], rec["decision"]
    if decision is None:
        raise _Refusal(f"{rid}: нет решения, к которому добавить слово")
    if a["option"] is None:
        raise _Refusal(f"{rid}: слово дано без выбора, а в журнале решено {decision['option']}")
    if a["option"] != decision["option"]:
        raise _Refusal(f"{rid}: в журнале решено {decision['option']}, а не {a['option']}")
    merged = _merge(decision["word"], _flat(a["word"]))
    if merged == decision["word"]:
        return f"{rid}: слово к решению {decision['option']} уже в журнале"
    decision["word"] = merged
    return f"{rid}: слово добавлено к решению {decision['option']}"


def _do_park(work: dict, by_id: dict, a: dict, date: str) -> str:
    rec = _fork(by_id, a)
    rid, addressee, text = rec["id"], a["addressee"], _flat(a["text"])
    if addressee not in PARKING_ADDRESSEES:
        raise _Refusal(f"{rid}: адресат «{addressee}» — допустимы {' | '.join(PARKING_ADDRESSEES)}")
    if not text:
        raise _Refusal(f"{rid}: парковка без вопроса")
    if any(p["addressee"] == addressee and p["text"] == text for p in rec["parking"]):
        return f"{rid}: парковка → {addressee} уже есть"
    rec["parking"].append({"addressee": addressee, "text": text})
    if rec["decision"] is None:
        rec["status"] = "припаркован"
    return f"{rid}: припарковано → {addressee}"


def _do_add_option(work: dict, by_id: dict, a: dict, date: str) -> str:
    rec = _fork(by_id, a)
    rid, letter, text = rec["id"], a["letter"], _flat(a["text"])
    if letter in {o["letter"] for o in rec["options"]}:
        raise _Refusal(f"{rid}: вариант {letter} уже есть")
    if not text:
        raise _Refusal(f"{rid}: вариант {letter} без текста")
    if ADDED_MARK not in text:
        text += f" {ADDED_MARK})"
    rec["options"].append({"letter": letter, "text": text, "added": True, "unlikely": None, "evidence": []})
    return f"{rid}: добавлен вариант {letter}"


def _do_dependency(work: dict, by_id: dict, a: dict, date: str) -> str:
    rec = _rec(by_id, a)
    rid, dep = rec["id"], a["dep"]
    if dep not in by_id:
        raise _Refusal(f"{rid}: зависимость на {dep}, такой записи нет")
    if a["op"] == "dep_add":
        if dep == rid:
            raise _Refusal(f"{rid}: запись не может зависеть от себя")
        if dep in rec["depends_on"]:
            return f"{rid}: зависимость от {dep} уже есть"
        rec["depends_on"].append(dep)
        return f"{rid}: зависимость добавлена {dep}"
    if dep not in rec["depends_on"]:
        return f"{rid}: зависимости от {dep} нет — снимать нечего"
    rec["depends_on"].remove(dep)
    return f"{rid}: зависимость снята {dep}"


def _do_dispute(work: dict, by_id: dict, a: dict, date: str) -> str:
    rec = _rec(by_id, a)
    rid, word = rec["id"], _flat(a["word"])
    if rec["kind"] != "факт":
        raise _Refusal(f"{rid}: это развилка — спорится факт, а решение меняется строкой с вариантом")
    if not word:
        raise _Refusal(f"{rid}: оспаривание без слова")
    quoted = f"«{word}»"
    if quoted in rec["dispute"]:
        return f"{rid}: спор уже записан"
    rec["dispute"] = f"{rec['dispute']} {quoted}" if rec["dispute"] else quoted
    return f"{rid}: факт оспорен"


def _do_new_fork(work: dict, by_id: dict, a: dict, date: str) -> str:
    question = _flat(a["question"])
    if not question:
        raise _Refusal(f"{a['id']}: развилка без вопроса")
    if len(a["options"]) > len(LETTERS):
        raise _Refusal(f"{a['id']}: вариантов {len(a['options'])}, букв только {len(LETTERS)}")
    numbers = [int(m.group(1)) for r in work["records"] if (m := re.fullmatch(r"F-(\d+)", r["id"]))]
    rid = f"F-{max(numbers, default=0) + 1:02d}"
    rec = _new_record(rid, question)
    rec["options"] = [{"letter": LETTERS[i], "text": _flat(text), "added": False, "unlikely": None, "evidence": []}
                      for i, text in enumerate(a["options"])]
    if _flat(a["word"]):
        rec["consequences"] = f"слово человека при внесении: {_flat(a['word'])}"
    work["records"].append(rec)
    by_id[rid] = rec
    return f"{a['id']} -> {rid}: новая развилка, вариантов {len(rec['options'])}"


def _do_note(work: dict, by_id: dict, a: dict, date: str) -> str:
    work.setdefault("notes", []).append({"date": date, "text": a["text"]})
    return "замечание к схеме внесено"


def _do_unknown(work: dict, by_id: dict, a: dict, date: str) -> str:
    raise _Refusal(f"{a['id']}: строка не по форме просмотрщика — «{_flat(a.get('raw', a['op']))[:80]}»")


_APPLY = {"decide": _do_decide, "word": _do_word, "park": _do_park, "add_option": _do_add_option,
          "dep_add": _do_dependency, "dep_remove": _do_dependency, "dispute": _do_dispute,
          "new_fork": _do_new_fork, "note": _do_note, "unknown": _do_unknown}


def apply_answers(journal: dict, answers: list[dict], date: str) -> list[str]:
    """Вносит разобранный промпт в журнал на месте; возвращает отчёт строками.

    Всё или ничего: любая строка с отказом (нет записи, буква не из вариантов, адресат не из
    трёх, зависимость на несуществующую запись, «было X» не сошлось с журналом, строка не по
    форме) оставляет журнал как был — отчёт тогда состоит из строк `отказ: …` с именем
    записи, чинится строка и промпт вносится целиком заново. Внесённый результат тоже должен
    пройти `validate_journal`. Слова человека сворачиваются в одну строку (формат markdown
    однострочный). `date` попадает в `decision.date` и `notes[].date`. Рендер — отдельный шаг."""
    work = copy.deepcopy(journal)
    by_id = {r["id"]: r for r in work["records"]}
    report: list[str] = []
    refusals: list[str] = []
    for answer in answers:
        handler = _APPLY.get(answer["op"], _do_unknown)
        try:
            report.append(handler(work, by_id, answer, date))
        except _Refusal as e:
            refusals.append(f"{REFUSED}: {e}")
    if not refusals:
        refusals = [f"{REFUSED}: после внесения журнал негоден — {e}" for e in validate_journal(work)]
    if refusals:
        return refusals + [f"{REFUSED}: журнал не изменён — отказов {len(refusals)}, строк в промпте {len(answers)}"]
    journal.clear()
    journal.update(work)
    return report


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


def cmd_render_design(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    Path(args.out).write_text(render_design(journal), encoding="utf-8", newline="\n")
    print(f"[ok] {args.out}")
    return 0


def _iso_date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError(f"дата {value!r} не в форме YYYY-MM-DD")
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"даты {value} не бывает") from None
    return value


def cmd_apply(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    if not args.answers.is_file():
        print(f"[!!] {args.answers}: файла нет", file=sys.stderr)
        return 1
    try:
        text = args.answers.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        print(f"[!!] {args.answers}: не UTF-8 — промпт возврата читается как UTF-8", file=sys.stderr)
        return 1
    answers = parse_answers(text)
    if not answers:
        print("[ok] в промпте нет строк для внесения — журнал не тронут")
        return 0
    report = apply_answers(journal, answers, args.date or dt.date.today().isoformat())
    if any(line.startswith(REFUSED) for line in report):
        for line in report:
            print(f"[!!] {line}", file=sys.stderr)
        return 1
    for line in report:
        print(f"[ok] {line}")
    if args.dry_run:
        print(f"[..] --dry-run: {args.json} не записан")
        return 0
    save_journal(args.json, journal)
    print(f"[ok] {args.json}")
    print("[..] apply не рендерит: дальше render-md и render-html")
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
    p = sub.add_parser("apply", help="внести промпт возврата просмотрщика в JSON (потом render-md, render-html)",
                       description="Вносит промпт возврата просмотрщика (кнопка «Скопировать промпт») в JSON "
                                   "журнала. Всё или ничего: любая строка с отказом называет запись, "
                                   "код 1, журнал не меняется. apply не рендерит: после него "
                                   "render-md и render-html. Слова человека сворачиваются в одну строку.")
    p.add_argument("json", type=Path)
    p.add_argument("answers", type=Path, help="файл с промптом возврата (UTF-8)")
    p.add_argument("--date", type=_iso_date, help="YYYY-MM-DD в decision.date и notes[].date; по умолчанию сегодня")
    p.add_argument("--dry-run", action="store_true", help="показать отчёт, JSON не записывать")
    p.set_defaults(func=cmd_apply)
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
    p = sub.add_parser("render-design", help="JSON -> design.md (Decisions, Risks, Open Questions из журнала); "
                                             "негодный журнал — код 1")
    p.add_argument("json", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_render_design)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
