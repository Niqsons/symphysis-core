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
    """`trace-signals`: «Отчёт называет закрытый состав сигналов» — строки идут по месту: сначала tasks.md выше specs не лезет."""
    root, _ = make_change(tmp_path, specs={"demo": spec(req("А"), req("Б"))}, tasks="- [ ] 1.1 `demo`: «Сц»\n- [ ] 1.2 ничего\n")
    places = [s.rsplit(" — ", 1)[1].split(", ")[0] for s in lines_of(root)]
    keys = [(p.rsplit(":", 1)[0], int(p.rsplit(":", 1)[1])) for p in places]
    assert keys == sorted(keys) and len(keys) >= 3
