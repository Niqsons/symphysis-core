# -*- coding: utf-8 -*-
"""Рендеры журнала — файл модуля `decisions`: markdown (`render_md`), `design.md` (`render_design`), данные для
показа вне страницы (`view_payload`, `destination`), проекция журнала для просмотрщика (`_viewer_payload`), номер контракта
`CONTRACT` и якоря рендера (`anchor_lines`). Страница `render_html` — в `viewer_render.py`, разбор файла атаки
`parse_attack_md` — в `attack_table.py`; оба зависят от этого файла, он от них — нет. Зависит от journal_model."""
from __future__ import annotations

import re
from html import escape

from journal_model import ADDED_MARK, DEVIATION_LABEL, DEVIATION_TAIL, RE_ANCHOR, _evidence_of, _flat

__all__ = [
    "CONTRACT",
    "render_md", "render_design", "view_payload", "destination", "parking_destination",
    "anchor_lines", "_lines", "_viewer_payload",
]


# Номер контракта ядра с плагином в выводе `view-json`: растёт при смене контракта, от нового поля не растёт (`docs/repo-contract.md`).
# 4 — значение адресата парковки и записи `материалы` → `агент` (изменение `parking-addressee-agent`);
# 5 — четвёртая линза атаки артефактов `rule-compliance` (изменение `attack-lens-conventions`); каждый номер назван
# абзацем «С номера N» в договоре, тест `test_journal_render.py` сверяет наибольший N с этим числом.
# 6 — строка `apply` о тяжести `- тяжесть: …` (F-23.A, изменение `attack-severity-buttons`); влито раньше линзы,
# поэтому номер 5 есть только в истории ветки `attack-lens-conventions`, `main` идёт 4 → 6.
CONTRACT = 6


# --- рендер ----------------------------------------------------------------

def _evidence_line(ev: dict, indent: str) -> str:
    return f"{indent}- улика: `{ev['path']}` «{ev['quote']}»"


def _render_option(opt: dict) -> list[str]:
    text = opt["text"]
    if opt["added"] and ADDED_MARK not in text:
        text += f" {ADDED_MARK})"
    if opt.get("deviation"):   # без поля хвост не пишется; текст, сам им оканчивающийся, отвергает check
        text += " " + DEVIATION_TAIL.format(opt["deviation"])
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
    """Всегда `вариант — почему`: причиной держится просьба слова при выборе мимо рекомендации."""
    return " — ".join(part for part in (rc["option"], rc["why"]) if part)


def _render_outcome(outcome: dict) -> str:
    """`<вид> — <значение>`, с причиной — `… — <причина>`. Пустая причина хвоста не даёт:
    хвост ` — ` без причины импорт прочитал бы как часть значения."""
    text = f"{outcome['kind']} — {outcome['value']}"
    if outcome["reason"].strip():
        text += f" — {outcome['reason']}"
    return text


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
    if rec["outcome"]:
        lines.append(f"- исход: {_render_outcome(rec['outcome'])}")
    if rec["consequences"]:
        lines.append(f"- следствия: {rec['consequences']}")
    return lines


def _generated_note(json_name: str = "") -> str:
    """Шапка производного файла: «рендер из …, не править руками» (её пропускает импорт)."""
    source = f"`{json_name}`" if json_name else "JSON-журнала"
    return f"> Рендер из {source}, не править руками."


def _render_notes(notes: list[dict]) -> list[str]:
    """Раздел «Заметки» в конце markdown: строка на заметку `- <дата> — <текст>`; перенос
    строки внутри текста — строка-продолжение с отступом в два пробела (импорт её склеит)."""
    lines = ["## Заметки"]
    for note in notes:
        first, *rest = note["text"].split("\n")
        lines.append(f"- {note['date']} — {first}")
        lines += [f"  {line}" for line in rest]
    return lines


def render_md(journal: dict, json_name: str = "") -> str:
    """Журнал -> markdown в формате `plan-flexible-pipeline.md`; после заголовка каждой
    записи — якорь `<!-- journal:F-NN -->`. `json_name` попадает в шапку: «рендер из …,
    не править руками». `notes` — разделом «Заметки» после последней записи (нет заметок —
    нет раздела). `outcome` — строкой `- исход: <вид> — <значение> — <причина>` между решением
    и следствиями (нет исхода — нет строки; пустая причина — без хвоста). `deviation` варианта — хвостом
    его строки `(отступление от F-NN)` после пометки «добавлен человеком». В markdown нет
    `reversibility`, `comments`, `generated`, `text` рекомендации и полей сверки улик (`line/found/verdict`) —
    их источник только JSON."""
    lines = [f"# {journal['title']}", "", _generated_note(json_name), ""]
    if journal.get("intro"):
        lines += [journal["intro"], ""]
    for rec in journal["records"]:
        lines += _render_record(rec) + [""]
    if journal.get("notes"):
        lines += _render_notes(journal["notes"]) + [""]
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


def _viewer_payload(journal: dict, journal_sha256: str | None) -> dict:
    """Проекция журнала для просмотра — одна на страницу `render-html` и на `view-json`: заголовок, счётчики,
    записи в форме просмотрщика, заметки. Улики берутся такими, какие в журнале."""
    records = journal["records"]
    forks = [r for r in records if r["kind"] == "развилка"]
    evidence = [ev for r in records for ev in _evidence_of(r)]
    return {
        "title": journal["title"],
        "source": journal["source"],
        **({"generated": journal["generated"]} if journal.get("generated") else {}),
        **({"sha256": journal_sha256} if journal_sha256 else {}),
        "stats": {"records": len(records), "forks": len(forks),
                  "facts": sum(1 for r in records if r["kind"] == "факт"),
                  "decided": sum(1 for r in forks if r["decision"]),
                  "parked": sum(1 for r in forks if r["parking"]),
                  "evidence_total": len(evidence),
                  "evidence_found": sum(1 for ev in evidence if ev.get("found"))},
        "records": [_viewer_record(r) for r in records],
        "notes": list(journal.get("notes") or []),
    }


# --- design.md из журнала --------------------------------------------------

ONE_WAY = "в одну сторону"
EMPTY_SECTION = "—"
NO_DECISIONS = "нет: решённых развилок в журнале нет"
# Каноническая фраза пометки решения «ничего не менять»: выбранный вариант с началом из
# UNCHANGED_PREFIXES рендерится с ней. Скилл брейншторма велит начинать такой вариант словами
# «Оставить как есть» и ссылается на эту константу.
UNCHANGED_NOTE = "- **Конструкция не меняется.**"
UNCHANGED_PREFIXES = ("оставить как есть", "ничего не менять")
GOALS_STUB = "Цели и не-цели — из proposal; здесь только решения."
MIGRATION_STUB = "Не применимо к журналу решений; см. tasks.md."


def _ref(ev: dict) -> str:
    """`путь:строка`; строка известна после сверки (`check --write`), без неё — один путь."""
    return f"{ev['path']}:{ev['line']}" if ev.get("line") is not None else ev["path"]


def _unmatched(ev: dict) -> str:
    """Улика, которую сверяли и не нашли (`found: false`) или не смогли проверить (`found: null`
    с вердиктом «не проверить: …» — бинарный файл, не UTF-8), несёт вердикт: цитата без пометки
    читалась бы как проверенная. Улика, которую не сверяли (нет ни `found`, ни `verdict`), — как есть."""
    if ev.get("found") is False:
        return f" — {ev.get('verdict') or 'цитаты нет'}"
    if ev.get("found") is None and ev.get("verdict"):
        return f" — {ev['verdict']}"
    return ""


def _escaped_quote(text: str) -> str:
    """Цитата — текст markdown, а не HTML: после сплющивания `&`, `<` и `>` экранируются."""
    return escape(_flat(text), quote=False)


def _cite(ev: dict) -> str:
    """`путь:строка «цитата»` с вердиктом несверенной. Цитата сплющена в одну строку: перенос
    внутри неё оборвал бы пункт списка, а строка `## …` в ней — раздел."""
    return f"{_ref(ev)} «{_escaped_quote(ev['quote'])}»{_unmatched(ev)}"


def _design_context(facts: list[dict]) -> list[str]:
    lines: list[str] = []
    for fact in facts:
        lines.append(f"- {fact['id']} {fact['question']}")
        lines += [f"  - {_cite(ev)}" for ev in fact["evidence"]]
    return lines


def _is_unchanged(option_text: str) -> bool:
    """Выбранный вариант — «ничего не менять»: текст после `strip()` начинается с «Оставить как есть»
    или «Ничего не менять», регистр первой буквы не важен."""
    return option_text.strip().lower().startswith(UNCHANGED_PREFIXES)


def _design_decision(rec: dict) -> list[str]:
    decision, chosen = rec["decision"], rec["decision"]["option"]
    picked = next(o for o in rec["options"] if o["letter"] == chosen)
    lines = [f"### {rec['id']} {rec['question']}", "", f"- **Выбрано:** {chosen}. {picked['text']}"]
    if _is_unchanged(picked["text"]):
        lines.append(UNCHANGED_NOTE)
    if picked.get("deviation"):
        lines.append(f"- **{DEVIATION_LABEL.capitalize()}:** {picked['deviation']}")
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
    return [f"- [Risk] {_escaped_quote(ev['quote'])} ({rec['id']}, отвергнут {opt['letter']}: {_ref(ev)}{_unmatched(ev)})"
            f" → Mitigation: решение {chosen}"
            for opt in rec["options"] if opt["letter"] != chosen for ev in opt["evidence"]]


def _is_probe(rec: dict) -> bool:
    """Кандидат пробы — запись с отзеркаленным исходом `outcome.kind == "проба"` (скиллы проб
    краёв и запретов); проектным решением он не считается."""
    return bool(rec["outcome"]) and rec["outcome"]["kind"] == "проба"


def _open_fork_line(rec: dict) -> str | None:
    """Строка Open Questions для развилки: без решения — «открыта»; кандидат пробы с исходом
    `Defer` — «отложена», со словом человека, если оно есть. Остальные развилки строки не дают."""
    if rec["kind"] != "развилка":
        return None
    if not rec["decision"]:
        return f"- {rec['id']} {rec['question']} — открыта"
    if _is_probe(rec) and rec["outcome"]["value"] == "Defer":
        reason = rec["outcome"]["reason"].strip()
        return f"- {rec['id']} {rec['question']} — отложена (Defer)" + (f" — «{reason}»" if reason else "")
    return None


def _design_open_questions(records: list[dict]) -> list[str]:
    lines = [line for r in records if (line := _open_fork_line(r))]
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

    Context — факты с уликами. Decisions — развилки со словом человека (без решённых — строка
    «нет: решённых развилок в журнале нет»; у решения «ничего не менять» — пометка «Конструкция
    не меняется»; выбранный вариант с `deviation` — строка «Отступление от постановки: F-NN»): сначала «в одну
    сторону», затем остальные, внутри групп по номеру. Risks / Trade-offs — улики отвергнутых
    опций решённых развилок, в порядке Decisions. Open Questions — развилки без решения,
    отложенные кандидаты проб, парковка с адресатом и спорные факты. Кандидаты проб
    (`outcome.kind == "проба"`) — не проектные решения: в Decisions и Risks их нет, в Open
    Questions стоит только отложенный (`Defer`). Номер строки в уликах и вердикт несверенной
    улики есть, только если журнал сверен (`check --write`); сама функция улик не сверяет.

    Улики самого вопроса (`evidence` записи) выводятся в Decisions отдельной меткой «Улики
    вопроса» — они общие для вариантов. Цитаты улик сплющиваются в одну строку. `source` — имя
    JSON, из которого сделан рендер: если оно есть, под заголовком встаёт та же шапка «рендер
    из …, не править руками», что у `render_md`; без него шапки нет."""
    records = journal["records"]
    decided = sorted((r for r in records if r["kind"] == "развилка" and r["decision"] and not _is_probe(r)),
                     key=lambda r: ((r["reversibility"] or {}).get("level") != ONE_WAY, int(r["id"][2:])))
    decisions: list[str] = []
    for rec in decided:
        decisions += ([""] if decisions else []) + _design_decision(rec)
    sections = [
        ("Context", _design_context([r for r in records if r["kind"] == "факт"])),
        ("Goals / Non-Goals", [GOALS_STUB]),
        ("Decisions", decisions or [NO_DECISIONS]),
        ("Risks / Trade-offs", [line for rec in decided for line in _design_risks(rec)]),
        ("Migration Plan", [MIGRATION_STUB]),
        ("Open Questions", _design_open_questions(records)),
    ]
    lines = ["# Design", ""] + ([_generated_note(source), ""] if source else [])
    for title, body in sections:
        lines += [f"## {title}", "", *(body or [EMPTY_SECTION]), ""]
    return "\n".join(lines)


# --- данные для просмотра вне страницы (`view-json`) -------------------------

def _recommended_why(rec: dict) -> str:
    """Причина рекомендованного выбора: человек выбрал вариант без слова, и причиной остаётся `why`."""
    rc, decision = rec.get("recommendation"), rec.get("decision")
    return rc["why"].strip() if rc and decision and decision["option"] == rc["option"] else ""


def destination(rec: dict) -> dict:
    """«Куда уйдёт» запись — проекция правил `render_design` для показа человеку: `{"label", "note"}`. Решённая развилка,
    не проба → Decisions («в одну сторону» — первыми); проба Specify* → spec.md; Backstop → тест-страховка в tasks.md;
    Dismiss → никуда; Defer и открытая развилка → Open Questions; факт → Context, спорный — ещё и Open Questions.
    То же правило есть в шаблоне страницы (`destination`), сверка — `decisions/tests/test_journal_view_json.py`."""
    if rec["kind"] == "факт":
        return {"label": "design.md › Context", "note": "спор → design.md › Open Questions" if rec["dispute"].strip() else ""}
    if _is_probe(rec):
        value, reason = rec["outcome"]["value"], rec["outcome"]["reason"].strip()
        if value.startswith("Specify"):
            return {"label": "spec.md", "note": f"исход {value}"}
        if value == "Backstop":
            return {"label": "tasks.md › тест-страховка", "note": "в design.md не попадает"}
        if value == "Dismiss":
            reason = reason or _recommended_why(rec)
            return {"label": "никуда", "note": f"причина: {reason}" if reason else "причина не записана"}
        if value == "Defer":
            return {"label": "design.md › Open Questions", "note": "отложена (Defer)"}
        return {"label": "никуда", "note": f"исход «{value}» вне четырёх"}
    if rec["decision"]:
        one_way = rec["reversibility"] and rec["reversibility"]["level"] == ONE_WAY
        return {"label": "design.md › Decisions", "note": "в одну сторону — первой" if one_way else ""}
    return {"label": "design.md › Open Questions", "note": "открыта"}


# `материалы` — старое значение адресата: читается только у старых журналов и ведёт туда же, куда `агент` (F-17, F-23).
PARKING_ANSWERS = {"ИБ": "security.md", "агент": "research/", "материалы": "research/", "человек": "вопрос человеку"}


def parking_destination(addressee: str) -> str:
    """Парковка всегда попадает в Open Questions; адресат говорит, где ищется ответ."""
    return f"design.md › Open Questions → {PARKING_ANSWERS.get(addressee, '—')}"


def view_payload(journal: dict, attacks: list[dict] | None = None, journal_sha256: str | None = None) -> dict:
    """Данные журнала для показа вне страницы: проекция страницы (`_viewer_payload`), у записи и парковки
    `destination`, в `attacks` — файлы атаки (`path` от корня проекта, F-72). Улики берутся такими, какие в журнале."""
    payload = _viewer_payload(journal, journal_sha256)
    for rec in payload["records"]:
        rec["destination"] = destination(rec)
        for park in rec["parking"]:
            park["destination"] = parking_destination(park["addressee"])
    payload["attacks"] = attacks or []
    payload["contract"] = CONTRACT
    return payload
