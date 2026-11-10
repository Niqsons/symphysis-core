"""Validated dispatcher context and the early global-entry delegation. Standard library only.

This module consumes a selected context; it never searches for a store or chooses
between installations. A discovery response alone has no execution lease.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONTEXT_ENV = "SYMPHYSIS_RUNTIME_CONTEXT"
TOOLS = {"journal": "journal.py", "trace": "trace_graph.py", "anchors": "anchor_refs.py",
         "sync-check": "sync_check.py", "help": "step_help.py", "config": "symphysis_config.py"}


class ContextError(ValueError):
    """An absent, stale or malformed execution context must not launch tools."""


def _object(value, label):
    if not isinstance(value, dict):
        raise ContextError(f"{label}: нужен JSON object")
    return value


def _read(file):
    try:
        return _object(json.loads(file.read_text(encoding="utf-8")), file.name)
    except (OSError, UnicodeError, ValueError) as error:
        raise ContextError(f"{file.name}: не прочитан корректный UTF-8 JSON") from error


def _absolute(value, label, *, directory=False):
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise ContextError(f"{label}: нужен абсолютный путь")
    file = Path(value)
    try:
        resolved = file.resolve(strict=True)
    except (OSError, ValueError) as error:
        raise ContextError(f"{label}: путь недоступен") from error
    if directory and not resolved.is_dir():
        raise ContextError(f"{label}: нужен каталог")
    return file


def _within(root, target):
    return target.resolve(strict=True).is_relative_to(root.resolve(strict=True))


def _same(first, second):
    return first.resolve(strict=True) == second.resolve(strict=True)


def _no_links(file):
    current = Path(file.anchor)
    for part in file.parts[1:]:
        current /= part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ContextError("Путь lease проходит через ссылку/reparse")


def _windows_process(pid):
    """Read a live process's parent, image and creation time; no shell or PID guessing.

    Win32 PROCESSENTRY32W / QueryFullProcessImageNameW / GetProcessTimes.
    https://learn.microsoft.com/windows/win32/api/tlhelp32/ns-tlhelp32-processentry32w
    """
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                    ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                    ("exe", wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = kernel.Process32FirstW.argtypes
    kernel.Process32NextW.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise OSError("Process snapshot unavailable")
    parent = None
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.pid == pid:
                parent = entry.parent
                break
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    process = kernel.OpenProcess(0x1000, False, pid)
    if parent is None or not process:
        if process:
            kernel.CloseHandle(process)
        raise OSError("Process identity unavailable")
    try:
        image = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(image))
        times = [wintypes.FILETIME() for _ in range(4)]
        exit_code = wintypes.DWORD()
        if not kernel.QueryFullProcessImageNameW(process, 0, image, ctypes.byref(length)) or not kernel.GetProcessTimes(process, *(ctypes.byref(value) for value in times)) or not kernel.GetExitCodeProcess(process, ctypes.byref(exit_code)) or exit_code.value != 259:
            raise OSError("Live process identity unavailable")
        created = ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) / 10000 - 11644473600000
        return {"parent": parent, "image": image.value, "created": created}
    finally:
        kernel.CloseHandle(process)


def _leased_parent(value, lease):
    if lease["pid"] == os.getppid():
        return True
    # CPython's Windows venv redirector launches the base interpreter and waits.
    # Accept precisely that declared intermediary, never arbitrary ancestors.
    launcher = value.get("launcher")
    if os.name != "nt" or not isinstance(launcher, dict) or launcher.get("kind") != "python":
        return False
    try:
        executable = _absolute(launcher.get("executable"), "launcher.executable")
        dispatcher = _absolute(launcher.get("dispatcherExecutable"), "launcher.dispatcherExecutable")
        if not _same(executable, Path(sys.executable)) or not (executable.parent.parent / "pyvenv.cfg").is_file():
            return False
        parent = _windows_process(os.getppid())
        owner = _windows_process(lease["pid"])
        child = _windows_process(os.getpid())
        return (parent["parent"] == lease["pid"] and _same(Path(parent["image"]), executable)
                and _same(Path(owner["image"]), dispatcher)
                and owner["created"] <= parent["created"] <= child["created"]
                and abs(owner["created"] - lease["startedAt"]) < 1000)
    except (ContextError, OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def _manifest(runtime, scope, store_root):
    root = _absolute(runtime.get("root"), "runtime.root", directory=True)
    tools = _absolute(runtime.get("toolsRoot"), "runtime.toolsRoot", directory=True)
    if not _same(tools, root / "tools") or not _within(root, tools):
        raise ContextError("Каталог tools не принадлежит выбранному runtime")
    schema = _absolute(runtime.get("schemaRoot"), "runtime.schemaRoot", directory=True)
    expected_schema = (store_root if scope == "local" else root) / "openspec" / "schemas" / "symphysis"
    if not _same(schema, expected_schema) or not _within(store_root if scope == "local" else root, schema):
        raise ContextError("Схема не принадлежит выбранной поставке")
    docs = _absolute(runtime.get("docsRoot"), "runtime.docsRoot", directory=True)
    if not _same(docs, root / "docs") or not _within(root, docs):
        raise ContextError("Общие документы не принадлежат выбранному runtime")
    generation = runtime.get("generation")
    if not isinstance(generation, str) or not generation:
        raise ContextError("Нет поколения выбранной поставки")
    for key in ("bootstrapApi", "runtimeApi", "schemaApi"):
        if type(runtime.get(key)) is not int or runtime[key] != 1:
            raise ContextError(f"Неподдерживаемый {key}")
    if runtime.get("legacy") is True:
        if scope != "local" or runtime.get("manifestPath") is not None or generation != "legacy-local" or root not in (store_root, store_root / ".symphysis"):
            raise ContextError("Некорректный контекст прежней local-поставки")
        return None, root if root != store_root else root / ".symphysis"
    manifest_file = _absolute(runtime.get("manifestPath"), "runtime.manifestPath")
    expected = root.parent / "install-manifest.json" if scope == "global" else root / "install-manifest.json"
    if scope == "global" and root.name != "runtime":
        raise ContextError("Некорректный корень global runtime")
    if scope == "local" and root not in (store_root, store_root / ".symphysis"):
        raise ContextError("Local runtime не принадлежит store")
    if not _same(manifest_file, expected):
        raise ContextError("Manifest не принадлежит выбранному runtime")
    manifest = _read(manifest_file)
    if type(manifest.get("format")) is not int or manifest["format"] != 1 or manifest.get("scope") != scope or manifest.get("generation") != generation:
        raise ContextError("Поколение или scope manifest изменились; повтори разрешение runtime")
    for key in ("bootstrapApi", "runtimeApi", "schemaApi"):
        if type(manifest.get(key)) is not int or manifest[key] != runtime[key]:
            raise ContextError(f"Неподдерживаемый {key}")
    if not isinstance(manifest.get("files"), list):
        raise ContextError("Manifest не содержит реестр файлов")
    return manifest, manifest_file.parent


def _resources(resources, runtime, manifest, scope, store_root):
    resources = _object(resources, "resources")
    registered = {}
    for entry in (manifest or {}).get("files", []):
        entry = _object(entry, "manifest.files[]")
        file = entry.get("path")
        if not isinstance(file, str) or not Path(file).is_absolute():
            raise ContextError("Manifest содержит относительный ресурс")
        registered[os.path.normcase(os.path.abspath(file))] = entry
    bases = {"tools": Path(runtime["toolsRoot"]), "docs": Path(runtime["docsRoot"]),
             "templates": Path(runtime["schemaRoot"]) / "templates"}
    for kind in ("tools", "docs", "skills", "templates"):
        for identity, target in _object(resources.get(kind), f"resources.{kind}").items():
            if not isinstance(identity, str) or not identity:
                raise ContextError("Ресурс не имеет имени")
            file = _absolute(target, f"resources.{kind}")
            if not file.is_file():
                raise ContextError("Именованный ресурс не является файлом")
            entry = registered.get(os.path.normcase(os.path.abspath(file)))
            if kind in bases and not _within(bases[kind], file):
                raise ContextError("Ресурс выходит за выбранную поставку")
            if kind == "skills" and scope == "global" and not _within(Path(runtime["root"]) / "skills", file):
                raise ContextError("Global skill не принадлежит выбранной поставке")
            if kind == "skills" and scope == "local" and not _within(store_root, file):
                allowed = False
                source = entry.get("source") if entry else None
                if manifest and isinstance(source, str) and source.startswith("skills/"):
                    suffix = source[len("skills/"):]
                    if suffix and not Path(suffix).is_absolute() and not any(part in ("", ".", "..") for part in re.split(r"[\\/]", suffix)):
                        for client in manifest.get("clients", []):
                            if not isinstance(client, dict) or (entry.get("clientId") and client.get("id") != entry["clientId"]):
                                continue
                            roots = client.get("skillsRoots", [])
                            if not isinstance(roots, list):
                                continue
                            for root in roots + ([client["skillsRoot"]] if client.get("skillsRoot") else []):
                                if isinstance(root, str) and Path(root).is_absolute() and os.path.normcase(os.path.abspath(Path(root) / suffix)) == os.path.normcase(os.path.abspath(file)):
                                    allowed = _within(Path(root), file)
                                    if allowed:
                                        break
                            if allowed:
                                break
                if not allowed:
                    raise ContextError("Local skill не принадлежит store или явно управляемому client skillsRoot")
            if manifest:
                if not entry or entry.get("projection") is True or entry.get("sha256") != hashlib.sha256(file.read_bytes()).hexdigest():
                    raise ContextError("Ресурс не подтверждён manifest выбранного поколения")
    asset_paths = {"mermaid": Path(runtime["toolsRoot"]) / "mermaid.min.js",
                   "mermaidLicense": Path(runtime["toolsRoot"]) / "mermaid.LICENSE",
                   "version": Path(runtime["toolsRoot"]) / "symphysis-version.txt",
                   "steps": Path(runtime["schemaRoot"]) / "steps.md"}
    for identity, target in _object(resources.get("assets", {}), "resources.assets").items():
        file = _absolute(target, "resources.assets")
        if identity not in asset_paths or not _same(file, asset_paths[identity]) or not file.is_file():
            raise ContextError("Неизвестный ресурс оформления выбранной поставки")
        if manifest:
            entry = registered.get(os.path.normcase(os.path.abspath(file)))
            if not entry or entry.get("projection") is True or entry.get("sha256") != hashlib.sha256(file.read_bytes()).hexdigest():
                raise ContextError("Ресурс оформления не подтверждён manifest выбранного поколения")
    schema = _object(resources.get("schema"), "resources.schema")
    if schema.get("name") != "symphysis" or not _same(_absolute(schema.get("path"), "resources.schema.path", directory=True), Path(runtime["schemaRoot"])):
        raise ContextError("Контекст ресурсов задаёт другую схему")


def consume_context():
    """Return a checked context or None for the unchanged source/legacy direct mode."""
    raw = os.environ.get(CONTEXT_ENV)
    if raw is None:
        return None
    try:
        value = _object(json.loads(raw), "Контекст dispatcher")
        if type(value.get("format")) is not int or value["format"] != 1 or value.get("scope") not in ("local", "global"):
            raise ContextError("Неподдерживаемый формат контекста dispatcher")
        store = _object(value.get("store"), "store")
        store_root = _absolute(store.get("root"), "store.root", directory=True)
        _absolute(store.get("sourceCwd"), "store.sourceCwd", directory=True)
        if not (store_root / "openspec").is_dir():
            raise ContextError("Выбранный store не имеет planning root")
        runtime = _object(value.get("runtime"), "runtime")
        manifest, management = _manifest(runtime, value["scope"], store_root)
        lease = _object(value.get("lease"), "lease")
        file = _absolute(lease.get("file"), "lease.file")
        _no_links(file)
        if not _same(file.parent, management / ".leases") or not re.fullmatch(r"[a-zA-Z0-9-]+\.json", file.name):
            raise ContextError("Lease не принадлежит выбранной поставке")
        record = _read(file)
        if type(record.get("format")) is not int or record["format"] != 1 or record.get("kind") != "reader":
            raise ContextError("Нет reader lease для исполнения инструмента")
        for key in ("id", "generation", "token", "pid", "startedAt", "instance"):
            if record.get(key) != lease.get(key) or record.get(key) is None:
                raise ContextError("Lease изменена или принадлежит другому запуску")
        if not isinstance(lease["id"], str) or not lease["id"] or not isinstance(lease["instance"], str) or not lease["instance"] or not re.fullmatch(r"[a-f0-9]{64}", str(lease["token"])):
            raise ContextError("Некорректная идентичность reader lease")
        if type(lease["pid"]) is not int or type(lease["startedAt"]) is not int or lease["startedAt"] <= 0 or lease["generation"] != runtime["generation"] or not _leased_parent(value, lease):
            raise ContextError("Lease не удерживается родительским dispatcher выбранного поколения")
        _resources(value.get("resources"), runtime, manifest, value["scope"], store_root)
        return value
    except ContextError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        raise ContextError("Контекст dispatcher не подтверждён; вызови инструмент через symphysis") from error


def context():
    """Read the explicit dispatcher context; no independent root discovery."""
    return consume_context()


def bootstrap(tool):
    """Before runtime imports, validate a leased child or delegate a direct global entry."""
    try:
        if tool not in TOOLS:
            raise ContextError("Неизвестный вход dispatcher")
        if consume_context() is not None:
            return
        here = Path(__file__).resolve().parent
        if here.name != "tools":
            return
        runtime = here.parent
        marker_file = runtime / ".symphysis-runtime.json"
        manifest_file = runtime.parent / "install-manifest.json"
        if not marker_file.exists() and runtime.name != "runtime":
            return
        marker = _read(marker_file) if marker_file.exists() else None
        manifest = _read(manifest_file) if manifest_file.exists() else None
        if marker is None and (manifest is None or manifest.get("scope") != "global"):
            return
        if marker is not None and (marker.get("format") != 1 or marker.get("scope") != "global"):
            raise ContextError("Некорректный marker global runtime")
        if manifest is None or manifest.get("format") != 1 or manifest.get("scope") != "global" or runtime.name != "runtime":
            raise ContextError("Global manifest отсутствует или повреждён; восстанови выбранную поставку")
        if not isinstance(manifest.get("files"), list):
            raise ContextError("Global manifest не содержит реестр файлов")
        target = _absolute(str(here / TOOLS[tool]), "global entrypoint")
        matches = [entry for entry in manifest.get("files", []) if isinstance(entry, dict) and entry.get("source") == f"tools/{TOOLS[tool]}" and entry.get("projection") is not True]
        if len(matches) != 1 or matches[0].get("path") != str(target) or matches[0].get("sha256") != hashlib.sha256(target.read_bytes()).hexdigest():
            raise ContextError("Global entrypoint не подтверждён manifest")
        launcher = _object(manifest.get("bootstrap"), "manifest.bootstrap")
        command = _absolute(launcher.get("command"), "bootstrap.command")
        prefix = launcher.get("args")
        if not command.is_file() or not isinstance(prefix, list) or not prefix or not all(isinstance(arg, str) and "\x00" not in arg for arg in prefix):
            raise ContextError("Global bootstrap не задан; переустанови поставку через symphysis")
        entry = _absolute(prefix[0], "bootstrap.args[0]")
        if not entry.is_file():
            raise ContextError("Bootstrap entrypoint недоступен")
        done = subprocess.run([str(command), *prefix, "--project", str(Path.cwd()), tool, *sys.argv[1:]],
                              cwd=str(Path.cwd()), shell=False, check=False)
        raise SystemExit(done.returncode)
    except (ContextError, OSError) as error:
        print(f"symphysis: {error}", file=sys.stderr)
        raise SystemExit(2) from error
