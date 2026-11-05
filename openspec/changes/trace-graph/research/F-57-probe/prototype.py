#!/usr/bin/env python3
"""Проба F-57: разовый прототип графа и сигналов по эталонам, не код поставки.

Читает клоны X:/symphysis-reference, ничего в них не пишет. Вывод: summary.txt и signals-<изменение>.txt
рядом с этим файлом. Совпадение по строкам: находка значит «ссылка есть», а не «ссылка верна по смыслу».
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REFERENCE = Path("X:/symphysis-reference")
CHANGES = {"recommendation-why": "probes/journal-roots.json", "step-help": "../journal-roots.json", "decision-scheme": "../journal-roots.json"}
HERE = Path(__file__).resolve().parent

RE_SECTION = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements", re.I)
RE_REQ = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$")
RE_SCN = re.compile(r"^####\s+Scenario:\s*(.+?)\s*$")
RE_TASK = re.compile(r"^\s*- \[[ xX]\]\s+(\d+\.\d+)\s+(.*)$")
# Без ограничения слева `UTF-8` даёт ложный номер F-8: так и вышло при первом запуске.
RE_FID = re.compile(r"(?<![A-Za-zА-Яа-яЁё])F-(\d+)(?!\d)")
RE_RANGE = re.compile(r"(?<![A-Za-zА-Яа-яЁё])F-(\d+)\s*[–-]\s*F-(\d+)")
RE_COMMENT = re.compile(r"<!--.*?-->", re.S)
RE_WORD = re.compile(r"[A-Za-zА-Яа-яЁё_`.-]{4,}")


def fids(text: str) -> set[str]:
    found = {f"F-{m}" for m in RE_FID.findall(text)}
    for a, b in RE_RANGE.findall(text):
        if int(b) - int(a) < 40:
            found |= {f"F-{n:02d}" if n < 100 else f"F-{n}" for n in range(int(a), int(b) + 1)}
    return found


@dataclass
class Scenario:
    capability: str
    requirement: str
    name: str
    line: int
    path: str
    body: str = ""
    refs: set[str] = field(default_factory=set)


@dataclass
class Requirement:
    capability: str
    name: str
    line: int
    path: str
    delta: str
    text: str = ""
    refs: set[str] = field(default_factory=set)
    probe_refs: set[str] = field(default_factory=set)
    scenarios: list[Scenario] = field(default_factory=list)


@dataclass
class Task:
    id: str
    text: str
    line: int
    refs: set[str] = field(default_factory=set)
    scenarios: list[Scenario] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)


@dataclass
class Change:
    name: str
    base: Path
    requirements: list[Requirement]
    tasks: list[Task]
    journal: dict
    security: list[tuple[int, str, str]]
    branches: list[tuple[int, str, str]]
    proposal: str


def parse_specs(base: Path) -> list[Requirement]:
    reqs: list[Requirement] = []
    for path in sorted((base / "specs").glob("**/spec.md")):
        capability = path.parent.relative_to(base / "specs").as_posix()
        rel = path.relative_to(base).as_posix()
        delta, req, scn = "", None, None
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if m := RE_SECTION.match(line):
                delta, req, scn = m.group(1).upper(), None, None
                continue
            if m := RE_REQ.match(line):
                req = Requirement(capability, m.group(1), number, rel, delta)
                reqs.append(req)
                scn = None
                continue
            if m := RE_SCN.match(line):
                if req:
                    scn = Scenario(capability, req.name, m.group(1), number, rel)
                    req.scenarios.append(scn)
                continue
            if req is None:
                continue
            if line.lstrip().startswith("<!--"):
                req.probe_refs |= fids(line)
                continue
            if scn:
                scn.body += line + "\n"
                scn.refs |= fids(line)
            else:
                req.text += line + "\n"
            req.refs |= fids(line)
    return reqs


def parse_tasks(base: Path, reqs: list[Requirement]) -> list[Task]:
    path = base / "tasks.md"
    if not path.exists():
        return []
    scenarios = [s for r in reqs for s in r.scenarios]
    tasks = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not (m := RE_TASK.match(line)):
            continue
        task = Task(m.group(1), m.group(2), number, fids(m.group(2)))
        task.scenarios = [s for s in scenarios if s.name in task.text]
        task.requirements = [r for r in reqs if r.name in task.text]
        tasks.append(task)
    return tasks


def parse_security(base: Path) -> list[tuple[int, str, str]]:
    """(строка, пункт, вторая колонка) у пунктов «применимо»."""
    path = base / "security.md"
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 2 and cells[1].startswith("применимо"):
            rows.append((number, cells[0], cells[1]))
    return rows


def parse_branches(base: Path) -> list[tuple[int, str, str]]:
    """(строка, вид, значение) у строк описи: `- сценарий: имя` и `- кандидат: F-NN`."""
    path = base / "consequences.md"
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if m := re.match(r"^\s*- сценарий:\s*(.+?)\s*$", line):
            rows.append((number, "сценарий", m.group(1)))
        elif m := re.match(r"^\s*- кандидат:\s*(.+?)\s*$", line):
            rows.append((number, "кандидат", m.group(1)))
    return rows


def load(name: str) -> Change:
    base = REFERENCE / name / "symphysis" / "openspec" / "changes" / name
    reqs = parse_specs(base)
    return Change(name, base, reqs, parse_tasks(base, reqs),
                  json.loads((base / "decisions.json").read_text(encoding="utf-8")),
                  parse_security(base), parse_branches(base),
                  (base / "proposal.md").read_text(encoding="utf-8") if (base / "proposal.md").exists() else "")


def words(text: str) -> set[str]:
    return {w.lower() for w in RE_WORD.findall(text)}


def signals(ch: Change) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    records = {r["id"]: r for r in ch.journal["records"]}
    req_refs = {f for r in ch.requirements for f in r.refs}
    probe_refs = {f for r in ch.requirements for f in r.probe_refs}
    task_refs = {f for t in ch.tasks for f in t.refs}
    named_scn = {id(s) for t in ch.tasks for s in t.scenarios}
    named_req = {id(r) for t in ch.tasks for r in t.requirements}
    scenarios = [s for r in ch.requirements for s in r.scenarios]
    by_name: dict[str, list[Scenario]] = {}
    for s in scenarios:
        by_name.setdefault(s.name, []).append(s)
    capabilities = {r.capability for r in ch.requirements}

    for rec in ch.journal["records"]:
        rid = rec["id"]
        question = rec["question"][:110]
        if rec.get("addressee") == "постановка" and rid not in req_refs and rid not in probe_refs:
            mark = "назван в proposal" if re.search(re.escape(rid) + r"(?!\d)", ch.proposal) else "не назван в proposal"
            out.append(("критерий без требования", f"{rid} [{mark}] {question}"))
        decision = rec.get("decision")
        if rec.get("kind") == "факт" or not decision:
            continue
        outcome = rec.get("outcome") or {}
        value = outcome.get("value") if outcome.get("kind") == "проба" else None
        chosen = next((o for o in rec["options"] if o["letter"] == decision["option"]), None)
        text = chosen["text"] if chosen else ""
        in_text, in_probe, in_task = rid in req_refs, rid in probe_refs, rid in task_refs
        if value == "Specify":
            if not in_text and not in_probe:
                out.append(("Specify нигде в спеке", f"{rid} {question}"))
            elif not in_text:
                wanted = words(re.split(r";\s*цена", text)[0])
                best = max((len(wanted & words(s.body)) / len(wanted) for s in scenarios), default=0) if wanted else 0
                if best < 0.5:
                    out.append(("Specify без сценария по словам", f"{rid} совпадение {best:.2f} {question}"))
        elif value == "Backstop":
            if not in_task and not in_text:
                out.append(("Backstop без задачи", f"{rid} {question}"))
        elif value in ("Dismiss", "Defer"):
            pass
        elif not in_text and not in_probe and not in_task:
            kind = "решение «как есть» без требования и задачи" if text.startswith("Оставить как есть") else "решение без требования и задачи"
            out.append((kind, f"{rid}.{decision['option']} {question}"))

    delta_of = {id(s): r.delta for r in ch.requirements for s in r.scenarios}
    for r in ch.requirements:
        if id(r) not in named_req and not any(id(s) in named_scn for s in r.scenarios):
            out.append((f"требование без задачи, {r.delta}", f"{r.capability} / {r.name} ({r.path}:{r.line})"))
    def in_master(s: Scenario) -> bool:
        master = REFERENCE / ch.name / "symphysis" / "openspec" / "specs" / s.capability / "spec.md"
        return master.exists() and f"#### Scenario: {s.name}" in master.read_text(encoding="utf-8")

    for s in scenarios:
        if id(s) not in named_scn:
            delta = delta_of[id(s)]
            if delta == "MODIFIED":
                delta = "MODIFIED, перенесён из мастера" if in_master(s) else "MODIFIED, новый"
            out.append((f"сценарий без задачи, {delta}", f"{s.capability} / {s.name} ({s.path}:{s.line})"))
    for path in sorted((ch.base / "specs").glob("**/spec.md")):
        rel = path.relative_to(ch.base).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.lstrip().startswith("<!--"):
                continue
            for fid in re.findall(r"(F-\d+) открыт", line):
                rec = records.get(fid)
                if rec and rec.get("decision"):
                    out.append(("след отстал от журнала", f"{rel}:{number} {fid} открыт, в журнале {rec['decision']['option']}"))
    for name, same in by_name.items():
        if len(same) > 1:
            tasks = [t.id for t in ch.tasks if name in t.text and not any(c in t.text for c in {x.capability for x in same})]
            out.append(("имя сценария неоднозначно", f"«{name}» у {len(same)} требований; задачи без capability: {', '.join(tasks) or 'нет'}"))
    for t in ch.tasks:
        if not t.scenarios and not t.requirements and not t.refs:
            out.append(("задача ни к чему", f"{t.id} {t.text[:110]}"))
    all_names = {r.name for r in ch.requirements} | {s.name for s in scenarios}
    for number, item, cell in ch.security:
        names = re.findall(r"«([^»]+)»", cell)
        if not names:
            out.append(("пункт security без имени", f"security.md:{number} {item[:70]} — {cell[:70]}"))
        for name in names:
            if name not in all_names:
                out.append(("пункт security называет неизвестное имя", f"security.md:{number} «{name[:80]}»"))
    for number, kind, value in ch.branches:
        if kind == "сценарий" and value not in all_names:
            out.append(("ветка называет неизвестный сценарий", f"consequences.md:{number} {value[:90]}"))
        if kind == "кандидат":
            for fid in fids(value):
                if fid not in records:
                    out.append(("висячий номер", f"consequences.md:{number} {fid}"))
    for r in ch.requirements:
        for fid in r.refs | r.probe_refs:
            if fid not in records:
                out.append(("висячий номер", f"{r.path}:{r.line} {fid}"))
    for t in ch.tasks:
        for fid in t.refs:
            if fid not in records:
                out.append(("висячий номер", f"tasks.md:{t.line} {fid}"))
    return out


def evidence_signals(ch: Change, roots: str) -> tuple[str, list[tuple[str, str]]]:
    """Сигналы `check` на самом клоне: улика, которая разошлась. `в задачах` значит файл назван в tasks.md: это грубое приближение
    к «файл правит само изменение»."""
    root = REFERENCE / ch.name / "symphysis"
    rel = ch.base.relative_to(root).as_posix()
    done = subprocess.run([sys.executable, "-X", "utf8", "tools/journal.py", "check", f"{rel}/decisions.json", "--roots", f"{rel}/{roots}" if roots.startswith("probes") else roots],
                          cwd=root, capture_output=True, text=True, encoding="utf-8")
    tasks_text = (ch.base / "tasks.md").read_text(encoding="utf-8") if (ch.base / "tasks.md").exists() else ""
    head, out = "", []
    for line in done.stdout.splitlines():
        if line.startswith("[ok] улик"):
            head = line
        if line.startswith("[!!]") and "цитаты нет" in line:
            m = re.search(r":\s*(\S+)\s+«", line)
            path = m.group(1) if m else ""
            short = path.removeprefix("vscode/").split("/")[-1]
            kind = "улика разошлась, файл назван в задачах" if short and short in tasks_text else "улика разошлась, файл в задачах не назван"
            out.append((kind, line[5:150]))
    return head, out


def main() -> None:
    lines = ["Проба F-57. Эталоны на последнем коммите перед архивацией. Совпадение строк, смысл не проверялся.", ""]
    kinds: dict[str, Counter] = {}
    for name, roots in CHANGES.items():
        ch = load(name)
        found = signals(ch)
        head, ev = evidence_signals(ch, roots)
        found += ev
        counter = Counter(k for k, _ in found)
        kinds[name] = counter
        scenarios = sum(len(r.scenarios) for r in ch.requirements)
        linked = sum(1 for t in ch.tasks if t.scenarios or t.requirements or t.refs)
        lines.append(f"{name}: требований {len(ch.requirements)}, сценариев {scenarios}, задач {len(ch.tasks)}, записей {len(ch.journal['records'])}, задач со связью {linked}, {head}")
        body = [f"# сигналы {name}"]
        for kind in sorted(counter):
            body.append(f"\n## {kind}: {counter[kind]}")
            body += [f"- {text}" for k, text in found if k == kind]
        (HERE / f"signals-{name}.txt").write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    lines += ["", "вид | " + " | ".join(CHANGES)]
    for kind in sorted({k for c in kinds.values() for k in c}):
        lines.append(f"{kind} | " + " | ".join(str(kinds[n][kind]) for n in CHANGES))
    (HERE / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
