#!/usr/bin/env python3
"""Проба F-58: прототип генератора requirementDiagram по разбору из F-57 и рисование на двух сборках mermaid.

Не код поставки. Берёт настоящие имена с трёх эталонов. Вывод: results.txt и образцы .mmd рядом с этим файлом."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "F-57-probe"))
sys.path.insert(0, str(HERE.parent / "F-54-probe"))
import prototype as P  # noqa: E402
import render as R  # noqa: E402

# Прототип конфига из слова владельца к F-54: вид → ближайший тип SysML, префикс id, класс.
KINDS = {
    "cap": ("requirement", "CAP", "kcap", "fill:#f1f5f9,stroke:#475569"),
    "req": ("requirement", "REQ", "kreq", "fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px"),
    "scn": ("element", "SCN", "kscn", "fill:#dcfce7,stroke:#15803d"),
    "task": ("element", "TASK", "ktask", "fill:#fef9c3,stroke:#a16207"),
    "rec": ("element", "REC", "krec", "fill:#f3e8ff,stroke:#7e22ce,stroke-dasharray:6"),
    "sec": ("designConstraint", "SEC", "ksec", "fill:#fee2e2,stroke:#b91c1c,stroke-width:3px"),
}


def clean(text: str, limit: int = 110) -> str:
    text = " ".join(text.split()).replace('"', "'")
    return text[:limit]


class Diagram:
    def __init__(self) -> None:
        self.nodes: dict[str, str] = {}
        self.kinds: dict[str, str] = {}
        self.edges: list[str] = []
        self.counters: Counter = Counter()

    def node(self, kind: str, key: str, title: str, text: str = "", docref: str = "") -> str:
        """Имя в диаграмме и есть ключ узла, поэтому в него входит id: одинаковые имена иначе сольются."""
        if key in self.nodes:
            return self.nodes[key]
        keyword, prefix, _, _ = KINDS[kind]
        self.counters[kind] += 1
        # Подчёркивание, а не дефис: дефис с двумя цифрами хук принимает за ключ задачи (tools/hooks/gate_hook.py). Числа в results.txt сняты ещё с дефисом, длина та же.
        ident = f"{prefix}_{self.counters[kind]}"
        name = clean(f"{ident} {title}", 90)
        self.nodes[key] = name
        self.kinds[name] = kind
        if keyword == "element":
            body = f'    type: "{ident}"\n' + (f'    docref: "{clean(docref, 80)}"\n' if docref else "")
        else:
            body = f'    id: "{ident}"\n' + (f'    text: "{clean(text)}"\n' if text else "")
        self.blocks = getattr(self, "blocks", [])
        self.blocks.append(f'{keyword} "{name}" {{\n{body}}}\n')
        return name

    def edge(self, a: str, kind: str, b: str) -> None:
        self.edges.append(f'"{a}" - {kind} -> "{b}"\n')

    def text(self) -> str:
        used = {self.kinds[n] for n in self.kinds}
        defs = "".join(f"classDef {KINDS[k][2]} {KINDS[k][3]}\n" for k in KINDS if k in used)
        classes = "".join(f'class "{n}" {KINDS[k][2]}\n' for n, k in self.kinds.items())
        return "requirementDiagram\ndirection LR\n" + defs + "".join(getattr(self, "blocks", [])) + "".join(self.edges) + classes


def build(ch: P.Change, wanted) -> Diagram:
    """`wanted(requirement)` выбирает часть графа: всё, capability, окрестность одного требования."""
    d = Diagram()
    records = {r["id"]: r for r in ch.journal["records"]}
    for r in ch.requirements:
        if not wanted(r):
            continue
        cap = d.node("cap", f"cap:{r.capability}", r.capability)
        req = d.node("req", f"req:{r.capability}/{r.name}", r.name, r.text, )
        d.edge(cap, "contains", req)
        for s in r.scenarios:
            scn = d.node("scn", f"scn:{r.capability}/{r.name}/{s.name}", s.name, docref=f"{s.path}:{s.line}")
            d.edge(scn, "verifies", req)
        for fid in sorted(r.refs):
            if fid in records:
                rec = d.node("rec", f"rec:{fid}", f"{fid} {records[fid]['question']}", docref="decisions.json")
                d.edge(req, "traces", rec)
    for t in ch.tasks:
        linked = False
        for s in t.scenarios:
            key = f"scn:{s.capability}/{s.requirement}/{s.name}"
            if key in d.nodes:
                task = d.node("task", f"task:{t.id}", f"Задача {t.id}", docref=f"tasks.md:{t.line}")
                d.edge(task, "satisfies", d.nodes[key])
                linked = True
        if linked:
            for fid in sorted(t.refs):
                key = f"rec:{fid}"
                if key in d.nodes:
                    d.edge(d.nodes[f"task:{t.id}"], "traces", d.nodes[key])
    return d


def row(label: str, version: str, d: Diagram, config: dict | None = None, name: str = "m", shot: bool = False) -> str:
    text = d.text()
    r = R.render(text, version, name=name, config=config, shot=shot, budget=200000, size="2400,1500")
    head = f"{version} | {label} | узлов {len(d.nodes)} | связей {len(d.edges)} | текст {len(text)} зн."
    if not r["ok"]:
        return f"{head} | ОТКАЗ | {r['error'][:140]}".replace("\n", " ")
    return f"{head} | годен | {r['ms']} мс, полный {r['wall']} с | {r['w']}x{r['h']} px"


def main() -> None:
    lines = ["Проба F-58. Текст диаграммы собран по настоящим файлам эталонов, настройки mermaid по умолчанию.", ""]
    for name in P.CHANGES:
        ch = P.load(name)
        whole = build(ch, lambda r: True)
        caps = Counter(r.capability for r in ch.requirements)
        top_cap = caps.most_common(1)[0][0]
        capability = build(ch, lambda r, c=top_cap: r.capability == c)
        biggest = max(ch.requirements, key=lambda r: len(r.scenarios))
        neighbour = build(ch, lambda r, b=biggest: r is b)
        for label, d in ((f"{name}: всё изменение", whole), (f"{name}: capability {top_cap}", capability), (f"{name}: требование «{clean(biggest.name, 50)}»", neighbour)):
            for version in R.VERSIONS:
                lines.append(row(label, version, d))
                print(lines[-1], flush=True)
        if name == "recommendation-why":
            (HERE / "whole-recommendation-why.mmd").write_text(whole.text(), encoding="utf-8", newline="\n")
        if name == "step-help":
            (HERE / "neighbour-step-help.mmd").write_text(neighbour.text(), encoding="utf-8", newline="\n")
            R.render(neighbour.text(), "12.2.0", name="neighbour", shot=True, size="1800,1100")
            R.render(whole.text(), "12.2.0", name="whole-step-help", shot=True, budget=200000, size="2400,1500")
        lines.append("")
    # Ключ узла это имя: что будет с одинаковыми именами в настоящем изменении.
    same = 'requirementDiagram\nelement "Есть поле" {\n    type: "SCN-1"\n}\nelement "Есть поле" {\n    type: "SCN-2"\n}\nrequirement "A" {\n    id: "R-1"\n}\nrequirement "B" {\n    id: "R-2"\n}\n"Есть поле" - verifies -> "A"\n"Есть поле" - verifies -> "B"\n'
    for version in R.VERSIONS:
        r = R.render(same, version, name="same")
        lines.append(f"{version} | два element с одним именем | {'годен, узлов ' + str(r['nodes']) if r['ok'] else 'ОТКАЗ ' + r['error'][:120]} | {[i['text'][:40] for i in r.get('info', [])]}")
    # Предел текста: настоящий ли он у этой диаграммы.
    big = P.load("decision-scheme")
    text = build(big, lambda r: True).text()
    for limit in (2000,):
        for version in R.VERSIONS:
            r = R.render(text, version, name="limit", config={"maxTextSize": limit})
            lines.append(f"{version} | maxTextSize={limit} при тексте {len(text)} зн. | {'годен, узлов ' + str(r.get('nodes')) + ' ' + str([i['text'][:60] for i in r.get('info', [])][:1]) if r['ok'] else 'ОТКАЗ ' + r['error'][:120]}")
    out = "\n".join(lines) + "\n"
    (HERE / "results.txt").write_text(out, encoding="utf-8", newline="\n")
    print(out[-900:])


if __name__ == "__main__":
    main()
