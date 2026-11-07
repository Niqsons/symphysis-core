# -*- coding: utf-8 -*-
"""Состав устаревшего вердикта — модуль `attack`: `scope_lines` по разбору файла атаки (`parse_attack_md`)
и каталогу изменения. Один расчёт на двух читателей, `journal.py check` и `step_help.py`
(capability `stale-verdict-scope`, F-17, F-18, F-19, F-23, F-24): строки без маркера `[..]` и имени атаки,
их добавляет читатель. Хеш файла — `sha256_file` журнала (модуль `decisions`): attack зависит от decisions,
не наоборот. Содержимое таблицы и строки `**Состав:**` — данные: наружу идут только номера записей,
пути целей из `targets[]` и фиксированный текст (F-34)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from journal_apply import sha256_file

__all__ = ["scope_lines", "JOURNAL", "UNREADABLE", "NO_HASH", "NOTHING_ADDED", "INCOMPLETE"]

JOURNAL = "decisions.json"
UNREADABLE = "журнал не читается"
NO_HASH = "хеш цели не задан: состав не считается"
NOTHING_ADDED = "записей не добавлено: журнал изменён иначе"
INCOMPLETE = "состав неполон: линза coverage выключена, записи без находок в таблице не названы"

RE_NUMBER = re.compile(r"\bF-(\d+)\b")
RE_RANGE = re.compile(r"\bF-\d+\s*[–—-]\s*F-\d+\b")
RE_OFF = re.compile(r"выключены\s*(.*)$")


def _record_numbers(journal_path: Path) -> list[tuple[int, str]] | None:
    """`(номер, id)` записей журнала по порядку файла; `None` — журнал не читается (битый JSON, нет `records`,
    запись без `id`). Номер — число после `F-`: `F-7` и `F-07` равны (F-26)."""
    try:
        records = json.loads(journal_path.read_text(encoding="utf-8-sig"))["records"]
        return [(int(m.group(1)), rec["id"]) for rec in records if (m := RE_NUMBER.fullmatch(rec["id"]))]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _count_word(n: int) -> str:
    """«добавлена 1 запись», «добавлено 2 записи», «добавлено 5 записей»: форма по правилу русского счёта."""
    last, tens = n % 10, n % 100
    if last == 1 and tens != 11:
        return f"добавлена {n} запись"
    if 2 <= last <= 4 and not 12 <= tens <= 14:
        return f"добавлено {n} записи"
    return f"добавлено {n} записей"


def _runs(added: list[tuple[int, str]]) -> str:
    """Перечень номеров: три и больше подряд — диапазоном `F-80–F-139`, остальные через запятую (пара подряд —
    перечнем: диапазон из двух читается хуже); id — как в журнале."""
    parts: list[str] = []
    i = 0
    while i < len(added):
        j = i
        while j + 1 < len(added) and added[j + 1][0] == added[j][0] + 1:
            j += 1
        parts.append(f"{added[i][1]}–{added[j][1]}" if j - i >= 2 else ", ".join(rid for _, rid in added[i:j + 1]))
        i = j + 1
    return ", ".join(parts)


def _coverage_off(composition: str | None) -> bool:
    """Строка `**Состав:**` называет `coverage` среди выключенных; строки нет — все линзы включены (F-10)."""
    if not composition:
        return False
    off = RE_OFF.search(composition)
    return bool(off) and "coverage" in off.group(1)


def _journal_scope(attack: dict, change_dir: Path, sha: str) -> list[str]:
    """Атака журнала: атакованные записи — номера из столбца «Раздел», добавленные — записи журнала, которых
    в таблице нет (F-17, F-18). Раздел диапазоном даёт сигнал, атакованными считаются только номера, стоящие
    дословно (F-40)."""
    journal_path = change_dir / JOURNAL
    if not journal_path.is_file():
        return [f"{JOURNAL}: файла нет"]
    if sha256_file(journal_path) == sha:
        return []
    numbers = _record_numbers(journal_path)
    if numbers is None:
        return [UNREADABLE]
    seen: set[int] = set()
    ranges: list[str] = []
    for row in attack["rows"]:
        section = row["section"]
        seen.update(int(n) for n in RE_NUMBER.findall(section))
        for found in RE_RANGE.findall(section):
            if found not in ranges:
                ranges.append(found)
    added = [(n, rid) for n, rid in sorted(numbers) if n not in seen]
    lines = [INCOMPLETE] if _coverage_off(attack.get("composition")) else []
    lines.append(f"после вердикта {_count_word(len(added))}: {_runs(added)}" if added else NOTHING_ADDED)
    lines += [f"раздел диапазоном: {r}, записи по одной не названы" for r in ranges]
    return lines


def _outside(declared: str, change_dir: Path) -> bool:
    """Путь цели с `..`, абсолютный, с буквой диска или уходящий по ссылке за каталог изменения — не читается,
    как причина `outside` у форка (F-29, F-33)."""
    raw = Path(declared)
    if raw.is_absolute() or raw.anchor or raw.drive or ".." in raw.parts or declared.startswith(("/", "\\")):
        return True
    root = change_dir.resolve()
    full = (change_dir / declared).resolve()
    return full != root and root not in full.parents


def _artifacts_scope(attack: dict, change_dir: Path) -> list[str]:
    """Атака артефактов: все цели с несовпавшим хешем, не первая (F-23); у журнала вместо состава записей —
    их число (F-24); цели без файла, без хеша и вне каталога — пометкой, не «изменена» (F-27, F-29, F-35)."""
    lines: list[str] = []
    for target in attack["frontmatter"]["targets"]:
        declared, sha = target["path"], target["sha256"].strip().lower()
        if _outside(declared, change_dir):
            lines.append(f"{declared}: вне каталога изменения")
            continue
        full = change_dir / declared
        if not full.is_file():
            lines.append(f"{declared}: файла нет")
            continue
        if not sha:
            lines.append(f"{declared}: хеш не задан")
            continue
        if sha256_file(full) == sha:
            continue
        if Path(declared).as_posix() == JOURNAL:
            numbers = _record_numbers(full)
            lines.append(f"{JOURNAL}: журнал изменён, {UNREADABLE}" if numbers is None
                         else f"{JOURNAL}: журнал изменён, записей сейчас {len(numbers)}")
        else:
            lines.append(f"{declared}: изменён после вердикта")
    return lines


def scope_lines(attack: dict, change_dir: Path | str) -> list[str]:
    """Строки состава устаревшего вердикта по разбору `parse_attack_md` и каталогу изменения; пустой список —
    хеши совпали, читателям показывать нечего. Форма по `targets[]`: одна цель `decisions.json` — атака журнала,
    иначе — артефактов. Хеши сравниваются по байтам файла без учёта регистра, как у форка (F-20, F-28); пустой
    хеш журнала — «не задан», состав не считается (F-27). Абсолютных путей в строках нет: пути — как объявлены
    в `targets[]`."""
    change_dir = Path(change_dir)
    targets = attack["frontmatter"]["targets"]
    if len(targets) == 1 and Path(targets[0]["path"]).as_posix() == JOURNAL:
        sha = targets[0]["sha256"].strip().lower()
        return [NO_HASH] if not sha else _journal_scope(attack, change_dir, sha)
    return _artifacts_scope(attack, change_dir)
