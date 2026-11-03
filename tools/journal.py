#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Журнал решений symphysis: источник — JSON, markdown и HTML — рендер (F-01.B).

Схема — `docs/journal.schema.json`. Ключи JSON английские, значения русские.

    python tools/journal.py import-md docs/plan-implementation.journal.md \
        --out docs/plan-implementation.journal.json
    python tools/journal.py check docs/plan-implementation.journal.json [--strict] [--write]
    python tools/journal.py render-md docs/plan-implementation.journal.json \
        --out docs/plan-implementation.journal.md
    python tools/journal.py render-html docs/plan-implementation.journal.json \
        --out docs/plan-implementation.html [--template tools/playground-template.html] \
        [--attack <каталог изменения>/attack/decisions.md [--attack <каталог изменения>/attack/artifacts.md]]
    python tools/journal.py render-design docs/plan-implementation.journal.json \
        --out design.md
    python tools/journal.py view-json docs/plan-implementation.journal.json \
        [--attack <каталог изменения>/attack/decisions.md]
    python tools/journal.py apply docs/plan-implementation.journal.json answers.md \
        [--date YYYY-MM-DD] [--dry-run]
    python tools/journal.py apply-md4h docs/plan-implementation.journal.json feedback.md \
        --render docs/plan-implementation.journal.md
    python tools/journal.py code-sites <каталог изменения>/decisions.json

Markdown, HTML и design.md — производные от JSON: правится JSON, потом рендер. Корни путей
улик задаёт только `tools/journal-roots.json`: префикс -> каталог, в значении `<root>` —
каталог над `tools/`, `<home>` и `~` — домашний. Путь улики, не подошедший ни под один
префикс, получает вердикт «корня для пути нет»: отката на корень symphysis нет, неявного
корня в коде нет. Корень по умолчанию существует, только если файл называет его пустым
префиксом; у инсталлятора это `{"": "<root>/.."}` — проект над `.symphysis/`.

`apply` вносит промпт возврата просмотрщика (кнопка «Скопировать промпт») в JSON: всё или
ничего, отказ называет запись; сам он не рендерит — после него `render-md` и `render-html`.

`apply-md4h` вносит комментарии человека из связки Markdown Editor for Humans (`md4h-feedback/v2`)
в `comments[]` записей: рендер -> комментарии в md4h -> `apply-md4h` -> агент действует по
`comments[]`. Связка должна быть запечатана и относиться к этому рендеру (SHA-256 файла); запись
комментария — по ближайшему якорю `<!-- journal:F-NN -->` выше его первой строки. Всё или ничего;
заново он не рендерит.

`render-html --attack <файл>` (повторяемый) подаёт просмотрщику файлы атаки для режима «атака»:
`parse_attack_md` читает frontmatter (`status`, цели с хешами) и таблицу строк; хеш файла журнала
встраивается в страницу, по нему режимы «проверка» и «атака» видят, устарел ли вердикт. Битый файл
атаки — код 2, HTML не пишется. Строки атаки `apply` не меняет: их закрывает правка цели и повторная атака.

`view-json` отдаёт на stdout те же данные, что получает страница, для показа вне неё (расширение VS Code):
улики сверены в памяти, у записи и парковки `destination` — «куда уйдёт», в `attacks` — разобранные файлы
атаки. Ничего не пишет. Негодный журнал — код 1 и stderr; битый файл атаки — `{"path", "error"}` у этого
файла, журнал виден, код 0.

`code-sites` печатает файлы кода из улик выбранных вариантов решённых развилок с номерами записей, кроме
проб и фактов; журнал не меняет, файлов кода не читает (F-15.D). `check` при `consequences.md` рядом с журналом
сверяет опись с этим списком и цитаты `путь:строка «цитата»` с кодом: сигнал, не стоп; файл со строкой
`**Причина:**` сверки мест не даёт, форму файла сверх этого скрипт не разбирает (F-128.A). Настройки
журнал не читает: это `symphysis_config.py`.
"""
from __future__ import annotations

import sys

from journal_apply import (REFUSED, ROOTS_PATH, apply_answers, apply_md4h, check_evidence, default_roots,
                           file_links, find_quote, parse_answers, project_href, parse_md4h, sha256_file)
from journal_cli import build_parser, main
from journal_consequences import check_consequences
from journal_model import (ROOT, SCHEMA_PATH, _flat, _unquote, import_md, import_md_text, load_journal,
                           save_journal, validate_journal)
from journal_render import (PLACEHOLDER, PLACEHOLDER_ATTACK, TEMPLATE_PATH, anchor_lines, parse_attack_md,
                            render_design, render_html, render_md, view_payload)
from journal_sites import code_sites, normalize_path

__all__ = [
    "ROOT", "SCHEMA_PATH", "ROOTS_PATH", "TEMPLATE_PATH", "PLACEHOLDER", "PLACEHOLDER_ATTACK", "REFUSED",
    "load_journal", "save_journal", "validate_journal", "import_md", "import_md_text",
    "default_roots", "find_quote", "check_evidence", "file_links", "project_href",
    "render_md", "render_html", "render_design", "view_payload", "anchor_lines", "parse_attack_md",
    "parse_answers", "apply_answers", "parse_md4h", "apply_md4h", "sha256_file",
    "code_sites", "normalize_path", "check_consequences",
    "build_parser", "main", "_unquote", "_flat",
]

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
