"""Команда `report` скрипта графа `tools/trace_graph.py`: находки `openspec validate` и сигналы графа одним отчётом (U09)."""
import ast
import os
import re
import subprocess
import sys

import pytest

import openspec_run
import trace_graph
from conftest import ROOT, fork_calls, fork_env, fork_reply, install_fork_shim, requires_fork
from test_schema import make_project
import journal_model
import json
from test_trace_graph import CHANGE, make_change as _make_change

SCRIPT = ROOT / "tools" / "trace_graph.py"
CLEAN = {"items": [{"id": CHANGE, "type": "change", "valid": True, "issues": [], "durationMs": 1}]}
FOUND = {"items": [{"id": CHANGE, "type": "change", "valid": False, "durationMs": 1, "issues": [
    {"level": "ERROR", "path": "specs/demo/spec.md", "message": "Requirement «Один» must have at least one scenario"}]}]}
ONE_REQ = "## ADDED Requirements\n\n### Requirement: Один\nТекст SHALL (F-01).\n\n#### Scenario: Первый\n- **WHEN** a\n- **THEN** b\n"
DONE = "- [ ] 1.1 сделать `demo`: «Первый»\n"
DONE_SC = "- [ ] 1.1 `demo`: «Сц»\n"
NO_TASK = "- [ ] 1.1 ничего\n"


def make_change(tmp_path, **kw):
    """Изменение `demo` с записью F-01 в журнале: требования отчётов этого файла называют её, сигнал «без записи» не мешает."""
    kw.setdefault("journal", ["F-01"])
    return _make_change(tmp_path, **kw)


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


@pytest.mark.parametrize("item", [
    {"id": CHANGE, "valid": False, "issues": []},
    {"id": CHANGE, "issues": []},
    {"id": CHANGE, "valid": False, "issues": None},
    {"id": CHANGE, "valid": False, "issues": "строка"},
], ids=["invalid-no-issues", "no-valid-field", "issues-null", "issues-string"])
def test_code_one_without_finding_lines_is_a_finding_not_clean(tmp_path, item):
    """`trace-signals`: «Находка validate в отчёте» — код 1 без строк находок не выглядит чистым отчётом."""
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ}, tasks=DONE)
    _, env = with_shim(tmp_path, fork_reply({"items": [item]}, code=1))
    done = report(root, env=env)
    assert done.returncode == 0 and "Traceback" not in done.stderr, done.stderr
    assert "[!!] openspec validate: изменение невалидно, а находок в ответе нет" in done.stdout, done.stdout
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


SPEC = ("## ADDED Requirements\n\n### Requirement: Один\nТекст SHALL (F-01).\n\n#### Scenario: Первый\n- **WHEN** a\n- **THEN** b\n\n"
        "#### Scenario: Второй\n- **WHEN** c\n- **THEN** d\n")


def test_requirement_and_scenario_without_task_are_signals_with_code_zero(tmp_path):
    """`trace-signals`: «Отчёт с сигналами» — сценарий без задачи назван с местом, код 0; закрытое не названо."""
    root, _ = make_change(tmp_path, specs={"demo": SPEC}, tasks="- [ ] 1.1 `demo`: «Первый»\n")
    _, env = with_shim(tmp_path, fork_reply(CLEAN))
    done = report(root, env=env)
    assert done.returncode == 0, done.stderr
    lines = [line for line in done.stdout.splitlines() if line.startswith("[!!]")]
    assert any("сценарий без задачи" in line and "Второй" in line and "specs/demo/spec.md:" in line for line in lines)
    assert not any("требование без задачи" in line for line in lines)  # Первый закрыт: требование держится
    assert not any("Первый" in line for line in lines)


def test_requirement_with_no_closed_scenario_is_named(tmp_path):
    """`trace-signals`: «Отчёт с сигналами» — требование без задачи названо вместе с его сценарием."""
    root, _ = make_change(tmp_path, specs={"demo": ONE_REQ})
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


# --- состав сигналов (U10, F-57, F-64) ----------------------------------------------------------------------------

def journal(base, *records):
    """Журнал изменения из словарей-поправок к пустой записи: `id`, `question` и любые поля записи."""
    full = []
    for part in records:
        rec = journal_model._new_record(part["id"], part.get("question", f"Вопрос {part['id']}?"))
        rec.update({k: v for k, v in part.items() if k not in ("id", "question")})
        full.append(rec)
    (base / "decisions.json").write_text(json.dumps({"title": "t", "source": "", "records": full}, ensure_ascii=False,
                                                    indent=1) + "\n", encoding="utf-8")


def decided(rid, text="Взять часть", outcome=None, letter="A", **extra):
    return {"id": rid, "status": "решён", "options": [{"letter": letter, "text": text, "added": False, "unlikely": None,
            "evidence": []}], "recommendation": {"option": letter, "why": "потому"},
            "decision": {"option": letter, "word": "да", "date": "2026-11-05"}, "outcome": outcome, **extra}


def probe(value):
    return {"kind": "проба", "value": value, "reason": ""}


def criterion(rid, quote="цитата критерия готовности"):
    return {"id": rid, "kind": "факт", "status": "решён", "addressee": "постановка", "evidence": [
        {"path": "intent.md", "quote": quote, "line": 1, "verdict": "сошлась", "found": True}]}


def lines_of(root):
    """Сигналы графа с контекстом журнала и спек, как их собирает отчёт."""
    graph, duplicates, unresolved = trace_graph.build_graph_with_signals(root, CHANGE)
    context = trace_graph.signal_context(root, CHANGE)
    return trace_graph.graph_signals(graph, duplicates, unresolved, context)


def of_kind(signals, kind):
    return [s for s in signals if s.startswith(f"[!!] {kind}:")]


def req(name, number=None, scenarios=("Сц",)):
    text = f"### Requirement: {name}\nТекст SHALL" + (f" (F-{number:02d})" if number else "") + ".\n\n"
    return text + "".join(f"#### Scenario: {s}\n- **WHEN** a\n- **THEN** b\n\n" for s in scenarios)


def spec(*blocks, section="ADDED"):
    return f"## {section} Requirements\n\n" + "".join(blocks)


def put_master(root, text, crlf=False):
    """Мастер-спека `demo`: заголовок секции у неё `## Requirements`."""
    path = root / "openspec" / "specs" / "demo" / "spec.md"
    path.parent.mkdir(parents=True)
    body = text.replace("## ADDED Requirements", "## Requirements")
    path.write_bytes((body.replace("\n", "\r\n") if crlf else body).encode("utf-8"))


def test_criterion_without_requirement_names_record_and_quote(tmp_path):
    """`trace-signals`: «Критерий без требования» — сигнал называет запись и цитату критерия."""
    root, base = make_change(tmp_path, specs={"demo": spec(req("Один", 2))}, tasks=DONE_SC)
    journal(base, criterion("F-01"), decided("F-02"))
    found = of_kind(lines_of(root), "критерий без требования")
    assert len(found) == 1 and "F-01" in found[0] and "цитата критерия готовности" in found[0], found
    (base / "specs" / "demo" / "spec.md").write_text(spec(req("Один", 1)), encoding="utf-8")
    assert of_kind(lines_of(root), "критерий без требования") == []


def test_scope_decision_is_a_plain_line_without_mark(tmp_path):
    """`trace-signals`: «Решение об объёме» — строка «решение без требования и задачи», отдельной пометки нет."""
    root, base = make_change(tmp_path, specs={"demo": spec(req("Один", 1))}, tasks=DONE_SC)
    journal(base, {"id": "F-01"}, decided("F-02", "Объём: только половина"))
    found = of_kind(lines_of(root), "решение без требования и задачи")
    assert len(found) == 1 and re.fullmatch(r"\[!!\] решение без требования и задачи: F-02\.A [^—]+ — decisions\.json:\d+", found[0]), found


def test_decision_reached_or_asis_or_probe_is_silent(tmp_path):
    """`trace-signals`: «Решение об объёме» и «Шумные виды в отчёт не идут» — «Оставить как есть», исход пробы,
    решение, до которого дошли требование или задача, строки не дают."""
    root, base = make_change(tmp_path, specs={"demo": spec(req("Один", 1))}, tasks="- [ ] 1.1 `demo`: «Сц» (F-04)\n")
    journal(base, {"id": "F-01"}, decided("F-02", "Оставить как есть: строка в отчёте"), decided("F-03", outcome=probe("Specify")),
            decided("F-04"), decided("F-05"))
    only = of_kind(lines_of(root), "решение без требования и задачи")
    assert [s.split()[6] for s in only] == ["F-05.A"], only  # F-04 держит задача, F-02 «как есть», F-03 проба
    (base / "specs" / "demo" / "spec.md").write_text(spec(req("Один", 5)), encoding="utf-8")
    assert of_kind(lines_of(root), "решение без требования и задачи") == []


def test_same_scenario_name_in_two_requirements_is_closed_and_ambiguous(tmp_path):
    """`trace-signals`: «Одно имя у двух требований capability» — оба сценария закрыты, сигнал называет оба требования."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Первое", 1, ("Пустой ввод",)), req("Второе", 1, ("Пустой ввод",)))},
                          tasks="- [ ] 1.1 `demo`: «Пустой ввод»\n")
    signals = lines_of(root)
    assert of_kind(signals, "сценарий без задачи") == [] and of_kind(signals, "требование без задачи") == [], signals
    found = of_kind(signals, "неоднозначное имя")
    assert len(found) == 1 and "Пустой ввод" in found[0] and "«Первое»" in found[0] and "«Второе»" in found[0], found


def test_same_name_without_task_is_not_ambiguous_only_unclosed(tmp_path):
    """`trace-signals`: «Одно имя у двух требований capability» — без задачи с этим именем неоднозначности нет."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Первое", 1, ("Общий",)), req("Второе", 1, ("Общий",)))}, tasks=NO_TASK)
    signals = lines_of(root)
    assert of_kind(signals, "неоднозначное имя") == [] and len(of_kind(signals, "сценарий без задачи")) == 2


def test_duplicate_id_is_an_ambiguous_name_with_all_places(tmp_path):
    """`trace-signals`: «Отчёт называет закрытый состав сигналов» — два требования с одним именем: неоднозначное имя с обоими местами."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1), req("Один", 1))}, tasks=DONE_SC)
    found = [s for s in of_kind(lines_of(root), "неоднозначное имя") if "demo/Один (" in s]
    assert len(found) == 1 and found[0].count("specs/demo/spec.md:") == 2, found


def test_evidence_that_diverged_is_not_in_the_report(tmp_path):
    """`trace-signals`: «Улика разошлась» — цитаты нет в файле, строки об улике в отчёте нет."""
    root, base = make_change(tmp_path, specs={"demo": spec(req("Один", 1))}, tasks=DONE_SC)
    rec = decided("F-01")
    rec["options"][0]["evidence"] = [{"path": "intent.md", "quote": "такой цитаты в файле нет", "line": 1,
                                      "verdict": "цитаты нет", "found": False}]
    journal(base, rec)
    assert lines_of(root) == []


def test_modified_scenario_carried_from_master_is_silent(tmp_path):
    """`trace-signals`: «MODIFIED несёт прежний сценарий» — тот же текст в мастере и в MODIFIED, строки о нём нет."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1, ("Старый",)), section="MODIFIED")})
    put_master(root, spec(req("Один", 1, ("Старый",))), crlf=True)
    assert lines_of(root) == []


def test_modified_scenario_new_in_master_is_named(tmp_path):
    """`trace-signals`: «Новый сценарий в MODIFIED» — до `/opsx:sync` сигнал называет сценарий, которого в мастере нет."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1, ("Старый", "Новый")), section="MODIFIED")})
    put_master(root, spec(req("Один", 1, ("Старый",))))
    signals = lines_of(root)
    found = of_kind(signals, "сценарий без задачи")
    assert len(found) == 1 and "Новый" in found[0] and "Старый" not in found[0], signals


def test_modified_same_name_other_text_is_its_own_kind(tmp_path):
    """`trace-signals`: «Прежнее имя, другой текст» — сигнал своего вида называет сценарий; вида «без задачи» у него нет."""
    changed = spec(req("Один", 1, ("Старый",)).replace("**THEN** b", "**THEN** другое"), section="MODIFIED")
    root, _ = make_change(tmp_path, specs={"demo": changed})
    put_master(root, spec(req("Один", 1, ("Старый",))))
    signals = lines_of(root)
    found = of_kind(signals, "сценарий MODIFIED с прежним именем и другим текстом")
    assert len(found) == 1 and "Старый" in found[0] and "specs/demo/spec.md:" in found[0], found
    assert of_kind(signals, "сценарий без задачи") == []


def test_modified_text_differing_in_spaces_and_line_ends_is_carried(tmp_path):
    """`trace-signals`: «MODIFIED несёт прежний сценарий» — различие только в пробелах и концах строк сценарий не меняет."""
    wrapped = spec(req("Один", 1, ("Старый",)).replace("- **WHEN** a", "-  **WHEN**   a  "), section="MODIFIED")
    root, _ = make_change(tmp_path, specs={"demo": wrapped})
    put_master(root, spec(req("Один", 1, ("Старый",))), crlf=True)
    assert lines_of(root) == []


def test_diverged_scenarios_go_to_their_own_report_section(tmp_path, monkeypatch):
    """`trace-signals`: «Прежнее имя, другой текст» — в сохранённом отчёте расхождение в отдельном разделе, не в «Сигналах графа»."""
    changed = spec(req("Один", 1, ("Старый",)).replace("**THEN** b", "**THEN** другое"), section="MODIFIED")
    root, _ = make_change(tmp_path, specs={"demo": changed})
    put_master(root, spec(req("Один", 1, ("Старый",))))
    use_shim(tmp_path, monkeypatch, fork_reply(CLEAN))
    text = trace_graph.build_report(root, CHANGE)
    head, _, tail = text.partition("## Расхождения сценариев MODIFIED")
    assert tail and "прежним именем" in tail and "Старый" in tail
    assert "прежним именем" not in head and "Сигналов нет." not in text


def test_security_item_without_name_or_with_known_name_is_silent_unknown_is_named(tmp_path):
    """`trace-signals`: «Пункт security закрыт доводом» — пункт без имени и с известным именем молчит, неизвестное имя названо."""
    table = ("| Пункт | Закрыт |\n| --- | --- |\n| Альфа | довод |\n| Бета | `demo` «Один» |\n"
             "| Гамма | `demo` «Нет такого» |\n")
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1))}, tasks=DONE_SC, security=table)
    found = of_kind(lines_of(root), "неизвестное имя или номер")
    assert len(found) == 1 and "Нет такого" in found[0] and "security.md:5" in found[0], found
    assert not any("Альфа" in s or "Бета" in s for s in lines_of(root))


def test_requirement_without_number_is_named_and_with_number_is_not(tmp_path):
    """`trace-conventions`: «Требование без номера» — сигнал «требование без записи» называет его."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Без номера"), req("С номером", 1))}, tasks="- [ ] 1.1 `demo`: «Сц»\n")
    found = of_kind(lines_of(root), "требование без записи")
    assert len(found) == 1 and "demo/Без номера" in found[0] and "specs/demo/spec.md:" in found[0], found


def test_probe_trace_does_not_replace_number_in_text(tmp_path):
    """`trace-conventions`: «След пробы не заменяет номер в тексте» (F-158) — связь `traces` к `rec:F-85` из следа есть,
    сигнал «требование без записи» называет требование."""
    block = req("Без номера") + "<!-- проба краёв: форма=io, исходы: F-85 Backstop -->\n"
    root, _ = make_change(tmp_path, journal=["F-01", "F-85"], specs={"demo": spec(block)}, tasks="- [ ] 1.1 `demo`: «Сц»\n")
    graph = trace_graph.build_graph(root, CHANGE)
    assert [(e["from"], e["to"]) for e in graph["edges"] if e["type"] == "traces"] == [("req:demo/Без номера", "rec:F-85")]
    found = of_kind(lines_of(root), "требование без записи")
    assert len(found) == 1 and "demo/Без номера" in found[0], found


def test_number_in_text_holds_requirement_next_to_probe_trace(tmp_path):
    """`trace-conventions`: «Требование без номера» (F-158) — номер в тексте гасит сигнал, след пробы рядом его не
    возвращает; номер в тексте и в следе на одной строке остаётся опорой."""
    block = req("Один", 1) + "<!-- проба краёв: форма=io, исходы: F-85 Backstop -->\n"
    same = req("Два").replace("Текст SHALL.", "Текст (F-85) SHALL. <!-- проба краёв: исходы: F-85 Specify -->")
    root, _ = make_change(tmp_path, journal=["F-01", "F-85"], specs={"demo": spec(block, same)}, tasks=DONE_SC)
    assert of_kind(lines_of(root), "требование без записи") == []


def test_parked_record_in_text_does_not_hold_requirement_but_decided_does(tmp_path):
    """`trace-conventions`: «Требование без номера» (F-158, F-157) — в тексте только номер парковки: сигнал есть; рядом
    номер решённой записи: сигнала нет."""
    both = req("Оба", 59).replace("(F-59)", "(F-59, F-01)")
    root, base = make_change(tmp_path, journal=["F-01", "F-59"], specs={"demo": spec(req("Парковка", 59), both)}, tasks=DONE_SC)
    journal(base, {"id": "F-01"}, {"id": "F-59", "status": "припаркован"})
    found = of_kind(lines_of(root), "требование без записи")
    assert len(found) == 1 and "demo/Парковка" in found[0], found


def test_number_cut_by_master_does_not_hold_requirement(tmp_path):
    """`trace-conventions`: «Требование без номера» (F-84) — номер MODIFIED, стоящий в тексте мастера, опорой не служит."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1), section="MODIFIED")})
    put_master(root, spec(req("Один", 1).replace("Текст", "Старый текст")))
    found = of_kind(lines_of(root), "требование без записи")
    assert len(found) == 1 and "demo/Один" in found[0], found


def test_requirement_with_unknown_number_is_unknown_not_without_record(tmp_path):
    """`trace-conventions`: «Требование без номера» — номер есть, записи нет: «неизвестное имя или номер», а не «без записи»."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 99))}, tasks=DONE_SC)
    signals = lines_of(root)
    assert of_kind(signals, "требование без записи") == []
    unknown = of_kind(signals, "неизвестное имя или номер")
    assert len(unknown) == 1 and "F-99" in unknown[0]


def test_unknown_parent_is_named_with_place(tmp_path):
    """`trace-conventions`: «Такого родителя нет» — сигнал «неизвестное имя» называет это место."""
    child = ("### Requirement: Дочернее\nЧасть требования «Нет такого». Текст SHALL (F-01).\n\n#### Scenario: Сц\n"
             "- **WHEN** a\n- **THEN** b\n")
    root, _ = make_change(tmp_path, specs={"demo": spec(child)}, tasks=DONE_SC)
    found = of_kind(lines_of(root), "неизвестное имя или номер")
    assert len(found) == 1 and "Нет такого" in found[0] and "specs/demo/spec.md:4" in found[0], found


def test_task_names_unknown_scenario_and_unknown_record(tmp_path):
    """`trace-signals`: «Отчёт называет закрытый состав сигналов» — неизвестное имя сценария и номер записи в задаче названы."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1))},
                          tasks="- [ ] 1.1 `demo`: «Сц»\n- [ ] 1.2 `demo`: «Нет сценария» (F-77)\n")
    found = of_kind(lines_of(root), "неизвестное имя или номер")
    assert len(found) == 2 and all("tasks.md:2" in s for s in found), found
    assert any("Нет сценария" in s for s in found) and any("F-77" in s for s in found)


def test_task_to_nothing_is_named_and_attached_task_is_not(tmp_path):
    """`trace-signals`: «Отчёт называет закрытый состав сигналов» — задача без сценария и записи названа, с ними — нет."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1))},
                          tasks="- [ ] 1.1 `demo`: «Сц»\n- [ ] 1.2 ничего не называет\n- [ ] 1.3 про (F-01)\n")
    found = of_kind(lines_of(root), "задача ни к чему")
    assert len(found) == 1 and "1.2" in found[0] and "tasks.md:2" in found[0], found


def test_stale_trace_names_record_with_other_outcome(tmp_path):
    """`trace-signals`: «Отчёт называет закрытый состав сигналов» — след пробы называет исход, а в журнале исход другой."""
    block = req("Один", 1) + "<!-- проба краёв: форма=io, исходы: F-02 Specify, F-03 Dismiss, F-04 открыт, F-05 Defer -->\n"
    root, base = make_change(tmp_path, specs={"demo": spec(block)}, tasks=DONE_SC)
    journal(base, {"id": "F-01"}, decided("F-02", outcome=probe("Dismiss")), decided("F-03", outcome=probe("Dismiss")),
            decided("F-04", outcome=probe("Specify")), decided("F-05", outcome=probe("Defer")))
    found = of_kind(lines_of(root), "след отстал от журнала")
    assert len(found) == 2, found
    assert "F-02" in found[0] and "Specify" in found[0] and "Dismiss" in found[0] and "specs/demo/spec.md:" in found[0]
    assert "F-04" in found[1] and "открыт" in found[1]  # F-03 и F-05 сошлись со следом


def test_common_record_gives_candidate_in_graph_not_in_report(tmp_path):
    """`trace-graph`: «Общая запись» — в графе кандидат с `source`, в отчёте сигналов строки о паре нет."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("А", 1, ("Первый",)), req("Б", 1, ("Второй",)))},
                          tasks="- [ ] 1.1 `demo`: «Первый»\n- [ ] 1.2 `demo`: «Второй»\n")
    graph = trace_graph.build_graph(root, CHANGE)
    assert len(graph["candidates"]) == 1 and graph["candidates"][0]["source"]
    assert lines_of(root) == []


def test_sample_form_in_double_backticks_is_not_a_reference(tmp_path):
    """`trace-signals`: «Отчёт называет закрытый состав сигналов» — образец формы в двойных обратных кавычках не ссылка:
    ни связи, ни неразрешённой записи; настоящая ссылка в той же строке работает."""
    tasks = "- [ ] 1.1 форма `` `capability`: «сценарий» `` и настоящая `demo`: «Сц»\n"
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1))}, tasks=tasks)
    graph, _, unresolved = trace_graph.build_graph_with_signals(root, CHANGE)
    assert unresolved == [] and [e["to"] for e in graph["edges"] if e["type"] == "satisfies"] == ["scn:demo/Один/Сц"]
    assert lines_of(root) == []


def test_quote_with_angle_brackets_is_not_left_bare(tmp_path):
    """`trace-signals`: «Критерий без требования» — цитата с угловыми скобками в отчёте не остаётся голой (плагин md4h)."""
    root, base = make_change(tmp_path, specs={"demo": spec(req("Один", 2))}, tasks=DONE_SC)
    journal(base, criterion("F-01", "список T<N> и <b>"), decided("F-02"))
    found = of_kind(lines_of(root), "критерий без требования")
    assert len(found) == 1 and "<" not in found[0] and ">" not in found[0], found


def test_signals_come_in_order_of_place(tmp_path):
    """`trace-signals`: «Отчёт называет закрытый состав сигналов» — строки сигналов идут по месту: путь файла и строка по
    возрастанию, у строки с несколькими местами сортирует первое."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("А"), req("Б"))}, tasks="- [ ] 1.1 `demo`: «Сц»\n- [ ] 1.2 ничего\n")
    places = [s.rsplit(" — ", 1)[1].split(", ")[0] for s in lines_of(root)]
    keys = [(p.rsplit(":", 1)[0], int(p.rsplit(":", 1)[1])) for p in places]
    assert keys == sorted(keys) and len(keys) >= 3


def test_trace_carried_from_master_is_silent_new_trace_is_checked(tmp_path):
    """`trace-signals`: «MODIFIED несёт прежний сценарий» — след пробы, дословно стоящий в том же требовании мастер-спеки,
    номера из журнала другого изменения: сигнала нет; новый след в том же требовании сверяется."""
    old = "<!-- проба краёв: форма=io, исходы: F-02 открыт -->\n"
    new = "<!-- проба краёв: форма=io, исходы: F-03 Specify -->\n"
    root, base = make_change(tmp_path, specs={"demo": spec(req("Один", 1) + old + new, section="MODIFIED")})
    put_master(root, spec(req("Один", 1) + old.replace("  ", " ")))
    journal(base, {"id": "F-01"}, decided("F-02", outcome=probe("Specify")), decided("F-03", outcome=probe("Dismiss")))
    found = of_kind(lines_of(root), "след отстал от журнала")
    assert len(found) == 1 and "F-03" in found[0], found


def test_modified_requirement_with_same_text_and_new_scenario_is_not_without_record(tmp_path):
    """`trace-signals`: «Новый сценарий в MODIFIED» — требование с неизменным текстом и новым сценарием «без записи» не
    получает, о сценарии говорит «сценарий без задачи»."""
    blocks = req("Один", None, ("Старый", "Новый"))
    root, _ = make_change(tmp_path, specs={"demo": spec(blocks, section="MODIFIED")})
    put_master(root, spec(req("Один", None, ("Старый",))))
    signals = lines_of(root)
    assert of_kind(signals, "требование без записи") == []
    assert len(of_kind(signals, "сценарий без задачи")) == 1 and "Новый" in of_kind(signals, "сценарий без задачи")[0]


# --- служебные задачи, исходы проб, записи [сигнал] (U11, F-43..F-47, F-64, F-69, F-90, F-98, F-114, F-116) ----------

SERVICE = "`служебная`"


def scn_spec(*scenarios, number=1):
    """Одно требование `Один` с записью `number` и сценариями `(имя, строки после заголовка)`."""
    body = "".join(f"#### Scenario: {name}\n{under}- **WHEN** a\n- **THEN** b\n\n" for name, under in scenarios)
    return spec(f"### Requirement: Один\nТекст SHALL (F-{number:02d}).\n\n{body}")


def test_service_task_with_mark_has_no_dangling_signal(tmp_path):
    """`trace-conventions`: «Прогон с пометкой», «Такая же задача без пометки» — пометка снимает сигнал «задача ни к чему»,
    та же задача без неё его получает."""
    tasks = DONE_SC + f"- [ ] 1.2 Полный прогон ядра {SERVICE}\n- [ ] 1.3 Полный прогон ядра\n"
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1))}, tasks=tasks)
    found = of_kind(lines_of(root), "задача ни к чему")
    assert len(found) == 1 and "1.3" in found[0], found


def test_service_word_in_text_or_not_at_the_end_is_not_a_mark(tmp_path):
    """`trace-conventions`: «Слово в тексте задачи» — слово «служебная» в тексте, без backticks, не в конце строки или в
    образце формы в двойных backticks пометкой не считается."""
    tasks = (DONE_SC + "- [ ] 1.2 Поправить служебная колонка\n" + f"- [ ] 1.3 {SERVICE} и ещё слова\n"
             + "- [ ] 1.4 образец `` `служебная` ``\n" + "- [ ] 1.5 слово служебная\n")
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1))}, tasks=tasks)
    found = of_kind(lines_of(root), "задача ни к чему")
    assert [k for s in found for k in ("1.2", "1.3", "1.4", "1.5") if k in s] == ["1.2", "1.3", "1.4", "1.5"], found


def test_service_tasks_line_names_count_and_numbers(tmp_path):
    """`trace-conventions`: «Отчёт называет служебные задачи» — отдельная строка с числом и номерами; это не сигнал `[!!]`
    и фразу «Сигналов нет.» она не отменяет."""
    tasks = DONE_SC + f"- [ ] 1.2 Настройка дерева {SERVICE}\n- [x] 10.1 Полный прогон {SERVICE}\n"
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1))}, tasks=tasks)
    _, env = with_shim(tmp_path, fork_reply(CLEAN))
    done = report(root, env=env)
    assert done.returncode == 0, done.stderr
    line = [row for row in done.stdout.splitlines() if "лужебн" in row]
    assert line == ["Служебных задач: 2 (1.2, 10.1)."], done.stdout
    assert "Сигналов нет." in done.stdout and "[!!]" not in done.stdout


def test_service_line_stands_next_to_signals_and_is_absent_without_marks(tmp_path):
    """`trace-conventions`: «Отчёт называет служебные задачи» — при сигналах строка тоже есть, без служебных задач её нет."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("Один", 1))}, tasks=DONE_SC + "- [ ] 1.2 ничего\n")
    _, env = with_shim(tmp_path, fork_reply(CLEAN))
    assert "Служебных" not in report(root, env=env).stdout
    (root / "openspec" / "changes" / CHANGE / "tasks.md").write_text(DONE_SC + f"- [ ] 1.2 прогон {SERVICE}\n"
                                                                     "- [ ] 1.3 ничего\n", encoding="utf-8")
    out = report(root, env=env).stdout
    assert "[!!] задача ни к чему: 1.3" in out and "Служебных задач: 1 (1.2)." in out and "1.2 —" not in out


def specify_change(tmp_path, under, *, number=12, outcome="Specify", extra=()):
    """Изменение с записью F-12 и исходом `outcome`; сценарий `Сц` несёт `under` под заголовком."""
    root, base = make_change(tmp_path, specs={"demo": scn_spec(("Сц", under))}, tasks=DONE_SC)
    journal(base, {"id": "F-01"}, decided(f"F-{number:02d}", outcome=probe(outcome)), *extra)
    return root, base


def test_outcome_specify_with_comment_is_silent(tmp_path):
    """`trace-signals`: «Specify с комментарием» — комментарий с номером записи сразу под заголовком сценария: сигнала нет."""
    root, _ = specify_change(tmp_path, "<!-- F-12 -->\n")
    assert of_kind(lines_of(root), "Specify без сценария") == []


def test_outcome_specify_without_comment_is_named(tmp_path):
    """`trace-signals`: «Specify без комментария» — сценария с номером нет: сигнал называет F-12 и место записи."""
    root, _ = specify_change(tmp_path, "")
    found = of_kind(lines_of(root), "Specify без сценария")
    assert len(found) == 1 and "F-12" in found[0] and re.search(r"— decisions\.json:\d+$", found[0]), found


@pytest.mark.parametrize("under", ["<!-- F-123 -->\n", "<!-- F-1 -->\n", "<!-- F-13 -->\n", "- **WHEN** a\n<!-- F-12 -->\n"],
                         ids=["longer-number", "shorter-number", "other", "not-under-heading"])
def test_outcome_specify_comment_must_match_exactly_under_the_heading(tmp_path, under):
    """`trace-signals`: «Specify без комментария» — совпадение номера точное, а комментарий стоит сразу под заголовком."""
    root, _ = specify_change(tmp_path, under)
    assert len(of_kind(lines_of(root), "Specify без сценария")) == 1


def test_outcome_specify_comment_with_blank_line_or_in_code_block(tmp_path):
    """`trace-signals`: «Specify с комментарием» — пустая строка между заголовком и комментарием допустима; комментарий в блоке
    кода комментарием сценария не считается."""
    root, _ = specify_change(tmp_path, "\n<!-- F-12 -->\n")
    assert of_kind(lines_of(root), "Specify без сценария") == []
    root2, _ = specify_change(tmp_path / "b", "```\n<!-- F-12 -->\n```\n")
    assert len(of_kind(lines_of(root2), "Specify без сценария")) == 1


def test_outcome_dismiss_and_defer_are_silent(tmp_path):
    """`trace-signals`: «Dismiss» — запись с исходом Dismiss или Defer без требования и задачи: строки о ней нет."""
    for word in ("Dismiss", "Defer"):
        root, _ = specify_change(tmp_path / word, "", outcome=word)
        assert lines_of(root) == [], word


def test_outcome_backstop_without_task_is_named_and_with_task_is_not(tmp_path):
    """`trace-signals`: «Сигнал о решении следует его исходу» — Backstop без задачи назван, со ссылкой задачи на запись нет."""
    root, base = specify_change(tmp_path, "", outcome="Backstop")
    found = of_kind(lines_of(root), "Backstop без задачи")
    assert len(found) == 1 and "F-12" in found[0], found
    (base / "tasks.md").write_text(DONE_SC + "- [ ] 1.2 защита (F-12)\n", encoding="utf-8")
    assert of_kind(lines_of(root), "Backstop без задачи") == []


def test_outcome_specify_lifted_later_names_the_lifting_record(tmp_path):
    """`trace-signals`: «Исход снят позже» — решённая F-30 с `depends_on: [F-12]`: строка о F-12 несёт «снято F-30?»; фикстура
    снятого Specify (F-69). Несколько записей называются все, неснявшие и нерешённые не называются."""
    lifting = [decided("F-30", depends_on=["F-12"]), decided("F-31", depends_on=["F-12", "F-01"]),
               {"id": "F-32", "depends_on": ["F-12"]}, decided("F-33", depends_on=["F-01"])]
    root, _ = specify_change(tmp_path, "", extra=lifting)
    found = of_kind(lines_of(root), "Specify без сценария")
    assert len(found) == 1 and "снято F-30?" in found[0] and "снято F-31?" in found[0], found
    assert "F-32" not in found[0] and "F-33" not in found[0]
    assert found[0].startswith("[!!] Specify без сценария: F-12 — ")


def test_outcome_record_forgot_to_name_the_lifted_one_gets_no_hint(tmp_path):
    """`brainstorm-interview`: «Запись забыла назвать снятое» — F-30 снимает F-12, но `depends_on` пуст: сигнал о F-12 есть без
    «снято», запись отчёт не отвергает."""
    root, _ = specify_change(tmp_path, "", extra=[decided("F-30")])
    found = of_kind(lines_of(root), "Specify без сценария")
    assert len(found) == 1 and "снято" not in found[0], found


def signal_record(rid, question, decision=True, **extra):
    """Запись `[сигнал]` с исходом пробы Dismiss; `decision=False` — без решения человека."""
    rec = decided(rid, outcome=probe("Dismiss"), question=question, **extra)
    if not decision:
        rec.update({"decision": None, "status": "открыт"})
    return rec


def test_signal_record_with_decision_removes_exactly_its_signal(tmp_path):
    """`trace-signals`: «Человек принял зазор», «Запись отвечает на один сигнал» — запись с решением снимает сигнал своего вида
    и ключа, соседний сигнал того же вида остаётся."""
    root, base = make_change(tmp_path, specs={"demo": spec(req("Один", 1), req("Два", 1))}, tasks="- [ ] 1.1 (F-01)\n")
    journal(base, {"id": "F-01"})
    assert len(of_kind(lines_of(root), "требование без задачи")) == 2
    journal(base, {"id": "F-01"}, signal_record("F-02", "[сигнал] требование без задачи · demo/Один"))
    found = of_kind(lines_of(root), "требование без задачи")
    assert len(found) == 1 and "demo/Два" in found[0], found


def test_signal_record_other_kind_same_key_stays(tmp_path):
    """`trace-signals`: «Запись отвечает на один сигнал» — тот же ключ другого вида не молчит."""
    root, base = make_change(tmp_path, specs={"demo": spec(req("Один"))}, tasks="- [ ] 1.1 (F-01)\n")
    journal(base, {"id": "F-01"}, signal_record("F-02", "[сигнал] требование без задачи · demo/Один"))
    signals = lines_of(root)
    assert of_kind(signals, "требование без задачи") == [] and len(of_kind(signals, "требование без записи")) == 1, signals


def test_signal_record_without_decision_removes_nothing(tmp_path):
    """`trace-signals`: «Запись без решения», «Человек ничего не записал» — запись `[сигнал]` без `decision` сигнал не снимает,
    без записи сигнал назван."""
    root, base = make_change(tmp_path, specs={"demo": spec(req("Один", 1))}, tasks="- [ ] 1.1 (F-01)\n")
    journal(base, {"id": "F-01"})
    assert len(of_kind(lines_of(root), "требование без задачи")) == 1
    journal(base, {"id": "F-01"}, signal_record("F-02", "[сигнал] требование без задачи · demo/Один", decision=False))
    assert len(of_kind(lines_of(root), "требование без задачи")) == 1


def test_signal_record_matches_after_whitespace_squash(tmp_path):
    """`trace-signals`: «Запись отвечает на один сигнал» — сравнение после приведения пробелов; ключ с угловой скобкой в
    записи сравнивается как написан, не как в экранированной строке отчёта."""
    root, base = make_change(tmp_path, specs={"demo": spec(req("Один  два", 1), req("Т<N>", 1))}, tasks="- [ ] 1.1 (F-01)\n")
    journal(base, {"id": "F-01"}, signal_record("F-02", "[сигнал]   требование без задачи  ·  demo/Один   два"),
            signal_record("F-03", "[сигнал] требование без задачи · demo/Т<N>"))
    assert of_kind(lines_of(root), "требование без задачи") == []


def test_signal_record_for_specify_signal_silences_only_that_record(tmp_path):
    """`trace-signals`: «Запись отвечает на один сигнал» — ключ сигнала «Specify без сценария» — номер записи."""
    root, base = specify_change(tmp_path, "", extra=[decided("F-13", outcome=probe("Specify")),
                                                     signal_record("F-40", "[сигнал] Specify без сценария · F-12")])
    found = of_kind(lines_of(root), "Specify без сценария")
    assert len(found) == 1 and "F-13" in found[0], found
