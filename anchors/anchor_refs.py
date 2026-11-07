#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Якоря записей журнала в мастер-спеках (изменение `trace-numbers-signals`: F-22, F-24, F-35, F-65). После `/opsx:sync`
голые ссылки `F-NN` блоков требований изменения в `openspec/specs/<capability>/spec.md` переписываются в форму
`<изменение>/F-NN`, если F-NN — запись журнала этого изменения: мастер перестаёт копить голые номера, и следующее изменение
не спутает их со своими. Ссылки с именем или якорем, номера вне журнала и блоки других требований не трогаются; голая
ссылка, стоящая в базе снимка `graph/req-graph.json`, унаследована от прежнего изменения и остаётся голой (F-40).
Зовётся моделью по строке правила `rules.specs` и подсказке архива; печатает каждую замену; повторный запуск ничего не меняет.
Разбор ссылок — `trace_graph` (что граф читает как ссылку, то скрипт и переписывает, F-41), правило имени изменения —
`openspec_run`. Пишет только мастер-спеки под корнем проекта (F-49); каталог изменения только читает. Только стандартная
библиотека."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True  # как у соседних скриптов: `__pycache__` в проекте от инструментов не появляется
# Исходник ядра: код модулей лежит в соседних каталогах первого уровня, точка входа ставит нужные ей в `sys.path`.
# В установке весь код рядом в `.symphysis/tools/`: `trace_graph.py` лежит возле этого файла, и путь не меняется.
_HERE = Path(__file__).resolve().parent
if not (_HERE / "trace_graph.py").is_file():
    sys.path[1:1] = [str(_HERE.parent / name) for name in ("trace", "roots", "decisions", "openspec-run")]
from openspec_run import ForkError, SAFE_NAME, check_change_name  # noqa: E402
from trace_graph import (Ref, Refusal, _ANY_HEADER, _fence_mask, _read_text, _spec_lines, find_root, parse_ref,  # noqa: E402
                         parse_spec, record_ref_spans, ref_text, saved_base)

_MASTER_HEADER = re.compile(r"^## Requirements[ \t]*$")  # мастер пишет `## Requirements`, `parse_spec` читает секции дельты
_RECORD_ID = re.compile(r"F-(\d+)")
NOTHING = "Переписывать нечего: голых номеров журнала в блоках изменения нет."


@dataclass(frozen=True)
class Rewrite:
    """Одна замена: путь мастер-спеки от корня, строка с 1, ссылка как стояла и якорь, который встал вместо неё."""
    rel: str
    line: int
    old: str
    new: str

    def text(self) -> str:
        return f"{self.rel}:{self.line}: {self.old} → {self.new}"


def journal_numbers(base: Path) -> set[int]:
    """Числа записей `decisions.json` изменения. Нет файла, не JSON или не по форме — отказ: без журнала нечего переписывать."""
    try:
        records = json.loads(_read_text(base, "decisions.json"))["records"]
        ids = [rec["id"] for rec in records]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise Refusal(f"decisions.json изменения не прочитан или не по форме ({e}): мастер не тронут") from None
    return {int(m.group(1)) for rid in ids if isinstance(rid, str) and (m := _RECORD_ID.fullmatch(rid))}


def delta_requirements(base: Path) -> dict[str, dict[str, str]]:
    """Требования дельт по capability — блоки, которые мастер несёт после синхронизации: `{имя: секция}` для ADDED, MODIFIED
    и новых имён RENAMED (секция `RENAMED`); REMOVED не в счёте. Capability — имя каталога дельты."""
    found: dict[str, dict[str, str]] = {}
    specs = base / "specs"
    for folder in (sorted(p for p in specs.iterdir() if p.is_dir()) if specs.is_dir() else []):
        rel = f"specs/{folder.name}/spec.md"
        if not (base / rel).is_file():
            continue
        parsed = parse_spec(_read_text(base, rel))
        names = {r.name: r.section for r in parsed.requirements if r.section in ("ADDED", "MODIFIED")}
        names.update({r.to_name: "RENAMED" for r in parsed.renames})
        if names:
            found[folder.name] = names
    return found


def master_target(root: Path, cap: str) -> Path:
    """Путь мастер-спеки capability под корнем проекта (F-49, парковка F-55): имя не по правилу имени изменения или путь,
    выводящий за корень (ссылка каталога), — отказ до любой записи."""
    if not SAFE_NAME.fullmatch(cap):
        raise Refusal(f"имя capability «{cap}» не подходит: начало — буква, цифра или «_», дальше ещё «-» и точка; "
                      "мастер не тронут")
    target = root / "openspec" / "specs" / cap / "spec.md"
    if not target.resolve().is_relative_to(root.resolve()):
        raise Refusal(f"мастер-спека capability «{cap}» лежит за корнем проекта: мастер не тронут")
    return target


def block_ranges(lines: list[str], mask: list[bool], names: set[str]) -> list[tuple[str, int, int]]:
    """Блоки требований мастера с именами из `names`: `(имя, первая строка, за последней)`, индексы с 0. Блок — от заголовка
    `### Requirement:` до следующего заголовка не ниже третьего уровня вне блока кода; сценарии, маркеры и комментарии
    блока внутри."""
    parsed = parse_spec("\n".join(_MASTER_HEADER.sub("## ADDED Requirements", line) for line in lines))
    found = []
    for req in parsed.requirements:
        if req.name not in names:
            continue
        first = req.line - 1
        last = next((i for i in range(first + 1, len(lines))
                     if not mask[i] and (m := _ANY_HEADER.match(lines[i])) and len(m.group(1)) <= 3), len(lines))
        found.append((req.name, first, last))
    return found


def inherited_refs(base: Path) -> dict[str, dict[str, set[Ref]]]:
    """Голые ссылки базы снимка по capability и имени требования (F-40): они стояли в мастере до синхронизации, это номера
    прежнего журнала, и переписывать их нельзя. Снимка нет или он прежнего формата — база пуста."""
    found: dict[str, dict[str, set[Ref]]] = {}
    for cap, entries in saved_base(base).items():
        for name, entry in entries.items():
            refs = {ref for text in entry["numbers"] if (ref := parse_ref(text)) and ref.change is None}
            found.setdefault(cap, {})[name] = refs
    return found


def rewrite_lines(lines: list[str], mask: list[bool], blocks: list[tuple[str, int, int]], change: str, numbers: set[int],
                  inherited: dict[str, set[Ref]], rel: str) -> tuple[list[str], list[Rewrite]]:
    """Строки мастера с якорями вместо голых ссылок журнала в блоках `blocks` и список замен. Строки блоков кода и ссылки
    с именем не трогаются; ссылка из `inherited` требования остаётся голой; число приводится к виду id записи (`F-7` → `F-07`)."""
    out, done = list(lines), []
    for name, first, last in blocks:
        keep = inherited.get(name, set())
        for i in range(first, last):
            if mask[i]:
                continue
            line, pieces, pos = out[i], [], 0
            for ref, start, end in record_ref_spans(line):
                if ref.change is not None or ref.number not in numbers or Ref(None, ref.number, ref.letter) in keep:
                    continue
                anchor = ref_text(Ref(change, ref.number, ref.letter))
                pieces += [line[pos:start], anchor]
                pos = end
                done.append(Rewrite(rel, i + 1, line[start:end], anchor))
            if pos:
                out[i] = "".join(pieces) + line[pos:]
    return out, done


def _write_master(path: Path, text: str) -> None:
    """Запись через временный файл рядом и `os.replace`, как у снимка графа: обрыв не оставляет обрезанного файла под
    настоящим именем."""
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(text, encoding="utf-8", newline="")
        os.replace(temp, path)
    except OSError as e:
        temp.unlink(missing_ok=True)
        raise Refusal(f"{path.name} не записан: {e.strerror or e}") from e


def anchor_change(root: Path, change: str) -> list[str]:
    """Переписывает голые номера журнала изменения `change` в блоках его требований в мастер-спеках проекта `root` и отдаёт
    строки вывода: по строке на замену, строку о блоке без базы снимка и итог. Имя проверяется до любого пути; нет изменения
    или журнала — `Refusal`, мастер не тронут. Повторный запуск замен не находит."""
    check_change_name(change)
    base = root / "openspec" / "changes" / change
    if not base.is_dir():
        raise Refusal(f"изменения «{change}» нет: нет каталога openspec/changes/{change}")
    numbers = journal_numbers(base)
    inherited = inherited_refs(base)
    lines_out, total, files = [], 0, 0
    for cap, names in delta_requirements(base).items():
        target = master_target(root, cap)
        rel = f"openspec/specs/{cap}/spec.md"
        if not target.is_file():
            lines_out.append(f"{rel}: мастер-спеки нет, блоки изменения переносить ещё нечего")
            continue
        raw = _read_text(root, rel)
        lines = _spec_lines(raw)
        mask = _fence_mask(lines)
        blocks = block_ranges(lines, mask, set(names))
        rewritten, done = rewrite_lines(lines, mask, blocks, change, numbers, inherited.get(cap, {}), rel)
        for name, first, last in blocks:  # блок MODIFIED без записи базы: унаследованный голый номер не отличить от нового (F-40)
            if names[name] == "MODIFIED" and name not in inherited.get(cap, {}) and any(first < d.line <= last for d in done):
                lines_out.append(f"{rel}: у требования «{name}» нет записи базы снимка graph/req-graph.json — переписаны все "
                                 "голые номера журнала")
        lines_out += [d.text() for d in done]
        if done:
            newline = "\r\n" if "\r\n" in raw else "\n"
            bom = "﻿" if raw.startswith("﻿") else ""
            _write_master(target, bom + newline.join(rewritten) + (newline if raw.endswith(("\n", "\r\n")) else ""))
            total, files = total + len(done), files + 1
    lines_out.append(f"Переписано ссылок: {total}, файлов: {files}." if total else NOTHING)
    return lines_out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="anchor_refs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Якоря записей журнала в мастер-спеках: голые ссылки `F-NN` блоков требований изменения в "
                    "`openspec/specs/<capability>/spec.md` переписываются в `<изменение>/F-NN`, если F-NN — запись журнала "
                    "этого изменения. Ссылки с именем или якорем, номера вне журнала, блоки других требований и голые ссылки, "
                    "стоящие в базе снимка graph/req-graph.json (унаследованные от прежнего изменения), не трогаются.\n"
                    "Звать, когда блоки дельты перенесены в мастер: после `/opsx:sync` и при архивации до переноса каталога — "
                    "по строке правила `rules.specs` и подсказке архива; вывод показать человеку, ссылки руками не переписывать. "
                    "Повторный запуск ничего не меняет.",
        epilog="Порядок: корень проекта — ближайший каталог с openspec/ от текущего; имя изменения проверяется до любого "
               "пути; читаются дельты, журнал и снимок изменения, пишутся только мастер-спеки под корнем проекта, файлы "
               "изменения не меняются.\n"
               "Маркеры: строка `путь:строка: ссылка → якорь` на каждую замену; строка о требовании без записи базы снимка; "
               "итог «Переписано ссылок: N, файлов: M.» или «Переписывать нечего…»; отказ — строка в stderr.\n"
               "Коды: 0 — выполнено, и когда переписывать нечего; 1 — отказ, текст в stderr, без трассировки: имя изменения "
               "не подходит, изменения или журнала нет, файл не в UTF-8, мастер-спека за корнем проекта, запись не удалась; "
               "2 — вызов неверен.")
    ap.add_argument("change", metavar="ИЗМЕНЕНИЕ", help="имя изменения, как у `openspec validate <имя>`")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        check_change_name(args.change)  # до любого пути (F-59)
        for line in anchor_change(find_root(Path.cwd()), args.change):
            print(line)
        return 0
    except (ForkError, Refusal) as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
