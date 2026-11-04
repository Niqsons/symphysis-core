# -*- coding: utf-8 -*-
"""Проба F-93: от какого корня считают вердикт улики и карта ссылок, когда инструменты лежат вне проекта (`symphysis.toolsPath`). Установка и проект — временные каталоги,
инструменты скопированы из этого worktree в раскладке инсталлятора. Заодно: какой файл `info/exclude` называет git в рабочем дереве. След — probe.log рядом, пути заменены метками."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
LOG = HERE / "probe.log"
ROOT = HERE.parents[4]
work = Path(tempfile.mkdtemp(prefix="roots probe "))
install, project = work / "install", work / "project"
tools = install / ".symphysis" / "tools"
tools.mkdir(parents=True)
for f in (ROOT / "tools").glob("*"):
    if f.is_file() and re.match(r"journal.*\.py|step_help\.py|symphysis_config\.py|playground-template\.html|mermaid\.min\.js", f.name):
        shutil.copy(f, tools / f.name)
(install / ".symphysis" / "docs").mkdir()
shutil.copy(ROOT / "docs" / "journal.schema.json", install / ".symphysis" / "docs" / "journal.schema.json")
(tools / "journal-roots.json").write_text('{"": "<root>/.."}\n', encoding="utf-8")  # так пишет инсталлятор
(install / "src").mkdir()
(install / "src" / "both.py").write_text("в установке\n", encoding="utf-8")
(install / "src" / "only_install.py").write_text("в установке\n", encoding="utf-8")
(project / "src").mkdir(parents=True)
(project / "src" / "both.py").write_text("в проекте\n", encoding="utf-8")
(project / "src" / "only_project.py").write_text("в проекте\n", encoding="utf-8")
change = project / "openspec" / "changes" / "demo"
change.mkdir(parents=True)
journal = {"title": "demo", "source": "decisions.json", "intro": "", "notes": [], "records": [{
    "id": "F-01", "question": "Файлы проекта", "kind": "факт", "status": "решён", "addressee": "материалы", "depends_on": [], "delivery": "", "options": [], "antipodes": [],
    "recommendation": None, "decision": None, "reversibility": None, "outcome": None, "parking": [], "dispute": "", "consequences": "",
    "evidence": [{"path": p, "quote": "в "} for p in ("src/both.py", "src/only_project.py", "src/only_install.py")], "comments": [], "nodes": []}]}
(change / "decisions.json").write_text(json.dumps(journal, ensure_ascii=False, indent=1), encoding="utf-8")


def clean(text):
    text = str(text)
    for value, mark in ((str(work), "<work>"), (str(ROOT), "<worktree>")):
        for form in (value.replace("\\", "\\\\"), value, value.replace("\\", "/")):
            text = text.replace(form, mark)
    return re.sub(r"[A-Za-z]:/[^\s\"']*/\.git/", "<основной клон>/.git/", text)


def core(*args):
    return subprocess.run([sys.executable, "-X", "utf8", str(tools / "journal.py"), *args], cwd=project, capture_output=True, encoding="utf-8", errors="replace")


out = []
try:
    page = core("render-html", "openspec/changes/demo/decisions.json", "--out", "openspec/changes/demo/symphysis.html")
    out.append(json.dumps({"case": "render-html, инструменты вне проекта", "code": page.returncode, "output": clean(page.stdout + page.stderr).splitlines()}, ensure_ascii=False))
    html = (change / "symphysis.html").read_text(encoding="utf-8")
    links = {name: (re.search(r'"src/' + name + r'":\s*"([^"]+)"', html) or [None, None])[1] for name in ("both.py", "only_project.py", "only_install.py")}
    out.append(json.dumps({"case": "карта ссылок на странице", "links": links}, ensure_ascii=False))
    view = core("view-json", "openspec/changes/demo/decisions.json")
    verdicts = {e["path"]: e.get("verdict") for e in json.loads(view.stdout)["records"][0]["evidence"]}
    out.append(json.dumps({"case": "вердикты view-json", "verdicts": verdicts}, ensure_ascii=False))
finally:
    shutil.rmtree(work, ignore_errors=True)
git = subprocess.run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace")
out.append(json.dumps({"case": "git в рабочем дереве", "exclude": clean(git.stdout.strip())}, ensure_ascii=False))
LOG.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
print(LOG.read_text(encoding="utf-8"))
