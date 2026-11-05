#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Граф трассируемости изменения OpenSpec (изменение `trace-graph`, F-39): требования, сценарии, решения журнала, задачи,
пункты security и ветки описи, связанные ссылками. Здесь пока каркас: пять подкоманд с `--help`, реестр артефактов схемы
и свой разбор спек (`parse_spec`, F-40); сборку, отчёт, проверку и заморозку добавят следующие порции.
Только стандартная библиотека."""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True  # как у соседних скриптов: `__pycache__` в проекте от инструментов не появляется (F-50)
from openspec_run import ForkError, check_change_name  # noqa: E402

# --- реестр артефактов (F-53, F-119, F-136) -----------------------------------
# Вложенный словарь, yaml-like: на каждый артефакт `openspec/schemas/symphysis/schema.yaml` строка, что граф из него берёт.
#   <id артефакта>:
#     берёт: список того, что граф берёт из артефакта, либо значение `ничего`
#     довод: причина, почему граф ничего не берёт; обязателен при `ничего`, при непустом списке не нужен
# Новый артефакт схемы без строки здесь даёт красный тест (`check_registry`); `ничего` с пустым доводом — тоже (F-119).
# Довод пишется о конкретном артефакте, общая отговорка не годится.
NOTHING = "ничего"

REGISTRY = {
    "intent": {
        "берёт": NOTHING,
        "довод": "intent.md — слова человека и критерии готовности без номеров и ссылок: узлу не за что зацепиться, "
                 "связь с требованиями граф видит через записи журнала",
    },
    "decisions": {"берёт": ["записи журнала"]},
    "research": {
        "берёт": NOTHING,
        "довод": "research/*.md — отчёты по парковкам: найденное из них уже внесено в записи журнала (second round), "
                 "а у самих отчётов нет ни номера узла, ни ссылки на требование",
    },
    "attack-decisions": {
        "берёт": NOTHING,
        "довод": "attack/decisions.md — вердикт и строки линз о журнале: это проверка узлов, а не узел; "
                 "необязательный артефакт, графа от него не зависит",
    },
    "proposal": {
        "берёт": NOTHING,
        "довод": "proposal.md — мотивация и список capabilities, которые граф берёт точнее из каталогов specs/; "
                 "ссылки F-NN в нём пересказ журнала, не новая связь",
    },
    "specs": {"берёт": ["требования", "сценарии", "capability"]},
    "consequences": {"берёт": ["ветки описи"]},
    "design": {
        "берёт": NOTHING,
        "довод": "design.md целиком рендерится из журнала (`render-design`): разделы F-NN повторяют записи, "
                 "а впечатанные руками Context и Goals / Non-Goals узлов не несут",
    },
    "security": {"берёт": ["пункты security"]},
    "tasks": {"берёт": ["задачи"]},
    "attack-artifacts": {
        "берёт": NOTHING,
        "довод": "attack/artifacts.md — вердикт и строки линз об артефактах: проверяет узлы графа, сам узлом не служит; "
                 "необязательный артефакт, вызывается по имени",
    },
}

ARTIFACT_ID = re.compile(r"^  - id:\s*(\S+)\s*$", re.MULTILINE)


def schema_artifacts(schema_path: Path | str) -> list[str]:
    """Идентификаторы артефактов из `schema.yaml` по порядку; без PyYAML: у схемы строка `  - id: <имя>` на артефакт."""
    return ARTIFACT_ID.findall(Path(schema_path).read_text(encoding="utf-8"))


def check_registry(schema_path: Path | str, registry: dict | None = None) -> list[str]:
    """Сверка реестра со схемой (F-53, F-119): список проблем, каждая называет артефакт; пустой список — всё сходится.
    Лишний артефакт схемы без строки, строка без артефакта схемы, `ничего` без довода, пустой список «берёт»."""
    registry = REGISTRY if registry is None else registry
    in_schema = schema_artifacts(schema_path)
    problems = [f"артефакт «{name}» есть в схеме, а строки реестра нет: решить, что граф из него берёт, "
                f"или записать `{NOTHING}` с доводом"
                for name in in_schema if name not in registry]
    problems += [f"строка реестра «{name}» без артефакта в схеме: убрать её или вернуть артефакт"
                 for name in registry if name not in in_schema]
    for name, row in registry.items():
        takes = row.get("берёт")
        if takes == NOTHING:
            if not str(row.get("довод", "")).strip():
                problems.append(f"у артефакта «{name}» значение `{NOTHING}` без довода: назвать, почему граф "
                                "из него ничего не берёт")
        elif not takes or isinstance(takes, str):
            problems.append(f"у артефакта «{name}» «берёт» не список и не `{NOTHING}`: назвать, что граф берёт")
    return problems


# --- разбор спек (F-40, F-85) -------------------------------------------------
# Правила повторяют разбор OpenSpec 1.15.0 (`src/core/parsers/`: `code-fence.ts`, `requirement-blocks.ts`,
# `requirement-text.ts`, `change-parser.ts`), чтобы счётчики совпадали, а не замысел. Расхождение ловит тест сверки с
# `openspec show --json` на фикстурах `tests/fixtures/trace/` (F-14, F-40). Что взято у OpenSpec:
#   - строки внутри блока кода (``` или ~~~, закрывает такой же маркер не короче открывающего) заголовками не считаются:
#     `### Requirement: x` в блоке кода не требование (F-85);
#   - дельта живёт только в секциях `## ADDED|MODIFIED|REMOVED|RENAMED Requirements`, регистр названия любой,
#     повторная секция читается так же, требование вне этих секций не считается;
#   - требование — `###Requirement: имя`, пробел после решёток необязателен, закрывающие решётки в имени отрезаются;
#   - сценарий — любой заголовок четвёртого уровня под требованием, а не только `#### Scenario:`; без тела
#     (ни строки до следующего заголовка) он не сценарий; посторонний заголовок третьего уровня внутри требования
#     обрывает его сценарии;
#   - REMOVED читается и заголовком `### Requirement:`, и строкой-маркером с таким заголовком (`-`, `*` или `+`).
# Номера строк с 1, как в редакторе; BOM и CRLF OpenSpec снимает до счёта, и разбор тоже.

@dataclass
class SpecScenario:
    name: str  # имя без `Scenario:` и закрывающих решёток
    line: int  # номер строки заголовка, с 1
    text: str  # тело сценария до следующего заголовка того же или высшего уровня, без краевых пробелов


@dataclass
class SpecRequirement:
    section: str  # секция дельты: `ADDED`, `MODIFIED` или `REMOVED`
    name: str  # имя без `Requirement:` и закрывающих решёток
    line: int  # номер строки заголовка, с 1
    text: str  # текст требования до первого заголовка; у записи REMOVED строкой-маркером пуст
    scenarios: list[SpecScenario] = field(default_factory=list)


@dataclass
class SpecRename:
    from_name: str  # старое имя из `FROM:`
    to_name: str  # новое имя из `TO:`
    line: int  # номер строки `FROM:`, с 1


@dataclass
class SpecParse:
    requirements: list[SpecRequirement] = field(default_factory=list)  # по порядку в файле
    renames: list[SpecRename] = field(default_factory=list)  # секция `RENAMED Requirements`: у переименования тела нет


DELTA_SECTIONS = {f"{op.lower()} requirements": op for op in ("ADDED", "MODIFIED", "REMOVED", "RENAMED")}
_FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})")
_FENCE_CLOSE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")
_REQ_HEADER = re.compile(r"^###\s*Requirement:\s*(.+)\s*$", re.IGNORECASE)
_REMOVED_BULLET = re.compile(r"^\s*[-*+]\s*`?###\s*Requirement:\s*(.+?)`?\s*$")
_RENAME_FROM = re.compile(r"^\s*[-*+]?\s*FROM:\s*`?###\s*Requirement:\s*(.+?)`?\s*$")
_RENAME_TO = re.compile(r"^\s*[-*+]?\s*TO:\s*`?###\s*Requirement:\s*(.+?)`?\s*$")
_SECTION_HEADER = re.compile(r"^##\s+(.+)$")
_ANY_HEADER = re.compile(r"^(#{1,6})\s+(.+)$")
_META_LINE = re.compile(r"^\*\*[^*]+\*\*:")


def _fence_mask(lines: list[str]) -> list[bool]:
    """Строки внутри блока кода, вместе с открывающей и закрывающей, как `buildCodeFenceMask` у OpenSpec."""
    mask, active = [False] * len(lines), None
    for i, line in enumerate(lines):
        if active is None:
            opened = _FENCE_OPEN.match(line)
            if opened:
                active, mask[i] = opened.group(1), True
            continue
        mask[i] = True
        closed = _FENCE_CLOSE.match(line)
        if closed and closed.group(1)[0] == active[0] and len(closed.group(1)) >= len(active):
            active = None
    return mask


def _unclose(name: str) -> str:
    """Имя без закрывающих решёток заголовка: их отрезают только после пробела или табуляции (`C#` остаётся)."""
    return re.sub(r"[ \t]+#+[ \t]*$", "", name).strip()


def _scenarios(lines: list[str], mask: list[bool], first: int, last: int) -> list[SpecScenario]:
    """Сценарии требования с заголовком в строке `first` и телом до `last` (не включая): дети его заголовка в дереве
    заголовков, как у `parseSectionsFromContent` OpenSpec; заголовок без тела не сценарий."""
    heads = [(i, len(m.group(1))) for i in range(first + 1, last)
             if not mask[i] and (m := _ANY_HEADER.match(lines[i]))]
    stack, kids = [3], []  # заголовок требования — третьего уровня, и для `###Requirement:` тоже
    for pos, (i, level) in enumerate(heads):
        while stack and stack[-1] >= level:
            stack.pop()
        if not stack:  # заголовок не ниже требования: оно закончилось, дальше чужие заголовки
            break
        if len(stack) == 1:  # родитель — само требование
            kids.append((i, next((j for j, lv in heads[pos + 1:] if lv <= level), last)))
        stack.append(level)
    result = []
    for i, end in kids:
        text = "\n".join(lines[i + 1:end]).strip()
        if text:
            title = _ANY_HEADER.match(lines[i]).group(2).strip()
            name = re.sub(r"^Scenario:\s*", "", re.sub(r"[ \t]+#+[ \t]*$", "", title), flags=re.IGNORECASE).strip()
            result.append(SpecScenario(name, i + 1, text))
    return result


def _requirement_text(lines: list[str], mask: list[bool], first: int, last: int, title: str) -> str:
    """Текст требования как `extractRequirementText`: строки до первого заголовка вне блока кода, без пустых; строки
    вида `**ID**: …` берутся, только если другого текста нет; пусто — заголовок целиком."""
    captured, meta = [], []
    for i in range(first + 1, last):
        if mask[i]:
            continue
        if re.match(r"^#{1,6}\s", lines[i]):
            break
        line = lines[i].strip()
        if line:
            (meta if _META_LINE.match(line) else captured).append(line)
    return "\n".join(captured or meta) or title.strip()


def _requirement(op: str, lines: list[str], mask: list[bool], first: int, last: int) -> SpecRequirement:
    """Требование из блока: заголовок в строке `first`, тело до строки `last` (не включая)."""
    title = re.sub(r"^###\s*", "", lines[first]).strip()  # `Requirement: имя`; так OpenSpec читает и `###Requirement:`
    name = _unclose(re.sub(r"^Requirement:\s*", "", title, flags=re.IGNORECASE))
    return SpecRequirement(op, name, first + 1, _requirement_text(lines, mask, first, last, title),
                           _scenarios(lines, mask, first, last))


def _section_requirements(op: str, lines: list[str], mask: list[bool], start: int, end: int) -> list[SpecRequirement]:
    """Требования одной секции: блок от заголовка до следующего заголовка требования; в REMOVED ещё строки-маркеры."""
    heads = [i for i in range(start, end) if not mask[i] and _REQ_HEADER.match(lines[i])]
    block_end = {head: (heads[k + 1] if k + 1 < len(heads) else end) for k, head in enumerate(heads)}
    found = []
    for i in range(start, end):
        if mask[i]:
            continue
        if i in block_end:
            found.append(_requirement(op, lines, mask, i, block_end[i]))
        elif op == "REMOVED" and (bullet := _REMOVED_BULLET.match(lines[i])):
            found.append(SpecRequirement(op, _unclose(bullet.group(1)), i + 1, ""))
    return found


def _renames(lines: list[str], mask: list[bool], start: int, end: int) -> list[SpecRename]:
    """Пары `FROM:` и `TO:` одной секции; непарные строки OpenSpec называет в `validate`, здесь они пропускаются."""
    pairs, pending = [], None
    for i in range(start, end):
        if mask[i]:
            continue
        if m := _RENAME_FROM.match(lines[i]):
            pending = (_unclose(m.group(1)), i + 1)
        elif (m := _RENAME_TO.match(lines[i])) and pending:
            pairs.append(SpecRename(pending[0], _unclose(m.group(1)), pending[1]))
            pending = None
    return pairs


def parse_spec(source: str | Path) -> SpecParse:
    """Разбор одной спеки (F-40): `Path` — файл `spec.md`, `str` — его текст. Даёт требования секций `ADDED`, `MODIFIED`,
    `REMOVED` в порядке файла (имя, номер строки заголовка, текст, сценарии с именем, строкой и текстом) и пары
    переименований секции `RENAMED`. Текст без секций дельты даёт пустой разбор. Правила — как у OpenSpec (см. выше)."""
    text = Path(source).read_bytes().decode("utf-8") if isinstance(source, Path) else source
    lines = re.sub(r"\r\n?", "\n", text.removeprefix("﻿")).split("\n")
    mask = _fence_mask(lines)
    heads = [(i, m.group(1).strip()) for i, line in enumerate(lines)
             if not mask[i] and (m := _SECTION_HEADER.match(line))]
    parsed = SpecParse()
    for pos, (start, title) in enumerate(heads):
        op = DELTA_SECTIONS.get(title.lower())
        end = heads[pos + 1][0] if pos + 1 < len(heads) else len(lines)
        if op == "RENAMED":
            parsed.renames += _renames(lines, mask, start + 1, end)
        elif op:
            parsed.requirements += _section_requirements(op, lines, mask, start + 1, end)
    return parsed


# --- командная строка ---------------------------------------------------------

def find_root(start: Path) -> Path:
    """Корень проекта — ближайший `openspec/` от каталога вызова, как у `step_help.py` и у форка."""
    return next((folder for folder in (start, *start.parents) if (folder / "openspec").is_dir()), start)


class Refusal(Exception):
    """Отказ подкоманды: текст идёт в stderr, код выхода 1, без трассировки."""


def _not_implemented(name: str) -> Refusal:
    return Refusal(f"подкоманда `{name}` ещё не реализована: это каркас, обработчик добавит следующая порция")


def cmd_build(args: argparse.Namespace, root: Path) -> int:
    raise _not_implemented("build")


def cmd_report(args: argparse.Namespace, root: Path) -> int:
    raise _not_implemented("report")


def cmd_check(args: argparse.Namespace, root: Path) -> int:
    raise _not_implemented("check")


def cmd_freeze(args: argparse.Namespace, root: Path) -> int:
    raise _not_implemented("freeze")


def cmd_archive_gaps(args: argparse.Namespace, root: Path) -> int:
    raise _not_implemented("archive-gaps")


HANDLERS = {"build": cmd_build, "report": cmd_report, "check": cmd_check, "freeze": cmd_freeze,
            "archive-gaps": cmd_archive_gaps}

# Подкоманда: (что делает, когда звать, коды). Правило `tests/test_flag_help.py`: «Звать, когда» и «Коды:».
SUBCOMMAND_HELP = {
    "build": ("Собирает граф трассируемости изменения из его артефактов и печатает его, файлов не пишет.",
              "Звать, когда нужен живой граф: перед отчётом, при разборе связей, в атаке артефактов.",
              "Коды: 0 — граф собран; 1 — отказ: имя изменения не подходит или подкоманда ещё не реализована; "
              "2 — вызов неверен."),
    "report": ("Печатает отчёт по графу изменения: сигналы о разрывах связей.",
               "Звать, когда нужен список разрывов человеку; отчёт отдаётся ссылкой, модель его не читает.",
               "Коды: 0 — отчёт напечатан, сигналы кода не меняют (F-31); 1 — отказ: имя изменения не подходит "
               "или подкоманда ещё не реализована; 2 — вызов неверен."),
    "check": ("Проверяет граф изменения: собирается ли он и сходятся ли связи, и сообщает сигналами.",
              "Звать, когда нужна проверка перед архивом или после правки артефактов.",
              "Коды: 0 — проверка прошла, сигнал кода не меняет (F-31); 1 — отказ: имя изменения не подходит "
              "или подкоманда ещё не реализована; 2 — вызов неверен."),
    "freeze": ("Замораживает снимок графа в каталоге graph изменения: собирает, если снимка нет, он неполон или устарел, "
               "иначе обновляет коммиты (F-139).",
               "Звать, когда изменение готово к архиву; одну команду, без выбора между сборкой и обновлением.",
               "Коды: 0 — снимок лежит в graph; 1 — отказ: имя изменения не подходит, сборка не удалась "
               "или подкоманда ещё не реализована; 2 — вызов неверен."),
    "archive-gaps": ("Ищет в каталоге архива изменения без снимка графа.",
                     "Звать, когда нужно понять, какие архивные изменения заморожены без графа.",
                     "Коды: 0 — перечень напечатан; 1 — отказ: каталога нет или подкоманда ещё не реализована; "
                     "2 — вызов неверен."),
}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="trace_graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Граф трассируемости изменения OpenSpec: требования, сценарии, решения журнала, задачи, пункты security "
                    "и ветки описи.\n"
                    "Область — расчёт и заморозка графа изменения; артефакты изменения не правит, решений за человека не "
                    "принимает.\n"
                    "Звать, когда нужно увидеть, чем держится каждое требование изменения, или заморозить граф перед архивом. "
                    "Вместо\n"
                    "проверки схемы не звать: сверку улик делает `journal.py check`.",
        epilog="Порядок: корень проекта — ближайший каталог с openspec/ от текущего; имя изменения проверяется до любого "
               "пути и вызова.\n"
               "Коды: 0 — выполнено; 1 — отказ, текст в stderr, без трассировки; 2 — вызов неверен. "
               "Сигнал кода выхода не меняет (F-31).\n"
               "Маркеры: их нет, вывод только текст подкоманды; отказ — строка в stderr.")
    sub = ap.add_subparsers(dest="command", required=True, metavar="ПОДКОМАНДА")
    for name, (what, when, codes) in SUBCOMMAND_HELP.items():
        sp = sub.add_parser(name, formatter_class=argparse.RawDescriptionHelpFormatter, help=what,
                            description=f"{what}\n{when}\n{codes}")
        if name == "archive-gaps":
            sp.add_argument("archive", metavar="КАТАЛОГ", type=Path, help="каталог архива изменений")
        else:
            sp.add_argument("change", metavar="ИЗМЕНЕНИЕ", help="имя изменения, как у `openspec validate <имя>`")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command != "archive-gaps":
            check_change_name(args.change)  # до любого пути и вызова (F-59)
        return HANDLERS[args.command](args, find_root(Path.cwd()))
    except (ForkError, Refusal) as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
