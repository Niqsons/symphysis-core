# -*- coding: utf-8 -*-
"""Журнал решений symphysis: источник — JSON, markdown и HTML — рендер (F-01.B).

Командная строка: подкоманды `cmd_*`, `build_parser`, `main`. Первая строка этого докстринга —
описание парсера в `--help` (`build_parser` берёт его из `__doc__`); она совпадает с первой
строкой докстринга `journal.py`, где описаны подкоманды, корни улик и коды выхода."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import sys
from pathlib import Path

from attack_scope import scope_lines
from attack_table import parse_attack_md
from journal_apply import REFUSED, apply_answers, apply_md4h, check_evidence, parse_answers, parse_md4h, sha256_file
from journal_consequences import check_consequences
from journal_model import dependency_cycles, import_md, load_journal, save_journal, unexplained_choices, validate_journal
from journal_render import render_design, render_md, view_payload
from journal_sites import code_sites
from roots import change_of as _change_of, default_roots, file_links, project_href
from viewer_render import TEMPLATE_PATH, no_help_snapshot, render_html, scheme_payload

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
    """Парковка «агент» без `finding` при файле `research/<F-NN>.md` рядом с журналом —
    сигнал: исследование есть, находка в журнал не внесена."""
    return [f"{rec['id']}: парковка «агент» без finding при research/{rec['id']}.md"
            for rec in journal["records"]
            if (base / "research" / f"{rec['id']}.md").is_file()
            and any(p["addressee"] == "агент" and not p.get("finding") for p in rec["parking"])]


def _human_parkings_without_finding(journal: dict) -> list[str]:
    """Парковка «человек» без `finding` — сигнал: у «агента» и «ИБ» есть свои шаги, а у этого адресата нет,
    и без сигнала вопрос так и остался бы строкой в Open Questions."""
    return [f"{rec['id']}: парковка «человек» без finding: {p['text']}"
            for rec in journal["records"] for p in rec["parking"]
            if p["addressee"] == "человек" and not p.get("finding")]


LEGACY_ADDRESSEE = "материалы"   # имя адресата «агент» до переименования: схема читает, новые записи не пишут


def _legacy_addressees(journal: dict) -> list[str]:
    """Старое значение адресата «материалы» у записи или у её парковки — сигнал, не ошибка схемы: у старых журналов
    (архив, журнал плана) оно законно, в журнале активного изменения запись переписывается на «агент»
    (parking-addressee-agent: F-22). Одна строка на запись; сравнение точное, без нормализации."""
    return [f"{rec['id']}: адресат «{LEGACY_ADDRESSEE}» — старое значение, новые записи пишут «агент»"
            for rec in journal["records"]
            if rec["addressee"] == LEGACY_ADDRESSEE or any(p["addressee"] == LEGACY_ADDRESSEE for p in rec["parking"])]


def cmd_check(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    roots = default_roots(args.roots, args.json)
    result = check_evidence(journal, roots)
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
    unasked = _human_parkings_without_finding(journal)
    for m in unasked:
        print(f"[!!] {m}")
    legacy = _legacy_addressees(journal)
    for m in legacy:
        print(f"[!!] {m}")
    unexplained = unexplained_choices(journal)
    for m in unexplained:
        print(f"[!!] {m}")
    cycles = dependency_cycles(journal)
    for m in cycles:
        print(f"[!!] {m}")
    inventory = check_consequences(journal, args.json.parent / "consequences.md", roots)
    for m in inventory["missing"]:
        print(f"[!!] {m}")
    for m in inventory["unchecked"]:
        print(f"[--] {m}")
    scope, broken_attack = _scope_report(args.json.parent)
    for m in scope:
        print(m)
    if args.write:
        save_journal(args.json, journal)
        print(f"[ok] {args.json}")
    return 2 if args.strict and (result["missing"] or unfound or unasked or legacy or unexplained or cycles
                                 or inventory["missing"] or broken_attack) else 0


ATTACK_FILES = (("decisions.md", "атака журнала"), ("artifacts.md", "атака артефактов"))


def _scope_report(change: Path) -> tuple[list[str], bool]:
    """Состав устаревшего вердикта по файлам атаки рядом с журналом (`stale-verdict-scope`, F-19): строки
    `[..] атака журнала: …` и `[..] атака артефактов: …` — сведения, код выхода они не меняют; при совпавших хешах
    строк нет. Файл есть, а не разбирается — `[!!] attack/<файл>: файл атаки не разбирается: <причина>` без пути
    к файлу (F-30), второй элемент `True`: с `--strict` это код 2. Каталога `attack/` или файла нет — ничего."""
    lines, broken = [], False
    for name, label in ATTACK_FILES:
        path = change / "attack" / name
        if not path.is_file():
            continue
        att, refusal = _read_attack(path)
        if att is None:
            reason = refusal[len(str(path)):].lstrip(":").strip() if refusal.startswith(str(path)) else refusal
            lines.append(f"[!!] attack/{name}: файл атаки не разбирается: {reason}")
            broken = True
            continue
        lines += [f"[..] {label}: {line}" for line in scope_lines(att, change)]
    return lines, broken


def cmd_code_sites(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    result = code_sites(journal, default_roots(args.roots, args.json))
    print(f"[ok] мест кода {len(result['sites'])}")
    for path, ids in result["sites"].items():
        print(f"  {path} — {', '.join(ids)}")
    for note in result["notes"]:
        print(f"[..] {note}")
    return 0


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


def _read_attack(path: Path) -> tuple[dict | None, str]:
    """Файл атаки: `(разбор, "")` или `(None, текст отказа)`."""
    if not path.is_file():
        return None, f"{path}: файла нет"
    try:
        return parse_attack_md(path), ""
    except UnicodeDecodeError:  # подкласс ValueError — раньше него
        return None, f"{path}: не UTF-8 — файл атаки читается как UTF-8"
    except ValueError as e:
        return None, str(e)


def _from_root(path: Path | str, root: Path) -> str:
    """Путь для команды, выполняемой из корня: без абсолютного пути, прямыми слешами (F-51). Другой диск — только имя файла."""
    try:
        return os.path.relpath(os.path.abspath(path), root).replace("\\", "/")
    except ValueError:
        return Path(path).name


def _attack_path(path: Path | str, journal_path: Path | str) -> str:
    """Поле `path` атаки на странице и в `view-json`: от корня проекта, с «/» на любой системе (F-72). Корень — из пути журнала,
    журнал вне `openspec/changes/` считается от каталога вызова. Сообщения об ошибках чтения называют файл как поданный."""
    where = _change_of(Path(journal_path))
    return _from_root(path, where[0] if where else Path.cwd())


def _shell_word(word: str) -> str:
    """Слово команды для вставки в терминал. `shlex.join` ставит одинарные кавычки, `cmd` их не читает; двойные читают
    PowerShell, bash и `cmd`. Простое слово идёт как есть. Слово с символом, что и в двойных кавычках что-то значит
    (`$`, обратная кавычка, обратная косая, `!`, `%`; `&`, `|`, `<`, `>`, `^` в двойных безопасны), остаётся за `shlex.quote`: путь с ним редок, а молча неверная команда хуже."""
    if re.fullmatch(r"[\w./:@+=,-]+", word):
        return word
    if re.search(r'[\\"$`!%]', word):
        return shlex.quote(word)
    return f'"{word}"'


def _rebuild_command(args: argparse.Namespace, root: Path) -> str:
    """Команда, которая из корня проекта соберёт эту же страницу заново: `--out` и `--attack` этой сборки (F-67)."""
    script = _from_root(os.path.join(os.path.dirname(os.path.abspath(__file__)), "journal.py"), root)
    if script.startswith("../") or "/" not in script:
        script = ".symphysis/tools/journal.py"  # инструменты вне проекта: в проекте они лежат здесь
    words = ["python", script, "render-html", _from_root(args.json, root), "--out", _from_root(args.out, root)]
    for path in args.attack or []:
        words += ["--attack", _from_root(path, root)]
    return " ".join(_shell_word(word) for word in words)


NO_HELP = "Справка не сформирована"


def _help_snapshot(args: argparse.Namespace) -> dict:
    """Снимок справки для страницы. Любой сбой расчёта идёт на панель и не меняет код выхода (F-34, F-61); текста исключения
    в причине нет: в нём бывает абсолютный путь (F-51). `step_help` импортируется здесь: без файла страница собирается (F-65)."""
    snapshot = _help_calculation(args)
    if snapshot["error"]:
        snapshot["error"] = f"{NO_HELP}: {snapshot['error']}"  # панель и сигнал `render-html` начинают одними словами (F-71)
    return snapshot


def _help_calculation(args: argparse.Namespace) -> dict:
    where = _change_of(args.json)
    if where is None:
        return no_help_snapshot("Журнал лежит вне openspec/changes/: проект и изменение по его пути не определить, "
                                "справка не считалась. Собери страницу из журнала активного изменения.")
    root, change = where
    try:
        import step_help
        snapshot = step_help.compute(root, change)
    except ImportError:
        snapshot = no_help_snapshot("Скрипта справки step_help.py нет рядом с инструментами или он не загрузился: "
                                    "обнови их командой symphysis install --force.")
    except Exception as e:
        snapshot = no_help_snapshot(f"Расчёт справки упал: {type(e).__name__}. Проверь step_help.py в терминале.")
    return {**snapshot, "rebuild": _rebuild_command(args, root)}


def cmd_render_html(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    # Атаки разбираются до рендера: битый файл атаки — код 2, HTML не пишется.
    attacks = []
    for path in args.attack or []:
        attack, refusal = _read_attack(path)
        if attack is None:
            print(f"[!!] {refusal}", file=sys.stderr)
            return 2
        attacks.append({**attack, "path": _attack_path(path, args.json)})
    # Сверка идёт в памяти: просмотрщик получает вердикты, файл журнала не меняется;
    # хеш журнала — по байтам файла на диске, как `sha256_file` у связки md4h.
    roots = default_roots(args.roots, args.json)
    result = check_evidence(journal, roots)
    snapshot = _help_snapshot(args)
    links = {"root": project_href(roots, args.out), "files": file_links(journal, roots, Path(args.json).parent, args.out, attacks, snapshot)}
    try:
        html = render_html(journal, args.template, attacks=attacks, journal_sha256=sha256_file(args.json),
                           scheme=scheme_payload(Path(args.json).parent / "scheme.md", args.out),
                           help_snapshot=snapshot, links=links)
    except ValueError as e:
        print(f"[!!] {e}", file=sys.stderr)
        return 1
    Path(args.out).write_text(html, encoding="utf-8", newline="\n")
    print(f"[ok] улик сверено {result['found']} из {result['total']}")
    for m in result["missing"]:
        print(f"[!!] не сверено — {m}")
    if snapshot["error"]:  # сигнал, не отказ: код выхода прежний (F-71)
        reason = " ".join(snapshot["error"][len(NO_HELP) + 2:].split())
        print(f"[..] {NO_HELP.lower()}: {reason}")
    print(f"[ok] {args.out}")
    return 0


def cmd_view_json(args: argparse.Namespace) -> int:
    journal = _valid_journal(args.json)
    if journal is None:
        return 1
    # Битый файл атаки журнал не прячет: атаку пишет агент, файл бывает недописан. Отказ — у своего файла.
    attacks = []
    for path in args.attack or []:
        attack, refusal = _read_attack(path)
        shown = _attack_path(path, args.json)
        attacks.append({**attack, "path": shown} if attack is not None else {"path": shown, "error": refusal})
    # Сверка идёт в памяти, файл журнала не меняется; хеш — по байтам файла, как у `render-html`.
    roots = default_roots(args.roots, args.json)
    check_evidence(journal, roots)
    payload = view_payload(journal, attacks=attacks, journal_sha256=sha256_file(args.json))
    # Карта для плагина (F-44): те же корни и тот же код, что у страницы, значение от корня проекта. Номер контракта прежний (F-35).
    payload["file_links"] = file_links(journal, roots, Path(args.json).parent, None, attacks, from_project=True)
    print(json.dumps(payload, ensure_ascii=False))
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


JOURNAL_HELP = "файл журнала decisions.json"
ROOTS_HELP = "файл корней вместо tools/journal-roots.json"

MAIN_EPILOG = """\
Порядок: журнал ведёт шаг decisions; check — после правки журнала или описи; после слова человека
  apply, затем render-md и render-html; code-sites — в начале шага consequences; render-design — на шаге design.
Исходы: check и code-sites — сигнал, не стоп; apply и apply-md4h — всё или ничего; рендеры пишут
  производные файлы, правится JSON. Корни путей улик — только tools/journal-roots.json.
Коды: 0 — шаг сделан; 1 — негодный журнал, нет или нечитаем вход, отказ apply; 2 — неверный вызов,
  check --strict при строках [!!], битый файл атаки у render-html, отказ связки у apply-md4h.
Маркеры: [ok] сделано; [!!] расхождение или отказ; [--] не проверить; [..] сведения, исходом не являются.
У каждой подкоманды своя справка: journal.py <подкоманда> --help."""


def _command(sub, name: str, line: str, subject: str, when: str, codes: str, extra: str = "") -> argparse.ArgumentParser:
    """Подкоманда по правилу справки: описание — предмет и строка «Звать, когда …», эпилог — исходы и коды.
    Коды только в эпилоге: написанные при части флагов, они читаются как разница в поведении."""
    return sub.add_parser(name, help=line, description=f"{subject}\nЗвать, когда {when}",
                          epilog=f"{extra}\nКоды: {codes}" if extra else f"Коды: {codes}",
                          formatter_class=argparse.RawDescriptionHelpFormatter)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="journal", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 description=__doc__.splitlines()[0] + "\nЗвать, когда ведётся журнал решений "
                                 "изменения: запись, сверка, слово человека, рендер.",
                                 epilog=MAIN_EPILOG)
    sub = ap.add_subparsers(dest="cmd", required=True, title="подкоманды")

    p = _command(sub, "import-md", "журнал в markdown -> JSON по схеме",
                 "Журнал в markdown -> JSON по схеме.",
                 "журнал есть только в markdown и нужен источник JSON.",
                 "0 — записан и годен; 1 — записан, но негоден по схеме: ошибки в stderr.")
    given = p.add_argument_group("вход")
    given.add_argument("md", type=Path, help="журнал в markdown")
    written = p.add_argument_group("выход")
    written.add_argument("--out", type=Path, required=True, help="куда записать JSON")
    p.set_defaults(func=cmd_import_md)

    p = _command(sub, "check", "сверить улики грепом по цитате (сигнал, не стоп); при consequences.md — и опись; "
                               "негодный по схеме журнал — код 1",
                 "Сверяет улики грепом по цитате, называет циклы в depends_on, парковки без finding и старое значение адресата «материалы». При consequences.md рядом с журналом — ещё две проверки описи:\n"
                 "место из code-sites названо путём в файле, цитата «путь:строка «цитата»» стоит в коде дословно.\n"
                 "Файл со строкой **Причина:** сверки мест не даёт; **Причина:** считается только в начале строки,\n"
                 "цитата сверяется только в форме путь:строка «цитата», форму файла сверх этого скрипт не разбирает.",
                 "журнал или опись правились и нужно увидеть, что их опоры стоят дословно.",
                 "0 — сверка прошла, сигналы код не меняют; 1 — нет файла, битый JSON или негодный по схеме журнал;\n"
                 "  2 — с --strict есть строки [!!].",
                 extra="Маркеры: [ok] итог сверки; [!!] несверенная улика, парковка без finding, выбор мимо рекомендации\n"
                       "  без слова, старое значение адресата «материалы», место или цитата описи;\n"
                       "  [--] не проверить: бинарный файл или не UTF-8.")
    given = p.add_argument_group("вход")
    given.add_argument("json", type=Path, help=JOURNAL_HELP)
    given.add_argument("--roots", type=Path, help=ROOTS_HELP)
    result = p.add_argument_group("исход")
    result.add_argument("--strict", action="store_true", help="код 2, если есть строки [!!]")
    result.add_argument("--write", action="store_true", help="сохранить line/found/verdict в JSON")
    p.set_defaults(func=cmd_check)

    p = _command(sub, "code-sites", "места кода из улик выбранных вариантов решённых развилок; журнал не меняется",
                 "Места кода: файлы из улик выбранных вариантов решённых развилок, кроме проб и фактов, с номерами\n"
                 "записей. Кодом считается всё, кроме .md и файлов каталогов изменений. Журнал не меняется, файлы\n"
                 "кода не читаются. Список предлагает, выбирает модель: дополняет его и исключает места с причиной.",
                 "начинается шаг consequences и нужно знать, что разбирать.",
                 "0 — список напечатан; 1 — нет файла, битый JSON или негодный по схеме журнал.",
                 extra="Маркеры: [ok] число мест, под ним строки «путь — номера записей»;\n"
                       "  [..] у выбранного варианта нет улик или путь вне корня: такого пути в списке нет.")
    given = p.add_argument_group("вход")
    given.add_argument("json", type=Path, help=JOURNAL_HELP)
    given.add_argument("--roots", type=Path, help=ROOTS_HELP)
    p.set_defaults(func=cmd_code_sites)

    p = _command(sub, "apply", "внести промпт возврата просмотрщика в JSON (потом render-md, render-html)",
                 "Вносит промпт возврата просмотрщика (кнопка «Скопировать промпт») в JSON журнала. Всё или ничего:\n"
                 "любая строка с отказом называет запись, журнал не меняется. apply не рендерит: после него\n"
                 "render-md и render-html. Слова человека сворачиваются в одну строку.",
                 "человек вернул промпт из просмотрщика и его слово надо внести в журнал.",
                 "0 — внесено или вносить нечего; 1 — негодный журнал, нет файла, не UTF-8, отказ по строке.")
    given = p.add_argument_group("вход")
    given.add_argument("json", type=Path, help=JOURNAL_HELP)
    given.add_argument("answers", type=Path, help="файл с промптом возврата (UTF-8)")
    given.add_argument("--date", type=_iso_date, help="YYYY-MM-DD в decision.date и notes[].date; по умолчанию сегодня")
    result = p.add_argument_group("исход")
    result.add_argument("--dry-run", action="store_true", help="показать отчёт, JSON не записывать")
    p.set_defaults(func=cmd_apply)

    p = _command(sub, "apply-md4h", "внести комментарии человека из связки md4h к рендеру в comments[] JSON",
                 "Порядок: render-md -> человек комментирует рендер в Markdown Editor for Humans (md4h) -> apply-md4h ->\n"
                 "агент действует по comments[] записей. Комментарий попадает в запись по ближайшему якорю журнала\n"
                 "выше его первой строки. Связка должна быть запечатана (state: sealed), а SHA-256 рендера (--render) —\n"
                 "совпасть с source_sha256 связки. Всё или ничего; повтор той же связки ничего не меняет.\n"
                 "apply-md4h не рендерит: ни markdown, ни HTML.",
                 "человек прокомментировал рендер журнала в md4h и связку надо внести в журнал.",
                 "0 — внесено; 1 — негодный журнал, нет файла или нечитаемая связка; 2 — связка не запечатана или\n"
                 "  не к этому рендеру, JSON не меняется.")
    given = p.add_argument_group("вход")
    given.add_argument("json", type=Path, help=JOURNAL_HELP)
    given.add_argument("feedback", type=Path, help="feedback.md связки md4h (md4h-feedback/v2, UTF-8)")
    given.add_argument("--render", type=Path, required=True,
                       help="отрендеренный markdown, к которому писались комментарии (сверяется SHA-256)")
    p.set_defaults(func=cmd_apply_md4h)

    p = _command(sub, "render-md", "JSON -> markdown (производный файл); негодный журнал — код 1",
                 "JSON -> markdown: производный файл, руками не правится.",
                 "журнал изменился и нужен его рендер: после apply или правки записи.",
                 "0 — записан; 1 — негодный журнал.")
    given = p.add_argument_group("вход")
    given.add_argument("json", type=Path, help=JOURNAL_HELP)
    written = p.add_argument_group("выход")
    written.add_argument("--out", type=Path, required=True, help="куда записать markdown")
    p.set_defaults(func=cmd_render_md)

    p = _command(sub, "render-html", "JSON -> просмотрщик; улики сверяются в памяти; "
                                     "негодный журнал — код 1; битый файл атаки — код 2",
                 "JSON -> просмотрщик: страница с вариантами и промптом возврата. Улики сверяются в памяти,\n"
                 "файл журнала не меняется. Страница несёт снимок справки о шаге от корня из пути журнала: новый снимок\n"
                 "даёт только новая сборка.",
                 "человек решает развилки или читает атаку в браузере: после круга брейншторма, пробы, атаки.",
                 "0 — записан, несверенные улики и сбой расчёта справки код не меняют, причину сбоя называет панель;\n"
                 "  1 — негодный журнал или шаблон; 2 — битый файл атаки, HTML не пишется.")
    given = p.add_argument_group("вход")
    given.add_argument("json", type=Path, help=JOURNAL_HELP)
    given.add_argument("--roots", type=Path, help=ROOTS_HELP)
    given.add_argument("--template", type=Path, default=TEMPLATE_PATH,
                       help="по умолчанию tools/playground-template.html")
    given.add_argument("--attack", type=Path, action="append",
                       help="файл атаки для режима «атака» (attack/decisions.md, attack/artifacts.md); повторяемый")
    written = p.add_argument_group("выход")
    written.add_argument("--out", type=Path, required=True, help="куда записать страницу")
    p.set_defaults(func=cmd_render_html)

    p = _command(sub, "view-json", "JSON журнала для показа вне страницы — на stdout; улики сверяются в памяти; "
                                   "негодный журнал — код 1; битый файл атаки — отказ у этого файла, код 0",
                 "JSON журнала для показа вне страницы — на stdout. Улики сверяются в памяти, файл не меняется.",
                 "журнал показывает не страница, а другой клиент: расширение VS Code.",
                 "0 — данные напечатаны, битый файл атаки — отказ у этого файла; 1 — негодный журнал.")
    given = p.add_argument_group("вход")
    given.add_argument("json", type=Path, help=JOURNAL_HELP)
    given.add_argument("--roots", type=Path, help=ROOTS_HELP)
    given.add_argument("--attack", type=Path, action="append",
                       help="файл атаки (attack/decisions.md, attack/artifacts.md); повторяемый")
    p.set_defaults(func=cmd_view_json)

    p = _command(sub, "render-design", "JSON -> design.md (Decisions, Risks, Open Questions из журнала); "
                                       "негодный журнал — код 1",
                 "JSON -> design.md: Decisions, Risks / Trade-offs и Open Questions из журнала.",
                 "идёт шаг design или журнал изменился после него.",
                 "0 — записан; 1 — негодный журнал.")
    given = p.add_argument_group("вход")
    given.add_argument("json", type=Path, help=JOURNAL_HELP)
    written = p.add_argument_group("выход")
    written.add_argument("--out", type=Path, required=True, help="куда записать design.md")
    p.set_defaults(func=cmd_render_design)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
