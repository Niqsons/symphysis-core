#!/usr/bin/env python3
"""Проба: номер с подчёркиванием вместо дефиса. Дефис с двумя цифрами хук принимает за ключ задачи.

Пересобирает образцы .mmd и рисует их на двух сборках mermaid. Вывод: underscore-results.txt."""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate as G  # noqa: E402

KEY = re.compile(r"\b([A-Z]{2,10})-\d{2,6}\b")   # то же правило, что в tools/hooks/gate_hook.py
lines = ["Проба: номер с подчёркиванием. Ключей задач считает то же правило, что в tools/hooks/gate_hook.py.", ""]

rw = G.build(G.P.load("recommendation-why"), lambda r: True)
sh = G.P.load("step-help")
biggest = max(sh.requirements, key=lambda r: len(r.scenarios))
neighbour = G.build(sh, lambda r: r is biggest)
(HERE / "whole-recommendation-why.mmd").write_text(rw.text(), encoding="utf-8", newline="\n")
(HERE / "neighbour-step-help.mmd").write_text(neighbour.text(), encoding="utf-8", newline="\n")
(HERE.parent / "F-54-probe" / "sample.mmd").write_text(G.R.SAMPLE, encoding="utf-8", newline="\n")

form = 'requirementDiagram\ndesignConstraint "SEC_12 Инъекции" {\n    id: "SEC_12"\n    text: "t"\n}\nelement "SCN_12 Есть поле" {\n    type: "сценарий"\n    docref: "spec.md:8"\n}\nelement "TASK_3.2 Задача" {\n    type: "задача"\n}\n"SCN_12 Есть поле" - verifies -> "SEC_12 Инъекции"\n"TASK_3.2 Задача" - satisfies -> "SCN_12 Есть поле"\nclassDef ksec fill:#fee2e2,stroke:#b91c1c,stroke-width:3px\nclass "SEC_12 Инъекции" ksec\n'
for label, text in (("всё recommendation-why", rw.text()), ("окрестность step-help", neighbour.text()), ("форма с вариантом F-67.B", form)):
    keys = len(KEY.findall(text))
    for version in G.R.VERSIONS:
        r = G.R.render(text, version, name="u", shot=label.startswith("форма") and version == "12.2.0", size="1300,500")
        state = f"годен | узлов {r['nodes']}" if r["ok"] else "ОТКАЗ " + r["error"][:120]
        lines.append(f"{version} | {label} | ключей задач {keys} | {state}")
        if label.startswith("форма") and r["ok"]:
            lines += [f"    {i['text'][:80]}" for i in r["info"]]
out = "\n".join(lines) + "\n"
(HERE / "underscore-results.txt").write_text(out, encoding="utf-8", newline="\n")
print(out)
