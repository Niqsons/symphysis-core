#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Граф трассируемости изменения OpenSpec (изменение `trace-graph`, F-39): требования, сценарии, решения журнала, задачи,
пункты security и ветки описи, связанные ссылками. Здесь: пять подкоманд с `--help`, реестр артефактов схемы, свой разбор
спек (`parse_spec`, F-40) и `build` с узлами (`build_graph`); связи, отчёт, проверку и заморозку добавят следующие порции.
Только стандартная библиотека."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True  # как у соседних скриптов: `__pycache__` в проекте от инструментов не появляется (F-50)
from roots import UNUSABLE_ROOTS, default_roots  # noqa: E402
from journal_model import PROBE_OUTCOMES, validate_journal  # noqa: E402
from openspec_run import ForkError, check_change_name, find_on_path, no_paths, run_fork  # noqa: E402

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

# --- конфиг видов диаграммы (F-54, F-67, F-135, F-136) ---------------------------------------------------------------
# Вложенный словарь, yaml-like: как `build --format mermaid` рисует каждый вид узла и каждый тип связи. Скрипт ничего не
# рисует, он выдаёт текст `requirementDiagram` (F-54).
#   предел: знаков текста, больше которого без выбора и с `--capability` текст не выдаётся (F-66, F-104)
#   имя: знаков в имени блока вместе с номером (F-137)
#   виды:
#     <вид узла: cap, req, scn, task, rec, sec, branch>:
#       sysml: ближайший тип SysML: `requirement`, `designConstraint` или `element`
#       type: у `element` слово вида в поле `type` (у `element` поля `id` нет, F-67); у остальных None
#       класс: имя `classDef`, только латиница без дефиса (ловушка F-54: кириллица и дефис — отказ разбора)
#       заливка, рамка, ширина, штрих: цвет и рамка класса; виды различаются ими, стереотип над блоком остаётся
#         стандартным; штрих одним числом, штрих с пробелом в `stroke-dasharray` схлопывается (F-54)
#       префикс: префикс номера в имени узла (`SCN_12`) и в `id` у типов требований (`REQ_3`); с подчёркиванием, форму с дефисом хук ключа задачи принимает за ключ
#   связи:
#     <тип связи графа>: слово связи на диаграмме; `candidate` — для кандидата связи (F-71), он идёт типом `copies`,
#       которого у записанных связей нет (F-120, F-135); пункт security идёт типом `refines`
DIAGRAM = {
    "предел": 50000,  # знаков текста без выбора и с `--capability`; у `--requirement` предела нет (F-66, F-104)
    "имя": 90,  # знаков в имени блока вместе с номером (F-137)
    "виды": {
        "cap": {"sysml": "requirement", "type": None, "класс": "cap", "заливка": "#e0e7ff", "рамка": "#4338ca",
                "ширина": "3px", "префикс": "CAP"},
        "req": {"sysml": "requirement", "type": None, "класс": "req", "заливка": "#dbeafe", "рамка": "#1d4ed8",
                "ширина": "2px", "префикс": "REQ"},
        "scn": {"sysml": "element", "type": "сценарий", "класс": "scn", "заливка": "#dcfce7", "рамка": "#15803d",
                "ширина": "1px", "префикс": "SCN"},
        "task": {"sysml": "element", "type": "задача", "класс": "task", "заливка": "#fef9c3", "рамка": "#a16207",
                 "ширина": "1px", "префикс": "TASK"},
        "rec": {"sysml": "element", "type": "запись", "класс": "rec", "заливка": "#f3e8ff", "рамка": "#7e22ce",
                "ширина": "1px", "штрих": "6", "префикс": "REC"},
        "sec": {"sysml": "designConstraint", "type": None, "класс": "sec", "заливка": "#fee2e2", "рамка": "#b91c1c",
                "ширина": "3px", "префикс": "SEC"},
        "branch": {"sysml": "element", "type": "ветка", "класс": "branch", "заливка": "#ffedd5", "рамка": "#c2410c",
                   "ширина": "2px", "штрих": "6", "префикс": "BR"},
    },
    "связи": {
        "contains": "contains",
        "verifies": "verifies",
        "traces": "traces",
        "satisfies": "satisfies",
        "derives": "derives",
        "refines": "refines",
        "candidate": "copies",
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
    lines = re.sub(r"\r\n?", "\n", text.removeprefix("\ufeff")).split("\n")
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


# --- сборка графа: узлы (F-70, F-80, F-81, F-125, F-131) ------------------------
# Узел — словарь: `id`, `kind` (`cap`, `req`, `scn`, `rec`, `task`, `sec`, `branch`), `name`, `at`; остальное по виду:
#   cap: —; req: `section` (ADDED, MODIFIED, REMOVED), `capability`; scn: `capability`, `requirement` (id требования);
#   rec: `record_kind` (вид записи журнала), `number` (число из `F-NN`); task: `done`; sec, branch: —.
# `at` — `путь:строка` от каталога изменения, путь с `/`, строки с 1. Файл графа: `format: 1`, `sources`, `nodes`, `edges`,
# `candidates`; `sources` — `[{"path", "sha256"}]`, хеш после приведения концов строк к LF (F-87, F-139).
# Узлы идут по `(путь из at, строка, id)`: порядок от файловой системы и от порядка чтения не зависит, две сборки одинаковы
# байт в байт (F-81). Узел с уже виденным id в граф не входит: id — ключ графа, остаётся первый по порядку чтения, а дубль
# уходит в список `build_graph_with_duplicates` и сигналом в stderr у `build`.

GRAPH_FORMAT = 1
_TASK_LINE = re.compile(r"^- \[[ xX]\] (\d+(?:\.\d+)+)\s+(.*?)\s*$")
_TABLE_ROW = re.compile(r"^\|(.*)$")
_TABLE_RULE = re.compile(r"^\|[\s:|-]+\|?\s*$")
_REC_REF = re.compile(r"(?<![\w-])F-(\d+)(?!\d)")  # граница слова слева: `UTF-8` не даёт `F-8`; `.A` у `F-07.A` остаётся за числом
_CAP_NAME = re.compile(r"`([^`]+)`:\s*«")  # `capability`: «имя…
_NEXT_NAME = re.compile(r"\s*,\s*«")  # следующее имя той же строки: своей capability у него нет (F-89)
_SEC_REQ = re.compile(r"`([^`]+)`:?\s*«")  # `capability` «имя» или `capability`: «имя» в любой колонке строки security (F-131)
_PARENT = re.compile(r"^\s*Часть требования\s+(?:`([^`]+)`:\s*)?«")  # фраза дочернего: в начале строки, не в кавычках (F-77)
_BRANCH_SCENARIO = re.compile(r"(?i:(?<!ближайший ))сценарий:\s*")  # «ближайший сценарий» (и «Ближайший») ветку не покрывает
_BRANCH_LINE = re.compile(r"^- \*\*(.+?)\*\*\s*—\s*`([^`\s]+:\d+)`\s*«")
_SAMPLE_FORM = re.compile(r"``.+?``")  # образец формы в двойных обратных кавычках: ссылкой не считается


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
    lines = re.sub(r"\r\n?", "\n", text.removeprefix("\ufeff")).split("\n")
    mask = _fence_mask(lines)
    return [(i + 1, line) for i, line in enumerate(lines) if not mask[i]]


def _read_records(base: Path, claims: list[dict]) -> list[dict]:
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


def _spec_lines(text: str) -> list[str]:
    return re.sub(r"\r\n?", "\n", text.removeprefix("\ufeff")).split("\n")


def _requirement_body(lines: list[str], mask: list[bool], heading: int) -> list[tuple[int, str]]:
    """Тело требования с заголовком в строке `heading` (с 1) как `(номер строки, текст)`: до первого заголовка вне блока кода,
    без строк в блоках кода и без HTML-комментариев (след пробы `<!-- проба краёв … -->` не текст требования, F-44)."""
    body, in_comment = [], False
    for i in range(heading, len(lines)):
        if mask[i]:
            continue
        if re.match(r"^#{1,6}\s", lines[i]):
            break
        rest, kept = lines[i], ""
        while rest:
            if in_comment:
                end = rest.find("-->")
                in_comment, rest = (False, rest[end + 3:]) if end >= 0 else (True, "")
            else:
                start = rest.find("<!--")
                kept, rest, in_comment = (kept + rest, "", False) if start < 0 else (kept + rest[:start], rest[start + 4:], True)
        if kept.strip():
            body.append((i + 1, kept))
    return body


def _record_numbers(text: str) -> list[int]:
    """Номера записей `F-NN` по границе слова: `UTF-8` не даёт `F-8`; суффикс варианта (`F-07.A`) отбрасывается."""
    return [int(m.group(1)) for m in _REC_REF.finditer(text)]


def _master_lines(root: Path, rel: str) -> list[str]:
    """Строки мастер-спеки без CRLF и BOM; она пишет `## Requirements`, а `parse_spec` читает секции дельты: заголовок читается
    как `ADDED`. Перевод строк нормализуется раньше подмены: `$` не стоит перед возвратом каретки, и спека с CRLF осталась бы
    без требований."""
    return [re.sub(r"^## Requirements[ \t]*$", "## ADDED Requirements", row) for row in _spec_lines(_read_text(root, rel))]


def _hash(text: str) -> str:
    """sha256 текста с приведением пробелов и концов строк (как сверка в `_squash`): в базу идут хеши, а не текст мастер-спеки."""
    return hashlib.sha256(_squash(text).encode("utf-8")).hexdigest()


def master_base(root: Path, cap: str) -> dict[str, dict]:
    """Что нужно знать о каждом требовании живой мастер-спеки `openspec/specs/<cap>/spec.md` (F-84, F-95, F-123): запись базы
    `{"numbers": [F-NN, ...], "scenarios": {имя сценария: хеш текста}, "text": хеш текста требования, "traces": [хеши следов
    проб]}` по имени требования; при повторе имени остаётся первое. Мастер-спека пишет `## Requirements`, а `parse_spec` читает
    секции дельты: заголовок читается как `ADDED`. Хеш — `_hash`; следы — комментарии `<!-- проба …, исходы: … -->` внутри
    требования."""
    rel = f"openspec/specs/{cap}/spec.md"
    if not (root / rel).is_file():
        return {}
    lines = _master_lines(root, rel)
    mask = _fence_mask(lines)
    reqs = parse_spec("\n".join(lines)).requirements
    traces: dict[str, set[str]] = {}
    for number, comment, _ in _trace_comments(lines):
        owner = max((r for r in reqs if r.line <= number), key=lambda r: r.line, default=None)
        if owner:
            traces.setdefault(owner.name, set()).add(_hash(comment))
    found: dict[str, dict] = {}
    for req in reqs:
        if req.name not in found:
            found[req.name] = {
                "numbers": sorted({n for _, line in _requirement_body(lines, mask, req.line) for n in _record_numbers(line)}),
                "scenarios": {s.name: _hash(s.text) for s in req.scenarios}, "text": _hash(req.text),
                "traces": sorted(traces.get(req.name, ()))}
    return found


def _entry_fits(entry) -> bool:
    """Запись базы годна, если все четыре поля на месте и нужного вида; иной записью база не служит."""
    return (isinstance(entry, dict) and set(entry) == {"numbers", "scenarios", "text", "traces"}
            and isinstance(entry["numbers"], list) and all(type(n) is int for n in entry["numbers"])
            and isinstance(entry["scenarios"], dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in entry["scenarios"].items())
            and isinstance(entry["text"], str) and isinstance(entry["traces"], list) and all(isinstance(t, str) for t in entry["traces"]))


def saved_base(base: Path) -> dict[str, dict[str, dict]]:
    """База из снимка `graph/req-graph.json` изменения `base`: `{capability: {имя требования: запись}}` только из годных записей.
    Нет снимка, он не JSON или у него нет поля `base` — база пуста, и сборка читает живой мастер (F-123)."""
    try:
        data = json.loads((base / "graph" / "req-graph.json").read_bytes().decode("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    raw = data.get("base") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {cap: {name: entry for name, entry in reqs.items() if isinstance(name, str) and _entry_fits(entry)}
            for cap, reqs in raw.items() if isinstance(cap, str) and isinstance(reqs, dict)}


class _Master:
    """Мастер-спека для сборки (F-123): запись базы по `(capability, имя требования)` берётся из `saved` — базы снимка; нет записи —
    из живого мастера (`master_base`, один раз на capability). `entry` отдаёт `(запись или None, взята ли из базы)`."""

    def __init__(self, root: Path, saved: dict):
        self.root, self.saved, self.live = root, saved, {}

    def entry(self, cap: str, name: str) -> tuple[dict | None, bool]:
        if name in self.saved.get(cap, {}):
            return self.saved[cap][name], True
        if cap not in self.live:
            self.live[cap] = master_base(self.root, cap)
        return self.live[cap].get(name), False


def _block_equals(entry: dict | None, req) -> bool:
    """Весь блок требования MODIFIED совпал с записью мастера: хеш текста и набор сценариев (имя и хеш текста). Текст требования
    сценариев не несёт, поэтому одного хеша текста мало: правка только сценариев оставляет его прежним (F-123)."""
    return (entry is not None and entry["text"] == _hash(req.text)
            and entry["scenarios"] == {s.name: _hash(s.text) for s in req.scenarios})


def _carried_without_base(entry: dict | None, from_base: bool, req) -> bool:
    """Базы на требование нет, а весь блок MODIFIED уже совпал с мастером (F-123): после `/opsx:sync` это то же самое, что до
    него, различить нельзя; номера не отсекаются, отчёт называет требование. Одна проверка для сборки, отчёта и заморозки."""
    return not from_base and _block_equals(entry, req)


def _read_specs(base: Path, claims: list[dict], master: "_Master | None" = None) -> list[dict]:
    """Capability, требования и сценарии `specs/<capability>/spec.md`; capability — имя каталога (F-131). Связи — в `claims`:
    capability — требование (`contains`), сценарий — требование (`verifies`), требование — запись по `(F-NN)` в тексте и по
    номерам в следе пробы (`trace`, F-156; след, дословно стоящий в мастере, связи не даёт, F-147). Номера,
    которые уже стоят в тексте требования MODIFIED у мастера, связи не дают (F-84): мастер — запись базы снимка, а без неё живой
    (`_Master`, F-123)."""
    nodes = []
    root = base.parents[2]
    master = master or _Master(root, saved_base(base))
    folders = sorted(p for p in (base / "specs").iterdir() if p.is_dir()) if (base / "specs").is_dir() else []
    for folder in folders:
        rel = f"specs/{folder.name}/spec.md"
        if not (base / rel).is_file():
            continue
        text = _read_text(base, rel)
        parsed = parse_spec(text)
        lines = _spec_lines(text)
        mask = _fence_mask(lines)
        cap = folder.name
        cap_node = _node(f"cap:{cap}", "cap", cap, rel, 1)
        nodes.append(cap_node)
        traces: dict[int, list[tuple[int, str, str]]] = {}  # след пробы по строке заголовка требования-владельца (F-156)
        for number, comment, _ in _trace_comments(lines):
            owner = max((r for r in parsed.requirements if r.line <= number), key=lambda r: r.line, default=None)
            if owner and _REQ_HEADER.match(lines[owner.line - 1]):
                traces.setdefault(owner.line, []).append((number, comment, lines[number - 1]))
        for req in parsed.requirements:
            req_id = f"req:{cap}/{req.name}"
            req_node = _node(req_id, "req", req.name, rel, req.line, section=req.section, capability=cap)
            nodes.append(req_node)
            claims.append({"kind": "edge", "from": cap_node["id"], "src": cap_node["at"], "to": req_id,
                           "type": "contains", "at": req_node["at"]})
            known, master_traces = set(), set()
            if req.section == "MODIFIED":
                entry, from_base = master.entry(cap, req.name)
                master_traces = set(entry["traces"]) if entry else set()
                if entry and not _carried_without_base(entry, from_base, req):
                    known = set(entry["numbers"])
                elif entry:  # блок уже в мастере без базы: родитель с таким текстом номера дочернего не отсекает (F-150)
                    claims.append({"kind": "carried", "from": req_id, "src": req_node["at"], "at": req_node["at"]})
            if _REQ_HEADER.match(lines[req.line - 1]):  # у записи REMOVED строкой-маркером тела нет
                for number, line in _requirement_body(lines, mask, req.line):
                    claims.append({"kind": "rec", "from": req_id, "src": req_node["at"], "at": f"{rel}:{number}",
                                   "text": line, "skip": known})
                    if _PARENT.match(line):
                        claims.append({"kind": "parent", "from": req_id, "src": req_node["at"], "at": f"{rel}:{number}",
                                       "text": line, "cap": cap, "section": req.section})
            for number, comment, line in traces.get(req.line, ()):
                if _hash(comment) in master_traces:
                    continue  # дословно стоит в том же требовании мастера: след прежнего изменения (F-147)
                claims.append({"kind": "trace", "from": req_id, "src": req_node["at"], "at": f"{rel}:{number}",
                               "text": comment.split("исходы:", 1)[1]})
            for scn in req.scenarios:
                scn_node = _node(f"scn:{cap}/{req.name}/{scn.name}", "scn", scn.name, rel, scn.line,
                                 capability=cap, requirement=req_id)
                nodes.append(scn_node)
                claims.append({"kind": "edge", "from": scn_node["id"], "src": scn_node["at"], "to": req_id,
                               "type": "verifies", "at": scn_node["at"]})
    return nodes


def _read_tasks(base: Path, claims: list[dict]) -> list[dict]:
    """Задачи `- [ ] N.M …` и `- [x] N.M …` из `tasks.md`; остальные пункты и строки в блоках кода не задачи. Строка задачи
    уходит в `claims` целиком: имена сценариев сверяются с известными, когда узлы всех артефактов собраны."""
    if not (base / "tasks.md").is_file():
        return []
    found = []
    for number, line in _plain_lines(_read_text(base, "tasks.md")):
        m = _TASK_LINE.match(line)
        if m:
            node = _node(f"task:{m.group(1)}", "task", m.group(2), "tasks.md", number, done=line[3] in "xX")
            found.append(node)
            claims.append({"kind": "task", "from": node["id"], "src": node["at"], "at": node["at"],
                           "text": _SAMPLE_FORM.sub(" ", m.group(2))})
    return found


def _read_security(base: Path, claims: list[dict]) -> list[dict]:
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
            node = _node(f"sec:{first}", "sec", first, "security.md", number)
            found.append(node)
            claims.append({"kind": "sec", "from": node["id"], "src": node["at"], "at": node["at"], "text": line})
    return found


def _read_branches(base: Path, claims: list[dict]) -> list[dict]:
    """Ветки описи `consequences.md`: строки `- **Имя** — `путь:строка` «цитата»`. Строка без `путь:строка` узла не даёт."""
    if not (base / "consequences.md").is_file():
        return []
    found, current = [], None
    for number, line in _plain_lines(_read_text(base, "consequences.md")):
        m = _BRANCH_LINE.match(line)
        if m:
            current = _node(f"branch:{m.group(2)}", "branch", m.group(1), "consequences.md", number)
            found.append(current)
        elif line[:1].strip():  # строка с нулевым отступом, не ветка, заканчивает опись ветки
            current = None
        elif current and _BRANCH_SCENARIO.search(line):
            claims.append({"kind": "branch", "from": current["id"], "src": current["at"],
                           "at": f"consequences.md:{number}", "text": line})
    return found


# Читатель на каждый артефакт реестра, из которого граф что-то берёт. Артефакт со значением `ничего` не читается вовсе.
READERS = {"decisions": _read_records, "specs": _read_specs, "consequences": _read_branches, "security": _read_security,
           "tasks": _read_tasks}


def build_graph(root: Path, change: str, saved: dict | None = None) -> dict:
    """Граф изменения без списков дублей и неразрешённых ссылок; см. `build_graph_with_signals`."""
    return build_graph_with_signals(root, change, saved)[0]


def build_graph_with_duplicates(root: Path, change: str) -> tuple[dict, list[dict]]:
    """Граф изменения и список дублей id; см. `build_graph_with_signals`."""
    graph, duplicates, _ = build_graph_with_signals(root, change)
    return graph, duplicates


def _take_name(text: str, start: int, known: set[str]) -> tuple[str, int, bool]:
    """Имя сценария после `«` (позиция `start`): `(имя, позиция после закрывающей », известно ли)`. Из известных имён
    берётся самое длинное, которое стоит в строке целиком вместе с закрывающей `»` (F-92: имена бывают с вложенными
    «ёлочками»); неизвестное имя читается до парной `»`, непарное — до конца строки."""
    fits = [name for name in known if text.startswith(name + "»", start)]
    if fits:
        name = max(fits, key=len)
        return name, start + len(name) + 1, True
    depth = 1
    for i in range(start, len(text)):
        depth += (text[i] == "«") - (text[i] == "»")
        if depth == 0:
            return text[start:i], i + 1, False
    return text[start:].strip(), len(text), False


def _master_names(root: Path) -> dict[str, dict[str, set[str]]]:
    """Имена требований и сценариев мастер-спек `openspec/specs/*/spec.md`: `{capability: {"req": …, "scn": …}}`. Нужны,
    чтобы родитель или сценарий, который живёт только в мастере, не считался опечаткой: узла в графе изменения у него нет."""
    found: dict[str, dict[str, set[str]]] = {}
    for path in sorted((root / "openspec" / "specs").glob("*/spec.md")):
        rel = path.relative_to(root).as_posix()
        reqs = parse_spec("\n".join(_master_lines(root, rel))).requirements
        found[path.parent.name] = {"req": {r.name for r in reqs}, "scn": {s.name for r in reqs for s in r.scenarios}}
    return found


def _take_scenario(text: str, start: int, known: set[str]) -> str:
    """Имя после `сценарий:`: самое длинное известное, за которым конец строки или знак препинания; иначе до `;`."""
    fits = [n for n in known if text.startswith(n, start) and (start + len(n) == len(text) or text[start + len(n)] in ";,. ")]
    return max(fits, key=len) if fits else text[start:].split(";", 1)[0].strip()


def _resolve_task_line(claim: dict, scenarios: dict, put_edge, put_unresolved) -> None:
    """Сценарии, названные строкой задачи (F-42, F-89): у каждого имени своя capability, без наследования; имя, стоящее
    после запятой без своей capability, не связывается и уходит в неразрешённые."""
    text, at, task = claim["text"], claim["at"], claim["from"]
    pos = 0
    while (m := _CAP_NAME.search(text, pos)):
        cap, start, first = m.group(1), m.end(), True
        while True:
            name, end, known = _take_name(text, start, set(scenarios.get(cap, {})) if first else set())
            if first and known:
                for scn_id in scenarios[cap][name]:
                    put_edge(task, scn_id, "satisfies", at)
            elif first:
                put_unresolved(claim, f"`{cap}`: «{name}»", f"в capability `{cap}` нет сценария с именем «{name}»")
            else:
                put_unresolved(claim, f"«{name}»", f"у имени «{name}» нет своей capability: после запятой она не "
                               "наследуется, нужна форма `capability`: «имя» у каждого имени")
            tail = _NEXT_NAME.match(text, end)
            if not tail:
                break
            start, first = tail.end(), False
        pos = end


def _resolve_claims(root: Path, nodes: list[dict], places: dict, claims: list[dict],
                    base_master: "_Master | None" = None) -> tuple[list[dict], list[dict], set[tuple[str, str]]]:
    """Связи и неразрешённые ссылки из заявок читателей. Заявка узла, который в граф не вошёл как дубль id, отбрасывается.
    Связь — `from`, `to`, `type`, `at` (место записи от каталога изменения); повтор `(from, to, type)` остаётся первым.
    Ссылка, которая не разрешилась (нет записи с таким номером, нет сценария с таким именем), связи не даёт и идёт в
    список `[{"ref", "from", "at", "why"}]`: что названо, чьё это, где и почему не связалось. Номер в тексте дочернего требования
    ADDED, который стоит в мастер-тексте его родителя (запись базы, а без неё живой мастер, `base_master`), связи не даёт
    (F-150, F-84 через `derives`); свой номер дочернего даёт. Родителя в мастере нет или он ADDED этого изменения — отсекать
    нечего: после `/opsx:sync` мастер-текст ADDED-родителя был бы новым и ответ поменялся бы. Третье значение — `{(from, to)}`
    связей `traces`, которые поставила заявка `rec` (номер в тексте требования, после отсечений), а не `trace` (F-158)."""
    records = {n["number"]: n["id"] for n in reversed(nodes) if n["kind"] == "rec" and n["number"] is not None}
    scenarios: dict[str, dict[str, list[str]]] = {}
    requirements: dict[str, dict[str, str]] = {}
    sections: dict[str, str] = {}
    for n in nodes:
        if n["kind"] == "req":
            sections.setdefault(n["id"], n["section"])
        if n["kind"] == "scn":
            scenarios.setdefault(n["capability"], {}).setdefault(n["name"], []).append(n["id"])
        elif n["kind"] == "req":
            requirements.setdefault(n["capability"], {})[n["name"]] = n["id"]
    masters: list = []  # мастер-спеки читаются один раз и только если нужны (F-84)
    edges: dict[tuple, dict] = {}
    unresolved: dict[tuple, dict] = {}
    text_links: set[tuple[str, str]] = set()

    def put_edge(src: str, dst: str, kind: str, at: str, by_place: bool = False) -> None:
        """Повтор `(from, to, type)` остаётся первым; связь по следу пробы различается ещё и местом (F-82.B, F-156): две связи
        к одной записи с разными `at` — не дубль, но та же строка, что у связи из текста, второй связи не даёт."""
        if by_place and (src, dst, kind) in edges and edges[(src, dst, kind)]["at"] == at:
            return
        edges.setdefault((src, dst, kind, at) if by_place else (src, dst, kind), {"from": src, "to": dst, "type": kind, "at": at})

    def put_unresolved(claim: dict, ref: str, why: str) -> None:
        unresolved.setdefault((claim["from"], ref), {"ref": ref, "from": claim["from"], "at": claim["at"], "why": why})

    def put_records(claim: dict, text: str, skip: set, by_place: bool = False) -> None:
        for number in _record_numbers(text):
            if number in skip:
                continue
            if number in records:
                put_edge(claim["from"], records[number], "traces", claim["at"], by_place)
                if claim["kind"] == "rec":
                    text_links.add((claim["from"], records[number]))
            else:
                put_unresolved(claim, f"F-{number:02d}", f"в журнале изменения нет записи F-{number:02d}")

    def master() -> dict:
        if not masters:
            masters.append(_master_names(root))
        return masters[0]

    def parent_of(claim: dict) -> tuple[re.Match, str, str, bool]:
        """Родитель из фразы дочернего: `(совпадение фразы, capability, имя, известно ли имя)`; известны имена изменения и мастера."""
        text = claim["text"]
        m = _PARENT.match(text)
        cap = m.group(1) or claim["cap"]
        name, _, known = _take_name(text, m.end(), set(requirements.get(cap, {})) | master().get(cap, {}).get("req", set()))
        return m, cap, name, known

    def resolve_parent(claim: dict) -> None:
        """`Часть требования [`cap`: ]«имя».` (F-77, F-92): родитель в изменении — `derives`; только в мастере — ничего."""
        m, cap, name, known = parent_of(claim)
        in_change = requirements.get(cap, {})
        if name in in_change:
            put_edge(claim["from"], in_change[name], "derives", claim["at"])
        elif not known:
            put_unresolved(claim, f"`{cap}`: «{name}»" if m.group(1) else f"«{name}»",
                           f"в capability `{cap}` нет требования с именем «{name}»: ни в изменении, ни в мастер-спеке")

    def resolve_security(claim: dict) -> None:
        """Требование в строке пункта: `cap` «имя» или `cap`: «имя»; пункт — `refines` к требованию (F-135)."""
        text, pos = claim["text"], 0
        while (m := _SEC_REQ.search(text, pos)):
            cap = m.group(1)
            in_change = requirements.get(cap, {})
            name, pos, known = _take_name(text, m.end(), set(in_change) | master().get(cap, {}).get("req", set()))
            if name in in_change:
                put_edge(claim["from"], in_change[name], "refines", claim["at"])
            elif not known:  # только в мастер-спеке: ни связи, ни записи, как у derives
                put_unresolved(claim, f"`{cap}`: «{name}»", f"в capability `{cap}` нет требования с именем «{name}»")

    def resolve_branch(claim: dict) -> None:
        """`сценарий: имя` в описи ветки: сценарии изменения во всех capability; только в мастере — ничего (узла нет)."""
        text = claim["text"]
        by_name: dict[str, list[str]] = {}
        for names in scenarios.values():
            for scn, ids_ in names.items():
                by_name.setdefault(scn, []).extend(ids_)
        for m in _BRANCH_SCENARIO.finditer(text):
            in_master = {n for caps in master().values() for n in caps["scn"]}
            name = _take_scenario(text, m.end(), set(by_name) | in_master)
            if name in by_name:
                for scn_id in by_name[name]:
                    put_edge(claim["from"], scn_id, "verifies", claim["at"])
            elif name not in in_master:
                put_unresolved(claim, f"сценарий: {name}", f"сценария «{name}» нет ни в изменении, ни в мастер-спеках")

    def live(claim: dict) -> bool:
        return places[claim["from"]][0] == claim["src"]

    carried = {c["from"] for c in claims if c["kind"] == "carried" and live(c)}
    cut: dict[str, set[int]] = {}  # номера мастер-текста родителя по id дочернего требования ADDED (F-150)
    for claim in claims:
        if claim["kind"] != "parent" or claim["section"] != "ADDED" or not live(claim) or base_master is None:
            continue
        _, cap, name, known = parent_of(claim)
        parent = requirements.get(cap, {}).get(name)
        if parent is None and not known:
            continue
        if parent is not None and (sections[parent] != "MODIFIED" or parent in carried):
            continue
        entry = base_master.entry(cap, name)[0]
        if entry:
            cut.setdefault(claim["from"], set()).update(entry["numbers"])
    for claim in claims:
        if not live(claim):
            continue
        if claim["kind"] == "carried":
            continue
        if claim["kind"] == "parent":
            resolve_parent(claim)
        elif claim["kind"] == "sec":
            resolve_security(claim)
        elif claim["kind"] == "branch":
            resolve_branch(claim)
        elif claim["kind"] == "edge":
            put_edge(claim["from"], claim["to"], claim["type"], claim["at"])
        elif claim["kind"] == "rec":
            put_records(claim, claim["text"], claim["skip"] | cut.get(claim["from"], set()))
        elif claim["kind"] == "trace":
            put_records(claim, claim["text"], set(), by_place=True)
        else:
            _resolve_task_line(claim, scenarios, put_edge, put_unresolved)
            put_records(claim, claim["text"], set())
    ordered = sorted(edges.values(), key=lambda e: (e["at"].rsplit(":", 1)[0], int(e["at"].rsplit(":", 1)[1]),
                                                    e["from"], e["to"], e["type"]))
    return ordered, list(unresolved.values()), text_links


CANDIDATE_SOURCE_RECORDS = "общие записи журнала"


def parked_ids(records: list[dict]) -> set[str]:
    """Id узлов записей со статусом `припаркован` (F-157) из списка записей журнала; одно определение парковки для сборки и сигналов."""
    return {"rec:" + r["id"] for r in records if r.get("status") == "припаркован"}


def parked_records(base: Path) -> set[str]:
    """Id узлов записей журнала со статусом `припаркован` (F-157); нет файла или журнал не разбирается — пусто (отказ по
    журналу даёт читатель записей раньше)."""
    try:
        journal = json.loads(_read_text(base, "decisions.json"))
        return parked_ids(journal["records"])
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def record_candidates(edges: list[dict], parked: set[str] = frozenset()) -> list[dict]:
    """Кандидаты связей между требованиями (F-23, F-71): два требования с `traces` к одной записи журнала. Запись из `parked`
    (статус `припаркован`) кандидатов не даёт, её связь `traces` остаётся (F-157): парковка — другой механизм. Кандидат —
    `{"a", "b", "source", "shared"}`: пара неупорядоченная (`a` < `b`), встречается один раз, `shared` — общие записи по порядку,
    `source` называет способ вычисления; новый источник добавляет свои кандидаты с другим `source`, записанных связей не трогая.
    Порядок — по `(a, b)`."""
    by_record: dict[str, set[str]] = {}
    for e in edges:
        if e["type"] == "traces" and e["from"].startswith("req:") and e["to"] not in parked:
            by_record.setdefault(e["to"], set()).add(e["from"])
    pairs: dict[tuple[str, str], list[str]] = {}
    for rec in sorted(by_record):
        owners = sorted(by_record[rec])
        for i, a in enumerate(owners):
            for b in owners[i + 1:]:
                pairs.setdefault((a, b), []).append(rec)
    return [{"a": a, "b": b, "source": CANDIDATE_SOURCE_RECORDS, "shared": shared} for (a, b), shared in sorted(pairs.items())]


def build_graph_with_signals(root: Path, change: str, saved: dict | None = None) -> tuple[dict, list[dict], list[dict]]:
    """Граф, дубли id и неразрешённые ссылки; описание — у `_build_all`, четвёртое значение которой здесь отброшено."""
    return _build_all(root, change, saved)[:3]


def _build_all(root: Path, change: str, saved: dict | None = None) -> tuple[dict, list[dict], list[dict], set]:
    """Граф изменения `change` проекта `root`, список дублей id и список неразрешённых ссылок и множество `(id требования, id
    записи)` связей `traces` из текста требования (`_resolve_claims`, F-158). Граф: `format`, `nodes`, `edges`,
    `sources` (исходники сборки с хешами, `source_hashes`), `candidates`; читает только артефакты, из которых `REGISTRY` что-то берёт (F-53). Читатель отдаёт узлы и заявки на связи за
    один проход по файлу; связи разрешаются, когда собраны узлы всех артефактов (`_resolve_claims`). Пункт security —
    `refines` к требованию, ветка описи — `verifies` к сценарию, дочернее требование — `derives` к родителю (U06); `candidates` —
    пары требований с общими записями журнала (`record_candidates`), отдельно от `edges`.
    Дубль — повторный id (два требования с одним именем в capability, два сценария, два пункта security): в графе остаётся
    первый по порядку чтения, id уникальны, а дубль не теряется молча, а идёт вторым значением: `[{"id": …, "at": [место
    первого, место повторного, …]}]` в порядке появления. Неразрешённые ссылки — третье значение: `[{"ref", "from", "at",
    "why"}]`. В JSON графа оба списка не входят (формат не меняется). Мастер-спеку сборка берёт из базы снимка `graph/req-graph.json`
    (`saved_base`), а для требования без записи в ней — живую; `saved` — готовая база вместо снимка (её передаёт заморозка, F-123)."""
    base = root / "openspec" / "changes" / change
    if not base.is_dir():
        raise Refusal(f"изменения «{change}» нет: нет каталога openspec/changes/{change}")
    master = _Master(root, saved_base(base) if saved is None else saved)
    nodes, places, claims = [], {}, []
    for artifact, row in REGISTRY.items():
        if row.get("берёт") == NOTHING:
            continue
        if artifact not in READERS:
            raise Refusal(f"в реестре у артефакта «{artifact}» значение «берёт», а читателя нет: добавить читателя "
                          f"или записать `{NOTHING}` с доводом")
        for node in (READERS[artifact](base, claims, master) if artifact == "specs" else READERS[artifact](base, claims)):
            if node["id"] in places:
                places[node["id"]].append(node["at"])
            else:
                places[node["id"]] = [node["at"]]
                nodes.append(node)
    nodes.sort(key=lambda n: (n["at"].rsplit(":", 1)[0], int(n["at"].rsplit(":", 1)[1]), n["id"]))
    duplicates = [{"id": node_id, "at": at} for node_id, at in places.items() if len(at) > 1]
    edges, unresolved, text_links = _resolve_claims(root, nodes, places, claims, master)
    return {"format": GRAPH_FORMAT, "sources": source_hashes(base), "nodes": nodes, "edges": edges,
            "candidates": record_candidates(edges, parked_records(base))}, duplicates, unresolved, text_links


# --- состав исходников и проверка сохранённого файла (F-41, F-86, F-87, F-118) ---------------------------------------
# Исходник — файл изменения, который читает сборка: у артефакта реестра со значением «берёт» не `ничего` (`specs/*/spec.md`
# у `specs`, один файл у остальных). Мастер-спеки в `sources` не входят: их смену учитывает база мастера (F-123).

SOURCE_FILES = {"decisions": "decisions.json", "consequences": "consequences.md", "security": "security.md",
                "tasks": "tasks.md"}
GRAPH_FIELDS = {"format": int, "sources": list, "nodes": list, "edges": list, "candidates": list}


def _lf_hash(path: Path) -> str:
    """sha256 содержимого после приведения CRLF и одиночного CR к LF: `.gitattributes` держит `*.md` с `eol=crlf`, и
    байтовый хеш расходился бы при том же содержимом (F-87)."""
    return hashlib.sha256(re.sub(rb"\r\n?", b"\n", path.read_bytes())).hexdigest()


def source_hashes(base: Path) -> list[dict]:
    """Исходники сборки изменения `base`: `[{"path", "sha256"}]` по пути от каталога изменения, с `/`, в порядке пути."""
    rels = []
    for artifact, row in REGISTRY.items():
        if row.get("берёт") == NOTHING:
            continue
        if artifact == "specs":
            folders = [p for p in (base / "specs").iterdir() if p.is_dir()] if (base / "specs").is_dir() else []
            rels += [f"specs/{p.name}/spec.md" for p in folders]
        elif artifact in SOURCE_FILES:
            rels.append(SOURCE_FILES[artifact])
    return [{"path": rel, "sha256": _lf_hash(base / rel)} for rel in sorted(set(rels)) if (base / rel).is_file()]


def _shape_problems(data) -> list[str]:
    if not isinstance(data, dict):
        return ["верхний уровень не объект JSON"]
    problems = [f"нет поля `{name}`" for name in GRAPH_FIELDS if name not in data]
    problems += [f"поле `{name}` не того вида (ждали {kind.__name__})" for name, kind in GRAPH_FIELDS.items()
                 if name in data and not isinstance(data[name], kind)]
    if not problems and data["format"] != GRAPH_FORMAT:
        problems.append(f"формат {data['format']}, а скрипт читает {GRAPH_FORMAT}")
    if isinstance(data.get("sources"), list):
        for item in data["sources"]:
            if not (isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("sha256"), str)):
                problems.append("в `sources` есть элемент без `path` и `sha256`")
                break
    return problems


def _stale_problems(base: Path, saved: list[dict]) -> list[str]:
    old = {item["path"]: item["sha256"] for item in saved}
    now = {item["path"]: item["sha256"] for item in source_hashes(base)}
    return ([f"{rel}: исходник изменён после сборки" for rel in sorted(old.keys() & now.keys()) if old[rel] != now[rel]]
            + [f"{rel}: новый исходник, в графе его нет" for rel in sorted(now.keys() - old.keys())]
            + [f"{rel}: исходник удалён" for rel in sorted(old.keys() - now.keys())])


def _item_key(item) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def _item_label(name: str, item) -> str:
    if not isinstance(item, dict):
        return _item_key(item)
    return f"{item.get('from')} -{item.get('type')}-> {item.get('to')}" if name == "edges" else f"{item.get('a')} / {item.get('b')}"


def _pathless(value, root: Path):
    """Копия значения JSON, где во всех строках сняты абсолютные пути (F-59): так снимок хранится и так он сверяется."""
    if isinstance(value, str):
        return no_paths(value, root)
    if isinstance(value, list):
        return [_pathless(item, root) for item in value]
    if isinstance(value, dict):
        return {_pathless(key, root): _pathless(item, root) for key, item in value.items()}
    return value


def _diff_problems(saved: dict, fresh: dict, root: Path) -> list[str]:
    """Расхождение узлов, связей и кандидатов файла со свежей сборкой (F-118): что лишнее, чего нет, что поправлено.
    Обе стороны идут без абсолютных путей: снимок их не хранит (F-59), и имя узла с путём не должно делать его «поправленным»."""
    saved, fresh = _pathless(saved, root), _pathless(fresh, root)
    problems = []
    got = {n.get("id"): n for n in saved["nodes"] if isinstance(n, dict)}
    want = {n["id"]: n for n in fresh["nodes"]}
    problems += [f"в файле лишний узел {node_id}" for node_id in sorted(map(str, got.keys() - want.keys()))]
    problems += [f"в файле нет узла {node_id}" for node_id in sorted(want.keys() - got.keys())]
    problems += [f"узел {node_id} в файле поправлен" for node_id in sorted(got.keys() & want.keys())
                 if got[node_id] != want[node_id]]
    for name in ("edges", "candidates"):
        have = {_item_key(e): e for e in saved[name]}
        need = {_item_key(e): e for e in fresh[name]}
        problems += [f"в `{name}` файла лишнее или поправленное: {_item_label(name, have[key])}"
                     for key in sorted(have.keys() - need.keys())]
        problems += [f"в `{name}` файла нет или не такое, как в сборке: {_item_label(name, need[key])}"
                     for key in sorted(need.keys() - have.keys())]
    return problems


def check_graph_file(root: Path, change: str, path: Path | str) -> list[str]:
    """Сигналы проверки сохранённого файла графа `path` изменения `change`: список строк `[!!] …`, пустой — сигналов нет.
    Ничего не печатает и код выхода не трогает (F-31); её зовёт `cmd_check` и зовёт заморозка на `graph/req-graph.json`.
    Нет изменения — `Refusal`. Порядок: форма; затем состав и хеши исходников (хеш после приведения к LF, F-87); только у
    файла, свежего по хешам, узлы и связи сверяются со свежей сборкой (F-118): у устаревшего расхождение — следствие, а не
    правка. Свежая сборка берёт мастер-спеку из базы снимка `graph/req-graph.json`, поэтому после `/opsx:sync` она совпадает с
    файлом (F-123)."""
    base = root / "openspec" / "changes" / change
    if not base.is_dir():
        raise Refusal(f"изменения «{change}» нет: нет каталога openspec/changes/{change}")
    path = Path(path)

    def signals(kind: str, texts: list[str]) -> list[str]:
        return [f"[!!] {path}: {kind}: {text}" for text in texts]

    try:
        data = json.loads(path.read_bytes().decode("utf-8-sig"))
    except OSError as e:
        return signals("форма не та", [f"файл не прочитан ({e.strerror or e})"])
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return signals("форма не та", [f"файл не разбирается как JSON ({e})"])
    problems = _shape_problems(data)
    if problems:
        return signals("форма не та", problems)
    stale = _stale_problems(base, data["sources"])
    if stale:
        return signals("устарел", stale)
    return signals("узел поправлен", _diff_problems(data, build_graph(root, change), root))


# --- текст диаграммы по графу (F-54, F-71, F-103, F-120) ------------------------------------------------------------
# `build --format mermaid` отдаёт текст `requirementDiagram` по графу: всё изменение, `--capability` (cap, её требования и
# сценарии, плюс связанные с ними задачи, записи, пункты security и ветки) или `--requirement` (требование, его сценарии,
# связанные задачи, записи, пункты security и ветки, соседи по кандидатам связью `copies`). Конфиг — `DIAGRAM`. Номер узла
# стоит в имени блока (`SCN_12 Есть поле`): имя и есть ключ узла в mermaid, номер делает его уникальным (F-67, F-68);
# подчёркивание, а не дефис: хук принимает номер с дефисом за ключ задачи (F-73). Имя с номером не длиннее `DIAGRAM["имя"]`
# знаков (F-137). Без выбора и с `--capability` текст длиннее `DIAGRAM["предел"]` не выдаётся (F-66, F-104).

DIAGRAM_HEADER = "requirementDiagram"


ENTITY = re.compile(r"#\w+;")  # коды сущностей mermaid: `#37;`, `#x25;`, `#lt;`, `#percnt;` декодируются в знак


def clean_text(text: str) -> str:
    """Строка для имени, `text` и `docref`: без `%%` (директива в имени меняет настройки всей диаграммы, F-59), без угловых
    скобок и кодов сущностей mermaid (`#lt;`, `#60;`, `#37;`: иначе знак возвращается при разборе), двойная кавычка заменена
    апострофом (иначе рвёт строку, F-15), пробельные подряд — один пробел. Снятие повторяется до неподвижной точки:
    `%<%{init}%>%` после снятия скобок иначе схлопывается в `%%`."""
    text = str(text)
    while True:
        cleaned = ENTITY.sub("", text.replace("<", "").replace(">", "")).replace("%%", "")
        if cleaned == text:
            break
        text = cleaned
    return " ".join(text.replace('"', "'").split())


def diagram_ident(node: dict, counters: dict[str, int]) -> str:
    """Номер узла с префиксом вида: запись и задача берут его из себя (`REC_19`, `TASK_3.2`), остальные считаются по виду
    внутри диаграммы (`SCN_12`). `counters` растёт на один у узлов, чей номер порядковый (F-68)."""
    kind = node["kind"]
    prefix = DIAGRAM["виды"][kind]["префикс"]
    if kind == "rec" and node.get("number") is not None:
        return f"{prefix}_{node['number']}"
    if kind == "task":
        return f"{prefix}_{clean_text(node['id'].split(':', 1)[1]).replace(' ', '')}"
    counters[kind] = counters.get(kind, 0) + 1
    return f"{prefix}_{counters[kind]}"


def diagram_name(node: dict, ident: str) -> str:
    """Имя блока: номер и начало подписи узла, вместе не длиннее `DIAGRAM["имя"]` знаков (F-137), очищено `clean_text`."""
    return clean_text(f"{ident} {node['name']}")[:DIAGRAM["имя"]].rstrip()


def _find_requirement(graph: dict, wanted: str) -> dict:
    reqs = [n for n in graph["nodes"] if n["kind"] == "req"]
    found = [n for n in reqs if n["id"] == f"req:{wanted}"] or [n for n in reqs if n["name"] == wanted]  # `capability/имя` (F-103)
    if len(found) == 1:
        return found[0]
    if found:
        forms = ", ".join(f"`{n['capability']}/{n['name']}`" for n in found)
        raise Refusal(f"требование «{wanted}» есть в нескольких capability: укажи {forms}")
    known = ", ".join(sorted(f"{n['capability']}/{n['name']}" for n in reqs)) or "требований нет"
    raise Refusal(f"требования «{wanted}» в изменении нет; известные: {known}")


def select_diagram(graph: dict, capability: str | None = None, requirement: str | None = None) -> tuple[list[dict], list[dict]]:
    """Часть графа для диаграммы: `(узлы в порядке графа, связи from/to/type)`. Связь входит, если выбраны оба конца.
    Кандидаты идут связью `candidate` только при выборе требования, соседями (F-71); без выбора — всё изменение."""
    if capability is None and requirement is None:
        return graph["nodes"], [{"from": e["from"], "to": e["to"], "type": e["type"]} for e in graph["edges"]]
    nodes = {n["id"]: n for n in graph["nodes"]}
    chosen: set[str] = set()
    extra: list[dict] = []
    if capability is not None:
        if f"cap:{capability}" not in nodes:
            known = ", ".join(sorted(n["name"] for n in nodes.values() if n["kind"] == "cap")) or "capability нет"
            raise Refusal(f"capability «{capability}» в изменении нет; известные: {known}")
        core = {i for i, n in nodes.items() if i == f"cap:{capability}" or n.get("capability") == capability}
        attach = ("task", "rec", "sec", "branch")
    else:
        req = _find_requirement(graph, requirement)
        core = {req["id"]} | {i for i, n in nodes.items() if n["kind"] == "scn" and n["requirement"] == req["id"]}
        attach = ("task", "rec", "sec", "branch")
        for cand in graph["candidates"]:
            if req["id"] in (cand["a"], cand["b"]):
                chosen.update((cand["a"], cand["b"]))
                extra.append({"from": cand["a"], "to": cand["b"], "type": "candidate"})
    chosen |= core
    for edge in graph["edges"]:
        for near, far in ((edge["from"], edge["to"]), (edge["to"], edge["from"])):
            if near in core and nodes[far]["kind"] in attach:
                chosen.add(far)
    edges = [{"from": e["from"], "to": e["to"], "type": e["type"]} for e in graph["edges"]
             if e["from"] in chosen and e["to"] in chosen] + extra
    return [n for n in graph["nodes"] if n["id"] in chosen], edges


def _classdef(row: dict) -> str:
    dash = f",stroke-dasharray:{row['штрих']}" if row.get("штрих") else ""
    return f"classDef {row['класс']} fill:{row['заливка']},stroke:{row['рамка']},stroke-width:{row['ширина']}{dash}"


def _block(node: dict, name: str, ident: str, row: dict) -> list[str]:
    if row["sysml"] == "element":
        return [f'element "{name}" {{', f'    type: "{row["type"]}"', f'    docref: "{clean_text(node["at"])}"', "}"]
    if node["kind"] == "req":
        text = f"{node['capability']}, {node['section']}"
    else:
        text = node["name"] if node["kind"] == "sec" else "capability"
    return [f'{row["sysml"]} "{name}" {{', f'    id: "{ident}"', f'    text: "{clean_text(text)}"', "}"]


def _render(nodes: list[dict], edges: list[dict]) -> str:
    """Текст по отобранной части: шапка, `classDef`, блоки, связи, `class` — `class` строго после блоков, иначе цвет молча
    не применится (F-54)."""
    kinds = DIAGRAM["виды"]
    counters: dict[str, int] = {}
    idents = {n["id"]: diagram_ident(n, counters) for n in nodes}
    names = {n["id"]: diagram_name(n, idents[n["id"]]) for n in nodes}
    lines = [DIAGRAM_HEADER, "direction LR"] + [_classdef(row) for row in kinds.values()]
    for node in nodes:
        lines += _block(node, names[node["id"]], idents[node["id"]], kinds[node["kind"]])
    for edge in edges:
        lines.append(f'"{names[edge["from"]]}" - {DIAGRAM["связи"][edge["type"]]} -> "{names[edge["to"]]}"')
    lines += [f'class "{names[n["id"]]}" {kinds[n["kind"]]["класс"]}' for n in nodes]
    return "\n".join(lines) + "\n"


def _part(graph: dict, capability: str | None = None, requirement: str | None = None) -> tuple[int, int]:
    """`(число узлов, размер текста)` части графа: для подсказки отказа по пределу."""
    nodes, edges = select_diagram(graph, capability, requirement)
    return len(nodes), len(_render(nodes, edges))


def _over_limit(graph: dict, size: int, capability: str | None) -> Refusal:
    """Отказ по пределу с подсказкой, чем выбрать меньше: без выбора — capability, с `--capability` — её требования (F-66, F-104)."""
    limit = DIAGRAM["предел"]
    if capability is None:
        rows = [(n["name"], *_part(graph, n["name"])) for n in graph["nodes"] if n["kind"] == "cap"]
        hint = "выбери часть: `--capability <имя>`; у каждой capability"
        what = "capability"
    else:
        rows = [(f"{n['capability']}/{n['name']}", *_part(graph, requirement=f"{n['capability']}/{n['name']}"))
                for n in graph["nodes"] if n["kind"] == "req" and n["capability"] == capability]
        hint = "выбери меньше: `--requirement <capability/имя>` (у него предела нет); у каждого требования"
        what = "требование"
    lines = [f"  {name}: {nodes} узл., {chars} знаков" for name, nodes, chars in rows]
    head = f"текст диаграммы {size} знаков, предел {limit}: {hint} число узлов и размер текста:"
    return Refusal("\n".join([head] + lines) if lines else f"текст диаграммы {size} знаков, предел {limit}: {what} для выбора нет")


def diagram_text(graph: dict, capability: str | None = None, requirement: str | None = None) -> str:
    """Текст `requirementDiagram` по графу и выбору. Без выбора и с `capability` длиннее `DIAGRAM["предел"]` — `Refusal`
    с подсказкой; у `requirement` предела нет (F-104)."""
    nodes, edges = select_diagram(graph, capability, requirement)
    text = _render(nodes, edges)
    if requirement is None and len(text) > DIAGRAM["предел"]:
        raise _over_limit(graph, len(text), capability)
    return text


def cmd_build(args: argparse.Namespace, root: Path) -> int:
    if args.format != "mermaid" and (args.capability or args.requirement):
        raise Refusal("--capability и --requirement выбирают часть диаграммы: нужен `--format mermaid`")
    graph, duplicates = build_graph_with_duplicates(root, args.change)
    for dup in duplicates:  # сигнал, не стоп (F-31): граф печатается, код 0
        print(f"[!!] дубль id {dup['id']}: места {', '.join(dup['at'])}; в графе остался первый", file=sys.stderr)
    if args.format == "mermaid":
        text = diagram_text(graph, args.capability, args.requirement)
    else:
        text = json.dumps(graph, ensure_ascii=False, indent=1) + "\n"
    if args.out is None:
        sys.stdout.write(text)
        return 0
    try:  # путь задаёт вызывающий: от текущего каталога или абсолютный, границы прав тут нет (F-41)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
    except OSError as e:
        raise Refusal(f"граф не записан в {args.out}: {e.strerror or e}") from e
    return 0


# --- отчёт: находки validate и сигналы графа (F-31, F-32, F-93, F-138) ----------------------------------------------
# Отчёт — Markdown. Сигнал — строка `[!!] <вид>: <ключ> — <место>`: ключ — id узла без префикса вида, место — `путь:строка`
# от каталога изменения. Виды добавляют в `graph_signals` по одному (U10, U11); сигнал кода выхода не меняет.

VALIDATE_ARGS = ("--type", "change", "--json", "--strict", "--no-interactive")
NO_SIGNALS = "Сигналов нет."


def _not_started(reason: str, root: Path) -> list[str]:
    return [f"[!!] validate не запустился: {no_paths(' '.join(reason.split()), root)}"]


def validate_findings(root: Path, change: str) -> list[str]:
    """Строки раздела «Находки openspec validate»: `openspec validate <имя> --json` через общий `run_fork`. Код 1 с JSON, где
    есть `items`, — находки, а не сбой (`validate.ts`: `exitCode = valid ? 0 : 1`). Ответ без `items` (`unknown_item`), не
    JSON, код не из 0 и 1, форк не найден или не ответил за предел — одна строка «validate не запустился» с причиной без
    абсолютных путей (F-93). Не печатает; имя проверяет `check_change_name` первой строкой (`run_fork` проверяет только
    `change=`, а здесь имя идёт позиционным аргументом): негодное — `ForkError`, форк не вызван."""
    check_change_name(change)
    try:
        reply = run_fork(root, "validate", change, *VALIDATE_ARGS)
    except ForkError as e:
        return _not_started(str(e), root)
    try:
        data = json.loads(reply.out)
    except ValueError:
        tail = (reply.err or reply.out).strip().splitlines()
        return _not_started(f"ответ не JSON, код {reply.code}" + (f": {tail[0][:200]}" if tail else ""), root)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items or reply.code not in (0, 1):
        return _not_started(f"ответ без находок `items`, код {reply.code}", root)
    lines = []
    invalid = reply.code == 1
    for item in items:
        issues = item.get("issues") if isinstance(item, dict) else None
        invalid = invalid or not isinstance(item, dict) or item.get("valid") is False
        for issue in issues if isinstance(issues, list) else []:
            if isinstance(issue, dict):
                lines.append(no_paths(f"[!!] openspec validate: {issue.get('level', '?')} {issue.get('path', '')}: "
                                      f"{' '.join(str(issue.get('message', '')).split())}", root))
    if invalid and not lines:  # невалидно, а строк нет: чистым отчёт выглядеть не должен (F-93)
        lines.append("[!!] openspec validate: изменение невалидно, а находок в ответе нет")
    return lines


DIVERGED = "сценарий MODIFIED с прежним именем и другим текстом"  # вид F-95: в отчёте идёт отдельным разделом
DIVERGED_TITLE = "Расхождения сценариев MODIFIED"
UNBASED = "у требования MODIFIED нет базы мастер-спеки, текст совпал с мастером, номера в нём не отсечены"  # F-123
UNBASED_TITLE = "Требования MODIFIED без базы мастер-спеки"
_TRACE_COMMENT = re.compile(r"<!--(.*?)-->")
_TRACE_PAIR = re.compile(r"(?<![\w-])F-(\d+)\s+(открыт|" + "|".join(PROBE_OUTCOMES) + r")(?!\w)")
_QUOTE_LIMIT = 110
_SERVICE_MARK = re.compile(r"(?<!`)`служебная`$")  # пометка служебной задачи: только в backticks и только в конце строки (F-43, F-90)
_SCENARIO_MARK = re.compile(r"^\s*<!--\s*(.*?)\s*-->\s*$")  # комментарий на всю строку; сам номер — по `_REC_REF`
_MARK_BODY = re.compile(r"F-\d+(?:\s*,\s*F-\d+)*")
_SIGNAL_QUESTION = re.compile(r"^\[сигнал\]\s+(.+?)\s+·\s+(.+)$")  # `[сигнал] <вид> · <ключ>` (F-47, F-98)


def _squash(text: str) -> str:
    """Текст без различий в пробелах и концах строк: так сверяются сценарии и требования с мастер-спекой (F-95)."""
    return " ".join(text.split())


def _md(text: str) -> str:
    """Угловые скобки без кода ломают плагин md4h: голые заменяются сущностями."""
    return text.replace("<", "&lt;").replace(">", "&gt;")


def _short(text: str) -> str:
    text = _squash(text)
    return text if len(text) <= _QUOTE_LIMIT else text[:_QUOTE_LIMIT - 1] + "…"


def _trace_comments(lines: list[str]) -> list[tuple[int, str, list[tuple[int, str]]]]:
    """Следы проб вне блоков кода: `(номер строки, комментарий без лишних пробелов, [(номер записи, слово)])`."""
    mask = _fence_mask(lines)
    found = []
    for number, line in enumerate(lines, 1):
        comment = _TRACE_COMMENT.search(line)
        if not mask[number - 1] and comment and "проба" in comment.group(1) and "исходы:" in comment.group(1):
            tail = comment.group(1).split("исходы:", 1)[1]
            found.append((number, _squash(comment.group(1)), [(int(m.group(1)), m.group(2)) for m in _TRACE_PAIR.finditer(tail)]))
    return found


def _scenario_marks(lines: list[str], mask: list[bool], heading: int) -> set[int]:
    """Номера записей из комментариев `<!-- F-NN -->` сразу под заголовком сценария (строка `heading`, с 1; F-45): подряд идущие
    строки-комментарии, пустые строки между ними не мешают, первая другая строка или блок кода обрывает. Комментарий не из
    номеров (`<!-- требование из F-116 -->`) пропускается и не обрывает."""
    found = set()
    for i in range(heading, len(lines)):
        if mask[i]:
            break
        if not lines[i].strip():
            continue
        comment = _SCENARIO_MARK.match(lines[i])
        if not comment:
            break
        if _MARK_BODY.fullmatch(comment.group(1)):
            found.update(_record_numbers(comment.group(1)))
    return found


def signal_context(root: Path, change: str, saved: dict | None = None) -> dict:
    """Данные для сигналов, которых нет в графе (U10): `records` — записи журнала (адресат, решение, исход; снимок графа
    ими не раздувается), `modified` — по требованию MODIFIED: `carried` (текст требования как в мастер-спеке; о сценариях говорит `scenarios`) и
    `scenarios` {id сценария: `same`, `new` или `changed`} по имени и тексту с приведением пробелов и концов строк (F-95),
    `traces` — следы проб `<!-- проба …, исходы: F-NN Исход -->` как `(место, номер, слово)`; след в требовании MODIFIED,
    дословно стоящий в том же требовании мастер-спеки, не входит: его номера из журнала другого изменения. `marks` — номера
    записей из комментариев `<!-- F-NN -->` под заголовками сценариев (F-45); сценарий MODIFIED, перенесённый из мастера без
    изменения, своих номеров не даёт: они из журнала другого изменения. `unbased` — `[(id требования, место)]` MODIFIED, у которых
    базы нет, а текст совпал с мастером (F-123). Мастер-спеку берёт из базы снимка, для требования без записи в ней — живую
    (`_Master`); `saved` — готовая база вместо снимка. `text_links` — `{(id требования, id записи)}`: связи `traces`, которые дали
    номера в тексте требования после всех отсечений F-84, F-147, F-150 (F-158); берётся из `_resolve_claims` той же сборки графа,
    второго разбора нет (граф собирается ещё раз). Только читает."""
    base = root / "openspec" / "changes" / change
    if not base.is_dir():
        raise Refusal(f"изменения «{change}» нет: нет каталога openspec/changes/{change}")
    master = _Master(root, saved_base(base) if saved is None else saved)
    try:
        records = json.loads(_read_text(base, "decisions.json"))["records"] if (base / "decisions.json").is_file() else []
    except (ValueError, KeyError, TypeError):
        records = []  # негодный журнал сборка графа уже назвала отказом
    modified, traces, marks, unbased = {}, [], set(), []
    folders = sorted(p for p in (base / "specs").iterdir() if p.is_dir()) if (base / "specs").is_dir() else []
    for folder in folders:
        rel = f"specs/{folder.name}/spec.md"
        if not (base / rel).is_file():
            continue
        text = _read_text(base, rel)
        parsed, cap = parse_spec(text), folder.name
        entries = {}  # запись мастера по имени требования MODIFIED: (запись или None, из базы ли); номера в ней из другого журнала (F-84)
        for item in parsed.requirements:
            if item.section == "MODIFIED" and item.name not in entries:
                entries[item.name] = master.entry(cap, item.name)
        lines = _spec_lines(text)
        for number, comment, pairs in _trace_comments(lines):
            owner = max((r for r in parsed.requirements if r.line <= number), key=lambda r: r.line, default=None)
            entry = entries[owner.name][0] if owner and owner.section == "MODIFIED" else None
            if entry and _hash(comment) in entry["traces"]:
                continue  # дословно стоит в том же требовании мастера: след прежнего изменения
            traces += [(f"{rel}:{number}", num, word) for num, word in pairs]
        for item in parsed.requirements:
            if item.section != "MODIFIED":
                continue
            entry, from_base = entries[item.name]
            old_text = entry["scenarios"] if entry else {}
            state = {}
            for scn in item.scenarios:
                state[f"scn:{cap}/{item.name}/{scn.name}"] = ("new" if scn.name not in old_text else
                                                              "same" if old_text[scn.name] == _hash(scn.text) else "changed")
            carried = entry is not None and entry["text"] == _hash(item.text)
            if f"req:{cap}/{item.name}" not in modified:
                modified[f"req:{cap}/{item.name}"] = {"carried": carried, "scenarios": state}
                if _carried_without_base(entry, from_base, item):
                    unbased.append((f"req:{cap}/{item.name}", f"{rel}:{item.line}"))
        mask = _fence_mask(lines)
        for item in parsed.requirements:
            state = modified.get(f"req:{cap}/{item.name}", {}).get("scenarios", {}) if item.section == "MODIFIED" else {}
            for scn in item.scenarios:
                if state.get(f"scn:{cap}/{item.name}/{scn.name}") != "same":
                    marks |= _scenario_marks(lines, mask, scn.line)
    return {"records": records, "modified": modified, "traces": traces, "marks": marks, "unbased": unbased,
            "text_links": _build_all(root, change, saved)[3]}


def _stale_trace(rec: dict, word: str) -> str | None:
    """Чем журнал расходится со словом следа (`открыт` или исход пробы), или `None`, если сходится (F-64)."""
    outcome = rec.get("outcome") or {}
    actual = outcome.get("value") if outcome.get("kind") == "проба" else None
    decision = rec.get("decision")
    if word == "открыт":
        return (f"в журнале исход «{actual}»" if actual else f"в журнале выбран вариант {decision['option']}") \
            if (actual or decision) else None
    return f"в журнале исход «{actual}»" if actual and actual != word else None


def graph_signals(graph: dict, duplicates: list[dict] | None = None, unresolved: list[dict] | None = None,
                  context: dict | None = None) -> list[str]:
    """Сигналы графа строками `[!!] вид: ключ — место`, порядок по месту в файле (F-57, F-64, F-65, F-83, F-94, F-95). Ключ — id
    без префикса вида. Из графа и списков сборки: «требование без задачи» и «сценарий без задачи» (ADDED), «требование без
    записи» (гасит только номер в тексте требования: связь из следа пробы и к записи-парковке нет, F-158; без `context`
    опоры нет и сигнал стоит у каждого требования), «неоднозначное имя» (дубль id из `duplicates`; одно имя сценария у двух требований capability при задаче с этим
    именем), «неизвестное имя или номер» (`unresolved`), «задача ни к чему» (кроме служебной: `служебная` в конце строки). Из `context` (`signal_context`): «критерий без
    требования», «решение без требования и задачи», «след отстал от журнала», «Specify без сценария» (рядом «снято F-NN?» от решённой записи
    с этой в `depends_on`) и «Backstop без задачи» по исходу пробы, в MODIFIED новые сценарии («сценарий без
    задачи») и сценарии с прежним именем и другим текстом (`DIVERGED`); без `context` MODIFIED и записи журнала не читаются.
    Сигнал, на который есть запись `[сигнал] <вид> · <ключ>` с решением, молчит (вид и ключ как в строке, пробелы приведены; F-47,
    F-98); запись без решения не снимает ничего (F-114). Молчат: улика, разошедшаяся с файлом (её называет `check`), перенесённое из мастера без изменения текста, решение
    «Оставить как есть», исходы Dismiss и Defer и кандидаты связей между требованиями (F-71). Не печатает."""
    context = context or {}
    edges = graph["edges"]
    closed = {e["to"] for e in edges if e["type"] == "satisfies"}
    unresolved = unresolved or []
    by_req: dict[str, list[dict]] = {}
    by_name: dict[tuple, list[dict]] = {}
    for n in graph["nodes"]:
        if n["kind"] == "scn":
            by_req.setdefault(n["requirement"], []).append(n)
            by_name.setdefault((n["capability"], n["name"]), []).append(n)
    found = []

    answered = set()  # (вид, ключ) сигналов, на которые человек ответил записью `[сигнал]` с решением (F-47, F-98, F-114)
    for rec in context.get("records", []):
        asked = _SIGNAL_QUESTION.match(_squash(rec.get("question", "")))
        if asked and rec.get("decision"):
            answered.add((asked.group(1), asked.group(2)))

    def add(at: str, kind: str, key: str, places: str | None = None) -> None:
        if (_squash(kind), _squash(key)) not in answered:
            found.append((at, _md(f"[!!] {kind}: {key} — {places or at}")))

    parked = parked_ids(context.get("records", []))
    # опора сигнала — номер в тексте требования (`text_links` из сборки графа): след пробы и парковка её не дают (F-158, F-157);
    # без `text_links` опоры нет
    named_traces = {src for src, dst in context.get("text_links", set()) if dst not in parked}
    bad_number = {u["from"] for u in unresolved if u["ref"].startswith("F-")}
    modified = context.get("modified", {})
    for req in (n for n in graph["nodes"] if n["kind"] == "req"):
        scenarios, key = by_req.get(req["id"], []), req["id"][4:]
        section = req.get("section")
        if section == "ADDED":
            if not any(s["id"] in closed for s in scenarios):
                add(req["at"], "требование без задачи", key)
            for s in scenarios:
                if s["id"] not in closed:
                    add(s["at"], "сценарий без задачи", s["id"][4:])
        elif section == "MODIFIED" and req["id"] in modified:
            state = modified[req["id"]]["scenarios"]
            for s in scenarios:
                if s["id"] not in closed and state.get(s["id"]) in ("new", "changed"):
                    add(s["at"], "сценарий без задачи" if state[s["id"]] == "new" else DIVERGED, s["id"][4:])
        counted = section == "ADDED" or (section == "MODIFIED" and req["id"] in modified and not modified[req["id"]]["carried"])
        if counted and req["id"] not in named_traces and req["id"] not in bad_number:
            add(req["at"], "требование без записи", key)
    for dup in duplicates or []:
        add(dup["at"][0], "неоднозначное имя", dup["id"].split(":", 1)[1] + " (повторный id)", ", ".join(dup["at"]))
    for (cap, name), same in by_name.items():
        owners = sorted({s["requirement"] for s in same})
        if len(owners) > 1 and any(s["id"] in closed for s in same):
            names = ", ".join("«" + o.split("/", 1)[1] + "»" for o in owners)
            add(same[0]["at"], "неоднозначное имя", f"{cap}/{name} (у требований {names}; задача закрыла все)",
                ", ".join(s["at"] for s in same))
    for u in unresolved:
        add(u["at"], "неизвестное имя или номер", f"{u['ref']} (у {u['from'].split(':', 1)[1]}): {u['why']}")
    unresolved_from = {u["from"] for u in unresolved}
    for task in (n for n in graph["nodes"] if n["kind"] == "task"):
        if task["id"] not in unresolved_from and not any(e["from"] == task["id"] and e["type"] in ("satisfies", "traces")
                                                         for e in edges):
            if not _SERVICE_MARK.search(task["name"]):  # служебная задача висящей не считается (F-43)
                add(task["at"], "задача ни к чему", task["id"][5:])
    if context:
        reached = {"req": {e["to"] for e in edges if e["type"] == "traces" and e["from"].startswith("req:")},
                   "task": {e["to"] for e in edges if e["type"] == "traces" and e["from"].startswith("task:")}}
        for rec in context["records"]:
            node = next((n for n in graph["nodes"] if n["id"] == "rec:" + rec["id"]), None)
            at = node["at"] if node else "decisions.json:1"
            decision = rec.get("decision")
            if rec["kind"] == "факт" and rec.get("addressee") == "постановка" and "rec:" + rec["id"] not in reached["req"]:
                quote = next((e["quote"] for e in rec.get("evidence", []) if e.get("quote")), rec["question"])
                add(at, "критерий без требования", f"{rec['id']} «{_short(quote)}»")
            elif rec["kind"] == "развилка" and (rec.get("outcome") or {}).get("kind") == "проба":
                word, number = rec["outcome"]["value"], re.search(r"\d+", rec["id"])
                if word == "Specify" and number and int(number.group()) not in context.get("marks", ()):
                    lifting = [r["id"] for r in context["records"] if (r.get("decision") or r.get("status") == "решён")
                               and rec["id"] in [d.split(".")[0] for d in r.get("depends_on", [])]]  # F-46: `F-12.A` называет F-12
                    add(at, "Specify без сценария", rec["id"], ", ".join([at, *(f"снято {i}?" for i in lifting)]))
                elif word == "Backstop" and "rec:" + rec["id"] not in reached["task"]:
                    add(at, "Backstop без задачи", rec["id"])
            elif rec["kind"] == "развилка" and decision:
                text = next((o["text"] for o in rec["options"] if o["letter"] == decision["option"]), "")
                if text.strip().lower().startswith("оставить как есть"):
                    continue
                if "rec:" + rec["id"] not in reached["req"] | reached["task"]:
                    add(at, "решение без требования и задачи", f"{rec['id']}.{decision['option']} {_short(rec['question'])}")
        records = {int(re.search(r"\d+", r["id"]).group()): r for r in reversed(context["records"]) if re.search(r"\d+", r["id"])}
        for at, number, word in context["traces"]:
            rec = records.get(number)
            why = _stale_trace(rec, word) if rec else None
            if why:
                add(at, "след отстал от журнала", f"F-{number:02d}: в следе «{word}», {why}")
    found.sort(key=lambda f: (f[0].rsplit(":", 1)[0], int(f[0].rsplit(":", 1)[1])))
    return [line for _, line in found]


def service_tasks(graph: dict) -> list[str]:
    """Номера задач с пометкой `служебная` в конце строки, по порядку в `tasks.md` (F-43, F-90)."""
    return [n["id"][5:] for n in graph["nodes"] if n["kind"] == "task" and _SERVICE_MARK.search(n["name"])]


def service_line(graph: dict) -> str:
    """Строка отчёта «Служебных задач: N (номера).» или пустая, если таких задач нет; это сведение, а не сигнал (F-116)."""
    numbers = service_tasks(graph)
    return f"Служебных задач: {len(numbers)} ({', '.join(numbers)})." if numbers else ""


def build_report(root: Path, change: str, saved: dict | None = None) -> str:
    """Текст отчёта изменения `change`: находки `openspec validate`, сигналы графа и отдельным разделом расхождения сценариев
    MODIFIED (F-95); без всех трёх — фраза, что сигналов нет. Ничего не печатает и не пишет (её зовёт `freeze` для
    `graph/report.md`); абсолютных путей в тексте нет (F-59). Имя проверяется до любого пути и вызова форка; нет изменения или
    негоден журнал — `Refusal`, форк тогда не вызван. Мастер-спека — из базы снимка, для требования без записи в ней живая; MODIFIED
    без базы, чей текст уже совпал с мастером, называется отдельным разделом (`UNBASED_TITLE`, F-123). `saved` — готовая база
    вместо снимка (её передаёт заморозка)."""
    check_change_name(change)
    graph, duplicates, unresolved = build_graph_with_signals(root, change, saved)
    context = signal_context(root, change, saved)
    findings = [_md(line) for line in validate_findings(root, change)]  # и находки: `<путь>` от `no_paths` голой скобкой не остаётся
    every = [_md(no_paths(line, root)) for line in graph_signals(graph, duplicates, unresolved, context)]
    unbased = [_md(no_paths(f"[!!] {UNBASED}: {rid[4:]} — {place}", root)) for rid, place in context["unbased"]]
    signals = [line for line in every if not line.startswith(f"[!!] {DIVERGED}:")]
    diverged = [line for line in every if line.startswith(f"[!!] {DIVERGED}:")]
    parts = [f"# Отчёт по изменению {change}", ""]
    service = service_line(graph)  # сведение отдельной строкой, «Сигналов нет.» не отменяет (F-116)
    if not findings and not every and not unbased:
        return "\n".join([*parts, NO_SIGNALS, "", *([service, ""] if service else [])])
    sections = [("Находки openspec validate", findings, "Находок нет."), ("Сигналы графа", signals, "Сигналов графа нет.")]
    if diverged:
        sections.append((DIVERGED_TITLE, diverged, ""))
    if unbased:
        sections.append((UNBASED_TITLE, unbased, ""))
    for title, lines, none in sections:
        parts += [f"## {title}", "", *(lines or [none]), ""]
    return "\n".join([*parts, *([service, ""] if service else [])])


def cmd_report(args: argparse.Namespace, root: Path) -> int:
    print(build_report(root, args.change), end="")  # сигналы и находки кода не меняют (F-31)
    return 0


def cmd_check(args: argparse.Namespace, root: Path) -> int:
    signals = check_graph_file(root, args.change, args.file)
    print("\n".join(signals) if signals else "сигналов нет")  # сигнал кода не меняет (F-31)
    return 0


# --- заморозка: снимок и отчёт в graph/ (F-51, F-52, F-59, F-74, F-79, F-100, F-101, F-139) -----------------------------
# Снимок `graph/req-graph.json`: поля графа и `roots`, `base`. `roots` — `[{"prefix", "commit"}]` по файлу корней, в его порядке;
# префикс как в файле, пути корня в снимке нет; `commit` — HEAD корня или пустая строка (корень вне git, без каталога, `git` не
# ответил). `base` (F-123) — то, что сборка и проверка берут из снимка вместо живой мастер-спеки, которую `/opsx:sync` уже
# переписал; по требованиям MODIFIED, чьё имя есть в мастере: `{capability: {имя требования: запись}}`, запись —
# `{"numbers": [F-NN, ...], "scenarios": {имя сценария: хеш текста}, "text": хеш текста требования, "traces": [хеши следов проб]}`.
# Номера — для отсечения F-84; сценарии — состояние `same`/`new`/`changed` (F-95) и `marks`; текст — признак «перенесено»; следы —
# след, дословно стоящий в мастере (Ruling U10). Хеши, не тексты: снимок не копирует мастер-спеку. База снимается первой заморозкой
# из живого мастера и при пересборке берётся из прежнего снимка (F-134): живой читается только для требования без записи.
# Имён мастера для `derives`, веток и security (`_master_names`) в базе нет: они нужны, чтобы не принять за опечатку имя, живущее
# только в мастере, а `/opsx:sync` добавляет в мастер лишь то, что уже есть узлом в самом изменении, и узел побеждает имя мастера.

GIT_TIMEOUT = 20
_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")


@dataclass
class FreezeResult:
    """Итог `freeze_change`: `action` — `build` (граф и отчёт собраны заново) или `commits` (обновлены только коммиты корней);
    `reason` — почему собрано заново (пусто при `commits`); `report` — путь к отчёту от корня проекта с `/` при `build`, иначе `None`;
    `unnamed` — префиксы корней без коммита."""
    action: str
    reason: str = ""
    report: str | None = None
    unnamed: list[str] = field(default_factory=list)


def root_commit(folder: Path) -> str:
    """Коммит HEAD каталога `folder` или `""`: каталога нет, он не корень git-дерева (лежит внутри чужого клона, F-101), коммитов нет,
    `git` не найден или не ответил. `git` зовётся списком аргументов, без оболочки, по абсолютному пути из `PATH` (F-59); читает только HEAD."""
    if not folder.is_dir():
        return ""
    git = find_on_path("git")  # абсолютный путь: голое имя Windows ищет в текущем каталоге раньше `PATH`
    if not git:
        return ""
    try:
        done = subprocess.run([git, "-C", str(folder), "rev-parse", "--show-toplevel", "HEAD"], capture_output=True,
                              text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=GIT_TIMEOUT)
        lines = done.stdout.splitlines()
        if done.returncode != 0 or len(lines) != 2 or not os.path.samefile(lines[0], folder):
            return ""
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    return lines[1].strip() if _COMMIT.match(lines[1].strip()) else ""


def _freeze_roots(root: Path, change: str, roots_file: Path | None) -> list[dict]:
    try:
        folders = default_roots(roots_file, root / "openspec" / "changes" / change / "decisions.json")
    except UNUSABLE_ROOTS as e:
        raise Refusal(f"файл корней не прочитан: {no_paths(str(e), root)}") from e
    return [{"prefix": no_paths(prefix, root), "commit": root_commit(folder)} for prefix, folder in folders.items()]


def _roots_note(roots: list[dict]) -> list[str]:
    """Строки отчёта про корни без коммита: корень называется префиксом (F-101); пусто, если коммиты есть у всех."""
    return [f"Корень {'`' + item['prefix'] + '`' if item['prefix'] else 'проекта'} вне git или без каталога: коммит не записан."
            for item in roots if not item["commit"]]


def _write(path: Path, text: str) -> None:
    """Запись через временный файл рядом и `os.replace`: обрыв не оставляет обрезанного файла под настоящим именем."""
    temp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temp, path)
    except OSError as e:
        temp.unlink(missing_ok=True)
        raise Refusal(f"{path.name} не записан в graph: {e.strerror or e}") from e


def _freeze_base(root: Path, change: str, prior: dict) -> dict[str, dict[str, dict]]:
    """База снимка: запись по каждому требованию MODIFIED изменения, у которого есть запись в `prior` (прежняя база) или требование
    в живой мастер-спеке (F-123, F-134). Прежняя запись не обновляется: после `/opsx:sync` мастер уже несёт номера и сценарии
    этого изменения. Требование, которое перестало быть MODIFIED, в базу не входит. Прежней записи нет, а весь блок MODIFIED (текст и набор
    сценариев) равен живому мастеру — синхронизация уже прошла: запись не снимается, сборка видит требование без базы и называет
    его в отчёте (F-123)."""
    base = root / "openspec" / "changes" / change
    master = _Master(root, prior)
    found: dict[str, dict[str, dict]] = {}
    folders = sorted(p for p in (base / "specs").iterdir() if p.is_dir()) if (base / "specs").is_dir() else []
    for folder in folders:
        rel = f"specs/{folder.name}/spec.md"
        if not (base / rel).is_file():
            continue
        for req in parse_spec(_read_text(base, rel)).requirements:
            entry, from_base = master.entry(folder.name, req.name) if req.section == "MODIFIED" else (None, False)
            if _carried_without_base(entry, from_base, req):
                continue  # F-123: мастер уже несёт весь блок изменения (`/opsx:sync` прошёл) — это не база, номера не отсекаются
            if entry:
                found.setdefault(folder.name, {}).setdefault(req.name, entry)
    return found


def _freeze_reason(root: Path, change: str, folder: Path) -> str:
    """Почему `graph/` надо собрать заново; пусто — снимок свежий и отчёт на месте (F-100, F-139)."""
    snap, report = folder / "req-graph.json", folder / "report.md"
    if not folder.is_dir():
        return "каталога graph нет"
    if not snap.is_file():
        return "снимка нет"
    if not report.is_file():
        return "отчёта нет, graph неполон"
    signals = check_graph_file(root, change, snap)
    if signals:
        return f"снимок устарел или негоден: {no_paths(signals[0].split(': ', 1)[-1], root)}" + (
            f" (и ещё сигналов: {len(signals) - 1})" if len(signals) > 1 else "")
    return ""


def freeze_change(root: Path, change: str, roots_file: Path | None = None) -> FreezeResult:
    """Заморозка изменения `change`: сама выбирает (F-79, F-139). Нет `graph/`, снимка или отчёта либо проверка снимка дала сигнал —
    граф и отчёт собираются заново и пишутся (прежний отчёт снимается до записи снимка, чтобы прерванная запись не выглядела
    свежей, F-100). Иначе пересчитываются только `roots` снимка, граф и отчёт не трогаются. Снимок и отчёт идут без
    абсолютных путей (F-59). Имя проверяется до любого пути; нет изменения, негоден файл корней, сборка не удалась — `Refusal`
    или `ForkError`, и тогда ничего не записано."""
    check_change_name(change)
    base = root / "openspec" / "changes" / change
    if not base.is_dir():
        raise Refusal(f"изменения «{change}» нет: нет каталога openspec/changes/{change}")
    folder = base / "graph"
    roots = _freeze_roots(root, change, roots_file)
    unnamed = [item["prefix"] for item in roots if not item["commit"]]
    reason = _freeze_reason(root, change, folder)
    if not reason:
        snap = json.loads((folder / "req-graph.json").read_bytes().decode("utf-8-sig"))
        snap["roots"] = roots
        _write(folder / "req-graph.json", json.dumps(snap, ensure_ascii=False, indent=1) + "\n")
        return FreezeResult("commits", unnamed=unnamed)
    frozen = _freeze_base(root, change, saved_base(base))  # до записи: прежняя база берётся из ещё не замененного снимка
    graph = _pathless({**build_graph(root, change, frozen), "roots": roots, "base": frozen}, root)
    note = _roots_note(roots)
    text = build_report(root, change, frozen).rstrip("\n") + "\n"
    if note:
        text += "\n## Корни без коммита\n\n" + "\n".join(_md(no_paths(line, root)) for line in note) + "\n"
    (folder / "report.md").unlink(missing_ok=True)
    _write(folder / "req-graph.json", json.dumps(graph, ensure_ascii=False, indent=1) + "\n")
    _write(folder / "report.md", text)
    return FreezeResult("build", reason, (folder / "report.md").relative_to(root).as_posix(), unnamed)


def cmd_freeze(args: argparse.Namespace, root: Path) -> int:
    result = freeze_change(root, args.change, args.roots)
    if result.action == "commits":
        print("Снимок свежий: обновлены только коммиты корней, граф и отчёт прежние.")
    else:
        print(f"Граф собран заново: {result.reason}. Отчёт: {result.report}")
    if result.unnamed:
        print(f"Корни без коммита: {', '.join(name or '(корень проекта)' for name in result.unnamed)}.")
    return 0


# --- архив: изменения без снимка (F-62, F-102) ---------------------------------------------------------------------------

_ARCHIVE_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")


@dataclass
class ArchiveGaps:
    """Итог `archive_gaps`: `named` — изменения без снимка поимённо (новее первого снимка или без даты в имени), `older` — без
    снимка и раньше первого, `first` — имя архива с самым ранним снимком или `None`, если снимка нет ни у одного."""
    named: list[str] = field(default_factory=list)
    older: list[str] = field(default_factory=list)
    first: str | None = None


def archive_gaps(archive: Path) -> ArchiveGaps:
    """Читает каталог архива `archive` и ничего в нём не пишет. Снимок у изменения есть, если лежит `graph/req-graph.json`. Дата —
    начало имени `ГГГГ-ММ-ДД-имя`; без снимка «старше первого» — дата строго раньше даты самого раннего архива со снимком (F-102);
    снимка нет ни у одного — старше первого все с датой. Каталог без даты в имени к старым не относится: назван поимённо."""
    if not archive.is_dir():
        raise Refusal("каталога архива нет" if not archive.exists() else "архив не каталог: нужен каталог архива изменений")
    folders = sorted(p for p in archive.iterdir() if p.is_dir())
    dated = lambda folder: (_ARCHIVE_DATE.match(folder.name) or [None, None])[1]  # noqa: E731
    has = {p.name: (p / "graph" / "req-graph.json").is_file() for p in folders}
    firsts = sorted((dated(p), p.name) for p in folders if has[p.name] and dated(p))
    result = ArchiveGaps(first=firsts[0][1] if firsts else None)
    for folder in folders:
        if has[folder.name]:
            continue
        date = dated(folder)
        (result.older if date and (not firsts or date < firsts[0][0]) else result.named).append(folder.name)
    return result


def cmd_archive_gaps(args: argparse.Namespace, root: Path) -> int:
    result = archive_gaps(args.archive or root / "openspec" / "changes" / "archive")
    for name in result.named:
        print(f"Без снимка: {name}")
    if result.older:
        since = f"старше первого снимка ({result.first})" if result.first else "снимка нет ни у одного изменения, все старше первого"
        print(f"Без снимка, {since}: {len(result.older)}.")
    if not result.named and not result.older:
        print("Все изменения архива со снимком.")
    return 0


HANDLERS = {"build": cmd_build, "report": cmd_report, "check": cmd_check, "freeze": cmd_freeze,
            "archive-gaps": cmd_archive_gaps}

# Подкоманда: (что делает, когда звать, коды). Правило `tests/test_flag_help.py`: «Звать, когда» и «Коды:».
SUBCOMMAND_HELP = {
    "build": ("Собирает граф трассируемости изменения из его артефактов и печатает его JSON в stdout; с `--out` пишет в указанный "
              "файл. С `--format mermaid` печатает текст `requirementDiagram` (всё изменение, `--capability ИМЯ` или "
              "`--requirement ИМЯ`); рисунка скрипт не делает и файла с ним не создаёт. Файлов изменения не пишет.",
              "Звать, когда нужен живой граф: перед отчётом, при разборе связей, в атаке артефактов. `--out ПУТЬ` — путь от "
              "текущего каталога или абсолютный, каталоги создаются; сигналы о дублях идут в stderr и с `--out`, и без. Диаграмма: "
              "`--format mermaid`; `--requirement` принимает имя и форму `capability/имя`, а имя в двух capability отказывает и "
              "называет обе формы.",
              "Коды: 0 — граф собран (у только что созданного изменения он пуст) и выведен или записан; 1 — отказ, графа "
              "нет: имя изменения не подходит, изменения нет, `decisions.json` не разбирается или негоден по схеме, файл "
              "не в UTF-8, путь `--out` не записать, выбор диаграммы не найден или неоднозначен, выбор без "
              "`--format mermaid`; 2 — вызов неверен (в том числе оба выбора сразу)."),
    "report": ("Печатает отчёт Markdown по изменению: находки `openspec validate --json` (форк запускается сам) и сигналы "
               "графа закрытого состава (F-64): критерий без требования, требование и сценарий без задачи (в MODIFIED только новые "
               "сценарии), требование без записи, решение без требования и задачи, неоднозначное имя, неизвестное имя или "
               "номер, задача ни к чему, след пробы, отставший от журнала; расхождения сценариев MODIFIED с мастером идут "
               "отдельным разделом, как и требования MODIFIED без базы мастер-спеки, чей текст совпал с мастером (F-123). Без находок и сигналов — «Сигналов нет.»; если validate не запустился, в отчёте строка "
               "«validate не запустился» с причиной.",
               "Звать, когда нужен список разрывов человеку; отчёт отдаётся ссылкой, модель его не читает. Форк берётся "
               "из `SYMPHYSIS_OPENSPEC`, затем из PATH; файлов изменения команда не пишет.",
               "Коды: 0 — отчёт напечатан, сигналы, находки и незапуск validate кода не меняют (F-31); 1 — отказ: имя "
               "изменения не подходит, изменения нет, сборка графа не удалась (журнал негоден, файл не в UTF-8); "
               "2 — вызов неверен."),
    "check": ("Проверяет сохранённый файл графа ФАЙЛ против изменения: форму, состав исходников и их хеши (после "
              "приведения концов строк к LF), а у свежего по хешам файла — узлы и связи против свежей сборки. Сигналы — "
              "строки `[!!]` с именем файла; без них одна строка «сигналов нет».",
              "Звать, когда граф записан в файл (`build --out`) и нужно знать, не устарел ли он и не правили ли его руками: "
              "перед архивом, после правки артефактов. ФАЙЛ — путь от текущего каталога или абсолютный.",
              "Коды: 0 — проверка прошла, сигналы кода не меняют (F-31), файл не той формы или отсутствующий — тоже сигнал; "
              "1 — отказ: имя изменения не подходит или изменения нет; 2 — вызов неверен."),
    "freeze": ("Замораживает граф изменения в `graph/` каталога изменения: снимок `req-graph.json` (узлы, связи, хеши исходников, "
               "коммиты корней, база мастер-спеки) и отчёт `report.md`. Сама выбирает (F-139): каталога, снимка или отчёта нет "
               "либо проверка снимка дала сигнал — собирает заново; снимок свежий — обновляет только коммиты корней, граф и "
               "отчёт прежние. Корни — из файла корней, как у `journal.py check --roots`; в снимке и отчёте они названы "
               "префиксами, абсолютных путей нет. Корень вне git или без каталога остаётся без коммита и назван в отчёте.",
               "Звать, когда изменение готово к архиву, одной командой, без выбора между сборкой и обновлением. При новой сборке "
               "вывод называет путь к отчёту от корня проекта: отдай его человеку ссылкой, сам отчёт не читай. "
               "`--roots ПУТЬ` — файл корней вместо `tools/journal-roots.json`.",
               "Коды: 0 — выполнено, сборка заново и обновление коммитов обе дают 0, сигналы кода не меняют (F-31); 1 — отказ: "
               "имя изменения не подходит, изменения нет, файл корней не прочитан, сборка не удалась (журнал негоден, файл "
               "не в UTF-8), запись не удалась, причина в stderr; 2 — вызов неверен."),
    "archive-gaps": ("Читает каталог архива изменений и называет изменения без снимка `graph/req-graph.json`: поимённо строками "
                     "«Без снимка: ИМЯ». Изменения старше первого снимка (раньше самого раннего архива со снимком; снимка нет "
                     "ни у одного — все) идут одной строкой со счётом, поимённо только более новые (F-102). Каталоги архива "
                     "названы `ГГГГ-ММ-ДД-имя`; без даты в имени каталог назван поимённо. Только читает: файлов в архиве не "
                     "прибавляет, снимок не собирает, `symphysis check` её не зовёт (F-62).",
                     "Звать, когда надо узнать, какие архивные изменения не заморожены с графом: например, после "
                     "ручного `openspec archive` мимо скилла. КАТАЛОГ — путь от текущего каталога или абсолютный; по умолчанию "
                     "`openspec/changes/archive` от корня проекта.",
                     "Коды: 0 — перечень напечатан, любая находка кода не меняет (F-31); 1 — отказ: каталога нет или это не "
                     "каталог; 2 — вызов неверен."),
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
            sp.add_argument("archive", metavar="КАТАЛОГ", type=Path, nargs="?", default=None,
                           help="каталог архива изменений; по умолчанию openspec/changes/archive от корня проекта")
        else:
            sp.add_argument("change", metavar="ИЗМЕНЕНИЕ", help="имя изменения, как у `openspec validate <имя>`")
        if name == "freeze":
            sp.add_argument("--roots", metavar="ПУТЬ", type=Path, default=None, help="файл корней вместо tools/journal-roots.json")
        if name == "check":
            sp.add_argument("file", metavar="ФАЙЛ", type=Path, help="сохранённый граф изменения (JSON от `build --out`)")
        if name == "build":
            sp.add_argument("--out", metavar="ПУТЬ", type=Path, default=None,
                            help="записать граф в этот файл вместо stdout; файлы изменения не меняются")
            sp.add_argument("--format", choices=("json", "mermaid"), default="json",
                            help="json (по умолчанию) — граф; mermaid — текст `requirementDiagram`, рисунка скрипт не делает")
            pick = sp.add_mutually_exclusive_group()
            pick.add_argument("--capability", metavar="ИМЯ", default=None,
                              help="с `--format mermaid`: только эта capability, её требования и сценарии, связанные задачи, "
                                   "записи, пункты security и ветки")
            pick.add_argument("--requirement", metavar="ИМЯ", default=None,
                              help="с `--format mermaid`: только это требование, его сценарии, связанные задачи и записи, "
                                   "соседи по кандидатам; имя в двух capability — форма `capability/имя`")
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
