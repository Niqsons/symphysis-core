#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Журнал решений symphysis: источник — JSON, markdown и HTML — рендер (F-01.B).

Схема — `docs/journal.schema.json`. Ключи JSON английские, значения русские.

    py -3.13 tools/journal.py import-md docs/plan-implementation.journal.md \
        --out docs/plan-implementation.journal.json
    py -3.13 tools/journal.py check docs/plan-implementation.journal.json [--strict] [--write]
    py -3.13 tools/journal.py render-md docs/plan-implementation.journal.json \
        --out docs/plan-implementation.journal.md
    py -3.13 tools/journal.py render-html docs/plan-implementation.journal.json \
        --out docs/plan-implementation.html [--template tools/playground-template.html]
    py -3.13 tools/journal.py render-design docs/plan-implementation.journal.json \
        --out design.md
    py -3.13 tools/journal.py apply docs/plan-implementation.journal.json answers.md \
        [--date YYYY-MM-DD] [--dry-run]
    py -3.13 tools/journal.py apply-md4h docs/plan-implementation.journal.json feedback.md \
        --render docs/plan-implementation.journal.md

Markdown, HTML и design.md — производные от JSON: правится JSON, потом рендер. Корни путей
улик — свои префиксы symphysis плюс `tools/journal-roots.json`. Путь улики, не
подошедший ни под один префикс, получает вердикт «корня для пути нет»: отката
на корень symphysis нет.

`apply` вносит промпт возврата просмотрщика (кнопка «Скопировать промпт») в JSON: всё или
ничего, отказ называет запись; сам он не рендерит — после него `render-md` и `render-html`.

`apply-md4h` вносит комментарии человека из связки Markdown Editor for Humans (`md4h-feedback/v2`)
в `comments[]` записей: рендер -> комментарии в md4h -> `apply-md4h` -> агент действует по
`comments[]`. Связка должна быть запечатана и относиться к этому рендеру (SHA-256 файла); запись
комментария — по ближайшему якорю `<!-- journal:F-NN -->` выше его первой строки. Всё или ничего;
заново он не рендерит.
"""
from __future__ import annotations

import sys

from journal_apply import (REFUSED, ROOTS_PATH, apply_answers, apply_md4h, check_evidence, default_roots,
                           find_quote, parse_answers, parse_md4h, sha256_file)
from journal_cli import build_parser, main
from journal_model import (ROOT, SCHEMA_PATH, _flat, _unquote, import_md, import_md_text, load_journal,
                           save_journal, validate_journal)
from journal_render import PLACEHOLDER, TEMPLATE_PATH, anchor_lines, render_design, render_html, render_md

__all__ = [
    "ROOT", "SCHEMA_PATH", "ROOTS_PATH", "TEMPLATE_PATH", "PLACEHOLDER", "REFUSED",
    "load_journal", "save_journal", "validate_journal", "import_md", "import_md_text",
    "default_roots", "find_quote", "check_evidence",
    "render_md", "render_html", "render_design", "anchor_lines",
    "parse_answers", "apply_answers", "parse_md4h", "apply_md4h", "sha256_file",
    "build_parser", "main", "_unquote", "_flat",
]

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
