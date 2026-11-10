"""Измеряет текст ADDED/MODIFIED без записи файлов и без замены валидатора OpenSpec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


SECTION = re.compile(r"^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements\s*$")
REQUIREMENT = re.compile(r"^### Requirement: (.+?)\s*$")
SCENARIO = re.compile(r"^#### Scenario: (.+?)\s*$")
TOP_LEVEL = re.compile(r"^#{1,3} ")


def measure(text: str, source: str) -> tuple[list[dict], list[str]]:
    """Считает буквально записанный текст до первого сценария, без внешних пустых строк."""
    results: list[dict] = []
    errors: list[str] = []
    section: str | None = None
    current: dict | None = None
    prose: list[str] = []
    has_scenario = False

    def finish() -> None:
        nonlocal current, prose, has_scenario
        if current is None:
            return
        while prose and not prose[0].strip():
            prose.pop(0)
        while prose and not prose[-1].strip():
            prose.pop()
        size = len("\n".join(prose))
        results.append({**current, "characters": size, "limit": 500, "within_limit": size <= 500})
        if not has_scenario:
            errors.append(f"{source}:{current['line']}: отсутствует первый заголовок #### Scenario:")
        current = None
        prose = []
        has_scenario = False

    for number, line in enumerate(text.splitlines(), start=1):
        matched_section = SECTION.fullmatch(line)
        if matched_section:
            finish()
            section = matched_section.group(1)
            continue
        matched_requirement = REQUIREMENT.fullmatch(line)
        if matched_requirement:
            finish()
            if section in {"ADDED", "MODIFIED"}:
                current = {
                    "source": source,
                    "line": number,
                    "section": section,
                    "requirement": matched_requirement.group(1),
                }
            continue
        if TOP_LEVEL.match(line):
            finish()
            if line.startswith("# ") or line.startswith("## "):
                section = None
            continue
        if current is not None:
            if SCENARIO.fullmatch(line):
                has_scenario = True
            elif not has_scenario:
                prose.append(line)
    finish()
    return results, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Явные пути дельт spec.md; glob обрабатывает вызывающая сторона.")
    parser.add_argument("--stdin", action="store_true", help="Прочитать одну дельту из стандартного ввода.")
    args = parser.parse_args()
    if args.stdin == bool(args.paths):
        parser.error("Укажите либо --stdin, либо один или несколько путей файлов.")

    # UTF-8 делает одинаковым ввод файлов и стандартного потока в поддерживаемых оболочках.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    requirements: list[dict] = []
    errors: list[str] = []
    sources = ["<stdin>"] if args.stdin else args.paths
    for source in sources:
        try:
            contents = sys.stdin.read() if args.stdin else Path(source).read_text(encoding="utf-8-sig")
            found, incomplete = measure(contents, source)
            requirements.extend(found)
            errors.extend(incomplete)
        except (OSError, UnicodeError) as error:
            errors.append(f"{source}: {error}")
    print(json.dumps({"requirements": requirements, "errors": errors}, ensure_ascii=False, indent=2))
    if errors:
        return 2
    return 1 if any(not item["within_limit"] for item in requirements) else 0


if __name__ == "__main__":
    raise SystemExit(main())
