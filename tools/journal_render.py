# -*- coding: utf-8 -*-
"""Рендеры журнала: markdown (`render_md`), HTML-просмотрщик (`render_html`), `design.md`
(`render_design`) и якоря рендера (`anchor_lines`). Зависит только от journal_model."""
from __future__ import annotations

import json
import re
from pathlib import Path

from journal_model import ADDED_MARK, RE_ANCHOR, ROOT, _evidence_of, _flat

__all__ = [
    "TEMPLATE_PATH", "PLACEHOLDER",
    "render_md", "render_html", "render_design", "anchor_lines", "_lines",
]


TEMPLATE_PATH = ROOT / "tools" / "playground-template.html"
PLACEHOLDER = "__JOURNAL_JSON__"


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


def _generated_note(json_name: str = "") -> str:
    """Шапка производного файла: «рендер из …, не править руками» (её пропускает импорт)."""
    source = f"`{json_name}`" if json_name else "JSON-журнала"
    return f"> Рендер из {source}, не править руками."


def render_md(journal: dict, json_name: str = "") -> str:
    """Журнал -> markdown в формате `plan-flexible-pipeline.md`; после заголовка каждой
    записи — якорь `<!-- journal:F-NN -->`. `json_name` попадает в шапку: «рендер из …,
    не править руками». В markdown нет `reversibility`, `outcome`, `comments`, `notes`,
    `generated` и полей сверки улик (`line/found/verdict`) — их источник только JSON."""
    lines = [f"# {journal['title']}", "", _generated_note(json_name), ""]
    if journal.get("intro"):
        lines += [journal["intro"], ""]
    for rec in journal["records"]:
        lines += _render_record(rec) + [""]
    return "\n".join(lines)


def _lines(text: str) -> list[str]:
    """Строки файла как их считает редактор: по `\\n` и `\\r\\n`; номер строки — индекс + 1."""
    return re.split(r"\r?\n", text)


def anchor_lines(rendered_text: str) -> list[tuple[int, str]]:
    """Якоря `<!-- journal:F-NN -->` рендера: `(номер строки с единицы, id записи)` в порядке
    файла. Якорь — вся строка; строки считаются так же при LF и при CRLF, чтобы номера
    совпали с теми, что связка md4h взяла из файла на диске."""
    return [(n, m.group(1)) for n, line in enumerate(_lines(rendered_text), 1)
            if (m := RE_ANCHOR.match(line))]


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


def _cite(ev: dict) -> str:
    """`путь:строка «цитата»` с вердиктом несверенной. Цитата сплющена в одну строку: перенос
    внутри неё оборвал бы пункт списка, а строка `## …` в ней — раздел."""
    return f"{_ref(ev)} «{_flat(ev['quote'])}»{_unmatched(ev)}"


def _design_context(facts: list[dict]) -> list[str]:
    lines: list[str] = []
    for fact in facts:
        lines.append(f"- {fact['id']} {fact['question']}")
        lines += [f"  - {_cite(ev)}" for ev in fact["evidence"]]
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
    lines += [f"- **Улики вопроса:** {_cite(ev)}" for ev in rec["evidence"]]
    lines += [f"- **Улики выбранного:** {_cite(ev)}" for ev in picked["evidence"]]
    for opt in rec["options"]:
        if opt["letter"] != chosen:
            lines.append(f"- **Отвергнуто:** {opt['letter']}. {opt['text']}"
                         + (f" — маловероятно: {opt['unlikely']}" if opt["unlikely"] else ""))
    return lines


def _design_risks(rec: dict) -> list[str]:
    """Улика за отвергнутую опцию — довод против выбранной: в Decisions она читается как
    обоснование, здесь — как то, чем плох выбранный путь (`fork-form.md`, «Разделы постановки»)."""
    chosen = rec["decision"]["option"]
    return [f"- [Risk] {_flat(ev['quote'])} ({rec['id']}, отвергнут {opt['letter']}: {_ref(ev)}{_unmatched(ev)})"
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


def render_design(journal: dict, source: str | None = None) -> str:
    """Журнал -> `design.md` по шаблону spec-driven (Context, Goals / Non-Goals, Decisions,
    Risks / Trade-offs, Migration Plan, Open Questions). Чистая функция: ничего не читает
    с диска, журнал не меняет; журнал предполагается годным (`validate_journal`).

    Context — факты с уликами. Decisions — развилки со словом человека: сначала «в одну
    сторону», затем остальные, внутри групп по номеру. Risks / Trade-offs — улики отвергнутых
    опций решённых развилок, в порядке Decisions. Open Questions — развилки без решения,
    парковка с адресатом и спорные факты. Номер строки в уликах и вердикт несверенной улики
    есть, только если журнал сверен (`check --write`); сама функция улик не сверяет.

    Улики самого вопроса (`evidence` записи) выводятся в Decisions отдельной меткой «Улики
    вопроса» — они общие для вариантов. Цитаты улик сплющиваются в одну строку. `source` — имя
    JSON, из которого сделан рендер: если оно есть, под заголовком встаёт та же шапка «рендер
    из …, не править руками», что у `render_md`; без него шапки нет."""
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
    lines = ["# Design", ""] + ([_generated_note(source), ""] if source else [])
    for title, body in sections:
        lines += [f"## {title}", "", *(body or [EMPTY_SECTION]), ""]
    return "\n".join(lines)
