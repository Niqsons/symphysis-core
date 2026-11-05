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


def bare_brackets(text):
    """Угловые скобки вне обратных кавычек (плагин md4h закрывает по ним комментирование файла)."""
    import re
    return [ch for ch in re.sub(r"`[^`\n]*`", "", text) if ch in "<>"]


def test_report_has_no_bare_angle_brackets_when_fork_fails_with_a_path(tmp_path, monkeypatch):
    """`trace-snapshot`: «Абсолютных путей нет» — замена пути на `<путь>` не оставляет голых скобок в report.md."""
    root, base, roots, _ = frozen_project(tmp_path)
    env = shim_env(tmp_path, fork_reply("", code=2, stderr=f"ENOENT {tmp_path.as_posix()}/proj/x and {tmp_path.as_posix()}/proj/y"))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    freeze(root, roots)
    text = (base / "graph" / "report.md").read_text(encoding="utf-8")
    assert "validate не запустился" in text and "&lt;" in text
    assert bare_brackets(text) == [], text


def test_report_has_no_bare_angle_brackets_in_any_section(tmp_path, fork):
    """`trace-snapshot`: «Абсолютных путей нет» — скобка в имени узла не даёт голой скобки ни в одном разделе отчёта."""
    root, base, roots, _ = frozen_project(tmp_path, security="| Пункт | Статус |\n| --- | --- |\n| Ввод <b> и >x | применимо |\n")
    freeze(root, roots)
    text = (base / "graph" / "report.md").read_text(encoding="utf-8")
    assert bare_brackets(text) == [], text


def test_findings_of_validate_are_escaped_too(tmp_path, monkeypatch):
    """`trace-snapshot`: «Абсолютных путей нет» — находка validate с угловой скобкой в сообщении идёт без голых скобок."""
    found = {"items": [{"id": CHANGE, "type": "change", "valid": False, "durationMs": 1,
                        "issues": [{"level": "ERROR", "path": "specs/demo/spec.md", "message": "тип <T> не тот"}]}]}
    root, base, roots, _ = frozen_project(tmp_path)
    for key, value in shim_env(tmp_path, fork_reply(found, code=1)).items():
        monkeypatch.setenv(key, value)
    freeze(root, roots)
    text = (base / "graph" / "report.md").read_text(encoding="utf-8")
    assert "тип &lt;T&gt; не тот" in text and bare_brackets(text) == []


def test_write_leaves_no_temporary_file_and_replaces_atomically(tmp_path, fork, monkeypatch):
    """`trace-snapshot`: «Снимок без отчёта» — файлы пишутся через временный и `os.replace`; после записи временных нет."""
    root, base, roots, _ = frozen_project(tmp_path)
    replaced = []
    real = os.replace
    monkeypatch.setattr(trace_graph.os, "replace", lambda a, b: (replaced.append((os.path.basename(a), os.path.basename(b))), real(a, b))[1])
    freeze(root, roots)
    assert sorted(p.name for p in (base / "graph").iterdir()) == ["report.md", "req-graph.json"]
    assert [dst for _, dst in replaced] == ["req-graph.json", "report.md"] and all(src != dst for src, dst in replaced)


# --- база мастер-спеки в снимке (U13, задача 4.3, F-84, F-95, F-118, F-123) --------------------------------------------

from test_trace_report import decided, journal, probe  # noqa: E402

TRACE = "<!-- проба краёв: форма=io, исходы: F-07 открыт -->\n"
SCN = "#### Scenario: {}\n{}- **WHEN** a\n- **THEN** {}\n\n"
MASTER_BEFORE = ("## Requirements\n\n### Requirement: Один\nТекст SHALL (F-07.A).\n" + TRACE + "\n"
                 + SCN.format("Старый", "<!-- F-07 -->\n", "b") + SCN.format("Меняется", "", "b"))
MODIFIED = ("## MODIFIED Requirements\n\n### Requirement: Один\nТекст SHALL (F-07.A) и новый (F-19).\n" + TRACE + "\n"
            + SCN.format("Старый", "<!-- F-07 -->\n", "b") + SCN.format("Меняется", "", "другое") + SCN.format("Новый", "", "b"))
CARRIED = ("## MODIFIED Requirements\n\n### Requirement: Один\nТекст SHALL (F-07.A).\n" + TRACE + "\n"
           + SCN.format("Старый", "<!-- F-07 -->\n", "b") + SCN.format("Меняется", "", "b"))
ONE = "req:demo/Один"


def master_path(root):
    return root / "openspec" / "specs" / "demo" / "spec.md"


def modified_project(tmp_path, spec_text=MODIFIED, tasks="- [ ] 1.1 сделать\n"):
    """Изменение с одним требованием MODIFIED и мастер-спекой до `/opsx:sync`; журнал: F-07 (проба Specify), F-19."""
    root, base = make_change(tmp_path, specs={"demo": spec_text}, tasks=tasks, journal=["F-07", "F-19"])
    journal(base, decided("F-07", outcome=probe("Specify")), {"id": "F-19"})
    master_path(root).parent.mkdir(parents=True)
    master_path(root).write_text(MASTER_BEFORE, encoding="utf-8", newline="\n")
    return root, base


def sync(root, spec_text=MODIFIED):
    """`/opsx:sync` для одного требования: в мастере то, что несёт MODIFIED, под заголовком `## Requirements`."""
    master_path(root).write_text(spec_text.replace("## MODIFIED Requirements", "## Requirements"), encoding="utf-8", newline="\n")


def view(root):
    """Связи, сигналы, состояния сценариев MODIFIED и `marks`, как их видит сборка."""
    graph, duplicates, unresolved = trace_graph.build_graph_with_signals(root, CHANGE)
    context = trace_graph.signal_context(root, CHANGE)
    edges = [(e["from"], e["to"], e["type"]) for e in graph["edges"]]
    return edges, trace_graph.graph_signals(graph, duplicates, unresolved, context), context["modified"], context["marks"]


def test_base_freeze_writes_numbers_scenarios_text_traces(tmp_path, fork):
    """`trace-snapshot`: «Пересборка после синхронизации» — заморозка кладёт в `base` по требованию MODIFIED номера, сценарии
    с хешами текста, хеш текста требования и хеши следов; текста мастера там нет."""
    root, base = modified_project(tmp_path)
    freeze(root)
    entry = snapshot(base)["base"]["demo"]["Один"]
    assert set(entry) == {"numbers", "scenarios", "text", "traces"}
    assert entry["numbers"] == [7] and sorted(entry["scenarios"]) == ["Меняется", "Старый"]
    assert all(len(h) == 64 for h in [entry["text"], *entry["scenarios"].values(), *entry["traces"]]) and len(entry["traces"]) == 1
    assert "SHALL" not in json.dumps(snapshot(base)["base"], ensure_ascii=False)


def test_base_rebuild_after_sync_keeps_links_and_signals(tmp_path, fork):
    """`trace-snapshot`: «Пересборка после синхронизации» — снимок с базой, затем `/opsx:sync`: после пересборки связи MODIFIED,
    сигналы о сценариях, состояния same/changed/new и `marks` те же, что до синхронизации."""
    root, base = modified_project(tmp_path)
    freeze(root)
    before = view(root)
    assert (ONE, "rec:F-19", "traces") in before[0] and (ONE, "rec:F-07", "traces") not in before[0]
    assert before[2][ONE]["scenarios"] == {"scn:demo/Один/Старый": "same", "scn:demo/Один/Меняется": "changed",
                                           "scn:demo/Один/Новый": "new"}
    assert before[3] == set() and any("Specify без сценария" in s for s in before[1])
    sync(root)
    (base / "tasks.md").write_text("- [x] 1.1 сделать\n", encoding="utf-8", newline="\n")  # заморозку конца пропустили
    assert freeze(root).action == "build"
    assert view(root) == before
    assert snapshot(base)["base"]["demo"]["Один"]["numbers"] == [7]  # база прежняя, мастер уже новый


def test_base_without_a_snapshot_after_sync_would_differ(tmp_path, fork):
    """`trace-snapshot`: «Пересборка после синхронизации» — контроль теста: без снимка та же правка мастера меняет ответ."""
    root, base = modified_project(tmp_path)
    before = view(root)
    sync(root)
    assert view(root) != before


def test_base_check_after_sync_gives_no_signals(tmp_path, fork):
    """`trace-snapshot`: «Проверка после синхронизации» — свежий снимок с базой, мастер переписан как при `/opsx:sync`:
    проверка файла графа сигналов не даёт."""
    root, base = modified_project(tmp_path)
    freeze(root)
    snap = base / "graph" / "req-graph.json"
    assert trace_graph.check_graph_file(root, CHANGE, snap) == []
    sync(root)
    assert trace_graph.check_graph_file(root, CHANGE, snap) == []
    done = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "check", CHANGE, str(snap)], capture_output=True,
                          text=True, encoding="utf-8", cwd=root)
    assert done.returncode == 0 and done.stdout.strip() == "сигналов нет", done.stdout


def test_base_sync_does_not_touch_snapshot(tmp_path, fork):
    """`trace-snapshot`: «Синхронизация не трогает снимок» — после правки мастера, как при `/opsx:sync`, заморозка видит снимок
    свежим: обновляет коммиты корней, граф и отчёт прежние."""
    root, base = modified_project(tmp_path)
    freeze(root)
    before = snapshot(base)
    report = (base / "graph" / "report.md").read_bytes()
    sync(root)
    assert freeze(root).action == "commits"
    assert {k: v for k, v in snapshot(base).items() if k != "roots"} == {k: v for k, v in before.items() if k != "roots"}
    assert (base / "graph" / "report.md").read_bytes() == report


def test_base_missed_end_freeze_keeps_the_old_base(tmp_path, fork):
    """`trace-snapshot`: «Заморозку конца реализации пропустили» — снимок устарел по `tasks.md` после `/opsx:sync`, собран заново,
    база в нём прежняя; живой мастер читается только для требования, которого в прежней базе нет."""
    root, base = modified_project(tmp_path)
    freeze(root)
    old = snapshot(base)["base"]
    sync(root)
    (base / "tasks.md").write_text("- [x] 1.1 сделать\n- [x] 1.2 ещё\n", encoding="utf-8", newline="\n")
    result = freeze(root)
    assert result.action == "build" and "устарел" in result.reason
    assert snapshot(base)["base"] == old
    extra = MODIFIED + "### Requirement: Второе\nТекст SHALL.\n\n" + SCN.format("Сц", "", "b")
    (base / "specs" / "demo" / "spec.md").write_text(extra, encoding="utf-8", newline="\n")
    master_path(root).write_text(master_path(root).read_text(encoding="utf-8") + "### Requirement: Второе\nМастер SHALL (F-19).\n",
                                 encoding="utf-8", newline="\n")
    freeze(root)
    again = snapshot(base)["base"]["demo"]
    assert again["Один"] == old["demo"]["Один"] and set(again) == {"Один", "Второе"} and again["Второе"]["numbers"] == [19]


def test_base_dropped_when_requirement_is_no_longer_modified(tmp_path, fork):
    """`trace-snapshot`: «Пересборка после синхронизации» — требование, которое перестало быть MODIFIED, из базы уходит."""
    root, base = modified_project(tmp_path)
    freeze(root)
    (base / "specs" / "demo" / "spec.md").write_text(MODIFIED.replace("MODIFIED", "ADDED"), encoding="utf-8", newline="\n")
    freeze(root)
    assert snapshot(base)["base"] == {}


def test_base_missing_numbers_stay_when_text_equals_master_and_report_names_it(tmp_path, fork):
    """`trace-snapshot`: «Базы на требование нет» — `graph/` нет, текст MODIFIED совпал с мастером: номера дают связи, отчёт
    называет требование отдельным разделом."""
    root, base = modified_project(tmp_path, spec_text=CARRIED)
    sync(root, CARRIED)
    assert (ONE, "rec:F-07", "traces") in view(root)[0]
    text = trace_graph.build_report(root, CHANGE)
    head, _, tail = text.partition("## Требования MODIFIED без базы мастер-спеки")
    assert tail and "demo/Один" in tail and "specs/demo/spec.md:" in tail and "Сигналов нет." not in text
    assert "без базы" not in head and bare_brackets(text) == []


def test_base_missing_but_text_differs_still_cuts_master_numbers(tmp_path, fork):
    """`trace-snapshot`: «Базы на требование нет» — текст MODIFIED не совпал с мастером: F-84 действует, раздела в отчёте нет."""
    root, base = modified_project(tmp_path)
    edges = view(root)[0]
    assert (ONE, "rec:F-07", "traces") not in edges and (ONE, "rec:F-19", "traces") in edges
    assert "без базы" not in trace_graph.build_report(root, CHANGE)


def test_base_present_after_freeze_so_report_does_not_name_requirement(tmp_path, fork):
    """`trace-snapshot`: «Базы на требование нет» — после заморозки база есть, отчёт требование не называет, F-84 действует
    и до, и после синхронизации."""
    root, base = modified_project(tmp_path, spec_text=CARRIED)
    freeze(root)
    assert "без базы" not in (base / "graph" / "report.md").read_text(encoding="utf-8")
    assert (ONE, "rec:F-07", "traces") not in view(root)[0]
    sync(root, CARRIED)
    assert (ONE, "rec:F-07", "traces") not in view(root)[0]


@pytest.mark.parametrize("broken", [{"numbers": [7]}, {"numbers": ["7"], "scenarios": {}, "text": "x", "traces": []}, "строка", None])
def test_base_with_bad_shape_is_not_used(broken, tmp_path, fork):
    """`trace-snapshot`: «Базы на требование нет» — запись базы негодной формы не служит, читается живой мастер."""
    root, base = modified_project(tmp_path)
    freeze(root)
    good = view(root)
    snap = snapshot(base)
    snap["base"] = {"demo": {"Один": broken}}
    (base / "graph" / "req-graph.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    assert view(root) == good  # до синхронизации живой мастер даёт то же
    sync(root)
    assert view(root) != good
    (base / "graph" / "req-graph.json").write_text("не json", encoding="utf-8")
    assert view(root) != good
