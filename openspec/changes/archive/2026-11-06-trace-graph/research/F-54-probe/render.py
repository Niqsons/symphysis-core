#!/usr/bin/env python3
"""Пробы F-54 и F-58: рисует текст mermaid в безголовом Chrome на указанной сборке и отдаёт исход.

Сборки лежат во временном каталоге: 12.2.0 из node_modules плагина, 11.17.2 из `npm pack` (её держит md4h в webview.js).
Запуск этого файла: случаи F-54 и results.txt рядом, снимки во временном каталоге."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"
BUILDS = Path(os.environ["TEMP"]) / "tg-mermaid"
VERSIONS = ("12.2.0", "11.17.2")
WORK = BUILDS / "work"

JS = """
(async function(){
  var st=document.getElementById('st');
  try{
    var t0=performance.now();
    mermaid.initialize(Object.assign({startOnLoad:false,securityLevel:'strict'},%(config)s));
    var r=await mermaid.render('g1',%(src)s);
    document.getElementById('out').innerHTML=r.svg;
    var svg=document.querySelector('#out svg');
    var box=svg.viewBox&&svg.viewBox.baseVal?svg.viewBox.baseVal:{width:0,height:0};
    var nodes=[].slice.call(svg.querySelectorAll('g.node'));
    var info=nodes.map(function(n){
      var shape=n.querySelector('path,rect,polygon');
      var cs=shape?getComputedStyle(shape):null;
      var txt=(n.textContent||'').replace(/\\s+/g,' ').trim();
      return {cls:n.getAttribute('class'),fill:cs?cs.fill:'',stroke:cs?cs.stroke:'',sw:cs?cs.strokeWidth:'',dash:cs?cs.strokeDasharray:'',text:txt.slice(0,70)};
    });
    st.textContent=JSON.stringify({ok:true,ms:Math.round(performance.now()-t0),w:Math.round(box.width),h:Math.round(box.height),nodes:nodes.length,edges:svg.querySelectorAll('.edgePaths path, path.relation, g.edgePaths > path').length,info:info});
  }catch(e){st.textContent=JSON.stringify({ok:false,error:String(e.message||e).slice(0,400)});}
})();
"""


def render(src: str, version: str, name: str = "case", config: dict | None = None, shot: bool = False, budget: int = 60000, size: str = "1600,1000") -> dict:
    WORK.mkdir(parents=True, exist_ok=True)
    build = (BUILDS / version / "mermaid.min.js").as_posix()
    embedded = json.dumps(src, ensure_ascii=False).replace("<", "\\u003c")
    page = WORK / f"{name}-{version}.html"
    page.write_text('<!doctype html><html><head><meta charset="utf-8"><script src="file:///' + build + '"></script></head>'
                    '<body style="background:#fff;margin:4px"><div id="st" style="display:none"></div><div id="out"></div><script>'
                    + JS % {"config": json.dumps(config or {}), "src": embedded} + "</script></body></html>", encoding="utf-8")
    base = [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={WORK.as_posix()}/prof",
            "--allow-file-access-from-files", f"--virtual-time-budget={budget}"]
    url = f"file:///{page.as_posix()}"
    started = time.time()
    try:
        done = subprocess.run(base + ["--dump-dom", url], capture_output=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "chrome: таймаут 300 с", "wall": 300}
    out = done.stdout.decode("utf-8", "replace")
    m = re.search(r'<div id="st"[^>]*>(.*?)</div>', out, re.S)
    if not m or not m.group(1).strip():
        return {"ok": False, "error": "нет статуса: страница не дорисовала за отведённое время", "wall": round(time.time() - started)}
    text = m.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    result = json.loads(text)
    result["wall"] = round(time.time() - started)
    if shot and result.get("ok"):
        subprocess.run(base + [f"--window-size={size}", f"--screenshot={(WORK / f'{name}-{version}.png').as_posix()}", url], capture_output=True, timeout=300)
    return result


BASE_REQ = 'requirement "Вход по паролю" {\n    id: "REQ-1"\n    text: "Система SHALL пускать"\n}\n'
BASE_ELEM = 'element "Сценарий успеха" {\n    type: "scenario"\n    docref: "spec.md:8"\n}\n'
CLS = "classDef sec fill:#fee2e2,stroke:#b91c1c,stroke-width:3px,stroke-dasharray:6 3\n"

CASES = {
    "база: requirement и element": "requirementDiagram\n" + BASE_REQ + BASE_ELEM + '"Сценарий успеха" - verifies -> "Вход по паролю"\n',
    "classDef и class по имени в кавычках": "requirementDiagram\n" + BASE_REQ + BASE_ELEM + CLS + 'class "Вход по паролю" sec\n',
    "::: в объявлении, имя в кавычках": 'requirementDiagram\nrequirement "Вход по паролю":::sec {\n    id: "REQ-1"\n    text: "t"\n}\nelement "Сценарий успеха":::sec {\n    type: "scenario"\n}\n' + CLS,
    "class со списком имён": "requirementDiagram\n" + BASE_REQ + BASE_ELEM + CLS + 'class "Вход по паролю","Сценарий успеха" sec\n',
    "style по имени": "requirementDiagram\n" + BASE_REQ + 'style "Вход по паролю" fill:#dbeafe,stroke:#1d4ed8\n',
    "id у element": 'requirementDiagram\nelement "Сценарий успеха" {\n    id: "SCN-3"\n    type: "scenario"\n}\n',
    "id в type у element": 'requirementDiagram\nelement "Сценарий успеха" {\n    type: "SCN-3"\n    docref: "spec.md:8"\n}\n',
    "id без кавычек: SEC-3": 'requirementDiagram\ndesignConstraint "Инъекции" {\n    id: SEC-3\n    text: "t"\n}\n',
    "id в кавычках: SEC-3": 'requirementDiagram\ndesignConstraint "Инъекции" {\n    id: "SEC-3"\n    text: "t"\n}\n',
    "шесть типов требований": "requirementDiagram\n" + "".join(
        f'{kind} "{kind} имя" {{\n    id: "X-{n}"\n    text: "t"\n}}\n' for n, kind in enumerate(
            ("requirement", "functionalRequirement", "interfaceRequirement", "performanceRequirement", "physicalRequirement", "designConstraint"), 1)),
    "имя класса кириллицей": 'requirementDiagram\n' + BASE_REQ + 'classDef безопасность fill:#fee2e2\nclass "Вход по паролю" безопасность\n',
    "имя класса с дефисом": 'requirementDiagram\n' + BASE_REQ + 'classDef kind-sec fill:#fee2e2\nclass "Вход по паролю" kind-sec\n',
    "классы до объявлений": 'requirementDiagram\n' + CLS + 'class "Вход по паролю" sec\n' + BASE_REQ,
    "direction LR и связь contains": 'requirementDiagram\ndirection LR\nrequirement "Родитель" {\n    id: "CAP-1"\n}\nrequirement "Вход" {\n    id: "REQ-1"\n}\n"Родитель" - contains -> "Вход"\n',
}

SAMPLE = """requirementDiagram
direction LR
classDef req fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px
classDef scn fill:#dcfce7,stroke:#15803d
classDef task fill:#fef9c3,stroke:#a16207
classDef rec fill:#f3e8ff,stroke:#7e22ce,stroke-dasharray:6 3
classDef sec fill:#fee2e2,stroke:#b91c1c,stroke-width:3px
requirement "Плагин показывает рекомендацию с причиной" {
    id: "REQ-1"
    text: "Карточка показывает вариант и why"
}
element "Карточка при поле text" {
    type: "SCN-1"
    docref: "specs/plugin-decision-view/spec.md:8"
}
element "Задача 3.2" {
    type: "TASK-3.2"
    docref: "tasks.md:24"
}
element "F-19 всегда вариант и why" {
    type: "REC_19"
    docref: "decisions.json"
}
designConstraint "Инъекции через содержимое файлов" {
    id: "SEC-1"
    text: "Закрывают требования плагина и страницы"
}
"Карточка при поле text" - verifies -> "Плагин показывает рекомендацию с причиной"
"Задача 3.2" - satisfies -> "Карточка при поле text"
"Плагин показывает рекомендацию с причиной" - traces -> "F-19 всегда вариант и why"
"Инъекции через содержимое файлов" - refines -> "Плагин показывает рекомендацию с причиной"
class "Плагин показывает рекомендацию с причиной" req
class "Карточка при поле text" scn
class "Задача 3.2" task
class "F-19 всегда вариант и why" rec
class "Инъекции через содержимое файлов" sec
"""


def main() -> None:
    lines = ["Проба F-54. requirementDiagram: classDef, id, стереотипы. Случаи — в render.py этого каталога.", ""]
    for name, src in CASES.items():
        for version in VERSIONS:
            r = render(src, version, name="c")
            if r["ok"]:
                sample = r["info"][0] if r["info"] else {}
                lines.append(f"{version} | {name} | годен | узлов {r['nodes']} | заливка {sample.get('fill','')} рамка {sample.get('stroke','')} толщина {sample.get('sw','')} штрих {sample.get('dash','')} | {sample.get('text','')[:60]}")
            else:
                lines.append(f"{version} | {name} | ОТКАЗ | {r['error'][:170]}".replace("\n", " "))
    lines.append("")
    for version in VERSIONS:
        r = render(SAMPLE, version, name="sample", shot=True, size="1500,900")
        lines.append(f"{version} | образец пяти видов | {'годен' if r['ok'] else 'ОТКАЗ ' + r.get('error','')[:200]}")
        for item in r.get("info", []):
            lines.append(f"    {item['fill']} {item['stroke']} {item['sw']} штрих {item['dash']} | {item['text']}")
    text = "\n".join(lines) + "\n"
    (Path(__file__).resolve().parent / "results.txt").write_text(text, encoding="utf-8", newline="\n")
    (Path(__file__).resolve().parent / "sample.mmd").write_text(SAMPLE, encoding="utf-8", newline="\n")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
