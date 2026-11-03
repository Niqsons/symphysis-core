# -*- coding: utf-8 -*-
"""Проба: как открыть файл на строке в IDE на платформе IntelliJ по ссылке со страницы symphysis.html.
Одноразовая. Своя песочница настроек, кэшей и плагинов во временном каталоге, настройки человека не затрагиваются; реестр не меняется; на экране
ненадолго появляется окно IDE. Протоколов idea:// и jetbrains:// в Windows нет, поэтому `jetbrains://` передаётся запускающему файлу IDE напрямую:
так проверяется сама команда, а не связка с браузером.

Внимание: блок FileEditorManager в `workspace.xml` оказался негодной уликой. Он пуст, хотя файлы открылись: a.py на строке 12 и пакет/b.py на строке 7 видел
владелец на экране, 2026-11-03. Смотреть надо на окно IDE. Третья форма, без проекта и с абсолютным путём, дала ошибку открытия URL.

Запуск: python -X utf8 docs/analysis/client-probe-ide-link.py <каталог IDE>"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

IDE = Path(sys.argv[1])
T = Path(tempfile.mkdtemp(prefix="ide-link-"))
PORTS = range(63342, 63362)
CHROME = next((p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe") if Path(p).is_file()), None)


def clean(text):
    for form in (str(T), str(T).replace("\\", "/"), urllib.parse.quote(str(T).replace("\\", "/"), safe="/:"), urllib.parse.quote(str(T).replace("\\", "/"), safe="/")):
        text = str(text).replace(form, "<T>")
    return text


def get(url, timeout=20):
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
            return r.status, r.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(300).decode("utf-8", "replace")
    except OSError as e:
        return None, type(e).__name__


product = json.loads((IDE / "product-info.json").read_text(encoding="utf-8"))
print(f"Проба 2026-11-03: {product['name']} {product['version']}, сборка {product['buildNumber']}")

box = T / "box"
for name in ("config", "system", "plugins", "log"):
    (box / name).mkdir(parents=True)
project = T / "проект с пробелами"
(project / "пакет").mkdir(parents=True)
(project / "a.py").write_text("".join(f"line_{i} = {i}\n" for i in range(1, 31)), encoding="utf-8")
(project / "пакет" / "b.py").write_text("".join(f"value_{i} = {i}\n" for i in range(1, 31)), encoding="utf-8")
(project / "c.ts").write_text("".join(f"const c{i} = {i};\n" for i in range(1, 31)), encoding="utf-8")
slash = lambda p: str(p).replace("\\", "/")
(box / "idea.properties").write_text("".join(f"idea.{k}.path={slash(box / k)}\n" for k in ("config", "system", "plugins", "log")), encoding="utf-8")
vm = (IDE / "bin" / "idea64.exe.vmoptions").read_text(encoding="utf-8").splitlines() + [
    "-Didea.trust.all.projects=true", "-Didea.initially.ask.config=never", "-Djb.consents.confirmation.enabled=false",
    "-Djb.privacy.policy.text=<!--999.999-->", "-Dide.newUsersOnboarding=false", "-Dide.experimental.ui.onboarding=false",
    "-Dide.show.tips.on.startup.default.value=false",
]
(box / "vm.options").write_text("\n".join(vm) + "\n", encoding="utf-8")
(box / "config" / "options").mkdir()
# Окно «Confirm Exit» держало штатное закрытие: человек видел его на экране.
(box / "config" / "options" / "ide.general.xml").write_text('<application><component name="GeneralSettings"><option name="confirmExit" value="false" /></component></application>\n', encoding="utf-8")
env = {k: v for k, v in os.environ.items() if not re.match(r"^(VSCODE_|ELECTRON_)", k) and k not in ("NoDefaultCurrentDirectoryInExePath", "PYTHONIOENCODING")}
env.update(IDEA_PROPERTIES=str(box / "idea.properties"), IDEA_VM_OPTIONS=str(box / "vm.options"))

proc = subprocess.Popen([str(IDE / "bin" / "idea64.exe"), str(project)], env=env)
print("запущена, идёт ожидание встроенного сервера")
port, started = None, time.time()
while port is None and time.time() - started < 180:
    for candidate in PORTS:
        status, body = get(f"http://127.0.0.1:{candidate}/api/about", timeout=2)
        if status == 200 and "name" in body:
            port = candidate
            break
    time.sleep(2)
print("порт:", port, "| за", round(time.time() - started), "с")


def stop():
    subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-Process -Id {proc.pid} -ErrorAction SilentlyContinue).CloseMainWindow() | Out-Null"], capture_output=True)
    try:
        proc.wait(45)
        print("закрыта штатно, код", proc.returncode)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        print("не закрылась за 45 с, снята")


if port is None:
    print("СТОП: сервер IDE не ответил")
    stop()
    shutil.rmtree(T, ignore_errors=True)
    sys.exit(0)

time.sleep(70)  # проект успевает открыться и пройти анализ: команда раньше него может потеряться
abs_path = lambda p: urllib.parse.quote(slash(p), safe="/:")

print("\n--- 1. служба открытия файла встроенного сервера")
status, body = get(f"http://localhost:{port}/api/file?file={urllib.parse.quote(slash(project / 'a.py'))}&line=3")
print("  /api/file: ответ", status)


def navigate(title, query):
    url = "jetbrains://idea/navigate/reference?" + query
    launcher = subprocess.Popen([str(IDE / "bin" / "idea64.exe"), url], env=env)
    try:
        launcher.wait(30)
        code = launcher.returncode
    except subprocess.TimeoutExpired:
        code = "ещё работает через 30 с"
    print(f"  {title}: запускающий файл вернул {code}")
    time.sleep(5)


name = urllib.parse.quote(project.name)
print("\n--- 2. команда jetbrains://, переданная запускающему файлу")
navigate("проект и путь от корня, a.py:11", f"project={name}&path=a.py:11")
navigate("кириллица в пути, пакет/b.py:6", f"project={name}&path={urllib.parse.quote('пакет/b.py')}:6")
navigate("без проекта, абсолютный путь, c.ts:19", f"path={urllib.parse.quote(slash(project / 'c.ts'))}:19")

stop()
time.sleep(1)
# Каталог проекта: `.idea` у IDEA, `.gigaide` у GIGA IDE.
workspace = next(project.glob(".*/workspace.xml"), project / ".idea" / "workspace.xml")
print("\nкаталоги проекта:", sorted(q.name for q in project.iterdir() if q.is_dir()), "| workspace.xml в:", workspace.parent.name)
log = box / "log" / "idea.log"
if log.is_file():
    lines = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if re.search(r"jetbrains://|JBProtocol|navigate/reference|protocol command|external command", line, re.I)]
    print("строк журнала IDE про команду:", len(lines))
    for line in lines[:8]:
        print("  ", clean(line)[:230])
if workspace.is_file():
    text = workspace.read_text(encoding="utf-8")
    block = re.search(r'<component name="FileEditorManager">.*?</component>', text, re.S)
    print("\n--- что записала IDE: открытые файлы и строка курсора (в файле счёт с нуля)")
    for entry in re.finditer(r'<entry file="([^"]+)".*?(?:<caret line="(\d+)"|</entry>)', block.group(0) if block else "", re.S):
        print("  ", clean(urllib.parse.unquote(entry.group(1))), "| строка", None if entry.group(2) is None else int(entry.group(2)) + 1)
    if not block:
        print("  блока FileEditorManager нет; это не значит, что файлы не открылись: смотреть на окно IDE")
else:
    print("\nworkspace.xml нет")
shutil.rmtree(T, ignore_errors=True)
print("--- конец")
