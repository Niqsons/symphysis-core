# -*- coding: utf-8 -*-
"""Used master blocks in attack reports (F-15.A).

`master_supports` is a single-line JSON array of capability, requirement, optional
scenario and sha256. Identifiers name blocks in the sole `## Requirements`
section of `<planning_root>/openspec/specs/<capability>/spec.md`.

The hashed block starts at its original heading and ends immediately before the
next heading of equal or higher level, or at EOF. Separator blank lines, heading
spelling, comments and all interior whitespace belong to the block. A requirement
includes its scenarios. Only CRLF/CR become LF, and a file-leading UTF-8 BOM is
removed. Fenced headings are data. Names strip optional ATX closing hashes and
the Requirement/Scenario label, with case-sensitive comparison thereafter.

Errors carry fixed reasons and an optional 1-based metadata index. Callers can
produce diagnostics without exposing declarations, file contents or paths.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath

__all__ = ["MasterSupportError", "master_block", "master_support", "parse_master_supports",
           "validate_master_support", "set_master_supports"]

_CAPABILITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")
_SHA256 = re.compile(r"[a-fA-F0-9]{64}")
_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_REQUIREMENT = re.compile(r"^###\s*Requirement:\s*(.+)$", re.IGNORECASE)
_FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")
_FIELD = re.compile(r"^master_supports:\s*(.*?)\s*$")


class MasterSupportError(ValueError):
    def __init__(self, reason: str, index: int | None = None):
        super().__init__(f"master support: {reason}")
        self.reason = reason
        self.index = index


def _identifier(value: object, capability: bool = False) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or _CONTROL.search(value):
        raise MasterSupportError("invalid")
    if (PurePosixPath(value).anchor or PureWindowsPath(value).anchor
            or PureWindowsPath(value).drive or ".." in re.split(r"[/\\]", value)):
        raise MasterSupportError("outside")
    if capability:
        components = re.split(r"[/\\]", value)
        if any(not _CAPABILITY.fullmatch(component) or component in (".", "..") for component in components):
            raise MasterSupportError("outside")
        return "/".join(components)
    return value


def _selection(capability: object, requirement: object, scenario: object = None) -> dict:
    selected = {"capability": _identifier(capability, capability=True), "requirement": _identifier(requirement)}
    if scenario is not None:
        selected["scenario"] = _identifier(scenario)
    return selected


def validate_master_support(support: object) -> dict:
    """Validate one metadata object and return a copy with a lower-case digest."""
    if not isinstance(support, dict):
        raise MasterSupportError("invalid")
    required = {"capability", "requirement", "sha256"}
    if not required <= support.keys() or support.keys() - required - {"scenario"}:
        raise MasterSupportError("invalid")
    if "scenario" in support and support["scenario"] is None:
        raise MasterSupportError("invalid")
    selected = _selection(support["capability"], support["requirement"], support.get("scenario"))
    digest = support["sha256"]
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise MasterSupportError("invalid")
    return {**selected, "sha256": digest.lower()}


def _validated_supports(supports: object) -> list[dict]:
    if not isinstance(supports, list):
        raise MasterSupportError("invalid")
    result, seen = [], set()
    for index, support in enumerate(supports, 1):
        try:
            valid = validate_master_support(support)
            identity = (valid["capability"], valid["requirement"], valid.get("scenario"))
            if identity in seen:
                raise MasterSupportError("ambiguous")
        except MasterSupportError as error:
            raise MasterSupportError(error.reason, index) from None
        result.append(valid)
        seen.add(identity)
    return result


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise MasterSupportError("invalid")
        result[key] = value
    return result


def parse_master_supports(value: str) -> list[dict]:
    """Parse the dedicated single physical line, rejecting duplicate keys/blocks."""
    if not isinstance(value, str) or "\n" in value or "\r" in value:
        raise MasterSupportError("invalid")
    try:
        supports = json.loads(value, object_pairs_hook=_unique_object)
    except (ValueError, TypeError, RecursionError):
        raise MasterSupportError("invalid") from None
    return _validated_supports(supports)


def _master_path(planning_root: Path | str, capability: str) -> Path:
    try:
        root = Path(planning_root).resolve()
        specs = (root / "openspec/specs").resolve()
        path = (specs / capability / "spec.md").resolve()
        if specs == root or not specs.is_relative_to(root) or not path.is_relative_to(specs):
            raise MasterSupportError("outside")
        return path
    except (OSError, RuntimeError, ValueError):
        raise MasterSupportError("outside") from None


def _name(title: str) -> str:
    return re.sub(r"[ \t]+#+[ \t]*$", "", title).strip()


def _headings(lines: list[str]) -> tuple[list[tuple[int, int, str]], int | None]:
    headings, active, opened_at = [], None, None
    for index, line in enumerate(lines):
        if active is not None:
            closed = _FENCE_CLOSE.match(line)
            if closed and closed.group(1)[0] == active[0] and len(closed.group(1)) >= len(active):
                active, opened_at = None, None
            continue
        opened = _FENCE_OPEN.match(line)
        if opened and not (opened.group(1)[0] == "`" and "`" in opened.group(2)):
            active, opened_at = opened.group(1), index
            continue
        requirement = _REQUIREMENT.match(line)
        if requirement:
            headings.append((index, 3, "Requirement: " + _name(requirement.group(1))))
        elif heading := _HEADING.match(line):
            headings.append((index, len(heading.group(1)), _name(heading.group(2))))
    return headings, opened_at


def _end(headings: list[tuple[int, int, str]], start: int, level: int, limit: int) -> int:
    return next((line for line, depth, _ in headings if line > start and depth <= level), limit)


def _one(matches: list[int]) -> int:
    if not matches:
        raise MasterSupportError("missing")
    if len(matches) != 1:
        raise MasterSupportError("ambiguous")
    return matches[0]


def master_block(planning_root: Path | str, capability: str, requirement: str, scenario: str | None = None) -> str:
    """Read exactly one selected block after checking resolved path containment."""
    selected = _selection(capability, requirement, scenario)
    path = _master_path(planning_root, selected["capability"])
    try:
        text = path.read_bytes().decode("utf-8").removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    except FileNotFoundError:
        raise MasterSupportError("missing") from None
    except (OSError, UnicodeError):
        raise MasterSupportError("unreadable") from None
    lines = text.split("\n")
    headings, unclosed_fence = _headings(lines)
    sections = [line for line, level, title in headings if level == 2 and title.lower() == "requirements"]
    if not sections:
        raise MasterSupportError("invalid")
    section = _one(sections)
    section_end = _end(headings, section, 2, len(lines))
    start = _one([line for line, level, title in headings if section < line < section_end
                  and level == 3 and title == "Requirement: " + requirement])
    end = _end(headings, start, 3, section_end)
    if scenario is not None:
        start = _one([line for line, level, title in headings if start < line < end
                      and level == 4 and re.sub(r"^Scenario:\s*", "", title, flags=re.IGNORECASE) == scenario])
        end = _end(headings, start, 4, end)
    if not "\n".join(lines[start + 1:end]).strip() or unclosed_fence is not None and start <= unclosed_fence < end:
        raise MasterSupportError("invalid")
    raw = "\n".join(lines[start:end])
    return raw + ("\n" if end < len(lines) else "")


def master_support(planning_root: Path | str, capability: str, requirement: str, scenario: str | None = None) -> dict:
    """Create metadata only for the explicitly selected used block."""
    selected = _selection(capability, requirement, scenario)
    block = master_block(planning_root, capability, requirement, scenario)
    return {**selected, "sha256": hashlib.sha256(block.encode("utf-8")).hexdigest()}


def set_master_supports(text: str, supports: list[dict]) -> str:
    """Return the report with one canonical field, preserving all other bytes."""
    valid = _validated_supports(supports)
    parts = re.split(r"(\r\n|\r|\n)", text)
    lines = parts[0::2]
    if not lines or lines[0].removeprefix("\ufeff").strip() != "---":
        raise MasterSupportError("invalid")
    end = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise MasterSupportError("invalid")
    fields = [index for index in range(1, end) if _FIELD.match(lines[index])]
    if len(fields) > 1:
        raise MasterSupportError("ambiguous")
    field = "master_supports: " + json.dumps(valid, ensure_ascii=False, separators=(",", ":"))
    if fields:
        index = fields[0]
        if index + 1 < end and lines[index + 1].startswith((" ", "\t")):
            raise MasterSupportError("invalid")
        parts[index * 2] = field
    else:
        ending = parts[1] if len(parts) > 1 else "\n"
        parts[end * 2:end * 2] = [field, ending]
    return "".join(parts)
