#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Журнал решений symphysis: источник — JSON, markdown и HTML — рендер (F-01.B).

Схема — `journal.schema.json` рядом с кодом журнала (модуль `decisions`, в установке — `.symphysis/tools/`).
Ключи JSON английские, значения русские. Команды ниже — из корня ядра; в проекте скрипт лежит
в `.symphysis/tools/journal.py`.

    python cli/journal.py import-md docs/plan-implementation.journal.md \
        --out docs/plan-implementation.journal.json
    python cli/journal.py check docs/plan-implementation.journal.json [--strict] [--write]
    python cli/journal.py render-md docs/plan-implementation.journal.json \
        --out docs/plan-implementation.journal.md
    python cli/journal.py render-html docs/plan-implementation.journal.json \
        --out docs/plan-implementation.html [--template viewer/playground-template.html] \
        [--attack <каталог изменения>/attack/decisions.md [--attack <каталог изменения>/attack/artifacts.md]]
    python cli/journal.py render-design docs/plan-implementation.journal.json \
        --out design.md
    python cli/journal.py view-json docs/plan-implementation.journal.json \
        [--attack <каталог изменения>/attack/decisions.md]
    python cli/journal.py apply docs/plan-implementation.journal.json answers.md \
        [--date YYYY-MM-DD] [--dry-run]
    python cli/journal.py apply-md4h docs/plan-implementation.journal.json feedback.md \
        --render docs/plan-implementation.journal.md
    python cli/journal.py code-sites <каталог изменения>/decisions.json

Markdown, HTML и design.md — производные от JSON: правится JSON, потом рендер. Корни путей
улик задаёт только `tools/journal-roots.json`: префикс -> каталог, в значении `<root>` —
каталог над каталогом кода (корень ядра или `.symphysis`), `<home>` и `~` — домашний. Путь улики, не подошедший ни под один
префикс, получает вердикт «корня для пути нет»: отката на корень symphysis нет, неявного
корня в коде нет. Корень по умолчанию существует, только если файл называет его пустым
префиксом; у инсталлятора это `{"": "<root>/.."}` — проект над `.symphysis/`.

`apply` вносит промпт возврата просмотрщика (кнопка «Скопировать промпт») в JSON: всё или
ничего, отказ называет запись; сам он не рендерит — после него `render-md` и `render-html`.
Строка `- тяжесть: <файл атаки> · <раздел> · «<утверждение>» → <тяжесть> — «<обоснование>»` журнал не меняет:
`apply` правит по ней файл атаки этого изменения, всё или ничего вместе со строками журнала; порядок записи —
журнал, потом файлы атаки; `--dry-run` не пишет ничего.

`apply-md4h` вносит комментарии человека из связки Markdown Editor for Humans (`md4h-feedback/v2`)
в `comments[]` записей: рендер -> комментарии в md4h -> `apply-md4h` -> агент действует по
`comments[]`. Связка должна быть запечатана и относиться к этому рендеру (SHA-256 файла); запись
комментария — по ближайшему якорю `<!-- journal:F-NN -->` выше его первой строки. Всё или ничего;
заново он не рендерит.

`render-html --attack <файл>` (повторяемый) подаёт просмотрщику файлы атаки для режима «атака»:
`parse_attack_md` читает frontmatter (`status`, цели с хешами) и таблицу строк; хеш файла журнала
встраивается в страницу, по нему режимы «проверка» и «атака» видят, устарел ли вердикт. Битый файл
атаки — код 2, HTML не пишется. Спор со строкой атаки `apply` не вносит: его закрывает правка цели и повторная
атака. Исключение — строка о тяжести (F-47.A): `apply` правит в файле атаки ячейку тяжести и `status`
(`parse_attack_text`, `set_severity`, модуль `attack`).

`view-json` отдаёт на stdout те же данные, что получает страница, для показа вне неё (расширение VS Code):
улики сверены в памяти, у записи и парковки `destination` — «куда уйдёт», в `attacks` — разобранные файлы
атаки. Ничего не пишет. Негодный журнал — код 1 и stderr; битый файл атаки — `{"path", "error"}` у этого
файла, журнал виден, код 0.

`code-sites` печатает файлы кода из улик выбранных вариантов решённых развилок с номерами записей, кроме
проб и фактов; журнал не меняет, файлов кода не читает (F-15.D). `check` при `consequences.md` рядом с журналом
сверяет опись с этим списком и цитаты `путь:строка «цитата»` с кодом: сигнал, не стоп; файл со строкой
`**Причина:**` сверки мест не даёт, форму файла сверх этого скрипт не разбирает (F-128.A). Настройки
журнал не читает: это `symphysis_config.py`.

`check` при файлах `attack/decisions.md` и `attack/artifacts.md` рядом с журналом печатает состав устаревшего
вердикта (`scope_lines`, модуль `attack`): `[..] атака журнала: после вердикта добавлено N записей: …`, у артефактов —
все изменившиеся цели; при совпавших хешах строк нет, код выхода они не меняют. Файл атаки, который не
разбирается, — `[!!] attack/<файл>: файл атаки не разбирается: <причина>`, с `--strict` код 2.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Исходник ядра (F-20 A): код модулей лежит в соседних каталогах первого уровня, точка входа ставит нужные ей в `sys.path`.
# В установке весь код рядом в `.symphysis/tools/`: `roots.py` лежит возле этого файла, и путь не меняется.
_HERE = Path(__file__).resolve().parent
if not (_HERE / "roots.py").is_file():
    sys.path[1:1] = [str(_HERE.parent / name) for name in
                     ("cli", "decisions", "viewer", "attack", "consequences", "step-help", "openspec-run", "roots")]

from attack_scope import scope_lines  # noqa: E402  (после правки sys.path)
from attack_table import parse_attack_md, parse_attack_text, set_severity  # noqa: E402
from journal_apply import REFUSED, apply_answers, apply_md4h, check_evidence, parse_answers, parse_md4h, sha256_file  # noqa: E402
from journal_cli import build_parser, main  # noqa: E402
from journal_consequences import check_consequences  # noqa: E402
from journal_model import SCHEMA_PATH, _flat, _unquote, import_md, import_md_text, load_journal, save_journal, validate_journal  # noqa: E402
from journal_render import anchor_lines, render_design, render_md, view_payload  # noqa: E402
from journal_sites import code_sites, normalize_path  # noqa: E402
from roots import ROOT, ROOTS_PATH, default_roots, file_links, find_quote, project_href  # noqa: E402
from viewer_render import PLACEHOLDER, PLACEHOLDER_ATTACK, TEMPLATE_PATH, render_html  # noqa: E402

__all__ = [
    "ROOT", "SCHEMA_PATH", "ROOTS_PATH", "TEMPLATE_PATH", "PLACEHOLDER", "PLACEHOLDER_ATTACK", "REFUSED",
    "load_journal", "save_journal", "validate_journal", "import_md", "import_md_text",
    "default_roots", "find_quote", "check_evidence", "file_links", "project_href",
    "render_md", "render_html", "render_design", "view_payload", "anchor_lines", "parse_attack_md", "parse_attack_text", "set_severity", "scope_lines",
    "parse_answers", "apply_answers", "parse_md4h", "apply_md4h", "sha256_file",
    "code_sites", "normalize_path", "check_consequences",
    "build_parser", "main", "_unquote", "_flat",
]

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
