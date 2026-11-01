# -*- coding: utf-8 -*-
"""Места кода из журнала: файлы из улик выбранных вариантов решённых развилок, кроме проб и фактов (F-15.D).
Скрипт предлагает, модель выбирает: дополнить список или исключить место можно на шаге `consequences`.
Журнал не меняется, файлы кода не читаются. Зависит от journal_apply."""
from __future__ import annotations

import re
from pathlib import Path

from journal_apply import OUTSIDE_ROOT, _resolve

__all__ = ["code_sites", "normalize_path"]

RE_DRIVE = re.compile(r"^[A-Za-z]:/")


def _slashes(path: str) -> str:
    """Прямые разделители и заглавная буква диска."""
    path = path.replace("\\", "/")
    return path[0].upper() + path[1:] if RE_DRIVE.match(path) else path


def normalize_path(path: str, roots: dict[str, Path]) -> str:
    """Одно написание пути: разделители и регистр диска нормализуются, `./` снимается, абсолютный путь
    внутри корня приводится к относительному с префиксом этого корня — до `_resolve`, иначе тот назовёт его
    «вне корня». `..` не сворачивается: это забота `_resolve`."""
    path = _slashes(path).removeprefix("./")
    if not (RE_DRIVE.match(path) or path.startswith("/")):
        return path
    # и корень как задан, и разрешённый: файл корней может называть каталог через ссылку
    known = [(prefix, _slashes(str(raw)).rstrip("/")) for prefix, root in roots.items() for raw in (root, root.resolve())]
    for prefix, root in sorted(known, key=lambda item: len(item[1]), reverse=True):
        if path == root:
            return prefix
        if path.startswith(root + "/"):
            return prefix + path[len(root) + 1:]
    return path


def _is_code_file(path: str) -> bool:
    """Граница F-73.A: всё, кроме `.md` и файлов каталогов изменений, на любой глубине."""
    return not path.lower().endswith(".md") and "/openspec/changes/" not in f"/{path}"


def _is_probe(rec: dict) -> bool:
    """Запись пробы: `outcome.kind: проба` или префикс вопроса `[<категория> · <форма>]`."""
    return (rec["outcome"] or {}).get("kind") == "проба" or rec["question"].startswith("[")


def code_sites(journal: dict, roots: dict[str, Path]) -> dict:
    """`{"sites": {путь: [номера записей]}, "notes": [строки сведений]}`; пути по алфавиту. Путь вне
    объявленных корней и с `..` в список не идёт и не читается (F-105)."""
    sites: dict[str, list[str]] = {}
    notes: list[str] = []
    for rec in journal["records"]:
        if rec["kind"] != "развилка" or rec["status"] != "решён" or not rec["decision"] or _is_probe(rec):
            continue
        chosen = next((o for o in rec["options"] if o["letter"] == rec["decision"]["option"]), None)
        if chosen is None or not chosen["evidence"]:
            notes.append(f"{rec['id']}: выбранный вариант без улик")
            continue
        for evidence in chosen["evidence"]:
            path = normalize_path(evidence["path"], roots)
            if not _is_code_file(path):
                continue
            if _resolve(path, roots) in (None, OUTSIDE_ROOT):
                note = f"{rec['id']}: путь вне корня"
                if note not in notes:
                    notes.append(note)
                continue
            ids = sites.setdefault(path, [])
            if rec["id"] not in ids:
                ids.append(rec["id"])
    return {"sites": dict(sorted(sites.items())), "notes": notes}
