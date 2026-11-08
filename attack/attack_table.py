# -*- coding: utf-8 -*-
"""Файл атаки для просмотрщика — модуль `attack`: `parse_attack_md` (файл) и `parse_attack_text` (текст в памяти),
`set_severity` (слово о тяжести: новый текст файла, F-47.A) и разбор строк таблицы (`_attack_frontmatter`,
`_attack_rows`, `_scan_row`). Строки файла считает `_lines` журнала
(модуль `decisions`): attack зависит от decisions, не наоборот."""
from __future__ import annotations

import re
from pathlib import Path

from journal_model import _flat
from journal_render import _lines

__all__ = ["ATTACK_ROW_KEYS", "parse_attack_md", "parse_attack_text", "set_severity"]


ATTACK_ROW_KEYS = ("claim", "section", "lens", "invariant", "severity", "support", "fix")
ATTACK_FIRST_COLUMN = "Утверждение"
RE_FRONT_KEY = re.compile(r"^(\w+):\s*(.*?)\s*$")
RE_TARGET_PATH = re.compile(r"^\s+-\s+path:\s*(.*?)\s*$")
RE_TARGET_SHA = re.compile(r"^\s+sha256:\s*(.*?)\s*$")
RE_COMPOSITION = re.compile(r"^\*\*Состав:\*\*\s*(.*?)\s*$")


def _composition(lines: list[str], start: int) -> str | None:
    """Строка `**Состав:**` файла атаки после frontmatter — текст после метки; файлы до неё строки не несут,
    и `None` читается как «все линзы включены» (F-10). Текст — данные: расчёт состава берёт из него только слово
    `coverage` в части «выключены»."""
    return next((m.group(1) for line in lines[start:] if (m := RE_COMPOSITION.match(line))), None)


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
    return [row for row, _ in _attack_rows_at(lines, name, start)]


def _attack_rows_at(lines: list[str], name: str, start: int) -> list[tuple[dict, int]]:
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
    rows: list[tuple[dict, int]] = []
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
        rows.append((dict(zip(ATTACK_ROW_KEYS, cells)), n))
    return rows


def parse_attack_md(path: Path) -> dict:
    """Файл атаки (`attack/decisions.md`, `attack/artifacts.md`) -> словарь для режима «атака»
    просмотрщика: `path` — как подан парсеру (CLI приводит его к пути от корня проекта, F-72); `frontmatter` — `status` и `targets[]` (`path`, `sha256`);
    `rows` — строки первой таблицы с семью колонками после D4b (`claim`, `section`, `lens`,
    `invariant`, `severity`, `support`, `fix`), ячейки `strip()`; `composition` — текст строки
    `**Состав:**` или `None` (нужен расчёту состава вердикта, `attack_scope`). Слуг линзы здесь не проверяется:
    строка вне закрытого списка — невалидная строка атаки, просмотрщик показывает её группой
    «вне списка»; падать на ней разбору незачем. Без frontmatter или без таблицы — `ValueError`
    с именем файла и причиной."""
    return parse_attack_text(Path(path).read_text(encoding="utf-8-sig"), str(path))


def parse_attack_text(text: str, name: str) -> dict:
    """Тот же разбор из текста: `name` идёт в `path` и в сообщения об ошибках; BOM в начале снимается."""
    lines = _lines(text.removeprefix("\ufeff"))
    frontmatter, end = _attack_frontmatter(lines, name)
    return {"path": name, "frontmatter": frontmatter, "rows": _attack_rows(lines, name, end + 1),
            "composition": _composition(lines, end + 1)}


SEVERITY_BLOCKER, SEVERITY_WARNING = "блокер", "предупреждение"
SEVERITY_COLUMN = ATTACK_ROW_KEYS.index("severity")
RE_STATUS_LINE = re.compile(r"^status:.*$")


def _severity_word(cell: str) -> str:
    """Первое слово ячейки тяжести, регистр сохранён: «Блокер» с заглавной не слово (F-29.B)."""
    return cell.split(maxsplit=1)[0] if cell.split() else ""


RE_BLOCKER_CELL = re.compile(r"блокер(?![а-яёa-z])", re.I)


def _counts_as_blocker(cell: str) -> bool:
    """Счёт блокеров для `status` — по правилу страницы: первое слово `блокер` без учёта регистра, дальше не буква
    (`Блокер`, `блокер(причина)`); ход тяжести берёт `_severity_word` — только точное слово."""
    return bool(RE_BLOCKER_CELL.match(cell.strip()))


def _is_coverage(row: dict) -> bool:
    """Строка покрытия (F-19.A): утверждение «не пройдено» или опора «нет: не пройдено» / «нет: файла нет»."""
    return row["claim"] == "не пройдено" or row["support"] in ("нет: не пройдено", "нет: файла нет")


def set_severity(text: str, name: str, section: str, claim: str, severity: str, why: str) -> str:
    """Слово человека о тяжести (F-17, F-47.A): новый текст файла атаки без записи на диск. Строка ищется по
    разобранным `section` и `claim` дословно; ход только `блокер` <-> `предупреждение` (F-18.B, F-29.B, F-31.B),
    строка покрытия и `справка` — отказ (F-19.A). Ячейка тяжести правится в сыром тексте по местам разделителей,
    становясь `<тяжесть> (<обоснование>)` одной строкой (F-28); `status` пересчитывается: `passed` при нуле
    строк `блокер`, иначе `gaps_found`. Остальные байты и концы строк целы. Любой отказ — `ValueError` с причиной."""
    bom = "\ufeff" if text.startswith("\ufeff") else ""
    parts = re.split(r"(\r?\n)", text.removeprefix(bom))       # чётные — строки, нечётные — их концы
    lines = parts[0::2]
    frontmatter_end = _attack_frontmatter(lines, name)[1]
    found = [(row, n) for row, n in _attack_rows_at(lines, name, frontmatter_end + 1)
             if row["section"] == section and row["claim"] == claim]
    if not found:
        raise ValueError(f"{name}: строки нет: раздел «{section}», утверждение «{claim}»")
    if len(found) > 1:
        raise ValueError(f"{name}: строк с этим ключом две ({len(found)}): раздел «{section}», утверждение «{claim}»")
    row, n = found[0]
    if _is_coverage(row):
        raise ValueError(f"{name}: строка покрытия «{claim}» тяжесть не меняет")
    current = _severity_word(row["severity"])
    if severity not in (SEVERITY_BLOCKER, SEVERITY_WARNING):
        raise ValueError(f"{name}: тяжесть «{severity}» не ставится: только {SEVERITY_BLOCKER} или {SEVERITY_WARNING}")
    if current not in (SEVERITY_BLOCKER, SEVERITY_WARNING):
        raise ValueError(f"{name}: текущая тяжесть «{row['severity']}» вне хода блокер <-> предупреждение")
    if current == severity:
        raise ValueError(f"{name}: тяжесть у строки уже «{severity}»")
    reason = _flat(why)
    if not reason:
        raise ValueError(f"{name}: обоснование пусто")
    cell = " " + f"{severity} ({reason})".replace("\\", "\\\\").replace("|", "\\|") + " "
    line = lines[n]
    body = line.strip()
    lead = line[:len(line) - len(line.lstrip())]
    trail = line[len(line.rstrip()):]
    cuts = _scan_row(line)[2]
    body = body[:cuts[SEVERITY_COLUMN - 1]] + cell + body[cuts[SEVERITY_COLUMN] - 1:]
    lines[n] = lead + body + trail
    try:
        rows = _attack_rows(lines, name, frontmatter_end + 1)
    except ValueError as err:
        raise ValueError(f"{name}: ячейка не разбирается: {err}") from None
    again = [r for r in rows if r["section"] == section and r["claim"] == claim]
    if len(again) != 1 or _severity_word(again[0]["severity"]) != severity:
        raise ValueError(f"{name}: ячейка не разбирается: после правки строка не находится с тяжестью «{severity}»")
    status = "gaps_found" if any(_counts_as_blocker(r["severity"]) for r in rows) else "passed"
    at = next((i for i in range(1, frontmatter_end) if RE_STATUS_LINE.match(lines[i])), None)
    if at is None:
        raise ValueError(f"{name}: во frontmatter нет строки status:")
    lines[at] = f"status: {status}"
    parts[0::2] = lines
    return bom + "".join(parts)
