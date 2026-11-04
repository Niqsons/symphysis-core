# -*- coding: utf-8 -*-
"""Сверка улик с файлами (`check_evidence`) и внесение чужих правок в журнал: промпт возврата
просмотрщика (`apply_answers`) и комментарии md4h к рендеру (`apply_md4h`). Зависит
от journal_model и journal_render."""
from __future__ import annotations

import bisect
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from journal_model import (ADDED_MARK, RE_REC, ROOT, _evidence_of, _flat, _new_record, _unquote,
                           validate_journal)
from journal_render import _lines, anchor_lines

__all__ = [
    "ROOTS_PATH", "REFUSED",
    "change_of", "default_roots", "project_roots", "find_quote", "check_evidence", "file_links", "project_href",
    "parse_answers", "apply_answers", "parse_md4h", "apply_md4h", "sha256_file",
]


ROOTS_PATH = ROOT / "tools" / "journal-roots.json"


# --- сверка улик -----------------------------------------------------------

def _expand_value(value: str) -> Path:
    """`<home>` и `~` — домашний каталог; `<root>` — ROOT (каталог над `tools/`), хвост
    после него разрешается (`<root>/..` — каталог над ROOT)."""
    if value.startswith("<root>"):
        return (ROOT / value[len("<root>"):].lstrip("/\\")).resolve()
    if value.startswith("<home>"):
        value = str(Path.home()) + value[len("<home>"):]
    return Path(value).expanduser()


def change_of(journal_path: Path) -> tuple[Path, str] | None:
    """Корень проекта и имя изменения из пути журнала: `<корень>/openspec/changes/[archive/]<имя>/<журнал>`. Корень не из
    каталога вызова: у вызова может быть свой проект с тем же именем (F-58). Журнал в другом месте — `None`."""
    folder = Path(os.path.abspath(journal_path)).parent
    changes = folder.parent.parent if folder.parent.name == "archive" else folder.parent
    if changes.name == "changes" and changes.parent.name == "openspec":
        return changes.parent.parent, folder.name
    return None


def _roots_from_file(roots_file: Path | None) -> dict[str, Path]:
    raw = json.loads(Path(roots_file or ROOTS_PATH).read_text(encoding="utf-8"))
    return {prefix: _expand_value(value) for prefix, value in raw.items()}


def _inside(path: Path, root: Path) -> bool:
    return Path(os.path.abspath(path)).resolve().is_relative_to(root.resolve())


def default_roots(roots_file: Path | None = None, journal_path: Path | None = None) -> dict[str, Path]:
    """Префикс пути улики -> каталог — только из файла корней (`tools/journal-roots.json`
    или `roots_file`); зашитых в код префиксов нет. Значение: `<root>`, `<home>`, `~` или
    путь; пустой префикс `""` — корень по умолчанию, если файл его называет.
    Файл корней вне проекта из пути журнала — инструменты вне проекта (`symphysis.toolsPath`, F-93, F-104): решает положение
    инструментов, а не содержимое файла (у клона ядра в нём нет `""`); файл не читается, единственный корень — проект.
    Явный `roots_file` важнее; путь журнала не из `openspec/changes/` — файл корней."""
    where = change_of(journal_path) if journal_path is not None and roots_file is None else None
    if where is not None and not _inside(ROOTS_PATH, where[0]):
        return {"": where[0].resolve()}
    return _roots_from_file(roots_file)


def project_roots(project: Path) -> dict[str, Path]:
    """Те же корни для вызова без журнала (`step_help.py`): корень проекта известен по каталогу вызова. Файл корней вне проекта —
    инструменты вне проекта (F-93, F-104): единственный корень — проект. Файла корней нет или он негоден — тоже."""
    project = Path(project)
    if not _inside(ROOTS_PATH, project):
        return {"": project.resolve()}
    try:
        roots = _roots_from_file(None)
    except (OSError, ValueError):
        return {"": project.resolve()}
    return {"": project.resolve(), **roots}   # файл без `""`: без префикса путь считается от проекта, а не от каталога установки


OUTSIDE_ROOT = Path("<вне корня>")   # признак `_resolve`: путь выходит за корень, файл не читается
BINARY_PROBE = 8192                   # байт NUL в первых 8 КиБ — файл бинарный (F-42)
VERDICT_OUTSIDE = "вне корня"
VERDICT_BINARY = "не проверить: бинарный файл"
VERDICT_NOT_UTF8 = "не проверить: не UTF-8"
VERDICT_UNREADABLE = "не проверить: файл не читается"   # права, чужая блокировка: сигнал, не стоп
NOT_CHECKED = (VERDICT_BINARY, VERDICT_NOT_UTF8, VERDICT_UNREADABLE)
RE_CODE_SPAN = re.compile(r"`([^`]+)`")   # та же разметка, что у `md()` страницы
RE_LINE_TAIL = re.compile(r":\d+(?:-\d+)?$")


def _resolve(path: str, roots: dict[str, Path]) -> Path | None:
    """Файл улики по самому длинному подходящему префиксу: `None` — корня для пути нет,
    `OUTSIDE_ROOT` — путь выходит за корень. Разделители путей нормализуются (обратная косая -> прямая);
    хвост с `..`, абсолютный хвост и файл, который после `resolve()` (регистр диска,
    ссылки и junction разрешены) лежит вне `resolve()`-нутого корня, — «вне корня»."""
    path = path.replace("\\", "/")
    for prefix in sorted(roots, key=len, reverse=True):
        if not path.startswith(prefix.replace("\\", "/")):
            continue
        tail = path[len(prefix):]
        if ".." in tail.split("/") or Path(tail).is_absolute() or tail.startswith("/"):
            return OUTSIDE_ROOT
        root = roots[prefix].resolve()
        file = (root / tail).resolve()
        # корень-файл (`CLAUDE.md`): хвост пуст, файл совпадает с корнем
        return file if file == root or file.is_relative_to(root) else OUTSIDE_ROOT
    return None


def _walk_references(value, paths: set[str]) -> None:
    """Пути из поля `path` и текст в backticks, без хвоста `:строка`; команда или обычное слово отсеются проверкой файла."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "path" and isinstance(item, str):
                paths.add(item)
            else:
                _walk_references(item, paths)
    elif isinstance(value, list):
        for item in value:
            _walk_references(item, paths)
    elif isinstance(value, str):
        paths.update(RE_LINE_TAIL.sub("", code) for code in RE_CODE_SPAN.findall(value))


def _relative_link(path: str, bases: list[dict[str, Path]], here: Path, encode: bool = True) -> str | None:
    """Относительный адрес от каталога `here`: первая база, где это файл внутри корня. Недопустимое имя и другой диск — без ссылки.
    `encode=False` — путь как есть (для плагина), без `quote`."""
    for roots in bases:
        try:
            file = _resolve(path, roots)
            if file is None or file == OUTSIDE_ROOT or not file.is_file():
                continue
            href = os.path.relpath(file, here).replace(os.sep, "/")
            return quote(href, safe="/") if encode else href
        except (OSError, ValueError):
            continue
    return None


def file_links(journal: dict, roots: dict[str, Path], change_dir: Path, out: Path | None, *others,
               from_project: bool = False) -> dict[str, str]:
    """Карта «путь из журнала -> адрес от страницы» для страницы `out`: путь улики или файла справки и текст в backticks
    из журнала и из `others` (атаки, снимок справки), если это существующий файл внутри корней улик или каталога изменения.
    Абсолютных путей в карте нет: страницу можно коммитить; адрес ссылки на странице берётся только отсюда.
    `from_project=True` (F-44): значение от корня `""` (без него — каталог над `tools/`), прямые слеши, без кодирования;
    `out` не нужен. `../` бывает только у префикса файла корней на соседний каталог."""
    paths: set[str] = set()
    for value in (journal, *others):
        _walk_references(value, paths)
    bases = [roots, {"": Path(change_dir).resolve()}]
    here = Path(roots.get("", ROOT)).resolve() if from_project else Path(out).resolve().parent
    found = {path: _relative_link(path, bases, here, encode=not from_project) for path in sorted(paths)}
    return {path: href for path, href in found.items() if href}


def project_href(roots: dict[str, Path], out: Path) -> str | None:
    """Адрес корня проекта от страницы `out`: пустой префикс файла корней, без него каталог над `tools/`.
    Корень на другом диске — `None`."""
    root = roots.get("", ROOT)
    try:
        return quote(os.path.relpath(Path(root).resolve(), Path(out).resolve().parent).replace(os.sep, "/"), safe="/") + "/"
    except (OSError, ValueError):
        return None


def _read_text(file: Path) -> tuple[str | None, str]:
    """(текст, вердикт): текст `None` — файл читать как текст нельзя, вердикт называет причину."""
    try:
        data = file.read_bytes()
    except OSError:
        return None, VERDICT_UNREADABLE
    if b"\x00" in data[:BINARY_PROBE]:
        return None, VERDICT_BINARY
    try:
        return data.decode("utf-8-sig"), ""
    except UnicodeDecodeError:
        return None, VERDICT_NOT_UTF8


def _match_lines(lines: list[str], quote: list[str]) -> int | None:
    """Номер первой строки совпадения (с 1): однострочная цитата — подстрока строки файла;
    многострочная — подряд идущие строки: первая цитаты — суффикс строки файла, средние равны,
    последняя — префикс следующей. Символы сравниваются как есть."""
    n = len(quote)
    for i, line in enumerate(lines):
        if n == 1:
            if quote[0] in line:
                return i + 1
        elif (i + n <= len(lines) and line.endswith(quote[0]) and lines[i + 1:i + n - 1] == quote[1:-1]
              and lines[i + n - 1].startswith(quote[-1])):
            return i + 1
    return None


def find_quote(path: str, quote: str, roots: dict[str, Path]) -> tuple[int | None, str]:
    """(строка, вердикт): сверка без нормализации по строкам файла, окончания строк в сравнение
    не входят. Нет строки — вердикт называет причину; «не проверить: …» — файл не текст."""
    file = _resolve(path, roots)
    if file is None:
        return None, "корня для пути нет"
    if file is OUTSIDE_ROOT:
        return None, VERDICT_OUTSIDE
    if not file.is_file():
        return None, "файла нет"
    text, verdict = _read_text(file)
    if text is None:
        return None, verdict
    quote_lines = quote.splitlines()
    line = _match_lines(text.splitlines(), quote_lines) if quote_lines else None
    return (line, "сверено") if line is not None else (None, "цитаты нет дословно")


def check_evidence(journal: dict, roots: dict[str, Path]) -> dict:
    """Сверяет каждую улику с файлом. Пишет в улики `line`, `found` (`True` — найдена, `False` —
    сверяли, не нашли, `None` — не проверить: бинарный файл или не UTF-8) и `verdict`.
    Несверенная улика — сигнал, не ошибка. «Не проверить» не входит ни в найденные, ни в `missing`."""
    total = found = 0
    missing: list[str] = []
    unchecked: list[str] = []
    for rec in journal["records"]:
        for ev in _evidence_of(rec):
            total += 1
            line, verdict = find_quote(ev["path"], ev["quote"], roots)
            ev["line"], ev["verdict"] = line, verdict
            if verdict in NOT_CHECKED:
                ev["found"] = None
                unchecked.append(f"{rec['id']}: {ev['path']} — {verdict}")
                continue
            ev["found"] = line is not None
            if line is not None:
                found += 1
            else:
                missing.append(f"{rec['id']}: {ev['path']} «{ev['quote']}» — {verdict}")
    return {"total": total, "found": found, "missing": missing, "unchecked": unchecked}


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


# --- комментарии md4h к рендеру --------------------------------------------

MD4H_SCHEMA = "md4h-feedback/v2"
MD4H_LINE_NUMBERING = "one-based-inclusive"
MD4H_REQUIRED = ("schema", "state", "round", "source", "source_sha256")
MD4H_LINES_LABEL = "**Source lines:**"
RE_MD4H_ITEM = re.compile(r"^## (F\d+)(?:\s.*)?$")
RE_MD4H_SPAN = re.compile(r"^\*\*Source lines:\*\*[ \t]*(\d+)(?:[ \t]*-[ \t]*(\d+))?[ \t]*$")
RE_MD4H_FEEDBACK = re.compile(r"^### Feedback[ \t]*$")
RE_FENCE_OPEN = re.compile(r"^(`{3,})[^`]*$")
RE_FENCE_CLOSE = re.compile(r"^(`{3,})[ \t]*$")


def _md4h_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        try:
            return json.loads(value) if value[0] == '"' else value[1:-1]
        except ValueError:
            return value[1:-1]
    return value


def _md4h_frontmatter(lines: list[str]) -> tuple[dict, int]:
    """Поля `ключ: значение` между первой парой `---`; второй результат — индекс строки после неё."""
    if not lines or lines[0].strip() != "---":
        raise ValueError("в связке нет frontmatter: файл должен начинаться со строки ---")
    meta: dict[str, str] = {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return meta, i + 1
        key, sep, value = lines[i].partition(":")
        if sep and key.strip() and " " not in key.strip():
            meta[key.strip()] = _md4h_scalar(value)
    raise ValueError("frontmatter связки не закрыт второй строкой ---")


def _md4h_span(item_id: str, line: str) -> tuple[int, int]:
    m = RE_MD4H_SPAN.match(line)
    if not m:
        raise ValueError(f"{item_id}: строка {line.strip()!r} не разобрана: ждали «{MD4H_LINES_LABEL} 12» или «… 12-15»")
    first = int(m.group(1))
    last = int(m.group(2) or first)
    if first < 1 or last < first:
        raise ValueError(f"{item_id}: строки {first}-{last} не годятся: счёт с единицы, от меньшей к большей")
    return first, last


def parse_md4h(text: str) -> dict:
    """Связка md4h (`md4h-feedback/v2`) -> `{schema, state, round, source, source_sha256,
    items: [{id, lines: (первая, последняя), feedback}]}`, комментарии в порядке файла.

    Инструкция человека — только текст в рамке под `### Feedback` (так сказано и в самой связке);
    выделенный текст, цели и заголовки — улики, в `feedback` они не попадают. Разбор идёт
    по рамкам кода: заголовок или рамка внутри чужой рамки (выделенный текст сам может
    быть markdown) разбор не сбивают; рамка закрывается строкой из стольких же обратных
    кавычек и больше. `Source lines:` — `a-b` или одно число (`a-a`), счёт с единицы, обе
    границы включены. Незнакомая схема, пропавшее поле или пустой комментарий —
    `ValueError` с именем того, чего нет. Концы строк LF и CRLF читаются одинаково."""
    lines = _lines(text.lstrip("\ufeff"))
    meta, body_start = _md4h_frontmatter(lines)
    for field in MD4H_REQUIRED:
        if not meta.get(field):
            raise ValueError(f"в frontmatter связки нет поля {field}")
    if meta["schema"] != MD4H_SCHEMA:
        raise ValueError(f"схема связки {meta['schema']!r} не поддерживается: разбирается только {MD4H_SCHEMA}")
    if meta.get("line_numbering", MD4H_LINE_NUMBERING) != MD4H_LINE_NUMBERING:
        raise ValueError(f"line_numbering: {meta['line_numbering']!r} — номера строк разобраны только "
                         f"в счёте {MD4H_LINE_NUMBERING}")

    items: list[dict] = []
    item: dict | None = None
    fence: tuple[int, bool, list[str]] | None = None   # (длина рамки, это Feedback, строки внутри)
    after_feedback_heading = False
    for line in lines[body_start:]:
        if fence is not None:
            ticks, is_feedback, inner = fence
            close = RE_FENCE_CLOSE.match(line)
            if close and len(close.group(1)) >= ticks:
                if is_feedback:
                    item["feedback"] = "\n".join(inner).strip()
                fence = None
            else:
                inner.append(line)
            continue
        open_ = RE_FENCE_OPEN.match(line)
        if open_:
            is_feedback = after_feedback_heading and item is not None and item["feedback"] is None
            fence = (len(open_.group(1)), is_feedback, [])
            after_feedback_heading = False
        elif line.startswith("#"):
            head = RE_MD4H_ITEM.match(line)
            if head:
                item = {"id": head.group(1), "lines": None, "feedback": None}
                items.append(item)
            after_feedback_heading = item is not None and bool(RE_MD4H_FEEDBACK.match(line))
        elif item is not None and item["lines"] is None and line.startswith(MD4H_LINES_LABEL):
            item["lines"] = _md4h_span(item["id"], line)
    if fence is not None and fence[1]:
        raise ValueError(f"{item['id']}: рамка под ### Feedback не закрыта")
    for it in items:
        if it["lines"] is None:
            raise ValueError(f"{it['id']}: нет строки «{MD4H_LINES_LABEL}»")
        if it["feedback"] is None:
            raise ValueError(f"{it['id']}: под ### Feedback нет рамки с текстом комментария")
        if not it["feedback"]:
            raise ValueError(f"{it['id']}: рамка под ### Feedback пуста — комментарий без текста")
    return {**{field: meta[field] for field in MD4H_REQUIRED}, "items": items}


def sha256_file(path: Path) -> str:
    """SHA-256 файла по байтам, как он лежит на диске (шестнадцатеричный, строчными)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _record_starts(text: str) -> list[tuple[int, str]]:
    """`(первая строка записи, id)` по порядку файла. Запись начинается заголовком `## F-NN …`,
    который `render_md` ставит строкой над якорем: комментарий к самому заголовку принадлежит
    этой записи, а не предыдущей. Нет такого заголовка над якорем — запись начинается с якоря."""
    lines = _lines(text)
    starts = []
    for n, rid in anchor_lines(text):
        head = RE_REC.match(lines[n - 2]) if n >= 2 else None
        starts.append((n - 1 if head and head.group(1) == rid else n, rid))
    return starts


def _md4h_comments(work: dict, bundle: dict, rendered_text: str) -> tuple[list[str], list[str]]:
    """Раскладывает комментарии связки по записям `work`; возвращает `(отчёт, отказы)`."""
    starts = _record_starts(rendered_text)
    if not starts:
        return [], [f"{REFUSED}: в рендере нет якорей `<!-- journal:F-NN -->` — это не рендер журнала"]
    firsts = [n for n, _ in starts]
    by_id = {r["id"]: r for r in work["records"]}
    report: list[str] = []
    refusals: list[str] = []
    for item in bundle["items"]:
        first, last = item["lines"]
        at = bisect.bisect_right(firsts, first) - 1
        if at < 0:
            refusals.append(f"{REFUSED}: комментарий {item['id']} выше первой записи "
                            f"(строка {first}, первая запись с {firsts[0]})")
            continue
        rid = starts[at][1]
        rec = by_id.get(rid)
        if rec is None:
            refusals.append(f"{REFUSED}: комментарий {item['id']}: записи {rid} нет в журнале — "
                            "рендер сделан не из этого журнала")
            continue
        comment = {"round": bundle["round"], "lines": [first, last], "text": item["feedback"]}
        if comment in rec["comments"]:
            report.append(f"{item['id']} → {rid}: уже внесён (строки {first}-{last})")
        else:
            rec["comments"].append(comment)
            report.append(f"{item['id']} → {rid}: комментарий внесён (строки {first}-{last})")
    return report, refusals


def apply_md4h(journal: dict, bundle: dict, rendered_md: Path) -> list[str]:
    """Вносит комментарии связки md4h в `comments[]` записей журнала на месте; возвращает
    отчёт строками.

    Отказ (строки `отказ: …`, журнал не меняется): связка не запечатана (`state` не `sealed`);
    SHA-256 файла `rendered_md` не равен `source_sha256` связки — комментарии относятся к
    другой версии рендера и их номера строк указывали бы не туда (после этого записи
    не сопоставляются); комментарий выше первой записи; в рендере есть запись, которой нет
    в журнале. Как и `apply_answers`, всё или ничего: любой отказ оставляет журнал как был,
    внесённый результат ещё и проходит `validate_journal`.

    Запись комментария — та, чей якорь `<!-- journal:F-NN -->` ближайший на строке `a`
    комментария или выше (запись начинается заголовком над якорем, см. `_record_starts`);
    строки считаются по файлу на диске. Вносится `{round, lines: [a, b], text}`; такой же
    комментарий (раунд, строки и текст) в записи уже есть — он пропускается со строкой
    «уже внесён», поэтому повторное внесение той же связки ничего не меняет. Рендер заново
    не делается."""
    refusals: list[str] = []
    if bundle["state"] != "sealed":
        refusals.append(f"{REFUSED}: связка не запечатана (state: {bundle['state']}) — "
                        "комментарии вносятся только из запечатанной")
    data = Path(rendered_md).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != str(bundle["source_sha256"]).lower():
        refusals.append(f"{REFUSED}: sha256 рендера не совпадает: связка к другой версии "
                        f"(в связке {str(bundle['source_sha256'])[:12]}…, у файла {actual[:12]}…)")
    work = copy.deepcopy(journal)
    report: list[str] = []
    if not refusals:  # номера строк чужой версии рендера указывали бы не туда — не сопоставляем
        report, refusals = _md4h_comments(work, bundle, data.decode("utf-8"))
    if not refusals:
        refusals = [f"{REFUSED}: после внесения журнал негоден — {e}" for e in validate_journal(work)]
    if refusals:
        return refusals + [f"{REFUSED}: журнал не изменён — отказов {len(refusals)}, "
                           f"комментариев в связке {len(bundle['items'])}"]
    journal.clear()
    journal.update(work)
    return report
