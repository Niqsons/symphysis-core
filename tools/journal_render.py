# -*- coding: utf-8 -*-
"""Рендеры журнала: markdown (`render_md`), HTML-просмотрщик (`render_html`), `design.md`
(`render_design`), якоря рендера (`anchor_lines`) и разбор файла атаки для просмотрщика
(`parse_attack_md`). Зависит только от journal_model."""
from __future__ import annotations

import json
import re
from pathlib import Path

from journal_model import ADDED_MARK, RE_ANCHOR, ROOT, _evidence_of, _flat

__all__ = [
    "TEMPLATE_PATH", "PLACEHOLDER", "PLACEHOLDER_ATTACK",
    "render_md", "render_html", "render_design", "anchor_lines", "parse_attack_md", "_lines",
]


TEMPLATE_PATH = ROOT / "tools" / "playground-template.html"
PLACEHOLDER = "__JOURNAL_JSON__"
PLACEHOLDER_ATTACK = "__ATTACK_JSON__"


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


def _render_outcome(outcome: dict) -> str:
    """`<вид> — <значение>`, с причиной — `… — <причина>`. Пустая причина (и причина из одних
    пробелов) хвоста не даёт: у исхода `Dismiss` её требует правило, у остальных она
    необязательна; хвост ` — ` без причины импорт прочитал бы как часть значения."""
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
    и следствиями (нет исхода — нет строки; пустая причина — без хвоста). В markdown нет
    `reversibility`, `comments`, `generated` и полей сверки улик (`line/found/verdict`) —
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


def _embed(obj) -> str:
    """JSON для `<script>` шаблона: `</` экранируется как `<\\/`, чтобы текст не закрыл `<script>`."""
    return json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/")


def render_html(journal: dict, template: Path, attacks: list[dict] | None = None,
                journal_sha256: str | None = None) -> str:
    """Шаблон просмотрщика с журналом вместо `__JOURNAL_JSON__` и списком атак вместо
    `__ATTACK_JSON__`; обе метки обязательны. Улики берутся такими, какие в журнале
    (`check --write` или сверка в памяти). Дата сборки `generated` — из журнала, если она
    там есть; своей даты рендер не ставит, и два рендера одного журнала совпадают.

    `attacks` — результаты `parse_attack_md` как есть (режим «атака» просмотрщика); без них
    на место метки встаёт `[]`. `journal_sha256` — SHA-256 файла журнала по байтам, его считает
    CLI: в payload он ключ `sha256`, по нему просмотрщик сверяет хеш цели из frontmatter атаки
    с журналом; ключа нет, если хеш не подан — рендер из памяти файла не знает. `notes[]`
    журнала отдаются режиму «проверка»; остальной payload прежний. Метки подставляются за один
    проход, чтобы текст журнала, похожий на метку, не был подставлен второй раз."""
    html = Path(template).read_text(encoding="utf-8")
    for mark in (PLACEHOLDER, PLACEHOLDER_ATTACK):
        if mark not in html:
            raise ValueError(f"в шаблоне нет метки {mark}")
    records = journal["records"]
    forks = [r for r in records if r["kind"] == "развилка"]
    evidence = [ev for r in records for ev in _evidence_of(r)]
    payload = {
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
    filled = {PLACEHOLDER: _embed(payload), PLACEHOLDER_ATTACK: _embed(attacks or [])}
    return "".join(filled.get(part, part) for part in re.split(f"({PLACEHOLDER}|{PLACEHOLDER_ATTACK})", html))


# --- файл атаки для просмотрщика --------------------------------------------

ATTACK_ROW_KEYS = ("claim", "section", "lens", "invariant", "severity", "support", "fix")
ATTACK_FIRST_COLUMN = "Утверждение"
RE_FRONT_KEY = re.compile(r"^(\w+):\s*(.*?)\s*$")
RE_TARGET_PATH = re.compile(r"^\s+-\s+path:\s*(.*?)\s*$")
RE_TARGET_SHA = re.compile(r"^\s+sha256:\s*(.*?)\s*$")


def _attack_frontmatter(lines: list[str], name: str) -> tuple[dict, int]:
    """Frontmatter файла атаки без YAML-библиотеки: форма задана двумя шаблонами схемы
    (`attack-decisions.md` — `target`/`target_sha256`, `attack-artifacts.md` — `targets[]`
    с `path` и `sha256`). Наружу всегда `targets[]`: форма журнала приводится к списку из одного
    элемента. Возвращает словарь и индекс закрывающей строки `---`."""
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{name}: нет frontmatter")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise ValueError(f"{name}: frontmatter не закрыт строкой ---")
    fields: dict[str, str] = {}
    targets: list[dict] = []
    for line in lines[1:end]:
        if (m := RE_TARGET_PATH.match(line)):
            targets.append({"path": m.group(1), "sha256": ""})
        elif (m := RE_TARGET_SHA.match(line)) and targets:
            targets[-1]["sha256"] = m.group(1)
        elif (m := RE_FRONT_KEY.match(line)):
            fields[m.group(1)] = m.group(2)
    if "target" in fields:
        targets.insert(0, {"path": fields["target"], "sha256": fields.get("target_sha256", "")})
    return {"status": fields.get("status", ""), "targets": targets}, end


def _split_row(line: str) -> tuple[list[str], int | None]:
    r"""Строка pipe-таблицы -> (ячейки без `strip()`, индекс ячейки с незакрытым backtick или `None`).
    Посимвольный автомат, не `split("|")`. `\\` даёт литеральную `\`, `\|` — литеральную `|`
    (везде, и в коде); иная обратная косая литеральна, следующий символ разбирается как обычно.
    Backtick переключает «внутри кода»; `|` внутри кода — текст ячейки, вне кода — разделитель.
    Backticks остаются в тексте ячейки: `<code>` из них делает просмотрщик. Ведущая `|` — начало
    первой ячейки, замыкающая неэкранированная `|` вне кода — конец последней, пустой ячейки после
    неё нет."""
    text = line.strip()
    cells: list[str] = []
    cur: list[str] = []
    in_code, opened_in = False, None
    ended_on_delim = False
    i = 1 if text.startswith("|") else 0
    while i < len(text):
        ch = text[i]
        ended_on_delim = False
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in "\\|":
            cur.append(text[i + 1])
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
            opened_in = len(cells) if in_code else None
        if ch == "|" and not in_code:
            cells.append("".join(cur))
            cur = []
            ended_on_delim = True
        else:
            cur.append(ch)
        i += 1
    if not ended_on_delim:
        cells.append("".join(cur))
    return cells, (opened_in if in_code else None)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in _split_row(line)[0]]


def _attack_rows(lines: list[str], name: str, start: int) -> list[dict]:
    """Строки первой pipe-таблицы после `start`, у которой заголовок из семи колонок и первая —
    «Утверждение». Ячейка разбирается `_split_row`. Разделитель заголовка и строки-подстановки
    шаблона (первая ячейка `<…>`) пропускаются. Ошибка — `ValueError` с `файл:строка:`: число
    ячеек не семь, незакрытый backtick (с колонкой, где он открыт), пустая ячейка (с колонкой
    по заголовку) — все семь ячеек обязательны, у строки покрытия в «Инварианте» стоит «—»."""
    header = next((i for i in range(start, len(lines)) if lines[i].startswith("|")
                   and len(_cells(lines[i])) == len(ATTACK_ROW_KEYS)
                   and _cells(lines[i])[0] == ATTACK_FIRST_COLUMN), None)
    if header is None:
        raise ValueError(f"{name}: нет таблицы атаки с заголовком «{ATTACK_FIRST_COLUMN}» из семи колонок")
    columns = _cells(lines[header])
    rows: list[dict] = []
    for n in range(header + 1, len(lines)):
        line = lines[n]
        if not line.startswith("|"):
            break
        raw, unclosed = _split_row(line)
        cells = [c.strip() for c in raw]
        if all(c and set(c) <= {"-", ":"} for c in cells):
            continue
        if unclosed is not None:
            col = columns[unclosed] if unclosed < len(columns) else f"№{unclosed + 1}"
            raise ValueError(f"{name}:{n + 1}: в столбце «{col}» (ячейка {unclosed + 1}) backtick не закрыт")
        if len(cells) != len(ATTACK_ROW_KEYS):
            raise ValueError(f"{name}:{n + 1}: в строке таблицы ячеек {len(cells)}, нужно {len(ATTACK_ROW_KEYS)}"
                             " (литеральная `|` вне backticks пишется `\\|`)")
        if cells[0].startswith("<") and cells[0].endswith(">"):
            continue
        empty = next((i for i, c in enumerate(cells) if not c), None)
        if empty is not None:
            raise ValueError(f"{name}:{n + 1}: в столбце «{columns[empty]}» (ячейка {empty + 1}) пусто;"
                             " все семь ячеек обязательны, нет содержимого — «—»")
        rows.append(dict(zip(ATTACK_ROW_KEYS, cells)))
    return rows


def parse_attack_md(path: Path) -> dict:
    """Файл атаки (`attack/decisions.md`, `attack/artifacts.md`) -> словарь для режима «атака»
    просмотрщика: `path` — как подан; `frontmatter` — `status` и `targets[]` (`path`, `sha256`);
    `rows` — строки первой таблицы с семью колонками после D4b (`claim`, `section`, `lens`,
    `invariant`, `severity`, `support`, `fix`), ячейки `strip()`. Слуг линзы здесь не проверяется:
    строка вне закрытого списка — невалидная строка атаки, просмотрщик показывает её группой
    «вне списка»; падать на ней разбору незачем. Без frontmatter или без таблицы — `ValueError`
    с именем файла и причиной."""
    name = str(path)
    lines = _lines(Path(path).read_text(encoding="utf-8-sig"))
    frontmatter, end = _attack_frontmatter(lines, name)
    return {"path": name, "frontmatter": frontmatter, "rows": _attack_rows(lines, name, end + 1)}


# --- design.md из журнала --------------------------------------------------

ONE_WAY = "в одну сторону"
EMPTY_SECTION = "—"
NO_DECISIONS = "нет: решённых развилок в журнале нет"
# Каноническая фраза пометки решения «ничего не менять». Её же велит ставить скилл брейншторма
# (задача 7.2 сошлётся на эту константу): выбранный вариант с таким началом рендерится с ней.
UNCHANGED_NOTE = "- **Конструкция не меняется.**"
UNCHANGED_PREFIXES = ("оставить как есть", "ничего не менять")
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
    не меняется»): сначала «в одну
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
