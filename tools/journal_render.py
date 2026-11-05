# -*- coding: utf-8 -*-
"""Рендеры журнала: markdown (`render_md`), HTML-просмотрщик (`render_html`), `design.md`
(`render_design`), данные для показа вне страницы (`view_payload`), якоря рендера (`anchor_lines`)
и разбор файла атаки для просмотрщика (`parse_attack_md`). Зависит только от journal_model."""
from __future__ import annotations

import json
import re
from pathlib import Path

from journal_model import ADDED_MARK, DEVIATION_LABEL, DEVIATION_TAIL, RE_ANCHOR, ROOT, _evidence_of, _flat

__all__ = [
    "TEMPLATE_PATH", "PLACEHOLDER", "PLACEHOLDER_ATTACK", "PLACEHOLDER_SCHEME", "PLACEHOLDER_HELP", "PLACEHOLDER_LINKS", "CONTRACT",
    "parse_scheme", "scheme_payload", "no_help_snapshot",
    "render_md", "render_html", "render_design", "view_payload", "destination", "parking_destination",
    "anchor_lines", "parse_attack_md", "_lines",
]


TEMPLATE_PATH = ROOT / "tools" / "playground-template.html"
PLACEHOLDER = "__JOURNAL_JSON__"
PLACEHOLDER_ATTACK = "__ATTACK_JSON__"
PLACEHOLDER_SCHEME = "__SCHEME_JSON__"
PLACEHOLDER_HELP = "__HELP_JSON__"
PLACEHOLDER_LINKS = "__LINKS_JSON__"
# Номер контракта ядра с плагином в выводе `view-json`: растёт при смене контракта, от нового поля не растёт (`docs/repo-contract.md`).
CONTRACT = 3


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


def _embed(obj) -> str:
    """JSON для `<script>` шаблона: `</` экранируется как `<\\/`, чтобы текст не закрыл `<script>`,
    `<!--` — как `\\u003c!--`, чтобы текст не открыл в скрипте «экранированное» состояние разбора HTML."""
    return json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/").replace("<!--", "\\u003c!--")


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


# --- scheme.md ----------------------------------------------------------------

RE_FENCE = re.compile(r"^ {0,3}(`{3,})[ \t]*([^`]*?)[ \t]*$")
NO_SCHEME = {"exists": False, "text": None, "blocks": 0, "first_line": None, "mermaid": None}


def parse_scheme(text: str) -> dict:
    """`scheme.md`: текст первого непустого блока mermaid, число непустых блоков и строка файла, с которой
    блок начинается, для номера строки в ошибке. BOM и CRLF не мешают; блок внутри другой ограды — не блок.
    Плагин разбирает файл сам, оба разбора сверяются набором `tests/fixtures/scheme/cases.json`."""
    fence = None
    blocks = []
    for number, line in enumerate(text.removeprefix("\ufeff").replace("\r\n", "\n").split("\n"), 1):
        match = RE_FENCE.match(line)
        if fence is None:
            if match:
                fence = {"length": len(match[1]), "mermaid": match[2] == "mermaid", "first": number + 1, "body": []}
        elif match and not match[2] and len(match[1]) >= fence["length"]:
            blocks.append(fence)
            fence = None
        else:
            fence["body"].append(line)
    if fence:
        blocks.append(fence)
    filled = [b for b in blocks if b["mermaid"] and "".join(b["body"]).strip()]
    if not filled:
        return {"text": None, "blocks": 0, "first_line": None}
    return {"text": "\n".join(filled[0]["body"]).rstrip("\n") + "\n", "blocks": len(filled), "first_line": filled[0]["first"]}


def _mermaid_src(out: Path) -> str | None:
    """Путь от страницы до файла mermaid проекта: страница вне проекта его не получает и показывает текст (F-39)."""
    here = Path(out).resolve().parent
    for up, base in enumerate([here, *here.parents]):
        if (base / ".symphysis" / "tools").is_dir():
            return "../" * up + ".symphysis/tools/mermaid.min.js"
    return None


def scheme_payload(scheme_path: Path, out: Path) -> dict:
    """Что страница `out` получает о файле `scheme_path`: своя метка шаблона, вне `_viewer_payload`, поэтому
    в `view-json` текст схемы не уходит (F-25). Не текст файла — файл без блока, а не отказ сборки."""
    path = Path(scheme_path)
    if not path.is_file():
        return {**NO_SCHEME, "mermaid": _mermaid_src(out)}
    return {"exists": True, **parse_scheme(path.read_text(encoding="utf-8", errors="replace")), "mermaid": _mermaid_src(out)}


def no_help_snapshot(reason: str) -> dict:
    """Снимок «расчёта нет»: поля те же, что у `step_help.compute`, причина в `error`, времени снятия нет."""
    return {"contract": CONTRACT, "taken_at": None, "versions": {"openspec": None, "symphysis": None}, "change": None,
            "changes": None, "error": reason, "current_step": None, "current_text": None, "turn": None,
            "next_by_status": None, "forks": None, "tasks": None, "steps": [], "rebuild": None}


def render_html(journal: dict, template: Path, attacks: list[dict] | None = None, journal_sha256: str | None = None,
                scheme: dict | None = None, help_snapshot: dict | None = None, links: dict | None = None) -> str:
    """Шаблон просмотрщика с журналом вместо `__JOURNAL_JSON__`, списком атак вместо `__ATTACK_JSON__`, схемой вместо
    `__SCHEME_JSON__`, справкой вместо `__HELP_JSON__` и картой ссылок на файлы вместо `__LINKS_JSON__`; все пять меток обязательны. Улики берутся такими, какие в журнале
    (`check --write` или сверка в памяти). Дата сборки `generated` — из журнала, если она
    там есть; своей даты рендер не ставит, и два рендера одного журнала совпадают: снимок справки и его время снятия
    добавляет CLI, из памяти на метку встаёт снимок «расчёта нет» (F-46).

    `attacks` — результаты `parse_attack_md` как есть (режим «атака» просмотрщика); без них
    на место метки встаёт `[]`. `journal_sha256` — SHA-256 файла журнала по байтам, его считает
    CLI: в payload он ключ `sha256`, по нему просмотрщик сверяет хеш цели из frontmatter атаки
    с журналом; ключа нет, если хеш не подан — рендер из памяти файла не знает. `notes[]`
    журнала отдаются режиму «проверка»; остальной payload прежний. Метки подставляются за один
    проход, чтобы текст журнала, похожий на метку, не был подставлен второй раз."""
    html = Path(template).read_text(encoding="utf-8")
    marks = (PLACEHOLDER, PLACEHOLDER_ATTACK, PLACEHOLDER_SCHEME, PLACEHOLDER_HELP, PLACEHOLDER_LINKS)
    for mark in marks:
        if mark not in html:
            raise ValueError(f"в шаблоне нет метки {mark}")
    filled = {PLACEHOLDER: _embed(_viewer_payload(journal, journal_sha256)), PLACEHOLDER_ATTACK: _embed(attacks or []),
              PLACEHOLDER_SCHEME: _embed(scheme or NO_SCHEME),
              PLACEHOLDER_HELP: _embed(help_snapshot or no_help_snapshot("Справка на этой странице не считалась.")),
              PLACEHOLDER_LINKS: _embed(links or {"root": None, "files": {}})}
    return "".join(filled.get(part, part) for part in re.split("(" + "|".join(marks) + ")", html))


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
    Разбор — `_scan_row`, она же отдаёт места разделителей.
    """
    cells, unclosed, _ = _scan_row(line)
    return cells, unclosed


def _scan_row(line: str) -> tuple[list[str], int | None, list[int]]:
    r"""Строка pipe-таблицы -> (ячейки, индекс ячейки с незакрытым backtick или `None`, столбцы разделителей:
    номера знаков `|` строки, считая с единицы, по одному на каждый разделитель вне кода).
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
    cuts: list[int] = []
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
            cuts.append(i + 1)
            cur = []
            ended_on_delim = True
        else:
            cur.append(ch)
        i += 1
    if not ended_on_delim:
        cells.append("".join(cur))
    return cells, (opened_in if in_code else None), cuts


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
        raw, unclosed, cuts = _scan_row(line)
        cells = [c.strip() for c in raw]
        if all(c and set(c) <= {"-", ":"} for c in cells):
            continue
        if unclosed is not None:
            col = columns[unclosed] if unclosed < len(columns) else f"№{unclosed + 1}"
            raise ValueError(f"{name}:{n + 1}: в столбце «{col}» (ячейка {unclosed + 1}) backtick не закрыт")
        if len(cells) != len(ATTACK_ROW_KEYS):
            # какая черта лишняя, по тексту не узнать: называем все черты вне backticks, кроме замыкающей
            inner = [c for c in cuts if c != len(line.rstrip())]
            where = (f"; черты вне backticks в столбцах {', '.join(map(str, inner))}; лишняя — одна из них"
                     if len(cells) > len(ATTACK_ROW_KEYS) else "")
            raise ValueError(f"{name}:{n + 1}: в строке таблицы ячеек {len(cells)}, нужно {len(ATTACK_ROW_KEYS)}{where}"
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
    просмотрщика: `path` — как подан парсеру (CLI приводит его к пути от корня проекта, F-72); `frontmatter` — `status` и `targets[]` (`path`, `sha256`);
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
    То же правило есть в шаблоне страницы (`destination`), сверка — `tests/test_journal_view_json.py`."""
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


PARKING_ANSWERS = {"ИБ": "security.md", "материалы": "research/", "человек": "вопрос человеку"}


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
