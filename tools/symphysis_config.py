#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Настройки symphysis: состав выбора из личного файла `symphysis.yaml` в корне проекта.

Журнал этот модуль не импортирует и настройки не читает (F-128.A). Файл читается пакетом PyYAML,
значения приходят текстом и сравниваются с `true` и `false` дословно (F-110.B, F-113); это единственный
читатель файла, `symphysis config` и `symphysis check` зовут этот скрипт (F-135.B).
Сомнение решается во включённую сторону сигналом, а не остановкой (F-24.A, F-25.A)."""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from journal_apply import default_roots
from journal_model import ROOT

__all__ = ["Settings", "read_settings", "composition_line", "build_parser", "main"]

FILE_NAME = "symphysis.yaml"
SIGNAL_UNPARSED = f"{FILE_NAME}: не разбирается"
SIGNAL_NOT_UTF8 = f"{FILE_NAME}: не UTF-8"
SIGNAL_NO_PACKAGE = f"{FILE_NAME}: нет пакета PyYAML — выполнить: python -m pip install pyyaml"

# Группа -> вложенный ключ -> поле `Settings`.
KEYS = {
    "consequences": {"failure_branches": "failure_branches", "assumptions": "assumptions"},
    "edge_probe": {"enabled": "edge_probe"},
}

@dataclass
class Settings:
    failure_branches: bool = True
    assumptions: bool = True
    edge_probe: bool = True
    signals: list[str] = field(default_factory=list)


def _show(value) -> str:
    """Значение в строке сигнала: текст как есть в одну строку, составное — словом."""
    if isinstance(value, str):
        return re.sub(r"\s*\n\s*", " ", value).strip(" ")
    return "составное"


def _apply(data, settings: Settings) -> None:
    """Разобранный файл -> поля и сигналы. Пустой корень равен пустому файлу, пустое значение —
    отсутствию ключа (F-50.C, F-109.A)."""
    if data is None or data == "":
        return
    if not isinstance(data, dict):
        settings.signals.append(SIGNAL_UNPARSED)
        return
    for group, inner in data.items():
        fields = KEYS.get(group)
        if fields is None:
            settings.signals.append(f"{FILE_NAME}: неизвестный ключ {group}")
        elif inner == "":
            continue
        elif not isinstance(inner, dict):
            settings.signals.append(f"{FILE_NAME}: {group} — нужен вложенный ключ")
        else:
            for key, value in inner.items():
                if key not in fields:
                    settings.signals.append(f"{FILE_NAME}: неизвестный ключ {group}.{key}")
                elif value == "false":
                    setattr(settings, fields[key], False)
                elif value not in ("true", ""):
                    settings.signals.append(f"{FILE_NAME}: недопустимое значение {_show(value)}")


def read_settings(project_root: Path | str) -> Settings:
    """Состав из `<project_root>/symphysis.yaml`. Нет файла — всё включено без сигнала; нет пакета,
    не UTF-8, файл не разбирается — всё включено и сигнал. Пакет импортируется только здесь и только
    при наличии файла: без него команды журнала и этот модуль работают как прежде (F-113)."""
    settings = Settings()
    path = Path(project_root) / FILE_NAME
    if not path.is_file():
        return settings
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        settings.signals.append(SIGNAL_NOT_UTF8)
        return settings
    except OSError:
        settings.signals.append(SIGNAL_UNPARSED)
        return settings
    try:
        import yaml
    except ImportError:
        settings.signals.append(SIGNAL_NO_PACKAGE)
        return settings
    try:
        # BaseLoader не разбирает типы и не исполняет теги: `no` остаётся строкой (research/F-110.md).
        data = yaml.load(text, Loader=yaml.BaseLoader)
    except (yaml.YAMLError, RecursionError):
        settings.signals.append(SIGNAL_UNPARSED)
        return settings
    _apply(data, settings)
    return settings


def composition_line(settings: Settings) -> str:
    """Строка состава: та же у `symphysis config` и в `symphysis check`."""
    on = lambda value: "вкл" if value else "выкл"
    return (f"{FILE_NAME}: ветки отказа {on(settings.failure_branches)}, допущения {on(settings.assumptions)}, "
            f"проба краёв {on(settings.edge_probe)}")


def _default_project() -> Path:
    """Корень проекта без параметра: пустой префикс файла корней (у установленной копии это проект
    над `.symphysis/`), иначе каталог над `tools/`."""
    try:
        return default_roots().get("", ROOT)
    except (OSError, ValueError):
        return ROOT


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="symphysis_config",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Состав выбора из symphysis.yaml: ветки отказа, допущения, проба краёв.\n"
                    "Звать, когда шаг начинается и ему нужен состав: скилл зовёт скрипт, файл сам не разбирает\n"
                    "и человека о составе не спрашивает; правка файла действует со следующего запуска шага.",
        epilog="Порядок: один вызов в начале шага, дальше шаг идёт по напечатанному составу.\n"
               "Исходы: файла нет или пустое значение — всё включено без сигнала; значение не из true и false,\n"
               "  неизвестный ключ, плоская запись, файл не разбирается, не UTF-8, нет пакета PyYAML — выбор\n"
               "  считается включённым и есть сигнал. Человеку тот же вывод даёт symphysis config.\n"
               "Коды: 0 — состав напечатан, сигналы код не меняют; 2 — с --strict есть сигналы, либо вызов неверен.\n"
               "Маркеры: [..] строка состава, исходом не является; [!!] сигнал.")
    general = ap.add_argument_group("общие")
    general.add_argument("--project", type=Path, metavar="ПУТЬ",
                         help="корень проекта; без него — проект над .symphysis/")
    result = ap.add_argument_group("исход")
    result.add_argument("--strict", action="store_true", help="код 2, если есть сигналы")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.project is not None and not args.project.is_dir():
        ap.error(f"--project: каталога нет: {args.project}")
    settings = read_settings(args.project if args.project is not None else _default_project())
    print(f"[..] {composition_line(settings)}")
    for signal in settings.signals:
        print(f"[!!] {signal}")
    return 2 if args.strict and settings.signals else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
