# -*- coding: utf-8 -*-
"""Две проверки описи `consequences.md` для `journal.py check`: каждое место из списка названо путём в файле,
цитата `путь:строка «цитата»` стоит в коде дословно. Сигнал, не стоп (F-25.A, F-128.A). Форму файла сверх этого
модуль не разбирает: строку без цитаты, шаблонную причину и состав судит человек или атака. Настройки
не читает. Зависит от journal_apply и journal_sites."""
from __future__ import annotations

import re
from pathlib import Path

from journal_apply import NOT_CHECKED, _read_text, find_quote
from journal_sites import code_sites, normalize_path

__all__ = ["check_consequences"]

FILE_NAME = "consequences.md"

# Строка начинается с причины; `**Причина:**` внутри строки, например в комментарии шаблона, сверку не снимает.
RE_REASON = re.compile(r"^\s*\*\*Причина:\*\*", re.M)

# `путь:строка «цитата»`, путь в обратных апострофах или без них. Цитата — до последней `»` в строке: в ней
# бывают `||`, апостроф и свои кавычки (край F-39), поэтому таблицу и разделители разбор не ищет.
RE_CITATION = re.compile(r"(?:`(?P<ticked>[^`\n]+?):\d+(?:[-–]\d+)?`"
                         r"|(?<![^\s(\[*|])(?P<bare>[^\s`«»*|]+?):\d+(?:[-–]\d+)?)"
                         r"\s*«(?P<quote>.*)»")

# Граница пути: `src/Foo.java` не закрывают `calibration/src/Foo.java`, `src/Foo.javascript` и `src/Foo.java.bak`.
PATH_BEFORE = r"(?<![\w./-])"
PATH_AFTER = r"(?![\w/-]|\.\w)"


def _path_named(text: str, path: str) -> bool:
    """Путь встречается в тексте: прямые разделители и `:строка` в сравнение не входят (край F-76)."""
    return re.search(PATH_BEFORE + re.escape(path) + PATH_AFTER, text) is not None


def _citations(text: str) -> list[tuple[str, str]]:
    found = []
    for line in text.splitlines():
        m = RE_CITATION.search(line)
        if m:
            found.append((m.group("ticked") or m.group("bare"), m.group("quote")))
    return found


def check_consequences(journal: dict, file: Path, roots: dict[str, Path]) -> dict:
    """`{"missing": [...], "unchecked": [...]}`: строки сигналов `[!!]` и строки «не проверить» `[--]`.
    Нет файла — сверки нет (F-75.A); строка `**Причина:**` снимает сверку мест, но не цитат."""
    result: dict[str, list[str]] = {"missing": [], "unchecked": []}
    if not file.is_file():
        return result
    text, verdict = _read_text(file)
    if text is None:
        result["unchecked"].append(f"{FILE_NAME}: {verdict}")
        return result
    if not RE_REASON.search(text):
        slashed = re.sub(r"(?<![\w./-])\./", "", text.replace("\\", "/"))
        result["missing"] += [f"{FILE_NAME}: {path} — нет ни разбора, ни исключения с причиной"
                              for path in code_sites(journal, roots)["sites"] if not _path_named(slashed, path)]
    for raw, quote in _citations(text):
        path = normalize_path(raw, roots)
        _, verdict = find_quote(path, quote, roots)
        if verdict in NOT_CHECKED:
            line = f"{FILE_NAME}: {path} — {verdict}"
            if line not in result["unchecked"]:
                result["unchecked"].append(line)
        elif verdict != "сверено":
            line = f"{FILE_NAME}: {path} «{quote}» — {verdict}"
            if line not in result["missing"]:
                result["missing"].append(line)
    return result
