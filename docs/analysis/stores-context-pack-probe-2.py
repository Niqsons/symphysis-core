# -*- coding: utf-8 -*-
"""Вторая проба к раунду замечаний b36c: реализация из репозитория кода, пакет в openspec/context, схема на уровне пользователя.
Одноразовая. Реестр и конфиг форка — во временном каталоге: глобальные настройки человека не трогаются."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SYMPHYSIS = Path(r"X:\symphysis")
T = Path(tempfile.mkdtemp(prefix="stores-probe2-"))
ENV = {**os.environ, "XDG_DATA_HOME": str(T / "data"), "XDG_CONFIG_HOME": str(T / "config"), "OPENSPEC_TELEMETRY": "0"}
OPENSPEC = shutil.which("openspec")


def clean(text):
    for form in (str(T), str(T).replace("\\", "\\\\"), T.as_posix()):
        text = text.replace(form, "<T>")
    return text


def run(cwd, *args):
    r = subprocess.run([OPENSPEC, *args], cwd=cwd, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, clean(r.stdout), clean(r.stderr)


def as_json(cwd, *args):
    code, out, err = run(cwd, *args)
    try:
        return code, json.loads(out), err
    except json.JSONDecodeError:
        return code, None, out + err


def head(title):
    print(f"\n--- {title}")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


print("Проба 2026-11-03, Windows. Форк:", run(T, "--version")[1].strip())
plans, code_repo, plain = T / "plans", T / "codebase1", T / "plain"

head("1. хранилище со схемой symphysis, изменение с готовым tasks.md")
run(T, "store", "setup", "demo-plans", "--path", str(plans))
shutil.copytree(SYMPHYSIS / "openspec/schemas", plans / "openspec/schemas")
shutil.copy(SYMPHYSIS / "openspec/config.symphysis.yaml", plans / "openspec/config.yaml")
code, out, err = run(plans, "new", "change", "add-demo")
print("  new change: код", code)
change = plans / "openspec/changes/add-demo"
meta = change / ".openspec.yaml"
meta.write_text(meta.read_text(encoding="utf-8") + "x-symphysis-components:\n  comp1: [codebase1, comp1-backend]\n", encoding="utf-8")
write(change / "tasks.md", "# Задачи\n\n## 1. codebase1: контракт\n\n- [ ] 1.1 Первая задача\n- [x] 1.2 Вторая задача\n\n## 2. comp1-backend: приёмник\n\n- [ ] 2.1 Третья задача\n")

head("2. репозиторий кода: указатель store и пакет в openspec/context, своих изменений нет")
write(code_repo / "openspec/config.yaml", "store: demo-plans\nx-symphysis-context-pack: openspec/context\n")
write(code_repo / "openspec/context/00-start-here.md", "# Перед любой задачей\n")
write(code_repo / "src/x.py", "def pay():\n    return 42\n")
code, d, err = as_json(code_repo, "status", "--change", "add-demo", "--json")
print("  status из репозитория кода: код", code, "| корень:", clean(json.dumps(d.get("root"), ensure_ascii=False)) if d else err[:200])
print("  предупреждение о ключе x-symphysis-context-pack:", "x-symphysis" in err, "| о каталоге context:", "context/" in err)

head("3. instructions apply из репозитория кода: что получит сессия реализации")
code, d, err = as_json(code_repo, "instructions", "apply", "--change", "add-demo", "--json")
print("  код", code)
if d:
    print("  state:", d.get("state"), "| progress:", json.dumps(d.get("progress"), ensure_ascii=False))
    print("  tasks:", clean(json.dumps(d.get("tasks"), ensure_ascii=False))[:360])
    print("  contextFiles:", clean(json.dumps(d.get("contextFiles"), ensure_ascii=False))[:360])
    print("  поля:", sorted(d.keys()))
    print("  missingArtifacts:", d.get("missingArtifacts"), "| missingPrerequisites:", d.get("missingPrerequisites"))
    for rel in (d.get("missingPrerequisites") or d.get("missingArtifacts") or []):
        print("   не хватает:", rel)
code, st, err = as_json(code_repo, "status", "--change", "add-demo", "--json")
for art in st["artifacts"]:
    out_rel = (st["artifactPaths"].get(art["id"], {}).get("resolvedOutputPath") or "").replace("<T>", str(T))
    if art["status"] == "done" or not out_rel or "attack" in art["id"]:
        continue
    write(change / "specs/pay/spec.md" if "*" in out_rel else Path(out_rel), "# заглушка пробы\n")
code, st, err = as_json(code_repo, "status", "--change", "add-demo", "--json")
print("  после заглушек артефактов:", {a["id"]: a["status"] for a in st["artifacts"]})
code, d, err = as_json(code_repo, "instructions", "apply", "--change", "add-demo", "--json")
print("  apply снова: код", code, "| state:", (d or {}).get("state"), "| progress:", json.dumps((d or {}).get("progress"), ensure_ascii=False), "| missing:", (d or {}).get("missingArtifacts"), (d or {}).get("missingPrerequisites"))
print("  contextFiles, ключи:", sorted(((d or {}).get("contextFiles") or {}).keys()))

head("4. x- в .openspec.yaml: после команд, validate, архив")
print("  после status и instructions:", "x-symphysis-components" in meta.read_text(encoding="utf-8"))
code, d, err = as_json(plans, "validate", "add-demo", "--json")
print("  validate: код", code, "| упоминание x-:", "x-symphysis" in json.dumps(d or {}, ensure_ascii=False) + err)
if d:
    issues = [i.get("message") for it in d.get("items", []) for i in it.get("issues", [])]
    print("  причины validate:", clean(json.dumps(issues, ensure_ascii=False))[:240])
code, out, err = run(plans, "archive", "add-demo", "--yes", "--skip-specs", "--no-validate")
archived = list((plans / "openspec/changes/archive").glob("*add-demo*/.openspec.yaml"))
print("  archive: код", code, "| x- в архиве:", bool(archived) and "x-symphysis-components" in archived[0].read_text(encoding="utf-8"))

head("5. схема только на уровне пользователя, в проекте копии нет")
user_schemas = T / "data/openspec/schemas"
shutil.copytree(SYMPHYSIS / "openspec/schemas/symphysis", user_schemas / "symphysis")
write(plain / "openspec/config.yaml", "schema: symphysis\n")
code, out, err = run(plain, "new", "change", "c1")
print("  new change: код", code, "|", (plain / "openspec/changes/c1/.openspec.yaml").read_text(encoding="utf-8").split() if (plain / "openspec/changes/c1/.openspec.yaml").exists() else err[:200])
code, d, err = as_json(plain, "schemas", "--json")
if d:
    found = [s for s in d if s.get("name") == "symphysis"] if isinstance(d, list) else d
    print("  источник схемы:", [(s.get("name"), s.get("source"), s.get("path")) for s in found] if isinstance(found, list) else found)

head("6. копия в проекте против копии пользователя: кто выигрывает")
shutil.copytree(SYMPHYSIS / "openspec/schemas/symphysis", plain / "openspec/schemas/symphysis")
marker = plain / "openspec/schemas/symphysis/schema.yaml"
marker.write_text(marker.read_text(encoding="utf-8").replace("name: symphysis", "name: symphysis\n# проектная копия", 1), encoding="utf-8")
code, d, err = as_json(plain, "schemas", "--json")
if d:
    found = [s for s in d if s.get("name") == "symphysis"] if isinstance(d, list) else d
    print("  источник схемы:", [(s.get("name"), s.get("source"), s.get("path")) for s in found] if isinstance(found, list) else found)
code, d, err = as_json(plain, "status", "--change", "c1", "--json")
print("  status: код", code)

head("7. схема на изменение: две версии рядом под разными именами")
shutil.copytree(SYMPHYSIS / "openspec/schemas/symphysis", user_schemas / "symphysis-2")
second = user_schemas / "symphysis-2/schema.yaml"
second.write_text(second.read_text(encoding="utf-8").replace("name: symphysis", "name: symphysis-2", 1), encoding="utf-8")
write(plain / "openspec/config.yaml", "schema: symphysis-2\n")
run(plain, "new", "change", "c2")
for name in ("c1", "c2"):
    code, d, err = as_json(plain, "status", "--change", name, "--json")
    print(f"  {name}: код {code} | схема изменения:", (d or {}).get("schemaName"), "|", (plain / f"openspec/changes/{name}/.openspec.yaml").read_text(encoding="utf-8").split()[:2])

shutil.rmtree(T, ignore_errors=True)
print("\n--- конец")
