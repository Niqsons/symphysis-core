#!/usr/bin/env python3
"""Проба к парковке F-59: что делает текст из файлов изменения, попавший в `requirementDiagram` в кавычках.

Стенд и сборки те же, что у F-54: `../F-54-probe/render.py`, каталог `%TEMP%/tg-mermaid/<версия>/mermaid.min.js`.
Заливка блока показывает, сменилась ли тема; текст блока показывает, разобран ли HTML. Запуск: python injection.py, итог в results.txt рядом.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "F-54-probe"))

from render import VERSIONS, render  # noqa: E402

CASES = {
    "обычное имя": "Вход по паролю",
    "директива темы в имени": '%%{init: {\\"theme\\":\\"forest\\"}}%% Вход',
    "директива без кавычек внутри": "%%{init: {'theme':'forest'}}%% Вход",
    "директива securityLevel в имени": "%%{init: {'securityLevel':'loose'}}%% Вход",
    "HTML в имени": "<img src=x onerror=alert(1)> Вход",
    "script в имени": "<script>alert(1)</script> Вход",
    "комментарий в имени": "Вход %% хвост",
    "перенос строки в имени": "Вход\nвторая строка",
}


def source(name: str) -> str:
    return f'requirementDiagram\nrequirement "{name}" {{\n    id: "REQ_1"\n    text: "t"\n}}\n'


def main() -> None:
    lines = ["Проба F-59: текст из файлов изменения в имени блока requirementDiagram. Стенд: ../F-54-probe/render.py.", ""]
    for label, name in CASES.items():
        for version in VERSIONS:
            r = render(source(name), version, name="inj")
            if r["ok"]:
                node = r["info"][0] if r.get("info") else {}
                lines.append(f"{version} | {label} | годен | заливка {node.get('fill')} | текст {str(node.get('text'))[:70]}")
            else:
                lines.append(f"{version} | {label} | ОТКАЗ | " + r["error"].replace("\n", " ")[:120])
    (HERE / "results.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
