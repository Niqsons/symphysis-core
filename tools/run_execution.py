"""Исполнение адресного плана. Сводка отделена от локального вывода команд."""
from __future__ import annotations

import configparser
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, nullcontext
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from xml.etree import ElementTree

from run_tests import (
    CORE, GROUPS, GROUP_REPOSITORY, VSCODE, VSCODE_REAL_CORE, VSCODE_SCRIPTS,
    Group, Plan, PlanError, Selection, _repository, confined, git, revision, worktree,
)


ARCHIVED_TRACE_TESTS = {
    "test_build_on_this_very_change_gives_nodes_of_every_kind",
    "test_this_very_change_has_links_of_every_kind_of_this_portion",
}
ARCHIVED_TRACE_REASON = "изменение trace-graph заархивировано: каталога openspec/changes/trace-graph нет"


@dataclass(frozen=True)
class Result:
    name: str
    status: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    not_applicable: int = 0
    seconds: float = 0
    code: int | None = None
    steps: tuple[Result, ...] = ()
    repositories: tuple[dict, ...] = ()


@dataclass(frozen=True)
class Counts:
    passed: int
    failed: int
    skipped: int
    not_applicable: int = 0


def full_plan(inputs, release=False):
    try:
        repos = tuple(_repository("full", item) for item in inputs)
        if not repos:
            raise PlanError("Для полного прогона нужен явный корень")
        selection = Selection(repos)
        if release and VSCODE in selection.repositories:
            core = selection.repositories.get(CORE)
            if core is None or git(core.root, "symbolic-ref", "-q", "HEAD").strip() != b"refs/heads/main":
                raise PlanError("Для выпуска VS Code нужен worktree main ядра")
        selection.expand("полный прогон на выпуске" if release else "полный прогон по решению владельца")
        return Plan("incomplete" if selection.incomplete else "ready", "full", repos,
                    selection.groups(), tuple(sorted(selection.diagnostics)))
    except PlanError as error:
        return Plan("incomplete", "full", (), (), (str(error),))


def _absolute_executable(name, env):
    suffix = ".exe" if os.name == "nt" else ""
    for item in env.get("PATH", "").split(os.pathsep):
        folder = Path(item)
        entry = folder / (name + suffix)
        if folder.is_absolute() and entry.is_file():
            return str(entry)
    raise PlanError(f"Не найден {name} в абсолютных каталогах PATH")


def _npm(node, env):
    if os.name != "nt":
        return [_absolute_executable("npm", env)]
    folder = Path(node).resolve().parent
    # Штатный npm Windows запускается JS CLI рядом с установленным Node.
    cli = folder / "node_modules" / "npm" / "bin" / "npm-cli.js"
    if not cli.is_file() or not cli.resolve().is_relative_to(folder):
        raise PlanError(f"Рядом с выбранным Node нет штатного npm CLI: {node}")
    return [node, str(cli.resolve())]


def _verify_input(root, rel, *, directory=False):
    path = confined(root, rel)
    if not (path.is_dir() if directory else path.is_file()):
        raise PlanError(f"{rel}: запланированный вход недоступен")
    return path


def _no_link(root, rel):
    confined(root, rel)
    current = root
    for name in rel.split("/"):
        current = current / name
        if current.is_symlink() or current.is_junction():
            raise PlanError(f"{rel}: ссылка в рабочем дереве")


def _checked_tree(root):
    if worktree(root) != root:
        raise PlanError(f"Корень рабочего дерева изменился: {root}")


def _state(repo, *, label=None):
    _checked_tree(repo.root)
    actual = revision(repo.root, "HEAD")
    statuses = git(repo.root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    dirty = bool(statuses)
    if repo.commit:
        state = "рабочее дерево с правками" if dirty else "чистое рабочее дерево"
        prefix = f"{label}, " if label else ""
        print(f"{prefix}{repo.name}: источник отбора {repo.commit}, запуск на HEAD {actual}, {state}", flush=True)
    return ({"name": repo.name, "selected_commit": repo.commit, "base": repo.base,
             "actual_head": actual, "dirty": dirty}, statuses)


def _local_output(path):
    data = path.read_bytes()
    return data.decode("utf-8", errors="replace")


def _invoke(name, command, root, env, log_dir):
    started = time.monotonic()
    stdout = log_dir / "stdout.log"
    stderr = log_dir / "stderr.log"
    log_dir.mkdir()
    _checked_tree(root)
    print(f"Начало {name}", flush=True)
    try:
        with stdout.open("wb") as out, stderr.open("wb") as err:
            proc = subprocess.run(command, cwd=root, env=env, stdout=out, stderr=err, check=False)
    except OSError as error:
        raise PlanError(f"{name}: не удалось запустить процесс: {error}") from None
    output = _local_output(stdout)
    errors = _local_output(stderr)
    if output:
        print(output, end="" if output.endswith("\n") else "\n", flush=True)
    if errors:
        print(errors, end="" if errors.endswith("\n") else "\n", file=sys.stderr, flush=True)
    return proc.returncode, output, round(time.monotonic() - started, 3)


def _no_active_journals(root):
    # Match the validator's one-level inventory. An unreadable tree is not confirmed empty.
    try:
        for change in confined(root, "openspec/changes").iterdir():
            try:
                (change / "decisions.json").lstat()
            except (FileNotFoundError, NotADirectoryError):
                continue
            return False
    except OSError:
        return False
    return True


def _pytest_counts(xml_path, root):
    try:
        cases = list(ElementTree.parse(xml_path).iter("testcase"))
    except (OSError, ElementTree.ParseError):
        return None
    failed = skipped = not_applicable = 0
    archived = not confined(root, "openspec/changes/trace-graph").is_dir()
    for case in cases:
        skip = case.find("skipped")
        if skip is not None:
            classname, name, reason = case.get("classname"), case.get("name"), skip.get("message")
            archived_trace = (archived and classname == "trace.tests.test_trace_graph"
                              and name in ARCHIVED_TRACE_TESTS and reason == ARCHIVED_TRACE_REASON)
            empty_journals = (classname == "decisions.tests.test_journal_validator"
                              and name == "test_no_journal_of_this_tree_breaks_on_the_new_rule[NOTSET]"
                              and reason == "got empty parameter set for (path)" and _no_active_journals(root))
            if archived_trace or empty_journals:
                not_applicable += 1
            else:
                skipped += 1
        elif case.find("failure") is not None or case.find("error") is not None:
            failed += 1
    return Counts(len(cases) - failed - skipped - not_applicable, failed, skipped, not_applicable)


def _node_counts(output):
    # Штатный node --test: сводка spec либо TAP. Берём последнюю
    # секцию верхнего уровня, а не строки отдельных тестов.
    summaries = re.findall(
        r"(?m)^[ℹ#] tests (\d+)\s*\n[ℹ#] suites \d+\s*\n"
        r"[ℹ#] pass (\d+)\s*\n[ℹ#] fail (\d+)\s*\n"
        r"[ℹ#] cancelled (\d+)\s*\n[ℹ#] skipped (\d+)\s*\n[ℹ#] todo (\d+)", output,
    )
    if not summaries:
        return None
    total, passed, failed, cancelled, skipped, todo = map(int, summaries[-1])
    if total < passed + failed + cancelled + skipped + todo:
        return None
    return Counts(passed, failed + cancelled, skipped + todo)


def _e2e_counts(output):
    lines = re.findall(r"(?m)^итого (\d+), упало (\d+)\s*$", output)
    if not lines:
        return None
    totals = [(int(total), int(failed)) for total, failed in lines]
    if any(failed > total for total, failed in totals):
        return None
    return Counts(sum(total - failed for total, failed in totals), sum(failed for _, failed in totals), 0)


def _outcome(name, code, counts, seconds, *, no_tests_code=None):
    missing = counts is None
    counts = counts if counts is not None else Counts(0, 0, 0)
    if (code and code != no_tests_code) or counts.failed:
        status = "failed"
    elif missing and code != no_tests_code:
        print(f"{name}: нет сводки о выполненных проверках", file=sys.stderr, flush=True)
        status = "incomplete"
    elif counts.skipped:
        status = "incomplete"
    elif not counts.passed:
        status = "zero"
    else:
        status = "passed"
    return Result(name, status, counts.passed, counts.failed, counts.skipped, counts.not_applicable, seconds, code)


def _isolated_env(env, temp):
    private = temp / "tmp"
    private.mkdir()
    return {**env, **dict.fromkeys(("TEMP", "TMP", "TMPDIR"), str(private))}


def _pytest_scope(root, explicit):
    config = _verify_input(root, "pytest.ini")
    if explicit:
        selected = explicit
    else:
        options = configparser.ConfigParser(interpolation=None)
        try:
            with config.open(encoding="utf-8") as stream:
                options.read_file(stream)
        except (OSError, configparser.Error) as error:
            raise PlanError(f"Не удалось прочитать pytest.ini: {error}") from None
        selected = options.get("pytest", "testpaths", fallback="").split()
        if not selected:
            raise PlanError("Полный pytest требует явных testpaths в pytest.ini")
    for rel in selected:
        file = _verify_input(root, rel, directory=not explicit)
        parent = (root / rel).parent
        while parent.is_relative_to(root):
            conftest = parent / "conftest.py"
            if os.path.lexists(conftest):
                _verify_input(root, conftest.relative_to(root).as_posix())
            if parent == root:
                break
            parent = parent.parent
        if not file.is_dir():
            continue
        for directory, subdirs, names in os.walk(file, followlinks=False):
            for name in (*subdirs, *names):
                entry = Path(directory) / name
                if entry.is_symlink() or entry.is_junction():
                    _no_link(root, entry.relative_to(root).as_posix())
    return selected


def _pytest(group, env, temp):
    paths = _pytest_scope(group.root, group.inputs)
    env = {key: value for key, value in env.items() if key.upper() not in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS"}}
    xml = temp / "pytest.xml"
    browser = group.name == "browser"
    command = [sys.executable, "-X", "utf8", "-B", "-m", "pytest", "-c", str(group.root / "pytest.ini"), "-q", "-ra",
               "-n", "2" if browser else "12", "-m", "browser" if browser else "not browser",
               "-p", "no:cacheprovider", f"--basetemp={temp / 'pytest'}", f"--junitxml={xml}"]
    command.extend(["--", *paths])
    code, output, seconds = _invoke(group.name, command, group.root, env, temp / "logs")
    return _outcome(group.name, code, _pytest_counts(xml, group.root), seconds, no_tests_code=5)


def _installer(group, env, temp):
    _verify_input(group.root, "installer", directory=True)
    _verify_input(group.root, "installer/package.json")
    for rel in ("installer/payload", "installer/generated/workflow-carriers.json"):
        _no_link(group.root, rel)
    node = _absolute_executable("node", env)
    env = {**env, "PATH": str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", ""),
           "NoDefaultCurrentDirectoryInExePath": "1"}
    python = _absolute_executable("python", env)
    if Path(python) != Path(sys.executable):
        raise PlanError("npm не получит выбранный Python. Запусти команду из среды, где python указывает на него")
    # npm ставит .bin каталог пакета и его предков раньше PATH.
    for ancestor in (group.root / "installer", group.root, *group.root.parents):
        bin_dir = ancestor / "node_modules" / ".bin"
        for candidate in ("python", "python.exe", "python.com", "python.cmd", "python.bat"):
            if (bin_dir / candidate).is_file():
                raise PlanError(f"npm подменит выбранный Python через {bin_dir / candidate}")
    command = [*_npm(node, env), "--prefix", "installer", "test"]
    code, output, seconds = _invoke(group.name, command, group.root, env, temp / "logs")
    return _outcome(group.name, code, _node_counts(output), seconds)


def _built_unit_paths(root, inputs):
    expected = {Path(source).with_suffix(".js").name for source in inputs}
    target = _verify_input(root, "out/test", directory=True)
    outputs = {path.name for path in target.iterdir() if path.name.endswith(".test.js")}
    if outputs != expected:
        missing = ", ".join(sorted(expected - outputs))
        extra = ", ".join(sorted(outputs - expected))
        raise PlanError(f"VS Code: состав сборки не совпал. Отсутствуют [{missing}], лишние [{extra}]")
    return tuple(str(_verify_input(root, f"out/test/{path}")) for path in sorted(expected))


def _vscode_preflight(name, node, group, env, temp, core):
    if core is None:
        raise PlanError(f"{name}: нужен рабочий корень ядра")
    _checked_tree(core)
    core_files = _verify_input(group.root, "test/core-files.mjs")
    checks = [
        "import {pathToFileURL} from 'node:url';",
        "const [, core, files, paths, script, ...inputs] = process.argv;",
        "if (paths) (await import(pathToFileURL(paths))).checkE2ePaths(process.cwd(), script);",
        "const {checkCoreFiles, checkCoreFixtures} = await import(pathToFileURL(files));",
        "checkCoreFiles(core);",
        "for (const input of inputs) checkCoreFixtures(core, input);",
    ]
    paths = ""
    inputs = group.inputs if not group.full else sorted(VSCODE_REAL_CORE)
    if name != "unit":
        _verify_input(group.root, "test/worktree-paths.mjs")
        paths = str(_verify_input(group.root, "test/e2e/paths.mjs"))
        inputs = [name]
    code, _, seconds = _invoke(
        f"preflight:{name}",
        [node, "--input-type=module", "-e", "\n".join(checks), "--", str(core), str(core_files), paths, name, *inputs],
        group.root, env, temp / f"preflight-{name.replace(':', '-')}",
    )
    if code:
        return Result(name, "incomplete", seconds=seconds, code=code)
    return None


def _vscode_units(group, node, env, temp):
    _verify_input(group.root, "build.mjs")
    _verify_input(group.root, "test/worktree-paths.mjs")
    if group.full:
        _verify_input(group.root, "package.json")
        code, output, seconds = _invoke("unit", [*_npm(node, env), "test"], group.root, env, temp / "unit")
        return _outcome("unit", code, _node_counts(output), seconds)
    for path in group.inputs:
        _verify_input(group.root, path)
    code, _, build_seconds = _invoke("build:unit", [node, "build.mjs", "--unit", "--", *group.inputs],
                                     group.root, env, temp / "build")
    if code:
        print("Адресная сборка VS Code не завершена: " + ", ".join(group.inputs), file=sys.stderr, flush=True)
        return Result("unit", "incomplete", seconds=build_seconds, code=code)
    for path in group.inputs:
        _verify_input(group.root, path)
    outputs = _built_unit_paths(group.root, group.inputs)
    code, output, seconds = _invoke("unit", [node, "--test", "--", *outputs], group.root, env, temp / "unit")
    return _outcome("unit", code, _node_counts(output), round(build_seconds + seconds, 3))


def _vscode(group, env, temp, core):
    if core is not None:
        _checked_tree(core)
        _verify_input(core, "cli/journal.py")
        env = {key: value for key, value in env.items() if key.upper() != "SYMPHYSIS_ROOT"}
        env["SYMPHYSIS_ROOT"] = str(core)
    else:
        env = {key: value for key, value in env.items() if key.upper() != "SYMPHYSIS_ROOT"}
    node = _absolute_executable("node", env)
    results = []
    if group.full or group.inputs:
        try:
            required = group.full or VSCODE_REAL_CORE.intersection(group.inputs)
            unavailable = _vscode_preflight("unit", node, group, env, temp, core) if required else None
            results.append(unavailable or _vscode_units(group, node, env, temp))
        except PlanError as error:
            print(f"unit: {error}", file=sys.stderr, flush=True)
            results.append(Result("unit", "incomplete"))
    for script in group.scripts:
        if results and results[-1].status != "passed":
            results.append(Result(script, "not_run"))
            continue
        try:
            if script not in VSCODE_SCRIPTS:
                raise PlanError("Неизвестная сквозная проверка VS Code")
            code_path = Path(env.get("SYMPHYSIS_CODE") or
                             (Path(env.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe"))
            if not code_path.is_absolute() or not code_path.is_file():
                raise PlanError("Недоступен VS Code. Укажи SYMPHYSIS_CODE")
            _verify_input(group.root, "build.mjs")
            if script == "e2e:vsix":
                code_cli = code_path.parent / "bin" / ("code.cmd" if os.name == "nt" else "code")
                if not code_cli.is_file():
                    raise PlanError("Недоступен командный вход VS Code рядом с SYMPHYSIS_CODE")
            unavailable = _vscode_preflight(script, node, group, env, temp, core)
            if unavailable:
                results.append(unavailable)
                continue
            code, output, seconds = _invoke(script, [*_npm(node, env), "run", script],
                                             group.root, env, temp / script.replace(":", "-"))
            results.append(_outcome(script, code, _e2e_counts(output), seconds))
        except PlanError as error:
            print(f"{script}: {error}", file=sys.stderr, flush=True)
            results.append(Result(script, "incomplete"))
    first = next((item for item in results if item.status != "passed"), None)
    return Result(
        group.name, first.status if first else "passed",
        sum(item.passed for item in results), sum(item.failed for item in results),
        sum(item.skipped for item in results), sum(item.not_applicable for item in results),
        round(sum(item.seconds for item in results), 3), first.code if first else 0, tuple(results),
    )


def _execute_group(group: Group, env, temp, core):
    try:
        env = _isolated_env(env, temp)
        if group.name in ("core", "browser"):
            return _pytest(group, env, temp)
        if group.name == "installer":
            return _installer(group, env, temp)
        return _vscode(group, env, temp, core)
    except PlanError as error:
        print(f"{group.name}: {error}", file=sys.stderr, flush=True)
        return Result(group.name, "incomplete")


def execute(plan, summary=None, log_dir=None):
    # Эксклюзивное создание до запуска: два прогона не разделяют отчёты.
    handles = ExitStack()
    try:
        report = handles.enter_context(summary.open("x", encoding="utf-8")) if summary is not None else None
        if log_dir is not None:
            try:
                log_dir.mkdir()
                log_dir = log_dir.resolve()
            except OSError:
                handles.close()
                if report is not None:
                    summary.unlink()
                raise
    except OSError as error:
        handles.close()
        print(f"Каталог локального вывода или сводка недоступны: {error}", file=sys.stderr)
        return 2
    with handles:
        outcome = plan.status
        states = []
        results = []
        if plan.status == "ready":
            try:
                snapshots = {repo.name: _state(repo) for repo in plan.repositories}
                states = [state for state, _ in snapshots.values()]
            except PlanError as error:
                print(str(error), file=sys.stderr, flush=True)
                outcome = "incomplete"
            else:
                core = next((repo.root for repo in plan.repositories if repo.name == CORE), None)
                env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
                by_name = {group.name: group for group in plan.groups}
                outcome = "passed" if by_name else "zero"
                logs = nullcontext(log_dir) if log_dir is not None else tempfile.TemporaryDirectory(prefix="symphysis-test-run-")
                with logs as raw:
                    for name in GROUPS:
                        if name not in by_name:
                            continue
                        if outcome != "passed":
                            results.append(Result(name, "not_run"))
                            continue
                        temp = Path(raw) / name
                        temp.mkdir()
                        group_repos = [repo for repo in plan.repositories if repo.name == GROUP_REPOSITORY[name]
                                       or name == "vscode" and repo.name == CORE]
                        actual = []
                        try:
                            for repo in group_repos:
                                state, statuses = _state(repo, label=name)
                                if (state, statuses) != snapshots[repo.name]:
                                    print(f"{name}: {repo.name} изменился после начала прогона", flush=True)
                                snapshots[repo.name] = state, statuses
                                actual.append(state)
                        except PlanError as error:
                            print(f"{name}: {error}", file=sys.stderr, flush=True)
                            result = Result(name, "incomplete")
                        else:
                            result = _execute_group(by_name[name], env, temp, core)
                        result = replace(result, repositories=tuple(actual))
                        results.append(result)
                        outcome = result.status
        messages = {"passed": "Проверки завершены", "failed": "Проверка завершилась ошибкой",
                    "incomplete": "Прогон не завершён", "zero": "Ноль выполненных проверок",
                    "empty": "Пустое сравнение", "not_run": "Не запущено"}
        for item in results:
            print(f"{item.name}: {messages[item.status]}, прошло {item.passed}, ошибок {item.failed}, "
                  f"пропущено {item.skipped}, неприменимо {item.not_applicable}")
        print(messages[outcome], flush=True)
        if report is not None:
            json.dump({"status": outcome, "mode": plan.mode, "repositories": states,
                       "groups": [asdict(item) for item in results]}, report, ensure_ascii=False, indent=2)
            report.write("\n")
    return {"passed": 0, "empty": 0, "failed": 1, "incomplete": 2, "zero": 3}[outcome]
