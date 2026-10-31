# -*- coding: utf-8 -*-
"""Журнал решений symphysis: источник — JSON, markdown и HTML — рендер (F-01.B).

Командная строка: подкоманды `cmd_*`, `build_parser`, `main`. Первая строка этого докстринга —
описание парсера в `--help` (`build_parser` берёт его из `__doc__`); она совпадает с первой
строкой докстринга `journal.py`, где описаны подкоманды, корни улик и коды выхода."""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from journal_apply import (REFUSED, apply_answers, apply_md4h, check_evidence, default_roots, parse_answers,
                           parse_md4h, sha256_file)
from journal_model import import_md, load_journal, save_journal, validate_journal
from journal_render import TEMPLATE_PATH, parse_attack_md, render_design, render_html, render_md

__all__ = ["build_parser", "main"]


# --- командная строка ------------------------------------------------------

def _valid_journal(path: Path) -> dict | None:
    """Журнал из файла; негодный — ошибки в stderr и `None`."""
    journal = load_journal(path)
    errors = validate_journal(journal)
    for e in errors:
        print(f"[!!] {e}", file=sys.stderr)
    return None if errors else journal


def _parkings_without_finding(journal: dict, base: Path) -> list[str]:
    """Парковка «материалы» без `finding` при файле `research/<F-NN>.md` рядом с журналом —
    сигнал: исследование есть, находка в журнал не внесена."""
    return [f"{rec['id']}: парковка «материалы» без finding при research/{rec['id']}.md"
            for rec in journal["records"]
            if (base / "research" / f"{rec['id']}.md").is_file()
            and any(p["addressee"] == "материалы" and not p.get("finding") for p in rec["parking"])]


def cmd_check(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    result = check_evidence(journal, default_roots(args.roots))
    summary = f"[ok] улик сверено {result['found']} из {result['total']}"
    if result["unchecked"]:
        summary += f", не проверить {len(result['unchecked'])}"
    print(summary)
    for m in result["missing"]:
        print(f"[!!] {m}")
    for m in result["unchecked"]:
        print(f"[--] {m}")
    unfound = _parkings_without_finding(journal, args.json.parent)
    for m in unfound:
        print(f"[!!] {m}")
    if args.write:
        save_journal(args.json, journal)
        print(f"[ok] {args.json}")
    return 2 if args.strict and (result["missing"] or unfound) else 0


def cmd_import_md(args: argparse.Namespace) -> int:
    journal = import_md(args.md)
    save_journal(args.out, journal)
    recs = journal["records"]
    forks = sum(1 for r in recs if r["kind"] == "развилка")
    print(f"[ok] записей {len(recs)}: развилок {forks}, фактов {sum(1 for r in recs if r['kind'] == 'факт')}")
    print(f"[ok] {args.out}")
    errors = validate_journal(journal)
    for e in errors:
        print(f"[!!] {e}", file=sys.stderr)
    return 1 if errors else 0


def cmd_render_md(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    Path(args.out).write_text(render_md(journal, json_name=args.json.name), encoding="utf-8", newline="\r\n")
    print(f"[ok] записей {len(journal['records'])}")
    print(f"[ok] {args.out}")
    return 0


def cmd_render_html(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    # Атаки разбираются до рендера: битый файл атаки — код 2, HTML не пишется.
    attacks = []
    for path in args.attack or []:
        if not path.is_file():
            print(f"[!!] {path}: файла нет", file=sys.stderr)
            return 2
        try:
            attacks.append(parse_attack_md(path))
        except UnicodeDecodeError:  # подкласс ValueError — раньше него
            print(f"[!!] {path}: не UTF-8 — файл атаки читается как UTF-8", file=sys.stderr)
            return 2
        except ValueError as e:
            print(f"[!!] {e}", file=sys.stderr)
            return 2
    # Сверка идёт в памяти: просмотрщик получает вердикты, файл журнала не меняется;
    # хеш журнала — по байтам файла на диске, как `sha256_file` у связки md4h.
    result = check_evidence(journal, default_roots(args.roots))
    try:
        html = render_html(journal, args.template, attacks=attacks, journal_sha256=sha256_file(args.json))
    except ValueError as e:
        print(f"[!!] {e}", file=sys.stderr)
        return 1
    Path(args.out).write_text(html, encoding="utf-8", newline="\n")
    print(f"[ok] улик сверено {result['found']} из {result['total']}")
    for m in result["missing"]:
        print(f"[!!] не сверено — {m}")
    print(f"[ok] {args.out}")
    return 0


def cmd_render_design(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    Path(args.out).write_text(render_design(journal, source=args.json.name), encoding="utf-8", newline="\r\n")
    print(f"[ok] {args.out}")
    return 0


def _iso_date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError(f"дата {value!r} не в форме YYYY-MM-DD")
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"даты {value} не бывает") from None
    return value


def cmd_apply(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    if not args.answers.is_file():
        print(f"[!!] {args.answers}: файла нет", file=sys.stderr)
        return 1
    try:
        text = args.answers.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        print(f"[!!] {args.answers}: не UTF-8 — промпт возврата читается как UTF-8", file=sys.stderr)
        return 1
    answers = parse_answers(text)
    if not answers:
        print("[ok] в промпте нет строк для внесения — журнал не тронут")
        return 0
    report = apply_answers(journal, answers, args.date or dt.date.today().isoformat())
    if any(line.startswith(REFUSED) for line in report):
        for line in report:
            print(f"[!!] {line}", file=sys.stderr)
        return 1
    for line in report:
        print(f"[ok] {line}")
    if args.dry_run:
        print(f"[..] --dry-run: {args.json} не записан")
        return 0
    save_journal(args.json, journal)
    print(f"[ok] {args.json}")
    print("[..] apply не рендерит: дальше render-md и render-html")
    return 0


def _comment_count(journal: dict) -> int:
    return sum(len(r["comments"]) for r in journal["records"])


def cmd_apply_md4h(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    for path in (args.feedback, args.render):
        if not path.is_file():
            print(f"[!!] {path}: файла нет", file=sys.stderr)
            return 1
    try:
        bundle = parse_md4h(args.feedback.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:  # раньше ValueError: это его подкласс
        print(f"[!!] {args.feedback}: не UTF-8 — связка md4h читается как UTF-8", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"[!!] {args.feedback}: {e}", file=sys.stderr)
        return 1
    before = _comment_count(journal)
    try:
        report = apply_md4h(journal, bundle, args.render)
    except UnicodeDecodeError:
        print(f"[!!] {args.render}: не UTF-8 — рендер читается как UTF-8", file=sys.stderr)
        return 1
    if any(line.startswith(REFUSED) for line in report):
        for line in report:
            print(f"[!!] {line}", file=sys.stderr)
        return 2
    for line in report:
        print(f"[ok] {line}")
    added = _comment_count(journal) - before
    print(f"[ok] комментариев внесено {added}")
    if added:  # ничего нового — файл не переписывается, чтобы повтор не менял его ни байтом
        save_journal(args.json, journal)
        print(f"[ok] {args.json}")
        print("[..] apply-md4h не рендерит: комментарии лежат в comments[] записей, дальше действует агент")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="journal", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("import-md", help="журнал в markdown -> JSON по схеме")
    p.add_argument("md", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_import_md)
    p = sub.add_parser("check", help="сверить улики грепом по цитате (сигнал, не стоп); "
                                     "негодный по схеме журнал — код 1")
    p.add_argument("json", type=Path)
    p.add_argument("--roots", type=Path, help="файл корней вместо tools/journal-roots.json")
    p.add_argument("--strict", action="store_true", help="код 2, если есть несверенные улики")
    p.add_argument("--write", action="store_true", help="сохранить line/found/verdict в JSON")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("apply", help="внести промпт возврата просмотрщика в JSON (потом render-md, render-html)",
                       description="Вносит промпт возврата просмотрщика (кнопка «Скопировать промпт») в JSON "
                                   "журнала. Всё или ничего: любая строка с отказом называет запись, "
                                   "код 1, журнал не меняется. apply не рендерит: после него "
                                   "render-md и render-html. Слова человека сворачиваются в одну строку.")
    p.add_argument("json", type=Path)
    p.add_argument("answers", type=Path, help="файл с промптом возврата (UTF-8)")
    p.add_argument("--date", type=_iso_date, help="YYYY-MM-DD в decision.date и notes[].date; по умолчанию сегодня")
    p.add_argument("--dry-run", action="store_true", help="показать отчёт, JSON не записывать")
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser("apply-md4h", help="внести комментарии человека из связки md4h к рендеру в comments[] JSON",
                       description="Порядок: render-md -> человек комментирует рендер в Markdown Editor for "
                                   "Humans (md4h) -> apply-md4h -> агент действует по comments[] записей. "
                                   "Комментарий попадает в запись по ближайшему якорю журнала выше его "
                                   "первой строки. Связка должна быть запечатана (state: sealed), а SHA-256 "
                                   "рендера (--render) — совпасть с source_sha256 связки; иначе отказ, код 2, "
                                   "JSON не меняется. Всё или ничего; повтор той же связки ничего не меняет. "
                                   "Негодный журнал или нечитаемая связка — код 1. "
                                   "apply-md4h не рендерит: ни markdown, ни HTML.")
    p.add_argument("json", type=Path)
    p.add_argument("feedback", type=Path, help="feedback.md связки md4h (md4h-feedback/v2, UTF-8)")
    p.add_argument("--render", type=Path, required=True,
                   help="отрендеренный markdown, к которому писались комментарии (сверяется SHA-256)")
    p.set_defaults(func=cmd_apply_md4h)
    p = sub.add_parser("render-md", help="JSON -> markdown (производный файл); негодный журнал — код 1")
    p.add_argument("json", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_render_md)
    p = sub.add_parser("render-html", help="JSON -> просмотрщик; улики сверяются в памяти; "
                                           "негодный журнал — код 1; битый файл атаки — код 2")
    p.add_argument("json", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--roots", type=Path, help="файл корней вместо tools/journal-roots.json")
    p.add_argument("--template", type=Path, default=TEMPLATE_PATH,
                   help="по умолчанию tools/playground-template.html")
    p.add_argument("--attack", type=Path, action="append",
                   help="файл атаки для режима «атака» (attack/decisions.md, attack/artifacts.md); повторяемый")
    p.set_defaults(func=cmd_render_html)
    p = sub.add_parser("render-design", help="JSON -> design.md (Decisions, Risks, Open Questions из журнала); "
                                             "негодный журнал — код 1")
    p.add_argument("json", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_render_design)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
