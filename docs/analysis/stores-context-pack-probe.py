# -*- coding: utf-8 -*-
"""Проба: хранилище OpenSpec со схемой symphysis и пакет контекста. Одноразовая.
Реестр и конфиг форка — во временном каталоге: глобальные настройки человека не трогаются."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SYMPHYSIS = Path(r"X:\symphysis")
T = Path(tempfile.mkdtemp(prefix="stores-probe-"))
ENV = {**os.environ, "XDG_DATA_HOME": str(T / "data"), "XDG_CONFIG_HOME": str(T / "config"), "OPENSPEC_TELEMETRY": "0"}
OPENSPEC = shutil.which("openspec")


def clean(text):
    for form in (str(T), str(T).replace("\\", "\\\\"), T.as_posix()):
        text = text.replace(form, "<T>")
    return text


def run(cwd, *args, cmd=None):
    r = subprocess.run([cmd or OPENSPEC, *args], cwd=cwd, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, clean(r.stdout), clean(r.stderr)


def head(title):
    print(f"\n--- {title}")


def show(cwd, *args, lines=12, width=170):
    code, out, err = run(cwd, *args)
    print(f"$ openspec {' '.join(args)}  # из {Path(cwd).name}; код {code}")
    for line in (out + err).splitlines()[:lines]:
        print("  " + line[:width])


def as_json(cwd, *args):
    code, out, err = run(cwd, *args)
    try:
        return code, json.loads(out), err
    except json.JSONDecodeError:
        return code, None, out + err


print("Проба 2026-11-02, Windows. Форк:", run(T, "--version")[1].strip())
plans, wt, a, b = T / "plans", T / "plans-wt", T / "repo-a", T / "repo-b"

head("1. хранилище и схема symphysis в нём")
show(T, "store", "setup", "demo-plans", "--path", str(plans), lines=4)
print("  состав:", sorted(p.name for p in plans.iterdir() if p.name != ".git"), "| store.yaml:", (plans / ".openspec-store/store.yaml").read_text().split())
shutil.copytree(SYMPHYSIS / "openspec/schemas", plans / "openspec/schemas")
shutil.copy(SYMPHYSIS / "openspec/config.symphysis.yaml", plans / "openspec/config.yaml")
(plans / "openspec/specs/pay").mkdir(parents=True)
(plans / "openspec/specs/pay/spec.md").write_text("# pay\n\n## Purpose\nПлатёжный контракт между компонентами.\n\n## Requirements\n\n### Requirement: R\nSHALL.\n\n#### Scenario: S\n- **WHEN** a\n- **THEN** b\n", encoding="utf-8")

head("2. репозиторий-указатель repo-a: новое изменение без флагов")
(a / "openspec").mkdir(parents=True)
(a / "openspec/config.yaml").write_text("store: demo-plans\ncontext: REPO-A-MARKER\ncontext_pack: .context/00-start-here.md\n", encoding="utf-8")
show(a, "new", "change", "add-demo", lines=4)
print("  .openspec.yaml:", (plans / "openspec/changes/add-demo/.openspec.yaml").read_text().split())

head("3. instructions из repo-a: что видно из его config.yaml")
code, d, err = as_json(a, "instructions", "intent", "--change", "add-demo", "--json")
print("  код", code, "схема", d["schemaName"], "| REPO-A-MARKER в context:", "REPO-A-MARKER" in (d.get("context") or ""), "| context из хранилища:", "symphysis" in (d.get("context") or ""))
print("  stderr о неизвестном ключе context_pack:", "context_pack" in err, "| поле references:", d.get("references"))
print("  changeDir:", clean(d["changeDir"]))

head("4. status из repo-a: блок root и пути")
code, d, err = as_json(a, "status", "--change", "add-demo", "--json")
print("  root:", clean(json.dumps(d.get("root"), ensure_ascii=False)))
print("  путь intent:", clean(d["artifactPaths"]["intent"]["resolvedOutputPath"]))

head("5. знает ли хранилище о репозиториях-указателях")
show(a, "context", "--json", lines=9)
_, out, _ = run(plans, "context", "--json")
print("  вхождений repo-a в context --json из хранилища:", out.count("repo-a"))

head("6. repo-b: свой корень и references")
(b / "openspec").mkdir(parents=True)
(b / "openspec/config.yaml").write_text("schema: spec-driven\nreferences:\n  - demo-plans\ncontext_pack: .context/00-start-here.md\n", encoding="utf-8")
run(b, "new", "change", "impl")
code, d, err = as_json(b, "instructions", "proposal", "--change", "impl", "--json")
print("  код", code, "| references:", clean(json.dumps(d.get("references"), ensure_ascii=False))[:330])
print("  context_pack в выводе:", "context_pack" in json.dumps(d), "| предупреждение:", "context_pack" in err)

head("7. worktree хранилища и регистрация второй копии")
subprocess.run(["git", "-C", str(plans), "add", "-A"], capture_output=True)
subprocess.run(["git", "-C", str(plans), "-c", "user.email=p@p", "-c", "user.name=p", "commit", "-qm", "wip"], capture_output=True)
subprocess.run(["git", "-C", str(plans), "worktree", "add", "-q", str(wt), "-b", "wt"], capture_output=True)
run(wt, "new", "change", "only-in-wt")
print("  в worktree:", sorted(p.name for p in (wt / "openspec/changes").iterdir()), "| в основной копии:", sorted(p.name for p in (plans / "openspec/changes").iterdir()))
code, d, err = as_json(a, "status", "--change", "only-in-wt", "--json")
print("  status из repo-a изменения из worktree: код", code, "|", clean(json.dumps(d, ensure_ascii=False))[:150] if d else (err[:150]))
show(T, "store", "register", str(wt), "--id", "demo-plans", lines=2, width=190)

head("8. workset как карта имён и путей")
run(T, "workset", "create", "demo", "--member", str(plans), "--member", str(a), "--tool", "code")
code, d, err = as_json(T, "workset", "list", "--json")
print("  ", clean(json.dumps(d["worksets"], ensure_ascii=False)))

head("9. doctor из repo-b")
code, d, err = as_json(b, "doctor", "--json")
print("  код", code, "| references:", clean(json.dumps(d.get("references"), ensure_ascii=False))[:220])

head("10. symphysis install в хранилище")
code, out, err = run(plans, str(SYMPHYSIS / "installer/bin/symphysis.js"), "install", cmd=shutil.which("node"))
print("  код", code)
for line in (out + err).splitlines()[-9:]:
    print("  " + line[:170])
print("  состав:", sorted(p.name for p in plans.iterdir() if p.name != ".git"))
print("  схема в config.yaml:", "schema: symphysis" in (plans / "openspec/config.yaml").read_text(encoding="utf-8"), "| корни улик:", (plans / ".symphysis/tools/journal-roots.json").read_text().strip() if (plans / ".symphysis/tools/journal-roots.json").exists() else "нет")
print("  что видно из repo-a: каталог .symphysis:", (a / ".symphysis").exists(), "| скиллы .claude:", (a / ".claude").exists())

head("11. инструменты журнала в хранилище: цитата из repo-a через префикс корней")
(a / "src").mkdir()
(a / "src/x.py").write_text("def pay():\n    return 42\n", encoding="utf-8")
(plans / ".symphysis/tools/journal-roots.json").write_text(json.dumps({"": "<root>/..", "repo-a/": str(a)}), encoding="utf-8")
journal = plans / "openspec/changes/add-demo/decisions.json"
evidence = {"path": "repo-a/src/x.py", "quote": "return 42"}
option = {"letter": "A", "text": "вариант", "added": False, "unlikely": None, "evidence": [evidence]}
record = {"id": "F-01", "question": "вопрос?", "kind": "развилка", "status": "открыт", "addressee": "человек", "depends_on": [], "delivery": "",
          "options": [option], "antipodes": [], "recommendation": {"option": "A", "why": "w", "text": "A"}, "decision": None, "reversibility": None,
          "outcome": None, "parking": [], "dispute": "", "consequences": "", "evidence": [evidence], "comments": []}
journal.write_text(json.dumps({"title": "t", "source": "s", "records": [record]}, ensure_ascii=False), encoding="utf-8")
code, out, err = run(plans, ".symphysis/tools/journal.py", "check", str(journal), cmd=sys.executable)
print("  код", code, "|", (out + err).strip()[:220])

shutil.rmtree(T, ignore_errors=True)
print("\n--- конец")
