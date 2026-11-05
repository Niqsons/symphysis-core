"""Команда `freeze` скрипта графа `tools/trace_graph.py`: снимок и отчёт в `graph/`, выбор «собрать или обновить коммиты»,
коммиты корней (U12, задачи 4.1 и 4.2)."""
import json
import os
import subprocess
import sys

import pytest

import trace_graph
from conftest import ROOT, fork_reply
from test_trace_graph import CHANGE, make_change
from test_trace_report import CLEAN, DONE, ONE_REQ, with_shim

SCRIPT = ROOT / "tools" / "trace_graph.py"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
REPORT_REL = f"openspec/changes/{CHANGE}/graph/report.md"


def git_repo(folder, text="a"):
    """Каталог под git с коммитом; возвращает полный хеш HEAD."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "f.txt").write_text(text, encoding="utf-8")
    for args in (["init", "-q"], ["add", "f.txt"], ["commit", "-q", "-m", text]):
        subprocess.run([*GIT, *args], cwd=folder, check=True, capture_output=True)
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=folder, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def roots_file(tmp_path, **roots):
    path = tmp_path / "roots.json"
    path.write_text(json.dumps(roots), encoding="utf-8")
    return path


def frozen_project(tmp_path, tasks=DONE, security=None):
    """Проект с готовым изменением, два корня под git (`core/`, `plugin/`) и файл корней с абсолютными путями."""
    root, base = make_change(tmp_path, specs={"demo": ONE_REQ}, tasks=tasks, journal=["F-01"], security=security)
    core, plugin = tmp_path / "core", tmp_path / "plugin"
    commits = {"core/": git_repo(core), "plugin/": git_repo(plugin)}
    return root, base, roots_file(tmp_path, **{"core/": str(core), "plugin/": str(plugin)}), commits


def shim_env(tmp_path, validate):
    """Окружение с шимом форка вместо настоящего; `PATH` остаётся целым: `git` корней должен находиться."""
    _, env = with_shim(tmp_path, validate)
    return {**os.environ, "SYMPHYSIS_OPENSPEC": env["SYMPHYSIS_OPENSPEC"], "FORK_SHIM_PYTHON": env["FORK_SHIM_PYTHON"]}


@pytest.fixture
def fork(tmp_path, monkeypatch):
    """Форк-шим с чистым `validate`: отчёт не зависит от настоящего форка."""
    for key, value in shim_env(tmp_path, fork_reply(CLEAN)).items():
        monkeypatch.setenv(key, value)


def freeze(root, roots=None, change=CHANGE):
    return trace_graph.freeze_change(root, change, roots)


def snapshot(base):
    return json.loads((base / "graph" / "req-graph.json").read_text(encoding="utf-8"))


def cli(root, roots=None, change=CHANGE, env=None):
    extra = ["--roots", str(roots)] if roots else []
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "freeze", change, *extra], capture_output=True,
                          text=True, encoding="utf-8", cwd=root, env=env)


def test_freeze_lays_snapshot_and_report(tmp_path, fork):
    """`trace-snapshot`: «Заморозка» — в `graph/` снимок и отчёт; снимок несёт узлы, связи, хеши, коммиты корней, базу."""
    root, base, roots, commits = frozen_project(tmp_path)
    result = freeze(root, roots)
    assert sorted(p.name for p in (base / "graph").iterdir()) == ["report.md", "req-graph.json"]
    snap = snapshot(base)
    assert set(snap) == {"format", "nodes", "edges", "candidates", "sources", "roots", "base"}
    assert snap["nodes"] and all(":" in node["at"] for node in snap["nodes"])
    assert snap["sources"] and all(len(item["sha256"]) == 64 for item in snap["sources"])
    assert snap["base"] == {}
    assert {item["prefix"]: item["commit"] for item in snap["roots"]} == commits
    assert (base / "graph" / "report.md").read_text(encoding="utf-8").startswith(f"# Отчёт по изменению {CHANGE}")
    assert (result.action, result.report) == ("build", REPORT_REL)


def test_freeze_cli_names_report_path_on_new_build(tmp_path):
    """`trace-snapshot`: «Заморозка» — вывод новой сборки называет путь к отчёту от корня проекта, код 0."""
    root, base, roots, _ = frozen_project(tmp_path)
    env = shim_env(tmp_path, fork_reply(CLEAN))
    done = cli(root, roots, env=env)
    assert done.returncode == 0, done.stderr
    assert REPORT_REL in done.stdout and "собран" in done.stdout and str(tmp_path) not in done.stdout
    again = cli(root, roots, env=env)
    assert again.returncode == 0 and REPORT_REL not in again.stdout
    assert "прежние" in again.stdout, again.stdout


def test_snapshot_without_report_is_rebuilt(tmp_path, fork):
    """`trace-snapshot`: «Снимок без отчёта» — снимок есть, отчёта нет: `graph/` неполон и собирается заново."""
    root, base, roots, _ = frozen_project(tmp_path)
    freeze(root, roots)
    (base / "graph" / "report.md").unlink()
    result = freeze(root, roots)
    assert result.action == "build" and "отчёта" in result.reason
    assert (base / "graph" / "report.md").is_file()


@pytest.mark.parametrize("missing", ["graph", "snapshot"])
def test_missing_graph_or_snapshot_is_built(missing, tmp_path, fork):
    """`trace-snapshot`: «Заморозка» — каталога или снимка нет: сборка с названной причиной."""
    root, base, roots, _ = frozen_project(tmp_path)
    if missing == "snapshot":
        (base / "graph").mkdir()
        (base / "graph" / "report.md").write_text("старый\n", encoding="utf-8")
    result = freeze(root, roots)
    assert result.action == "build" and ("снимка" if missing == "snapshot" else "каталога") in result.reason
    assert "старый" not in (base / "graph" / "report.md").read_text(encoding="utf-8")


def test_stale_snapshot_is_rebuilt(tmp_path, fork):
    """`trace-snapshot`: «Снимок устарел» — исходник изменён после заморозки: снимок и отчёт собраны заново."""
    root, base, roots, _ = frozen_project(tmp_path)
    freeze(root, roots)
    before = snapshot(base)
    (base / "tasks.md").write_text(DONE + "- [ ] 1.2 ещё\n", encoding="utf-8", newline="\n")
    result = freeze(root, roots)
    assert result.action == "build" and "устарел" in result.reason
    assert snapshot(base)["sources"] != before["sources"]
    assert any("ещё" in node["name"] for node in snapshot(base)["nodes"])


def test_fresh_snapshot_only_updates_root_commits(tmp_path, fork):
    """`trace-snapshot`: «Снимок свежий, код закоммичен позже» — обновлены коммиты корней, граф и отчёт те же."""
    root, base, roots, commits = frozen_project(tmp_path)
    freeze(root, roots)
    report, before = (base / "graph" / "report.md").read_bytes(), snapshot(base)
    later = git_repo(tmp_path / "core", "b")
    result = freeze(root, roots)
    after = snapshot(base)
    assert result.action == "commits" and result.report is None
    assert {item["prefix"]: item["commit"] for item in after["roots"]} == {"core/": later, "plugin/": commits["plugin/"]}
    assert {k: v for k, v in after.items() if k != "roots"} == {k: v for k, v in before.items() if k != "roots"}
    assert (base / "graph" / "report.md").read_bytes() == report


def test_no_absolute_paths_in_snapshot_and_report(tmp_path, monkeypatch):
    """`trace-snapshot`: «Абсолютных путей нет» — `openspec` падает с путём, имя узла и файл корней несут пути."""
    security = "| Пункт | Статус |\n| --- | --- |\n| Чтение X:\\symphysis\\.context\\00-start-here.md | применимо |\n"
    root, base, roots, _ = frozen_project(tmp_path, security=security)
    env = shim_env(tmp_path, fork_reply("", code=2, stderr=f"ENOENT {tmp_path}\\proj\\x and {tmp_path.as_posix()}/proj/y"))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    freeze(root, roots)
    assert "validate не запустился" in (base / "graph" / "report.md").read_text(encoding="utf-8")
    for name in ("req-graph.json", "report.md"):
        text = (base / "graph" / name).read_text(encoding="utf-8")
        for absolute in (str(tmp_path), tmp_path.as_posix(), "X:\\\\symphysis", "X:\\symphysis", "X:/symphysis"):
            assert absolute not in text, (name, absolute)
    assert [item["prefix"] for item in snapshot(base)["roots"]] == ["core/", "plugin/"]
    assert any(node["kind"] == "sec" and "<путь>" in node["name"] for node in snapshot(base)["nodes"])
    assert freeze(root, roots).action == "commits"  # путь в имени узла свежесть снимка не ломает


def test_roots_two_each_has_a_commit_and_evidence_has_none(tmp_path, fork):
    """`trace-snapshot`: «Два корня» — коммит каждого из двух корней, у улик полей с коммитом нет."""
    root, base, roots, commits = frozen_project(tmp_path)
    freeze(root, roots)
    snap = snapshot(base)
    assert [(i["prefix"], i["commit"]) for i in snap["roots"]] == [("core/", commits["core/"]), ("plugin/", commits["plugin/"])]
    assert all(set(item) == {"prefix", "commit"} for item in snap["roots"])
    assert not any("commit" in node for node in snap["nodes"])


def test_roots_outside_git_or_missing_are_empty_and_named_in_report(tmp_path, fork):
    """`trace-snapshot`: «Корень вне git или без каталога» — у корня пусто, отчёт называет его префиксом, заморозка идёт дальше."""
    root, base, _, commits = frozen_project(tmp_path)
    inside = tmp_path / "core" / "context"  # лежит внутри клона: `rev-parse` там вернул бы чужой коммит (F-101)
    inside.mkdir()
    plain = tmp_path / "plain"
    plain.mkdir()
    roots = roots_file(tmp_path, **{"core/": str(tmp_path / "core"), "context/": str(inside), "plain/": str(plain),
                                    "gone/": str(tmp_path / "gone")})
    result = freeze(root, roots)
    got = {item["prefix"]: item["commit"] for item in snapshot(base)["roots"]}
    assert got == {"core/": commits["core/"], "context/": "", "plain/": "", "gone/": ""} and result.action == "build"
    report = (base / "graph" / "report.md").read_text(encoding="utf-8")
    for prefix in ("context/", "plain/", "gone/"):
        assert f"`{prefix}`" in report
    assert "`core/`" not in report


def test_roots_git_is_called_with_an_argument_list_and_no_shell(tmp_path, fork, monkeypatch):
    """`trace-snapshot`: «Два корня» — `git` зовётся списком аргументов, `shell` не передаётся."""
    root, base, roots, _ = frozen_project(tmp_path)
    calls = []
    real = subprocess.run

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(trace_graph.subprocess, "run", spy)
    freeze(root, roots)
    git_calls = [c for c in calls if isinstance(c[0][0], list) and c[0][0][0] == "git"]
    assert len(git_calls) == 2
    assert all("shell" not in kwargs for _, kwargs in calls)
    assert all(isinstance(args[0], list) for args, _ in calls)


def test_roots_missing_git_binary_gives_empty_commit(tmp_path, fork, monkeypatch):
    """`trace-snapshot`: «Корень вне git или без каталога» — `git` не найден: пусто, заморозка идёт дальше."""
    root, base, roots, _ = frozen_project(tmp_path)

    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(trace_graph.subprocess, "run", no_git)
    freeze(root, roots)
    assert [item["commit"] for item in snapshot(base)["roots"]] == ["", ""]


def test_bad_name_is_refused_before_any_path(tmp_path, fork):
    """`trace-snapshot`: «Заморозка» — имя с `..` получает отказ до пути; ничего не создано."""
    root, base, roots, _ = frozen_project(tmp_path)
    done = cli(root, roots, change="../x")
    assert done.returncode == 1 and "не подходит" in done.stderr, done.stderr
    assert not (base / "graph").exists() and not (root / "openspec" / "x").exists()


def test_missing_change_and_bad_roots_file_are_refused(tmp_path):
    """`trace-snapshot`: «Заморозка» — нет изменения или негоден файл корней: код 1, причина в stderr, без трассировки."""
    root, base, roots, _ = frozen_project(tmp_path)
    env = shim_env(tmp_path, fork_reply(CLEAN))
    none = cli(root, roots, change="nothing", env=env)
    assert none.returncode == 1 and "nothing" in none.stderr and "Traceback" not in none.stderr
    bad = tmp_path / "bad.json"
    bad.write_text("не json", encoding="utf-8")
    done = cli(root, bad, env=env)
    assert done.returncode == 1 and "корней" in done.stderr and "Traceback" not in done.stderr, done.stderr
    assert not (base / "graph").exists()


def test_not_utf8_source_fails_without_partial_graph(tmp_path):
    """`trace-snapshot`: «Сборка не удалась» — spec.md не в UTF-8: код 1 с именем файла, `graph/` не создан."""
    root, base, roots, _ = frozen_project(tmp_path)
    (base / "specs" / "demo" / "spec.md").write_bytes(b"## ADDED Requirements\n\xff\xfe\n")
    env = shim_env(tmp_path, fork_reply(CLEAN))
    done = cli(root, roots, env=env)
    assert done.returncode == 1 and "spec.md" in done.stderr and "Traceback" not in done.stderr, done.stderr
    assert not (base / "graph").exists()


def test_roots_without_option_are_the_journal_default_roots(tmp_path, fork):
    """`trace-snapshot`: «Два корня» — без `--roots` корни те же, что у журнала (`default_roots`)."""
    root, base, _, _ = frozen_project(tmp_path)
    freeze(root)
    expected = trace_graph.default_roots(None, base / "decisions.json")
    assert [item["prefix"] for item in snapshot(base)["roots"]] == list(expected)
