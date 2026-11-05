#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Граф трассируемости изменения OpenSpec (изменение `trace-graph`, F-39): требования, сценарии, решения журнала, задачи,
пункты security и ветки описи, связанные ссылками. Здесь пока каркас: пять подкоманд с `--help` и реестр артефактов схемы;
сборку, отчёт, проверку и заморозку добавят следующие порции. Только стандартная библиотека."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from openspec_run import ForkError, check_change_name

sys.dont_write_bytecode = True  # как у соседних скриптов: `__pycache__` в проекте от инструментов не появляется (F-50)

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
