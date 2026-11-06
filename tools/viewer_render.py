# -*- coding: utf-8 -*-
"""Страница просмотрщика — файл будущего модуля `viewer`: `render_html` (шаблон и пять меток), схема решения
(`scheme_payload`, `parse_scheme`), снимок «справки нет» (`no_help_snapshot`). Данные страницы собирает
`journal_render._viewer_payload` (модуль `decisions`): viewer зависит от decisions, не наоборот."""
from __future__ import annotations

import json
import re
from pathlib import Path

from journal_render import CONTRACT, _viewer_payload
from roots import ROOT

__all__ = [
    "TEMPLATE_PATH", "PLACEHOLDER", "PLACEHOLDER_ATTACK", "PLACEHOLDER_SCHEME", "PLACEHOLDER_HELP", "PLACEHOLDER_LINKS",
    "parse_scheme", "scheme_payload", "no_help_snapshot", "render_html",
]


TEMPLATE_PATH = ROOT / "tools" / "playground-template.html"
PLACEHOLDER = "__JOURNAL_JSON__"
PLACEHOLDER_ATTACK = "__ATTACK_JSON__"
PLACEHOLDER_SCHEME = "__SCHEME_JSON__"
PLACEHOLDER_HELP = "__HELP_JSON__"
PLACEHOLDER_LINKS = "__LINKS_JSON__"


def _embed(obj) -> str:
    """JSON для `<script>` шаблона: `</` экранируется как `<\\/`, чтобы текст не закрыл `<script>`,
    `<!--` — как `\\u003c!--`, чтобы текст не открыл в скрипте «экранированное» состояние разбора HTML."""
    return json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/").replace("<!--", "\\u003c!--")


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
