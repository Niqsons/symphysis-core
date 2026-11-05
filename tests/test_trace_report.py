"""Команда `report` скрипта графа `tools/trace_graph.py`: находки `openspec validate` и сигналы графа одним отчётом (U09)."""
import ast
import os
import subprocess
import sys

import pytest

import openspec_run
import trace_graph
from conftest import ROOT, fork_calls, fork_env, fork_reply, install_fork_shim, requires_fork
from test_schema import make_project
from test_trace_graph import CHANGE, SPEC, make_change

SCRIPT = ROOT / "tools" / "trace_graph.py"
CLEAN = {"items": [{"id": CHANGE, "type": "change", "valid": True, "issues": [], "durationMs": 1}]}
FOUND = {"items": [{"id": CHANGE, "type": "change", "valid": False, "durationMs": 1, "issues": [
    {"level": "ERROR", "path": "specs/demo/spec.md", "message": "Requirement «Один» must have at least one scenario"}]}]}
ONE_REQ = "## ADDED Requirements\n\n### Requirement: Один\nТекст SHALL.\n\n#### Scenario: Первый\n- **WHEN** a\n- **THEN** b\n"
DONE = "- [ ] 1.1 сделать `demo`: «Первый»\n"
NO_TASK = "- [ ] 1.1 ничего\n"


def report(root, *args, env=None, change=CHANGE):
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "report", change, *args], capture_output=True,
                          text=True, encoding="utf-8", cwd=root, env=env)


def with_shim(tmp_path, validate):
    """Каталог шима и окружение, где `SYMPHYSIS_OPENSPEC` указывает на шим с ответом `validate`."""
    shim_dir = tmp_path / "fork"
    shim = install_fork_shim(shim_dir, validate=validate)
    return shim_dir, fork_env(shim_dir, SYMPHYSIS_OPENSPEC=str(shim))


def use_shim(tmp_path, monkeypatch, validate):
    shim_dir, env = with_shim(tmp_path, validate)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return shim_dir


def test_validate_finding_stands_next_to_graph_signals(tmp_path):
    """`trace-signals`: «Находка validate в отчёте» — находка `openspec validate` рядом с сигналом графа, код 0."""
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ}, tasks=NO_TASK)
    shim_dir, env = with_shim(tmp_path, fork_reply(FOUND, code=1))
    done = report(root, env=env)
    assert done.returncode == 0, done.stderr
    assert "## Находки openspec validate" in done.stdout and "## Сигналы графа" in done.stdout
    assert "must have at least one scenario" in done.stdout and "specs/demo/spec.md" in done.stdout
    assert "validate не запустился" not in done.stdout
    assert done.stdout.index("must have at least one") < done.stdout.index("требование без задачи")
    argv = fork_calls(shim_dir)[0]["argv"]
    assert argv == ["validate", CHANGE, "--type", "change", "--json", "--strict", "--no-interactive"]


@requires_fork
def test_real_fork_names_requirement_without_scenario(tmp_path):
    """`trace-signals`: «Находка validate в отчёте» — настоящий форк: требование без сценария."""
    root = make_project(tmp_path, change="demo")
    spec = root / "openspec" / "changes" / "demo" / "specs" / "demo" / "spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("## ADDED Requirements\n\n### Requirement: Один\nТекст SHALL.\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "SYMPHYSIS_OPENSPEC"}
    bin_js = ROOT / "upstream" / "openspec" / "bin" / "openspec.js"
    if bin_js.exists():
        env["SYMPHYSIS_OPENSPEC"] = str(bin_js)
    done = report(root, env=env, change="demo")
    assert done.returncode == 0, done.stderr
    findings = done.stdout.split("## Сигналы графа")[0]
    assert "[!!] openspec validate" in findings and "scenario" in findings.lower(), done.stdout
    assert "validate не запустился" not in done.stdout and "требование без задачи" in done.stdout


def test_clean_validate_and_no_signals_says_so(tmp_path):
    """`trace-signals`: «Находок нет» — отчёт говорит, что сигналов нет, код 0."""
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ}, tasks=DONE)
    _, env = with_shim(tmp_path, fork_reply(CLEAN))
    done = report(root, env=env)
    assert done.returncode == 0 and "Сигналов нет." in done.stdout, done.stdout + done.stderr
    assert "[!!]" not in done.stdout


def test_missing_fork_gives_not_started_line_and_graph_signals(tmp_path):
    """`trace-signals`: «`openspec` не запустился» — форка нет: сигналы графа и строка с причиной, код 0."""
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ})
    env = fork_env(None, SYMPHYSIS_OPENSPEC=str(tmp_path / "нет" / "openspec.js"))
    done = report(root, env=env)
    assert done.returncode == 0, done.stderr
    assert "validate не запустился: openspec не найден" in done.stdout and "требование без задачи" in done.stdout
    assert str(tmp_path) not in done.stdout and "Сигналов нет" not in done.stdout


@pytest.mark.parametrize("reply", [
    fork_reply("падение", code=1, stderr="boom"),
    fork_reply("", code=2),
    fork_reply(FOUND, code=2),
], ids=["not-json", "empty", "code-two"])
def test_fork_failure_gives_not_started_line(tmp_path, reply):
    """`trace-signals`: «`openspec` не запустился» — форк завершился ошибкой: строка с причиной и сигналы графа, код 0."""
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ})
    _, env = with_shim(tmp_path, reply)
    done = report(root, env=env)
    assert done.returncode == 0, done.stderr
    assert "validate не запустился" in done.stdout and "требование без задачи" in done.stdout, done.stdout


def test_unknown_item_without_items_is_not_started_not_clean(tmp_path):
    """`trace-signals`: «`openspec` не запустился» — JSON без `items` (`unknown_item`) не читается как «находок нет»."""
    body = {"status": [{"severity": "error", "code": "unknown_item", "message": "нет такого"}]}
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ}, tasks=DONE)
    _, env = with_shim(tmp_path, fork_reply(body, code=1))
    done = report(root, env=env)
    assert done.returncode == 0 and "validate не запустился" in done.stdout, done.stdout
    assert "Сигналов нет." not in done.stdout


def test_hung_fork_gives_not_started_line(tmp_path, monkeypatch):
    """`trace-signals`: «`openspec` не запустился» — форк не ответил за предел: строка с причиной, без трассировки."""
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ})
    use_shim(tmp_path, monkeypatch, fork_reply(CLEAN, hang=5))
    monkeypatch.setattr(openspec_run, "FORK_TIMEOUT", 1)
    text = trace_graph.build_report(root, CHANGE)
    assert "validate не запустился" in text and "не ответил" in text


def test_reason_has_no_absolute_paths(tmp_path, monkeypatch):
    """`trace-signals`: «`openspec` не запустился» — причина без абсолютных путей: отчёт уйдёт в git."""
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ})
    err = f"Error at {tmp_path}\\x and X:\\other\\file.js"
    use_shim(tmp_path, monkeypatch, fork_reply("не json", code=1, stderr=err))
    text = trace_graph.build_report(root, CHANGE)
    assert "validate не запустился" in text
    assert str(tmp_path) not in text and "X:\\other" not in text


def test_shell_symbols_in_name_refuse_before_fork(tmp_path):
    """`trace-signals`: «Имя изменения с символами оболочки» — отказ называет имя, форк не вызван, файла `файл` нет."""
    name = "a&echo.>файл"
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ})
    shim_dir, env = with_shim(tmp_path, fork_reply(CLEAN))
    before = sorted(p.name for p in root.iterdir())
    done = report(root, env=env, change=name)
    assert done.returncode == 1 and name in done.stderr and "Traceback" not in done.stderr, done.stderr
    assert fork_calls(shim_dir) == []
    assert not (root / "файл").exists() and not (root / "openspec" / "changes" / "файл").exists()
    assert sorted(p.name for p in root.iterdir()) == before


def test_report_function_checks_name_itself(tmp_path):
    """`trace-signals`: «Имя изменения с символами оболочки» — функция отчёта (её зовёт freeze) проверяет имя сама."""
    with pytest.raises(openspec_run.ForkError, match="a&echo"):
        trace_graph.build_report(tmp_path, "a&echo.>файл")


def test_missing_change_is_refusal_before_fork(tmp_path):
    """Нет изменения — отказ, код 1, форк не вызван."""
    (tmp_path / "openspec").mkdir()
    shim_dir, env = with_shim(tmp_path, fork_reply(CLEAN))
    done = report(tmp_path, env=env)
    assert done.returncode == 1 and CHANGE in done.stderr, done.stderr
    assert fork_calls(shim_dir) == []


def test_broken_journal_is_refusal(tmp_path):
    """Негодный журнал — отказ сборки, код 1, форк не вызван."""
    root, base = make_change(tmp_path, specs={"demo": ONE_REQ})
    (base / "decisions.json").write_text("{не json", encoding="utf-8")
    shim_dir, env = with_shim(tmp_path, fork_reply(CLEAN))
    done = report(root, env=env)
    assert done.returncode == 1 and "Traceback" not in done.stderr, done.stderr
    assert fork_calls(shim_dir) == []


def test_requirement_and_scenario_without_task_are_signals_with_code_zero(tmp_path):
    """`trace-signals`: «Отчёт с сигналами» — сценарий без задачи назван с местом, код 0; закрытое и MODIFIED не названы."""
    root, _ = make_change(tmp_path, specs={"demo": SPEC}, tasks="- [ ] 1.1 `demo`: «Первый»\n")
    _, env = with_shim(tmp_path, fork_reply(CLEAN))
    done = report(root, env=env)
    assert done.returncode == 0, done.stderr
    lines = [line for line in done.stdout.splitlines() if line.startswith("[!!]")]
    assert any("сценарий без задачи" in line and "Второй" in line and "specs/demo/spec.md:" in line for line in lines)
    assert not any("требование без задачи" in line for line in lines)  # Первый закрыт: требование держится
    assert not any("Третий" in line or "Два" in line for line in lines)  # MODIFIED — вид U10
    assert not any("Первый" in line for line in lines)


def test_requirement_with_no_closed_scenario_is_named(tmp_path):
    """`trace-signals`: «Отчёт с сигналами» — требование без задачи названо вместе с его сценарием."""
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ}, tasks=NO_TASK)
    signals = trace_graph.graph_signals(trace_graph.build_graph(root, CHANGE))
    assert {s.split(":", 1)[0] for s in signals} == {"[!!] требование без задачи", "[!!] сценарий без задачи"}, signals
    assert all("demo/Один" in s and "specs/demo/spec.md:" in s for s in signals)


def test_graph_signals_does_not_print(tmp_path, capsys):
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ}, tasks=DONE)
    assert trace_graph.graph_signals(trace_graph.build_graph(root, CHANGE)) == []
    assert capsys.readouterr().out == ""


def test_report_function_returns_text_and_prints_nothing(tmp_path, monkeypatch, capsys):
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ}, tasks=DONE)
    use_shim(tmp_path, monkeypatch, fork_reply(CLEAN))
    text = trace_graph.build_report(root, CHANGE)
    assert "Сигналов нет." in text and capsys.readouterr().out == ""


def test_step_help_and_report_run_the_same_fork_file(tmp_path):
    """`trace-signals`: «Запуск форка общий» — и отчёт, и `step_help.py` запускают файл из `SYMPHYSIS_OPENSPEC`."""
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ}, tasks=DONE)
    shim_dir, env = with_shim(tmp_path, fork_reply(CLEAN))
    assert report(root, env=env).returncode == 0
    subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "step_help.py"), "--change", CHANGE], cwd=root, env=env,
                   capture_output=True, text=True, encoding="utf-8")
    names = [call["argv"][0] for call in fork_calls(shim_dir)]
    assert "validate" in names and len(names) >= 2, names
    for module in ("trace_graph.py", "step_help.py"):
        tree = ast.parse((ROOT / "tools" / module).read_text(encoding="utf-8"))
        assert any(isinstance(n, ast.ImportFrom) and n.module == "openspec_run" for n in ast.walk(tree)), module


def test_report_help_is_no_longer_a_stub():
    done = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "report", "--help"], capture_output=True, text=True,
                          encoding="utf-8")
    assert done.returncode == 0 and "ещё не реализована" not in done.stdout
    assert "validate" in done.stdout and "Звать, когда" in done.stdout and "Коды:" in done.stdout
