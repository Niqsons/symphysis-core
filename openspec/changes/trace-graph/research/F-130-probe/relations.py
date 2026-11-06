#!/usr/bin/env python3
"""Проба к F-77 и F-120: какие типы связей `requirementDiagram` разбираются и рисуются на обеих сборках mermaid.

Стенд и сборки те же, что у F-54: `../F-54-probe/render.py`, каталог `%TEMP%/tg-mermaid/<версия>/mermaid.min.js`.
Запуск: python relations.py, результат в results.txt рядом.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "F-54-probe"))

from render import VERSIONS, render  # noqa: E402

TYPES = ("contains", "copies", "derives", "satisfies", "verifies", "refines", "traces")
BODY = 'requirementDiagram\nrequirement "Дочернее" {\n    id: "REQ_1"\n    text: "t"\n}\nrequirement "Родитель" {\n    id: "REQ_2"\n    text: "t"\n}\n'


def main() -> None:
    lines = ["Проба типов связей requirementDiagram. Стенд: ../F-54-probe/render.py.", ""]
    for kind in TYPES:
        for version in VERSIONS:
            r = render(BODY + f'"Дочернее" - {kind} -> "Родитель"\n', version, name=f"rel-{kind}")
            verdict = f"годен | узлов {r['nodes']}" if r["ok"] else "ОТКАЗ | " + r["error"].replace("\n", " ")[:160]
            lines.append(f"{version} | {kind} | {verdict}")
    (HERE / "results.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
