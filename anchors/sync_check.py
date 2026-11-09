#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Повторяемая сверка дельт с мастером после sync. Только читает; семантические различия не решает за модель."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
_HERE = Path(__file__).resolve().parent
if not (_HERE / "trace_graph.py").is_file():
    sys.path[1:1] = [str(_HERE.parent / name) for name in ("trace", "roots", "decisions", "openspec-run")]
from openspec_run import ForkError, SAFE_NAME, check_change_name  # noqa: E402
from trace_graph import (Ref, Refusal, _ANY_HEADER, _fence_mask, find_root, parse_ref,  # noqa: E402
                         parse_spec, record_ref_spans, ref_text, saved_base)

_MASTER = re.compile(r"^## Requirements[ \t]*$", re.MULTILINE)
_DELTA = re.compile(r"^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements[ \t]*$", re.IGNORECASE)
_PROBES = ("проба краёв", "проба запретов")


def strip_probe_trails(text: str) -> str:
    """Удаляет только следы проб вне fenced-кода и образцов в двойных backticks."""
    lines = text.splitlines(keepends=True)
    mask = _fence_mask([line.rstrip("\r\n") for line in lines])
    starts, offset = [], 0
    for line in lines:
        starts.append(offset)
        offset += len(line)
    parts, cursor, search = [], 0, 0
    while (start := text.find("<!--", search)) >= 0:
        search = start + 4
        line = text.count("\n", 0, start)
        prefix = text[starts[line]:start]
        sample = prefix.count("``") % 2
        if mask[line] or sample:
            continue
        stop = text.find("-->", search)
        if stop < 0:
            break
        search = stop + 3
        if text[start + 4:stop].lstrip().startswith(_PROBES):
            parts += [text[cursor:start], "\n" * text[start:search].count("\n")]
            cursor = search
    return "".join(parts) + text[cursor:]


def _blocks(text: str, master=False) -> tuple[dict, list[str]]:
    text = strip_probe_trails(text)
    lines = text.splitlines()
    mask = _fence_mask(lines)
    parsed = parse_spec(_MASTER.sub("## ADDED Requirements", text) if master else text)
    blocks, duplicates = {}, []
    for req in parsed.requirements:
        if req.name in blocks:
            duplicates.append(req.name)
            continue
        start = req.line - 1
        end = next((i for i in range(start + 1, len(lines)) if not mask[i]
                    and (head := _ANY_HEADER.match(lines[i])) and len(head.group(1)) <= 3), len(lines))
        first_heading = next((i for i in range(start + 1, end) if not mask[i] and _ANY_HEADER.match(lines[i])), end)
        scenarios = {}
        for scenario in req.scenarios:
            stop = next((i for i in range(scenario.line, end) if not mask[i]
                         and (head := _ANY_HEADER.match(lines[i])) and len(head.group(1)) <= 4), end)
            if scenario.name in scenarios:
                duplicates.append(f"{req.name}: {scenario.name}")
            scenarios[scenario.name] = {"text": "\n".join(lines[scenario.line:stop]), "parsed": scenario.text,
                                        "canonical": lines[scenario.line - 1].startswith("#### Scenario: ")}
        blocks[req.name] = {"req": req, "text": "\n".join(lines[start + 1:first_heading]), "scenarios": scenarios,
                            "canonical": lines[start].startswith("### Requirement: ")}
    return blocks, duplicates


def _normalize(text: str, change: str, numbers: set[int], inherited: set[Ref], uncertain: bool,
               expected: bool) -> tuple[str, set[str], bool]:
    lines = text.splitlines()
    mask = _fence_mask(lines)
    normalized, references, review = [], set(), False
    for index, line in enumerate(lines):
        if mask[index]:
            normalized.append(line)
            continue
        parts, position = [], 0
        for ref, start, end in record_ref_spans(line):
            bare = Ref(None, ref.number, ref.letter)
            own = ref.change in (None, change) and ref.number in numbers
            if own and ref.change is None and bare in inherited:
                value = "legacy:" + ref_text(bare)
            elif own and ref.change == change and bare in inherited:
                value = "wrong-origin:" + ref_text(ref)
            elif own and uncertain:
                review = True
                value = "unverified:" + ref_text(bare)
            elif own:
                value = ("own:" if expected or ref.change == change else "unanchored:") + ref_text(bare)
            else:
                value = ref_text(ref)
            references.add(value)
            parts += [line[position:start], "[[" + value + "]]"]
            position = end
        parts.append(line[position:])
        normalized.append("".join(parts).strip())
    return "\n".join(line for line in normalized if line.strip()), references, review


def _purpose(text: str) -> str | None:
    lines, start = text.splitlines(), None
    mask = _fence_mask(lines)
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        if line == "## Purpose":
            start = i + 1
        elif start is not None and re.match(r"^#{1,2} ", line):
            return "\n".join(lines[start:i]).strip()
    return "\n".join(lines[start:]).strip() if start is not None else None


def check_sync(root: Path, change: str, *, capabilities: list[str] | None = None) -> dict:
    """Проверяет выбранные дельты; match/mismatch/review. Отсутствие базы само по себе не mismatch."""
    check_change_name(change)
    root = root.resolve()
    base = root / "openspec/changes" / change
    if not base.is_dir():
        raise Refusal(f"изменения «{change}» нет")
    deltas = {path.parent.relative_to(base / "specs").as_posix(): path
              for path in sorted((base / "specs").rglob("spec.md"))} if (base / "specs").is_dir() else {}
    selected = sorted(deltas if capabilities is None else set(capabilities))
    unknown = sorted(set(selected) - deltas.keys())
    if unknown:
        raise Refusal(f"capability нет в дельтах изменения: {', '.join(unknown)}")
    try:
        journal = json.loads((base / "decisions.json").read_text(encoding="utf-8-sig"))
        numbers = {int(record["id"][2:]) for record in journal["records"] if re.fullmatch(r"F-\d+", record["id"])}
    except (OSError, ValueError, KeyError, TypeError):
        raise Refusal("decisions.json не прочитан: происхождение своих ссылок не проверено") from None
    saved, findings = saved_base(base), []
    def note(level, cap, name, message):
        findings.append({"level": level, "capability": cap, "requirement": name, "message": message})
    for cap in selected:
        if not all(SAFE_NAME.fullmatch(part) for part in cap.split("/")):
            raise Refusal(f"неверное имя capability «{cap}»")
        target = root / "openspec/specs" / cap / "spec.md"
        if not target.resolve().is_relative_to(root) or not deltas[cap].resolve().is_relative_to(base.resolve()):
            raise Refusal(f"spec.md capability «{cap}» лежит за выбранным корнем")
        delta = deltas[cap].read_text(encoding="utf-8-sig")
        parsed = parse_spec(delta)
        if not parsed.requirements and not parsed.renames:
            note("mismatch", cap, "", "дельта не содержит операций")
            continue
        if not target.is_file():
            removed_only = bool(parsed.requirements) and all(r.section == "REMOVED" for r in parsed.requirements) and not parsed.renames
            note("review" if removed_only else "mismatch", cap, "", "мастера нет; сверить явный retire_capabilities: true" if removed_only else "мастер-спека отсутствует")
            continue
        main = target.read_text(encoding="utf-8-sig")
        main_lines = main.splitlines()
        main_mask = _fence_mask(main_lines)
        if any(_DELTA.match(line) for i, line in enumerate(main_lines) if not main_mask[i]):
            note("mismatch", cap, "", "в мастере остались заголовки дельты")
        if not any(line == "## Requirements" for i, line in enumerate(main_lines) if not main_mask[i]) or not _purpose(main):
            note("mismatch", cap, "", "мастер должен содержать непустой Purpose и раздел Requirements")
        if not any(line.startswith("# ") for i, line in enumerate(main_lines) if not main_mask[i]):
            note("mismatch", cap, "", "у мастера нет заголовка первого уровня")
        expected, duplicates = _blocks(delta)
        actual, main_duplicates = _blocks(main, master=True)
        for name in duplicates + main_duplicates:
            note("mismatch", cap, name, "повтор имени требования или сценария")
        if _purpose(delta) is not None and _purpose(delta) != _purpose(main):
            note("review", cap, "", "Purpose отличается от дельты; сверить, существовал ли мастер до sync")
        renames = {r.to_name: r.from_name for r in parsed.renames}
        for rename in parsed.renames:
            if rename.to_name not in actual or rename.from_name in actual:
                note("mismatch", cap, rename.to_name, "RENAMED: новое имя должно присутствовать, старое отсутствовать")
        for name, block in expected.items():
            req = block["req"]
            if req.section == "REMOVED":
                if name in actual:
                    note("mismatch", cap, name, "REMOVED: требование осталось в мастере")
                continue
            if name not in actual:
                note("mismatch", cap, name, "требование отсутствует в мастере")
                continue
            current = actual[name]
            entry = saved.get(cap, {}).get(name) or saved.get(cap, {}).get(renames.get(name, ""))
            base_refs = {ref for value in entry["numbers"] if (ref := parse_ref(value))} if entry else set()
            # A late freeze can copy the already anchored result. It is not proof of the pre-sync origin.
            uncertain = req.section == "MODIFIED" and (entry is None or any(ref.change == change for ref in base_refs))
            inherited = {ref for ref in base_refs if ref.change is None} if not uncertain else set()
            if not current["canonical"]:
                note("mismatch", cap, name, "заголовок требования должен иметь форму ### Requirement:")
            if not current["scenarios"]:
                note("mismatch", cap, name, "у требования нет сценария")
            # Only the changed block is checked: unrelated historical probe trails are preserved.
            start = current["req"].line - 1
            stop = next((i for i in range(start + 1, len(main_lines)) if not main_mask[i]
                         and (head := _ANY_HEADER.match(main_lines[i])) and len(head.group(1)) <= 3), len(main_lines))
            raw = "\n".join(main_lines[start:stop])
            if strip_probe_trails(raw) != raw:
                note("mismatch", cap, name, "в перенесённом блоке остался след пробы")
            def compare(want, got, label, unknown_origin):
                left, refs_left, review_left = _normalize(want, change, numbers, inherited, unknown_origin, True)
                right, refs_right, review_right = _normalize(got, change, numbers, inherited, unknown_origin, False)
                if refs_left != refs_right:
                    note("mismatch", cap, name, f"{label}: различается происхождение или состав ссылок")
                elif left != right:
                    note("review", cap, name, f"{label}: текст отличается; требуется семантическая сверка")
                if review_left or review_right:
                    note("review", cap, name, f"{label}: происхождение голых номеров не доказано снимком; сверить прежний блок")
            compare(block["text"], current["text"], "требование", uncertain)
            if entry:
                for old in entry["scenarios"]:
                    if old not in current["scenarios"]:
                        note("mismatch", cap, name, f"пропал прежний сценарий «{old}»")
            for scenario, wanted in block["scenarios"].items():
                got = current["scenarios"].get(scenario)
                if got is None:
                    note("mismatch", cap, name, f"пропал сценарий «{scenario}»")
                else:
                    if not got["canonical"]:
                        note("mismatch", cap, name, f"неканонический заголовок сценария «{scenario}»")
                    previous_scenario = entry and scenario in entry["scenarios"]
                    compare(wanted["text"], got["text"], f"сценарий «{scenario}»", uncertain or bool(previous_scenario))
    status = "mismatch" if any(f["level"] == "mismatch" for f in findings) else "review" if findings else "match"
    return {"change": change, "root": str(root), "capabilities": selected, "status": status, "findings": findings}


def build_parser():
    parser = argparse.ArgumentParser(description="Сверка результата sync без записи файлов. Звать, когда выбранные дельты перенесены в мастер, до архива.",
        epilog="Порядок: cwd выбирает planning root; проверяются только выбранные дельты, мастер, журнал и прежняя база снимка; файлы не меняются. "
               "Маркеры: match — проверенные части совпали; mismatch — явное расхождение; review — требуется суждение о тексте, происхождении или retirement. "
               "Коды: 0 — match; 1 — mismatch; 2 — review (или неверный вызов); 3 — ошибка чтения. Review не является ошибкой графа или автоматическим стопом архива.")
    parser.add_argument("change", metavar="ИЗМЕНЕНИЕ", help="имя активного изменения")
    parser.add_argument("--capability", action="append", metavar="ИМЯ", help="выбранная capability; повторяемый; без флага — все дельты")
    parser.add_argument("--json", action="store_true", help="машиночитаемый результат")
    return parser


def main(argv=None):
    # Machine-readable output stays UTF-8 even in a Windows shell configured for CP1251.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        result = check_sync(find_root(Path.cwd()), args.change, capabilities=args.capability)
    except (Refusal, ForkError, OSError, UnicodeError) as error:
        if args.json:
            print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False))
        else:
            print(str(error), file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Сверка sync: {result['status']}.")
        for finding in result["findings"]:
            print(f"{finding['capability']}: {finding['requirement']} — {finding['message']}")
    return {"match": 0, "mismatch": 1, "review": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
