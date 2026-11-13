"""Локальный план тестов Symphysis по явному Git-сравнению."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / name) for name in ("tools", "trace", "roots", "runtime")]
from trace_modules import DeclarationError, module, owner, read_declaration

CORE = "symphysis-core"
VSCODE = "symphysis-vscode"
GROUPS = ("core", "browser", "installer", "vscode")
GROUP_REPOSITORY = {"core": CORE, "browser": CORE, "installer": CORE, "vscode": VSCODE}
CONTRACT = "test/unit/contract.test.ts"
GRAPH_SCRIPT = "e2e:graph"
VSCODE_REAL_CORE = frozenset((
    CONTRACT, "test/unit/core-files.test.ts", "test/unit/views.test.tsx",
    "src/core/test/core.test.ts", "src/core/test/project.test.ts", "src/scheme/test/scheme.test.ts",
    "src/viewer/test/apply.test.ts", "src/step-help/test/help-view.test.tsx",
    "src/step-help/test/step-help.test.ts",
))


class PlanError(ValueError):
    """Сравнение или план не могут быть завершены."""


@dataclass(frozen=True)
class Change:
    before: str | None
    after: str | None
    previous: str
    current: str


@dataclass(frozen=True)
class Comparison:
    root: Path
    base: str
    head: str
    changes: tuple[Change, ...]
    commit: str | None = None


def git_executable() -> Path:
    name = "git.exe" if os.name == "nt" else "git"
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        folder = Path(entry)
        if folder.is_absolute() and (folder / name).is_file():
            return folder / name
    raise PlanError("Git не найден в абсолютных каталогах PATH")


def git(root: Path, *args: str, input_data: bytes | None = None) -> bytes:
    # Git получает только выбранное дерево. Унаследованные GIT_DIR, индекс,
    # подмены объектов и внешний diff не участвуют в сравнении.
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    try:
        result = subprocess.run(
            [str(git_executable()), "--no-replace-objects", "-c", "core.fsmonitor=false",
             "-C", str(root), *args],
            capture_output=True, env=env, input=input_data, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PlanError(f"Git {args[0]}: {error}") from None
    if result.returncode:
        reason = result.stderr.decode("utf-8", errors="replace").strip()
        raise PlanError(f"Git {args[0]} (код {result.returncode}): {reason}")
    return result.stdout


def worktree(path: Path) -> Path:
    try:
        root = path.resolve(strict=True)
        if not root.is_dir() or git(root, "rev-parse", "--is-inside-work-tree").strip() != b"true":
            raise PlanError("не является рабочим деревом Git")
        top = Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel").rstrip(b"\r\n"))).resolve(strict=True)
        if top != root:
            raise PlanError("нужен корень рабочего дерева Git")
    except (OSError, ValueError, RuntimeError) as error:
        raise PlanError(f"Недоступное рабочее дерево {path}: {error}") from None
    return root


def revision(root: Path, value: str) -> str:
    try:
        resolved = git(root, "rev-parse", "--verify", "--end-of-options", f"{value}^{{commit}}").strip()
    except PlanError as error:
        raise PlanError(f"Не разрешена ревизия {value!r}: {error}") from None
    if not re.fullmatch(rb"(?:[0-9a-f]{40}|[0-9a-f]{64})", resolved):
        raise PlanError(f"Git вернул неверный идентификатор ревизии {value!r}")
    return resolved.decode("ascii")


def relative_path(value: str) -> str:
    if (not value or "\\" in value or "\x00" in value or PureWindowsPath(value).anchor
            or PurePosixPath(value).is_absolute() or any(part in ("", ".", "..") for part in value.split("/"))
            or (os.name == "nt" and ":" in value)):
        raise PlanError(f"Путь вне рабочего дерева или неверный относительный путь: {value!r}")
    return value


def nul_fields(data: bytes) -> list[bytes]:
    if not data:
        return []
    if not data.endswith(b"\0"):
        raise PlanError("Git вернул незавершённый список путей")
    return data[:-1].split(b"\0")


def git_path(data: bytes) -> str:
    return relative_path(os.fsdecode(data))


def diff(root: Path, previous: str, current: str, *args: str) -> list[Change]:
    fields = iter(nul_fields(git(root, "diff", "--name-status", "-z", "--find-renames", "--no-ext-diff",
                                 "--no-textconv", "--ignore-submodules=dirty", *args, "--")))
    changes = []
    for status in fields:
        try:
            path = git_path(next(fields))
            if status.startswith((b"R", b"C")):
                before, after = path, git_path(next(fields))
            else:
                before = None if status == b"A" else path
                after = None if status == b"D" else path
        except StopIteration:
            raise PlanError("Git вернул неполную запись изменения пути") from None
        changes.append(Change(before, after, previous, current))
    return changes


def compare(path: Path, mode: str, ref: str, parent: str | None = None) -> Comparison:
    root = worktree(path)
    target = revision(root, ref)
    head = revision(root, "HEAD")
    if mode == "change":
        if parent is not None:
            raise PlanError("Родитель сравнения применяется только к коммиту")
        paths = [
            *(diff(root, target, head, target, head) if target != head else ()),
            *diff(root, head, "index", "--cached", head),
            *diff(root, "index", "worktree"),
        ]
        paths.extend(Change(None, git_path(item), "index", "worktree")
                     for item in nul_fields(git(root, "ls-files", "--others", "--exclude-standard", "-z")))
        return Comparison(root, target, head, tuple(paths))
    if mode != "commit":
        raise PlanError(f"Неизвестный режим сравнения {mode!r}")
    ancestry = git(root, "rev-list", "--parents", "-n", "1", target).decode("ascii").split()
    parents = ancestry[1:]
    if not parents:
        raise PlanError(f"У коммита {ref!r} нет родителя")
    if parent is None and len(parents) != 1:
        raise PlanError(f"Для merge-коммита {ref!r} укажи родителя явно")
    base = revision(root, parent) if parent is not None else parents[0]
    if base not in parents:
        raise PlanError(f"{parent!r} не является родителем коммита {ref!r}")
    return Comparison(root, base, head, tuple(diff(root, base, target, base, target)), target)


@dataclass(frozen=True)
class Repository:
    name: str
    root: Path
    ref: str | None = None
    parent: str | None = None


@dataclass(frozen=True)
class PlannedRepository:
    name: str
    root: Path
    base: str | None
    head: str
    commit: str | None
    changes: tuple[Change, ...]


@dataclass(frozen=True)
class Group:
    name: str
    root: Path
    inputs: tuple[str, ...]
    scripts: tuple[str, ...]
    full: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    status: str
    mode: str
    repositories: tuple[PlannedRepository, ...]
    groups: tuple[Group, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class Snapshot:
    files: frozenset[str]
    modules: tuple[dict, ...]
    problems: tuple[str, ...]


def confined(root: Path, rel: str) -> Path:
    relative_path(rel)
    try:
        path = (root / rel).resolve()
    except (OSError, ValueError, RuntimeError) as error:
        raise PlanError(f"{rel!r}: путь недоступен ({type(error).__name__})") from None
    if not path.is_relative_to(root):
        raise PlanError(f"{rel!r}: путь вне рабочего дерева")
    return path


def _readme_path(repo: str, path: str) -> bool:
    parts = path.split("/")
    if repo == VSCODE:
        return len(parts) == 3 and parts[0] == "src" and parts[-1] == "README.md"
    return (len(parts) == 2 and not parts[0].startswith(".") and parts[-1] == "README.md"
            or path == "openspec/schemas/symphysis/README.md")


def _index_entries(root: Path) -> dict[str, tuple[bytes, bytes]]:
    entries = {}
    for item in nul_fields(git(root, "ls-files", "--stage", "-z")):
        meta, name = item.split(b"\t", 1)
        mode, oid, stage = meta.split()
        if stage == b"0":
            entries[git_path(name)] = mode, oid
    return entries


def _tree_entries(root: Path, oid: str) -> dict[str, tuple[bytes, bytes]]:
    entries = {}
    for item in nul_fields(git(root, "ls-tree", "-r", "-z", oid, "--")):
        meta, name = item.split(b"\t", 1)
        mode, kind, blob = meta.split()
        if kind == b"blob":
            entries[git_path(name)] = mode, blob
    return entries


def _read_blobs(root: Path, ids: list[bytes]) -> dict[bytes, bytes]:
    if not ids:
        return {}
    result = git(root, "cat-file", "--batch", input_data=b"\n".join(ids) + b"\n")
    blobs = {}
    offset = 0
    for oid in ids:
        end = result.find(b"\n", offset)
        fields = result[offset:end].split()
        if end < 0 or len(fields) != 3 or fields[:2] != [oid, b"blob"] or not fields[2].isdigit():
            raise PlanError("Git не вернул запрошенный объект README")
        size = int(fields[2])
        offset = end + 1
        blobs[oid] = result[offset:offset + size]
        offset += size
        if result[offset:offset + 1] != b"\n":
            raise PlanError("Git вернул неполный объект README")
        offset += 1
    return blobs


def snapshot(repo: PlannedRepository, source: str) -> Snapshot:
    index = source in ("index", "worktree")
    entries = _index_entries(repo.root) if index else _tree_entries(repo.root, source)
    paths = set(entries)
    if source == "worktree":
        paths.update(git_path(path) for path in nul_fields(git(repo.root, "ls-files", "--others", "--exclude-standard", "-z")))
        paths = {path for path in paths if os.path.lexists(repo.root / path)}
    readmes = sorted(path for path in paths if _readme_path(repo.name, path))
    blobs = {} if source == "worktree" else _read_blobs(
        repo.root, [entries[path][1] for path in readmes if entries[path][0] != b"120000"],
    )
    found = []
    problems = []
    for path in readmes:
        try:
            if source == "worktree":
                file = confined(repo.root, path)
                if not file.exists() and not (repo.root / path).is_symlink():
                    continue
                data = file.read_bytes()
            else:
                mode, oid = entries[path]
                if mode == b"120000":
                    raise DeclarationError("README в Git является ссылкой")
                data = blobs[oid]
            declaration = read_declaration(data)
        except (DeclarationError, PlanError, OSError) as error:
            message = str(error) if not isinstance(error, OSError) else "README не читается"
            problems.append(f"{repo.name}/{path}: {message}")
        else:
            if declaration:
                found.append({**declaration, "repo": repo.name, "path": path.rsplit("/", 1)[0], "source": path})
    return Snapshot(frozenset(paths), tuple(found), tuple(problems))


def _scope(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


PYTEST_CONFIG = ("pytest.ini", "tests/conftest.py", "tools/journal-roots.json")
CORE_CONFIG = ("requirements-dev.txt", ".gitattributes", ".gitignore", "tools/test_runs.py", "tools/test_run_execution.py")
VSCODE_CONFIG = ("package.json", "package-lock.json", "build.mjs", "tsconfig.json", ".vscodeignore", ".gitignore",
                 "test/worktree-paths.mjs", "test/e2e/paths.mjs")
CORE_COMMON = {
    "anchors/anchor_refs.py": ("trace/tests/test_trace_snapshot.py", "runtime/tests/test_runtime_context.py"),
    "anchors/sync_check.py": ("runtime/tests/test_runtime_context.py",),
    "tools/hooks": ("tests/test_gate_hook.py",),
    "tools/allowed-lines.txt": ("tests/test_gate_hook.py", "tests/test_guide.py"),
    "tools/allowed-hosts.txt": ("tests/test_gate_hook.py", "tests/test_guide.py"),
    "docs/GUIDE.md": ("tests/test_guide.py",),
    "docs/repo-contract.md": ("tests/test_repo_contract.py",),
    "tests/repository_structure.py": ("tests/test_repository_live.py", "tests/test_repository_structure.py"),
    "tests/test_skills.py": ("tests/test_agents.py",),
    "probes": ("tests/test_skills.py", "tests/test_agents.py"),
    "research": ("tests/test_skills.py", "tests/test_agents.py"),
    "skill-shared": ("tests/test_skills.py", "tests/test_agents.py"),
}
CORE_PACKAGING = ("installer", "vendor", "openspec/schemas/symphysis", "docs/THIRD-PARTY-NOTICES.md")
CORE_PACKAGED_CONTENT = (
    "runtime/runtime_context.py", "viewer/playground-template.html", "decisions/journal.schema.json",
    "skill-shared/terms.md", "skill-shared/driver.md", "decisions/candidate.md", "cli/journal-cli.md",
    "settings/config.md", "settings/symphysis_config.py", "attack/attack-table.md", "trace/module-declarations.md",
)
JOURNAL_CONTRACT = ("cli", "decisions", "viewer/viewer_render.py", "viewer/playground-template.html")
GRAPH_CONTRACT = ("trace",)
CORE_VSCODE_TESTS = {
    "tests/fixtures/viewer-smoke.js": (CONTRACT,),
    "tests/fixtures/scheme/cases.json": ("src/scheme/test/scheme.test.ts",),
    "installer/package.json": ("src/scheme/test/scheme.test.ts",),
    "installer/scripts/sync-payload.js": ("test/unit/core-files.test.ts",),
    "openspec/schemas/symphysis/steps.md": ("src/step-help/test/help-view.test.tsx", "src/step-help/test/step-help.test.ts"),
    "step-help/step_help.py": ("src/step-help/test/step-help.test.ts",),
    "tests/fixtures/fork-shim": (CONTRACT, "src/step-help/test/step-help.test.ts"),
    "runtime/runtime_context.py": (CONTRACT, "src/step-help/test/step-help.test.ts"),
}
VSCODE_PACKAGING = ("src/hook/hook.py", "src/ui/style.css", "docs/package-readme.md", "package.mjs",
                    "media/icon.svg", "package.json", ".vscodeignore")
VSCODE_E2E = {
    "test/e2e/req-graph.mjs": GRAPH_SCRIPT, "test/e2e/req-graph-scenario.ts": GRAPH_SCRIPT,
    "test/e2e/run.mjs": "e2e", "test/e2e/scenario.ts": "e2e",
    "test/e2e/vsix.mjs": "e2e:vsix", "test/e2e/vsix-scenario.ts": "e2e:vsix",
    "test/e2e/reload.mjs": "e2e:reload", "test/e2e/reload-host": "e2e:reload",
    "test/e2e/activation.mjs": "e2e:activation", "test/e2e/activation-scenario.ts": "e2e:activation",
    "test/e2e/hook-clients.mjs": "e2e:hook",
}
VSCODE_SCRIPTS = tuple(sorted(set(VSCODE_E2E.values()) - {"e2e:hook"}))
# Этот e2e проверяет активацию в настоящем VS Code, автоустановку хука,
# палитру справки и обновление при смене состава workspace.
ACTIVATION_INPUTS = (
    "src/activation", "src/hook/hook.ts", "src/hook/hookRunner.ts", "src/hook/hookGit.ts",
    "src/changes/sidebar.ts", "src/step-help/stepHelp.ts", "src/step-help/helpTasks.ts",
    "src/core/project.ts", "src/core/python.ts",
)
VSCODE_COMMON = {
    "core": (CONTRACT, "test/unit/views.test.tsx", "test/unit/core-files.test.ts"),
    "journal": (CONTRACT, "test/unit/views.test.tsx"),
    "protocol": (CONTRACT, "test/unit/views.test.tsx"),
    "file-links": ("test/unit/views.test.tsx",),
    "search": ("test/unit/views.test.tsx",),
    "step-help": ("test/unit/views.test.tsx",),
    "ui": ("test/unit/views.test.tsx",),
    "viewer": ("test/unit/views.test.tsx",),
}


class Selection:
    def __init__(self, repositories):
        self.repositories = {item.name: item for item in repositories}
        self.reasons = defaultdict(set)
        self.inputs = defaultdict(set)
        self.scripts = defaultdict(set)
        self.full = set()
        self.diagnostics = set()
        self.incomplete = False

    def add(self, name, reason, *, inputs=(), scripts=(), full=False):
        repo = GROUP_REPOSITORY[name]
        if repo not in self.repositories:
            self.incomplete = True
            self.diagnostics.add(f"Нужен корень {repo} для проверки {name}: {reason}")
            return
        if name == "vscode" and (VSCODE_REAL_CORE.intersection(inputs) or scripts or full) and CORE not in self.repositories:
            self.incomplete = True
            self.diagnostics.add(f"Нужен корень {CORE} как стенд VS Code: {reason}")
        self.reasons[name].add(reason)
        self.inputs[name].update(inputs)
        self.scripts[name].update(scripts)
        if full:
            self.full.add(name)

    def expand(self, reason, repo=None):
        for name in GROUPS:
            if GROUP_REPOSITORY[name] in self.repositories and (repo is None or GROUP_REPOSITORY[name] == repo):
                self.add(name, reason, full=True, scripts=VSCODE_SCRIPTS if name == "vscode" else ())

    def groups(self):
        return tuple(
            Group(name, self.repositories[GROUP_REPOSITORY[name]].root,
                  tuple(sorted(self.inputs[name])) if name not in self.full else (),
                  tuple(sorted(self.scripts[name])), name in self.full, tuple(sorted(self.reasons[name])))
            for name in GROUPS if name in self.reasons
        )


def _pytest_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.startswith("test_") and name.endswith(".py")


def _browser_test(path: str) -> bool:
    return path in ("viewer/tests/test_viewer_browser.py", "viewer/tests/test_global_resources_browser.py")


def _vscode_test(path: str) -> bool:
    return path.endswith((".test.ts", ".test.tsx"))


def _pick_python(selection, reason, paths):
    browser = {path for path in paths if _browser_test(path)}
    ordinary = set(paths) - browser
    if ordinary:
        selection.add("core", reason, inputs=ordinary)
    if browser:
        selection.add("browser", reason, inputs=browser)


def _pick_module(selection, item, active, reason, changed_repo, changed_path):
    name, repo, directory = item["name"], item["repo"], item["path"]
    files = active[repo].files
    module_state = {"modules": active[repo].modules}
    if repo == CORE:
        if name == "installer":
            return
        prefix = "tests/" if directory == "." else directory + "/tests/"
        candidates = {file for file in files if file.startswith(prefix) and _pytest_test(file)
                      and owner(module_state, repo, file) is item}
        _pick_python(selection, reason, candidates)
    else:
        prefix = directory + "/test/"
        candidates = {file for file in files if file.startswith(prefix) and "/" not in file[len(prefix):] and _vscode_test(file)
                      and owner(module_state, repo, file) is item}
        candidates.update(file for file in VSCODE_COMMON.get(name, ()) if file in files)
        if candidates:
            selection.add("vscode", reason, inputs=candidates)
        if name == "req-graph" and any(file.startswith("test/e2e/req-graph") for file in files):
            selection.add("vscode", reason, scripts=(GRAPH_SCRIPT,))
        if name == "activation" and changed_repo == VSCODE and _scope(changed_path, ACTIVATION_INPUTS):
            selection.add("vscode", reason, scripts=("e2e:activation",))


def _path_rules(selection, repo, path, change, active, item):
    """Rules outside the declared module graph, keyed by the checked input."""
    source = f"{repo}/{path}"
    known = False
    if repo == CORE:
        if path in ("cli/journal.py", "cli/journal_cli.py"):
            selection.add("browser", f"{source}: рендер страницы в браузере", full=True)
        for prefix, tests in CORE_VSCODE_TESTS.items():
            if _scope(path, (prefix,)):
                selection.add("vscode", f"{source}: сквозная проверка на ядре", inputs=tests)
                known = True
        if path == "tests/fixtures/scheme/wide.md":
            selection.add("vscode", f"{source}: сквозная проверка на ядре", scripts=("e2e",))
    elif _scope(path, VSCODE_PACKAGING):
        selection.add("vscode", f"{source}: вход VSIX", scripts=("e2e:vsix",))
        known = True
    if repo == CORE and _scope(path, PYTEST_CONFIG):
        for name in ("core", "browser"):
            selection.add(name, f"{source}: общая настройка", full=True)
        return True
    if _scope(path, CORE_CONFIG if repo == CORE else VSCODE_CONFIG):
        selection.expand(f"{source}: общая настройка", repo)
        return True
    if repo == CORE:
        if path == "tests/fixtures/viewer-browser.mjs":
            selection.add("browser", f"{source}: общая фикстура", full=True)
            return True
        if _scope(path, ("tests/fixtures", "tests/fork_shim.py")):
            for name in ("core", "browser"):
                selection.add(name, f"{source}: общая фикстура", full=True)
            return True
        for prefix, checks in CORE_COMMON.items():
            if _scope(path, (prefix,)):
                _pick_python(selection, f"{source}: связанная проверка", checks)
                known = True
        if path.startswith("tests/") and _pytest_test(path):
            if path in active[repo].files:
                _pick_python(selection, f"{source}: изменён тест", (path,))
            else:
                selection.add("core", f"{source}: удалён тест", full=True)
            return True
        if (path in CORE_PACKAGED_CONTENT
                or ("/skills/" in path or "/agents/" in path) and path.endswith(".md")
                or _scope(path, CORE_PACKAGING) and "/tests/" not in path
                or change.before != change.after and "/tests/" not in path
                and ("/skills/" in path or "/agents/" in path or path.endswith((".py", ".html", ".json")))
                and item is not None):
            selection.add("installer", f"{source}: вход поставки")
            known = True
        if _scope(path, JOURNAL_CONTRACT) and "/tests/" not in path and not path.endswith("/README.md"):
            selection.add("vscode", f"{source}: контракт журнала", inputs=(CONTRACT,))
            known = True
        if _scope(path, GRAPH_CONTRACT) and "/tests/" not in path and not path.endswith("/README.md"):
            selection.add("vscode", f"{source}: контракт графа", scripts=(GRAPH_SCRIPT,))
            known = True
        return known
    if path.startswith("test/unit/"):
        if _vscode_test(path) and path in active[repo].files:
            selection.add("vscode", f"{source}: изменён тест", inputs=(path,))
        else:
            selection.expand(f"{source}: общая фикстура", VSCODE)
        return True
    if path.startswith("test/e2e/"):
        scripts = tuple(sorted({name for prefix, name in VSCODE_E2E.items() if _scope(path, (prefix,))}))
        if scripts == ("e2e:hook",):
            selection.incomplete = True
            selection.diagnostics.add(f"{source}: нужна ручная проверка npm run e2e:hook")
            return True
        if not scripts:
            scripts = VSCODE_SCRIPTS
        selection.add("vscode", f"{source}: сквозная проверка", scripts=scripts)
        return True
    if _scope(path, ("test",)):
        selection.expand(f"{source}: общая фикстура", VSCODE)
        return True
    return known


def _module_graph(snapshots, diagnostics):
    state = {"modules": [item for snap in snapshots.values() for item in snap.modules]}
    reverse = defaultdict(set)
    duplicate = set()
    for item in state["modules"]:
        key = item["repo"], item["name"]
        if module(state, *key) is not item:
            duplicate.add(f"{item['repo']}/{item['source']}: неоднозначный модуль {item['name']}")
            continue
        for dependency in item["dependencies"]:
            target = dependency["repo"], dependency["module"]
            if target[0] in (CORE, VSCODE) and target[0] not in snapshots:
                continue
            if module(state, *target) is None:
                diagnostics.add(f"{item['repo']}/{item['source']}: зависимость не разрешена: {'/'.join(target)}")
            else:
                reverse[target].add(key)
    return state, reverse, duplicate


def _pick_path(selection, active, active_graph, side, side_graph, repo, path, change, historical):
    state, reverse, duplicates = side_graph
    problems = {problem for snap in side.values() for problem in snap.problems} | duplicates
    if problems:
        prefix = "прежние связи недоступны" if historical else "полнота отбора не подтверждена"
        for problem in problems:
            selection.diagnostics.add(f"{prefix}: {problem}")
            selection.expand(f"{prefix}: {problem}")
    item = owner(state, repo, path)
    known = _path_rules(selection, repo, path, change, active, item)
    if item is None:
        if not known:
            reason = "прежние связи недоступны" if historical else "неизвестный путь"
            selection.expand(f"{repo}/{path}: {reason}", VSCODE if repo == VSCODE else None)
        return
    cause = f"{repo}/{path}"
    start = item["repo"], item["name"]
    pending = deque([start])
    seen = {start}
    while pending:
        key = pending.popleft()
        current = module(active_graph[0], *key)
        if current:
            reason = f"{cause}: модуль {key[1]}" if key == start else f"{cause}: потребитель {'/'.join(key)}"
            _pick_module(selection, current, active, reason, repo, path)
        for consumer in sorted(reverse[key] - seen):
            seen.add(consumer)
            pending.append(consumer)


def _repository(mode: str, requested: Repository) -> PlannedRepository:
    if requested.ref is not None:
        result = compare(requested.root, mode, requested.ref, requested.parent)
        return PlannedRepository(requested.name, result.root, result.base, result.head, result.commit, result.changes)
    if requested.parent is not None:
        raise PlanError(f"{requested.name}: родитель задан без коммита")
    root = worktree(requested.root)
    return PlannedRepository(requested.name, root, None, revision(root, "HEAD"), None, ())


def plan(mode: str, inputs: list[Repository]) -> Plan:
    if not any(repo.ref is not None for repo in inputs):
        return Plan("incomplete", mode, (), (), ("Нужно хотя бы одно явное Git-сравнение",))
    repositories = []
    errors = []
    names = set()
    for repo in inputs:
        if repo.name not in (CORE, VSCODE) or repo.name in names:
            errors.append(f"Неверный или повторный репозиторий {repo.name!r}")
            continue
        names.add(repo.name)
        try:
            repositories.append(_repository(mode, repo))
        except PlanError as error:
            errors.append(f"{repo.name}: {error}")
    scope = tuple(repositories)
    if errors:
        return Plan("incomplete", mode, scope, (), tuple(errors))
    if not any(repo.changes for repo in scope):
        return Plan("empty", mode, scope, (), ())

    selection = Selection(scope)
    caches = {}

    def at(repo, source):
        key = repo.name, source
        if key not in caches:
            caches[key] = snapshot(repo, source)
        return caches[key]

    try:
        active = {repo.name: at(repo, repo.commit or "worktree") for repo in scope}
        current = _module_graph(active, selection.diagnostics)
        side_graphs = {}
        for repo in scope:
            for change in repo.changes:
                for path, source, historical in (
                    (change.before, change.previous, change.before != change.after),
                    (change.after, change.current, False),
                ):
                    if path is None:
                        continue
                    if source == "worktree":
                        confined(repo.root, path)
                    active_source = repo.commit or "worktree"
                    if not historical and change.before == change.after and source != active_source:
                        # For an ordinary modification current declarations define its consumers.
                        source = active_source
                    key = repo.name, source, historical
                    if key not in side_graphs:
                        sides = dict(active)
                        sides[repo.name] = at(repo, source)
                        if historical:
                            for peer in scope:
                                if peer.name != repo.name and peer.base:
                                    sides[peer.name] = at(peer, peer.base)
                        side_graphs[key] = sides, _module_graph(sides, selection.diagnostics)
                    sides, graph = side_graphs[key]
                    _pick_path(selection, active, current, sides, graph, repo.name, path, change, historical)
        for group in selection.groups():
            for path in group.inputs:
                confined(group.root, path)
    except PlanError as error:
        return Plan("incomplete", mode, scope, (), (str(error),))
    selected = selection.groups()
    if not selected and not selection.incomplete:
        changed = sorted({f"{repo.name}/{path}" for repo in scope for change in repo.changes
                          for path in (change.before, change.after) if path is not None})
        selection.diagnostics.add("Есть изменения, но нет применимых проверок: " + ", ".join(changed))
    return Plan("incomplete" if selection.incomplete else "ready", mode, scope,
                selected, tuple(sorted(selection.diagnostics)))


def format_plan(result: Plan) -> str:
    titles = {"ready": "План построен", "empty": "Пустое сравнение", "incomplete": "План не завершён"}
    lines = [titles[result.status]]
    for repo in result.repositories:
        comparison = f"база {repo.base}" if repo.base else "стенд без сравнения"
        if repo.commit:
            comparison += f", коммит {repo.commit}"
        lines.append(f"{repo.name}: {repo.root} ({comparison}, HEAD {repo.head})")
    for group in result.groups:
        scope = "полный набор" if group.full else ", ".join((*group.inputs, *group.scripts))
        lines.append(f"{group.name}: {scope}")
        if group.full and group.scripts:
            lines.append("  Сквозные: " + ", ".join(group.scripts))
        lines.extend(f"  {reason}" for reason in group.reasons)
    lines.extend(result.diagnostics)
    return "\n".join(lines)


def main(argv=None) -> int:
    from test_run_execution import execute, full_plan

    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="action", required=True)
    for action, help_text in (("plan", "показать план"), ("run", "выполнить план последовательно")):
        modes = commands.add_parser(action, help=help_text).add_subparsers(dest="mode", required=True)
        for name, suffix in (("change", "base"), ("commit", "commit"), ("full", None)):
            command = modes.add_parser(name, allow_abbrev=False)
            for short in ("core", "vscode"):
                command.add_argument(f"--{short}-root", type=Path,
                                     help="корень Git, без ревизии — стенд с текущими декларациями")
                if suffix:
                    command.add_argument(f"--{short}-{suffix}", dest=f"{short}_ref")
                if name == "commit":
                    command.add_argument(f"--{short}-parent")
            if name == "full":
                command.add_argument("--release", action="store_true", help="для выпуска VS Code нужен main ядра")
            if action == "run":
                command.add_argument("--summary", type=Path, help="записать переносимую сводку в новый JSON")
                command.add_argument("--log-dir", type=Path,
                                     help="сохранить сырой локальный вывод и JUnit в новый каталог")
    args = parser.parse_args(argv)
    inputs = []
    for short, name in (("core", CORE), ("vscode", VSCODE)):
        root = getattr(args, f"{short}_root")
        ref = getattr(args, f"{short}_ref", None)
        parent = getattr(args, f"{short}_parent", None)
        if root is None:
            if ref is not None or parent is not None:
                parser.error(f"Для ревизии нужен --{short}-root")
        else:
            inputs.append(Repository(name, root, ref, parent))
    result = full_plan(inputs, args.release) if args.mode == "full" else plan(args.mode, inputs)
    print(format_plan(result), flush=True)
    if args.action == "run":
        return execute(result, args.summary, args.log_dir)
    return int(result.status == "incomplete")


if __name__ == "__main__":
    sys.modules["test_runs"] = sys.modules[__name__]
    raise SystemExit(main())
