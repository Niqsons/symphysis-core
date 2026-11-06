#!/usr/bin/env python3
"""Проба F-58, дополнение: при тексте больше 50 000 знаков mermaid не падает, а рисует заглушку. Что будет с поднятым пределом и хватит ли директивы."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate as G  # noqa: E402

lines = ["", "Дополнение: предел текста. По умолчанию maxTextSize 50000.", ""]
for name in ("step-help", "decision-scheme"):
    ch = G.P.load(name)
    whole = G.build(ch, lambda r: True)
    text = whole.text()
    for version in G.R.VERSIONS:
        r = G.R.render(text, version, name="d", budget=200000)
        first = r["info"][0]["text"][:45] if r.get("ok") and r.get("info") else ""
        lines.append(f"{version} | {name}: всё изменение, {len(text)} зн., настройки по умолчанию | узлов нарисовано {r.get('nodes')} из {len(whole.nodes)} | {r.get('w')}x{r.get('h')} px | первый узел: {first}")
        r = G.R.render(text, version, name="l", config={"maxTextSize": 500000}, budget=200000)
        lines.append(f"{version} | {name}: то же, maxTextSize 500000 | {'узлов нарисовано ' + str(r.get('nodes')) + ', ' + str(r.get('ms')) + ' мс, ' + str(r.get('w')) + 'x' + str(r.get('h')) + ' px' if r.get('ok') else 'ОТКАЗ ' + r.get('error', '')[:140]}")
        directive = '%%{init: {"maxTextSize": 500000}}%%\n' + text
        r = G.R.render(directive, version, name="i", budget=200000)
        lines.append(f"{version} | {name}: то же, директива init в самом тексте | узлов нарисовано {r.get('nodes')} | {r.get('w')}x{r.get('h')} px")
print("\n".join(lines))
with (HERE / "results.txt").open("a", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
