#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Настройки symphysis: состав выбора из личного файла `symphysis.yaml` в корне проекта.

Журнал этот модуль не импортирует и настройки не читает (F-128.A). Файл читается пакетом PyYAML,
значения приходят текстом и сравниваются с `true` и `false` дословно (F-110.B, F-113); это единственный
читатель файла, `symphysis config` и `symphysis check` зовут этот скрипт (F-135.B).
Сомнение решается во включённую сторону сигналом, а не остановкой (F-24.A, F-25.A).
Группа `drivers` — водители-субагенты (ревью скиллов 2026-11-05, Р11-A): у атаки и исследования умолчание
`true`, у проб и описи `false`; недопустимое значение оставляет умолчание ключа и даёт сигнал."""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Исходник ядра (F-20 A): код модулей лежит в соседних каталогах первого уровня, точка входа ставит нужные ей в `sys.path`.
# В установке весь код рядом в `.symphysis/tools/`: `roots.py` лежит возле этого файла, и путь не меняется.
_HERE = Path(__file__).resolve().parent
if not (_HERE / "roots.py").is_file():
    sys.path[1:1] = [str(_HERE.parent / "roots")]

from roots import ROOT, default_roots  # noqa: E402  (после правки sys.path)

__all__ = ["Settings", "read_settings", "composition_line", "lenses_line", "LENSES", "build_parser", "main"]

FILE_NAME = "symphysis.yaml"
SIGNAL_UNPARSED = f"{FILE_NAME}: не разбирается"
SIGNAL_NOT_UTF8 = f"{FILE_NAME}: не UTF-8"
SIGNAL_NO_PACKAGE = f"{FILE_NAME}: нет пакета PyYAML — выполнить: python -m pip install pyyaml"

# Линзы атаки обоих файлов: ключ группы `attack` равен слугу (F-132.A). `claim-extraction` стоит в обоих
# файлах и включается одним ключом (F-109.B). Порядок — порядок строки состава.
LENSES = ("context-compliance", "claim-authority", "claim-extraction", "coverage", "scenario-run", "trace-link",
          "rule-compliance")

# Группа -> вложенный ключ -> поле `Settings` (у линзы — её слуг в `Settings.lenses`).
KEYS = {
    "consequences": {"failure_branches": "failure_branches", "assumptions": "assumptions"},
    "edge_probe": {"enabled": "edge_probe"},
    "drivers": {"attack": "driver_attack", "probes": "driver_probes", "consequences": "driver_consequences",
                "research": "driver_research"},
    "attack": {slug: slug for slug in LENSES},
}

@dataclass
class Settings:
    failure_branches: bool = True
    assumptions: bool = True
    edge_probe: bool = True
    driver_attack: bool = True
    driver_probes: bool = False
    driver_consequences: bool = False
    driver_research: bool = True
    lenses: dict[str, bool] = field(default_factory=lambda: dict.fromkeys(LENSES, True))
    signals: list[str] = field(default_factory=list)


def _show(value) -> str:
    """Значение в строке сигнала: текст как есть в одну строку, составное — словом."""
    if isinstance(value, str):
        return re.sub(r"\s*\n\s*", " ", value).strip(" ")
    return "составное"


def _set(settings: Settings, name: str, flag: bool) -> None:
    """Поле `Settings` или линза в `Settings.lenses`: имя поля линзы — её слуг."""
    if name in LENSES:
        settings.lenses[name] = flag
    else:
        setattr(settings, name, flag)


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
                if key not in fields and group == "attack":
                    # Опечатка в слуге: линза работает, а человек считает её выключенной (F-108.A).
                    settings.signals.append(f"{FILE_NAME}: неизвестная линза {_show(key)}")
                elif key not in fields:
                    settings.signals.append(f"{FILE_NAME}: неизвестный ключ {group}.{key}")
                elif value in ("false", "true"):
                    _set(settings, fields[key], value == "true")
                elif value != "":
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
            f"проба краёв {on(settings.edge_probe)}, водители: атака {on(settings.driver_attack)}, "
            f"пробы {on(settings.driver_probes)}, опись {on(settings.driver_consequences)}, "
            f"исследование {on(settings.driver_research)}")


def lenses_line(settings: Settings) -> str:
    """Строка состава линз атаки: каждая линза названа включённой или выключенной, в порядке `LENSES`.
    Скилл атаки берёт из неё строку `**Состав:**` файла атаки (F-61.D, F-63.A). Прежняя строка состава
    не меняется: скиллы описи и пробы краёв читают её дословно."""
    on = lambda value: "вкл" if value else "выкл"
    return f"{FILE_NAME}: линзы атаки: " + ", ".join(f"{slug} {on(settings.lenses[slug])}" for slug in LENSES)


def _default_project() -> Path:
    """Корень проекта без параметра: пустой префикс файла корней (у установленной копии это проект
    над `.symphysis/`), иначе `ROOT` — каталог над каталогом кода."""
    try:
        return default_roots().get("", ROOT)
    except (OSError, ValueError):
        return ROOT


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="symphysis_config",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Состав выбора из symphysis.yaml: ветки отказа, допущения, проба краёв, водители, линзы атаки.\n"
                    "Звать, когда шаг начинается и ему нужен состав: скилл зовёт скрипт, файл сам не разбирает\n"
                    "и человека о составе не спрашивает; правка файла действует со следующего запуска шага.",
        epilog="Порядок: один вызов в начале шага, дальше шаг идёт по напечатанному составу.\n"
               "Умолчания: ветки отказа, допущения, проба краёв, водители атаки и исследования, линзы атаки — вкл;\n"
               "  водители проб и описи — выкл.\n"
               "Исходы: файла нет или пустое значение — умолчание ключа без сигнала; значение не из true и false,\n"
               "  неизвестный ключ или линза, плоская запись, файл не разбирается, не UTF-8, нет пакета PyYAML —\n"
               "  умолчание ключа и сигнал. Человеку тот же вывод даёт symphysis config.\n"
               "Коды: 0 — состав напечатан, сигналы код не меняют; 2 — с --strict есть сигналы, либо вызов неверен.\n"
               "Маркеры: [..] строки состава (выбор шага и линзы атаки), исходом не является; [!!] сигнал.")
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
    print(f"[..] {lenses_line(settings)}")
    for signal in settings.signals:
        print(f"[!!] {signal}")
    return 2 if args.strict and settings.signals else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
