# -*- coding: utf-8 -*-
"""Файл атаки для просмотрщика — модуль `attack`: `parse_attack_md` и разбор строк
таблицы (`_attack_frontmatter`, `_attack_rows`, `_scan_row`). Строки файла считает `_lines` журнала
(модуль `decisions`): attack зависит от decisions, не наоборот."""
from __future__ import annotations

import re
from pathlib import Path

from journal_render import _lines

__all__ = ["ATTACK_ROW_KEYS", "parse_attack_md"]


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
    `invariant`, `severity`, `support`, `fix`), ячейки `strip()`; `composition` — текст строки
    `**Состав:**` или `None` (нужен расчёту состава вердикта, `attack_scope`). Слуг линзы здесь не проверяется:
    строка вне закрытого списка — невалидная строка атаки, просмотрщик показывает её группой
    «вне списка»; падать на ней разбору незачем. Без frontmatter или без таблицы — `ValueError`
    с именем файла и причиной."""
    name = str(path)
    lines = _lines(Path(path).read_text(encoding="utf-8-sig"))
    frontmatter, end = _attack_frontmatter(lines, name)
    return {"path": name, "frontmatter": frontmatter, "rows": _attack_rows(lines, name, end + 1),
            "composition": _composition(lines, end + 1)}
