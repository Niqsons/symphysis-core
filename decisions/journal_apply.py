# -*- coding: utf-8 -*-
"""Сверка улик журнала (`check_evidence`) и внесение чужих правок в журнал: промпт возврата
просмотрщика (`apply_answers`) и комментарии md4h к рендеру (`apply_md4h`). Корни улик и поиск цитат —
в `roots.py`. Зависит от journal_model, journal_render и roots."""
from __future__ import annotations

import bisect
import copy
import hashlib
import json
import re
from pathlib import Path

from journal_model import ADDED_MARK, RE_REC, _evidence_of, _flat, _new_record, _unquote, validate_journal
from journal_render import _lines, anchor_lines
from roots import NOT_CHECKED, find_quote

__all__ = [
    "REFUSED", "check_evidence",
    "parse_answers", "apply_answers", "parse_md4h", "apply_md4h", "sha256_file",
]


# --- сверка улик -----------------------------------------------------------

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

# Старое значение «материалы» (имя адресата «агент» до переименования) схема читает ради старых журналов, `apply` его
# не пишет: строка с ним — отказ с этим перечнем (parking-addressee-agent: F-17.A).
PARKING_ADDRESSEES = ("агент", "человек", "ИБ")
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
REFUSED = "отказ"

# Строки промпта — те, что пишет `updateOut()` в `viewer/playground-template.html`.
RE_ITEM = re.compile(r"^- (F-N?\d+):[ \t]*(.*)$")
RE_NEW_FORKS = re.compile(r"^Новые развилки:\s*$")
# Строка о тяжести (F-47.A): путь до первой « · », раздел до первой « · «», утверждение до последнего
# «» → <слово> — «», обоснование — в «». Начало узнаёт RE_SEVERITY_START, форму — RE_SEVERITY.
RE_SEVERITY_START = re.compile(r"^- тяжесть:")
RE_SEVERITY = re.compile(r"^- тяжесть:[ \t]*(.+?) · (.+?) · «(.*)» → (\S+) — («.*»|\(без слова\))$", re.S)
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


def _severity_why(group: str) -> str:
    """Обоснование строки о тяжести: текст между внешними «» последней группы, как её даёт RE_SEVERITY.
    Одинокая » внутри не делает пару «внутренней»: `«a » b»` -> `a » b` (`_unquote` тут не годится)."""
    return "" if group == "(без слова)" else group[1:-1]


def _parse_item(rid: str | None, body: str) -> dict:
    if rid is None:   # строка о тяжести: body — вся строка с продолжением
        m = RE_SEVERITY.match(body)
        if m:
            return {"id": None, "op": "severity", "path": m.group(1).strip(), "section": m.group(2).strip(),
                    "claim": m.group(3), "severity": m.group(4), "why": _severity_why(m.group(5))}
        return {"id": None, "op": "unknown", "raw": body}
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
    строка `- тяжесть: …` (F-47.A) — свой пункт `op: severity` в любом месте выше замечаний: она
    закрывает предыдущий пункт, продолжение идёт в её обоснование, после неё снова узнаётся
    `- F-NN:`; не по форме — `op: unknown`; `Замечания к схеме:` идут последними и забирают текст до конца. Строка не по форме
    даёт `op: unknown` — `apply_answers` откажет по ней поимённо."""
    items: list[list] = []
    cur: list | None = None
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
        if RE_SEVERITY_START.match(line):
            cur = [None, line]
            items.append(cur)
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
    raise _Refusal(f"{a['id'] or 'строка о тяжести'}: строка не по форме просмотрщика — «{_flat(a.get('raw', a['op']))[:80]}»")


_APPLY = {"decide": _do_decide, "word": _do_word, "park": _do_park, "add_option": _do_add_option,
          "dep_add": _do_dependency, "dep_remove": _do_dependency, "dispute": _do_dispute,
          "new_fork": _do_new_fork, "note": _do_note, "unknown": _do_unknown}


def apply_answers(journal: dict, answers: list[dict], date: str) -> list[str]:
    """Вносит разобранный промпт в журнал на месте; возвращает отчёт строками.

    Всё или ничего: любая строка с отказом (нет записи, буква не из вариантов, адресат не из
    трёх `агент | человек | ИБ` — старое `материалы` тоже отказ, зависимость на несуществующую
    запись, «было X» не сошлось с журналом, строка не по форме) оставляет журнал как был —
    отчёт тогда состоит из строк `отказ: …` с именем записи, чинится строка и промпт вносится
    целиком заново. Внесённый результат тоже должен
    пройти `validate_journal`. Слова человека сворачиваются в одну строку (формат markdown
    однострочный). `date` попадает в `decision.date` и `notes[].date`. Рендер — отдельный шаг."""
    work = copy.deepcopy(journal)
    by_id = {r["id"]: r for r in work["records"]}
    report: list[str] = []
    refusals: list[str] = []
    for answer in answers:
        if answer["op"] == "severity":   # строку вносит план файлов атаки (F-17.D), журнал она не меняет
            continue
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
