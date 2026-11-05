#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Граф трассируемости изменения OpenSpec (изменение `trace-graph`, F-39): требования, сценарии, решения журнала, задачи,
пункты security и ветки описи, связанные ссылками. Здесь: пять подкоманд с `--help`, реестр артефактов схемы, свой разбор
спек (`parse_spec`, F-40) и `build` с узлами (`build_graph`); связи, отчёт, проверку и заморозку добавят следующие порции.
Только стандартная библиотека."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True  # как у соседних скриптов: `__pycache__` в проекте от инструментов не появляется (F-50)
from journal_model import validate_journal  # noqa: E402
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
    """Отказ подкоманды: текст идёт в stderr, код выхода 1, без трассировки. `lines` — подробности (например, ошибки схемы),
    их печатает `main` перед текстом: библиотечные функции в stderr не пишут."""

    def __init__(self, message: str, lines: list[str] | None = None):
        super().__init__(message)
        self.lines = list(lines or [])


def _not_implemented(name: str) -> Refusal:
    return Refusal(f"подкоманда `{name}` ещё не реализована: это каркас, обработчик добавит следующая порция")


# --- сборка графа: узлы (F-70, F-80, F-81, F-125, F-131) ------------------------
# Узел — словарь: `id`, `kind` (`cap`, `req`, `scn`, `rec`, `task`, `sec`, `branch`), `name`, `at`; остальное по виду:
#   cap: —; req: `section` (ADDED, MODIFIED, REMOVED), `capability`; scn: `capability`, `requirement` (id требования);
#   rec: `record_kind` (вид записи журнала), `number` (число из `F-NN`); task: `done`; sec, branch: —.
# `at` — `путь:строка` от каталога изменения, путь с `/`, строки с 1. Файл графа: `format: 1`, `nodes`, `edges`, `candidates`.
# Узлы идут по `(путь из at, строка, id)`: порядок от файловой системы и от порядка чтения не зависит, две сборки одинаковы
# байт в байт (F-81). Узел с уже виденным id в граф не входит: id — ключ графа, остаётся первый по порядку чтения, а дубль
# уходит в список `build_graph_with_duplicates` и сигналом в stderr у `build`.

GRAPH_FORMAT = 1
_TASK_LINE = re.compile(r"^- \[[ xX]\] (\d+(?:\.\d+)+)\s+(.*?)\s*$")
_TABLE_ROW = re.compile(r"^\|(.*)$")
_TABLE_RULE = re.compile(r"^\|[\s:|-]+\|?\s*$")
_BRANCH_LINE = re.compile(r"^- \*\*(.+?)\*\*\s*—\s*`([^`\s]+:\d+)`\s*«")


def _node(node_id: str, kind: str, name: str, file: str, line: int, **extra) -> dict:
    return {"id": node_id, "kind": kind, "name": name, "at": f"{file}:{line}", **extra}


def _read_text(base: Path, rel: str) -> str:
    """Текст файла изменения в UTF-8; иначе отказ с именем файла."""
    try:
        return (base / rel).read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        raise Refusal(f"{rel}: файл не в UTF-8 ({e.reason}, байт {e.start}): граф не собран") from None


def _plain_lines(text: str) -> list[tuple[int, str]]:
    """Строки файла вне блоков кода как `(номер с 1, текст)`; BOM и CRLF не мешают счёту."""
    lines = re.sub(r"\r\n?", "\n", text.removeprefix("﻿")).split("\n")
    mask = _fence_mask(lines)
    return [(i + 1, line) for i, line in enumerate(lines) if not mask[i]]


def _read_records(base: Path) -> list[dict]:
    """Записи журнала `decisions.json` (F-80, F-125): проверка схемы тем же `validate_journal`, что у `journal.py check`;
    разбор здесь свой, потому что `load_journal` бросает без имени файла. Нет файла — нет узлов."""
    if not (base / "decisions.json").is_file():
        return []
    text = _read_text(base, "decisions.json")
    try:
        journal = json.loads(text)
    except ValueError as e:
        raise Refusal(f"decisions.json: журнал не разбирается ({e}): граф не собран") from None
    errors = validate_journal(journal)
    if errors:
        raise Refusal(f"decisions.json: журнал негоден по схеме, ошибок {len(errors)}: граф не собран",
                      [f"[!!] {e}" for e in errors])
    lines = text.split("\n")
    nodes = []
    for rec in journal["records"]:
        rid = rec["id"]
        own = re.compile(r'^\s*"id":\s*"' + re.escape(rid) + r'"\s*,?\s*$')
        line = next((i + 1 for i, row in enumerate(lines) if own.match(row)), 1)  # журнал в одну строку: строка 1
        number = re.search(r"\d+", rid)
        nodes.append(_node(f"rec:{rid}", "rec", rec["question"], "decisions.json", line,
                           record_kind=rec["kind"], number=int(number.group()) if number else None))
    return nodes


def _read_specs(base: Path) -> list[dict]:
    """Capability, требования и сценарии `specs/<capability>/spec.md`; capability — имя каталога (F-131)."""
    nodes = []
    folders = sorted(p for p in (base / "specs").iterdir() if p.is_dir()) if (base / "specs").is_dir() else []
    for folder in folders:
        rel = f"specs/{folder.name}/spec.md"
        if not (base / rel).is_file():
            continue
        parsed = parse_spec(_read_text(base, rel))
        cap = folder.name
        nodes.append(_node(f"cap:{cap}", "cap", cap, rel, 1))
        for req in parsed.requirements:
            req_id = f"req:{cap}/{req.name}"
            nodes.append(_node(req_id, "req", req.name, rel, req.line, section=req.section, capability=cap))
            nodes += [_node(f"scn:{cap}/{req.name}/{scn.name}", "scn", scn.name, rel, scn.line,
                            capability=cap, requirement=req_id) for scn in req.scenarios]
    return nodes


def _read_tasks(base: Path) -> list[dict]:
    """Задачи `- [ ] N.M …` и `- [x] N.M …` из `tasks.md`; остальные пункты и строки в блоках кода не задачи."""
    if not (base / "tasks.md").is_file():
        return []
    found = []
    for number, line in _plain_lines(_read_text(base, "tasks.md")):
        m = _TASK_LINE.match(line)
        if m:
            found.append(_node(f"task:{m.group(1)}", "task", m.group(2), "tasks.md", number, done=line[3] in "xX"))
    return found


def _read_security(base: Path) -> list[dict]:
    """Пункты чек-листа `security.md`: первая колонка строк таблицы, без шапки и разделителя."""
    if not (base / "security.md").is_file():
        return []
    rows = _plain_lines(_read_text(base, "security.md"))
    found = []
    for pos, (number, line) in enumerate(rows):
        if not _TABLE_ROW.match(line) or _TABLE_RULE.match(line):
            continue
        following = rows[pos + 1][1] if pos + 1 < len(rows) else ""
        if _TABLE_RULE.match(following):  # строка над разделителем — шапка
            continue
        first = line[1:].split("|", 1)[0].strip()
        if first:
            found.append(_node(f"sec:{first}", "sec", first, "security.md", number))
    return found


def _read_branches(base: Path) -> list[dict]:
    """Ветки описи `consequences.md`: строки `- **Имя** — `путь:строка` «цитата»`. Строка без `путь:строка` узла не даёт."""
    if not (base / "consequences.md").is_file():
        return []
    found = []
    for number, line in _plain_lines(_read_text(base, "consequences.md")):
        m = _BRANCH_LINE.match(line)
        if m:
            found.append(_node(f"branch:{m.group(2)}", "branch", m.group(1), "consequences.md", number))
    return found


# Читатель на каждый артефакт реестра, из которого граф что-то берёт. Артефакт со значением `ничего` не читается вовсе.
READERS = {"decisions": _read_records, "specs": _read_specs, "consequences": _read_branches, "security": _read_security,
           "tasks": _read_tasks}


def build_graph(root: Path, change: str) -> dict:
    """Граф изменения без списка дублей id; см. `build_graph_with_duplicates`."""
    return build_graph_with_duplicates(root, change)[0]


def build_graph_with_duplicates(root: Path, change: str) -> tuple[dict, list[dict]]:
    """Граф изменения `change` проекта `root` и список дублей id. Граф: `format`, `nodes`, `edges`, `candidates`; читает только
    артефакты, из которых `REGISTRY` что-то берёт (F-53). Связи добавят следующие порции: `edges` и `candidates` пока пусты.
    Дубль — повторный id (два требования с одним именем в capability, два сценария, два пункта security): в графе остаётся
    первый по порядку чтения, id уникальны, а дубль не теряется молча, а идёт вторым значением: `[{"id": …, "at": [место
    первого, место повторного, …]}]` в порядке появления. В JSON графа список не входит (формат не меняется)."""
    base = root / "openspec" / "changes" / change
    if not base.is_dir():
        raise Refusal(f"изменения «{change}» нет: нет каталога openspec/changes/{change}")
    nodes, places = [], {}
    for artifact, row in REGISTRY.items():
        if row.get("берёт") == NOTHING:
            continue
        if artifact not in READERS:
            raise Refusal(f"в реестре у артефакта «{artifact}» значение «берёт», а читателя нет: добавить читателя "
                          f"или записать `{NOTHING}` с доводом")
        for node in READERS[artifact](base):
            if node["id"] in places:
                places[node["id"]].append(node["at"])
            else:
                places[node["id"]] = [node["at"]]
                nodes.append(node)
    nodes.sort(key=lambda n: (n["at"].rsplit(":", 1)[0], int(n["at"].rsplit(":", 1)[1]), n["id"]))
    duplicates = [{"id": node_id, "at": at} for node_id, at in places.items() if len(at) > 1]
    return {"format": GRAPH_FORMAT, "nodes": nodes, "edges": [], "candidates": []}, duplicates


def cmd_build(args: argparse.Namespace, root: Path) -> int:
    graph, duplicates = build_graph_with_duplicates(root, args.change)
    for dup in duplicates:  # сигнал, не стоп (F-31): граф печатается, код 0
        print(f"[!!] дубль id {dup['id']}: места {', '.join(dup['at'])}; в графе остался первый", file=sys.stderr)
    print(json.dumps(graph, ensure_ascii=False, indent=1))
    return 0


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
    "build": ("Собирает граф трассируемости изменения из его артефактов и печатает его JSON в stdout, файлов не пишет.",
              "Звать, когда нужен живой граф: перед отчётом, при разборе связей, в атаке артефактов.",
              "Коды: 0 — граф собран (у только что созданного изменения он пуст); 1 — отказ, графа нет: имя изменения "
              "не подходит, изменения нет, `decisions.json` не разбирается или негоден по схеме, файл не в UTF-8; "
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
        for line in getattr(e, "lines", []):
            print(line, file=sys.stderr)
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
