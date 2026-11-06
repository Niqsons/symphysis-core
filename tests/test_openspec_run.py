"""`tools/openspec_run.py`: общий запуск форка OpenSpec — поиск форка, правило имени изменения, телеметрия, предел времени,
снятие дерева процессов. Тесты переехали из `test_step_help.py` вместе с кодом (F-138); форк подменён шимом
`tests/fixtures/fork-shim/`."""
import ast
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

import openspec_run
from conftest import ROOT, fork_calls, fork_env, fork_reply, install_fork_shim

OPENSPEC_RUN = ROOT / "tools" / "openspec_run.py"
STEP_HELP = ROOT / "tools" / "step_help.py"

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="нет node в PATH")


def use_shim(monkeypatch, directory: Path, **replies) -> Path:
    """Шим в `directory` и окружение этого процесса, где `SYMPHYSIS_OPENSPEC` указывает на него: `run_fork` зовётся как функция."""
    shim = install_fork_shim(directory, **replies)
    for key, value in fork_env(directory, SYMPHYSIS_OPENSPEC=str(shim)).items():
        monkeypatch.setenv(key, value)
    return shim


def process_alive(pid: int) -> bool:
    if os.name == "nt":
        listed = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, errors="replace")  # вывод в OEM, не UTF-8
        return str(pid) in listed.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@pytest.mark.parametrize("symbol", ["&", "|", "<", ">", "^", "%", '"'])
@pytest.mark.parametrize("name", ["openspec.cmd", "openspec.bat", "OPENSPEC.CMD"])
def test_every_metacharacter_of_a_shim_path_is_named(symbol, name, monkeypatch):
    """Не все эти символы законны в имени каталога Windows, поэтому проверка на самой функции; файл не трогается и не запускается."""
    monkeypatch.setenv("SYMPHYSIS_OPENSPEC", f"a{symbol}b/{name}")
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    with pytest.raises(openspec_run.ForkError, match=f"«{re.escape(symbol)}»"):
        openspec_run._fork_command()


@requires_node
def test_js_route_runs_node_by_absolute_path(tmp_path, monkeypatch):
    """Маршрут `.js`: `node` берётся из PATH до вызова, а не ищется заново в `cwd` проекта."""
    script = tmp_path / "openspec.js"
    script.write_text("", encoding="utf-8")
    monkeypatch.setenv("SYMPHYSIS_OPENSPEC", str(script))
    command = openspec_run._fork_command()
    assert command[1] == str(script) and os.path.isabs(command[0])
    assert Path(command[0]).samefile(shutil.which("node"))


def test_fork_is_spawned_in_one_place():
    """Единственная функция вызова: второй `Popen` обошёл бы проверку имени, телеметрию и предел. Он не вернулся и в `step_help.py`."""
    def spawns(path: Path) -> list:
        return [node for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Popen"]
    assert len(spawns(OPENSPEC_RUN)) == 1 and spawns(STEP_HELP) == []


def test_refusal_stands_in_the_call_function_itself(tmp_path, monkeypatch):
    """Проверка в самой функции вызова, а не в разборе аргументов: обойти её негде."""
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("форк вызван с опасным именем"))
    with pytest.raises(openspec_run.ForkError, match="не подходит"):
        openspec_run.run_fork(tmp_path, "status", "--json", change="a&md,marker")


@pytest.mark.parametrize("name", ["a&echo.>marker", "a|md,marker", "имя пробел", "a\nb", "%PATH%", "a^b", "..", "../x",
                                  "..\\x", ".hidden", "-x", "--all", "-", ""])
def test_change_name_rule_refuses(name):
    """`trace-signals`: «Имя изменения с символами оболочки» и пути с `../`: правило отдельной функцией, текст отказа прежний."""
    with pytest.raises(openspec_run.ForkError, match="не подходит") as refusal:
        openspec_run.check_change_name(name)
    assert f"«{name}»" in str(refusal.value) and "переименуй" in str(refusal.value)


@pytest.mark.parametrize("name", ["step-help", "Add_Auth", "имя", "v1.2", "9a", "_x", "a-", "trace-graph"])
def test_change_name_rule_passes(name):
    assert openspec_run.check_change_name(name) is None


def test_run_fork_uses_the_same_name_rule(tmp_path, monkeypatch):
    """`trace-signals`: «Запуск форка общий» — имя проверяется тем же правилом, что зовёт скрипт графа до любого вызова."""
    seen = []
    monkeypatch.setattr(openspec_run, "check_change_name", lambda name: seen.append(name))
    use_shim(monkeypatch, tmp_path / "bin")
    reply = openspec_run.run_fork(tmp_path, "status", "--json", change="demo")
    assert seen == ["demo"] and reply.code == 0
    assert fork_calls(tmp_path / "bin")[0]["argv"] == ["status", "--json", "--change", "demo"]


def test_run_fork_without_change_asks_no_name(tmp_path, monkeypatch):
    """Без `change=` правило имени не зовётся: `--version` и `status --all` имени не имеют."""
    monkeypatch.setattr(openspec_run, "check_change_name", lambda name: pytest.fail("имени нет, проверять нечего"))
    use_shim(monkeypatch, tmp_path / "bin")
    assert openspec_run.run_fork(tmp_path, "--version").code == 0


def test_the_file_from_symphysis_openspec_is_run(tmp_path, monkeypatch):
    """`trace-signals`: «Запуск форка общий» — `SYMPHYSIS_OPENSPEC` указывает на файл форка, запускается он, с `cwd` корня."""
    use_shim(monkeypatch, tmp_path / "chosen", version="1.0.0-symphysis.1")
    reply = openspec_run.run_fork(tmp_path, "--version")
    assert reply.code == 0 and reply.out.strip() == "1.0.0-symphysis.1" and reply.label == "openspec --version"
    calls = fork_calls(tmp_path / "chosen")
    assert [call["argv"] for call in calls] == [["--version"]] and Path(calls[0]["cwd"]) == tmp_path


def test_telemetry_of_the_fork_is_off(tmp_path, monkeypatch):
    """`trace-signals`: «Запуск форка общий» (security.md, F-138): в окружении человека телеметрия включена, у процесса форка 0."""
    use_shim(monkeypatch, tmp_path / "bin")
    monkeypatch.setenv("OPENSPEC_TELEMETRY", "1")
    openspec_run.run_fork(tmp_path, "--version")
    calls = fork_calls(tmp_path / "bin")
    assert len(calls) == 1 and calls[0]["env"]["OPENSPEC_TELEMETRY"] == "0"


def test_hung_fork_is_taken_down_with_its_tree(tmp_path, monkeypatch):
    """Сценарий «`openspec` завис»: вызов снят, `ForkError` называет команду и предел, процесс шима не пережил снятие."""
    use_shim(monkeypatch, tmp_path / "bin", status=fork_reply(hang=50))
    monkeypatch.setattr(openspec_run, "FORK_TIMEOUT", 3)
    started = time.monotonic()
    with pytest.raises(openspec_run.ForkError, match=r"openspec status.*3 с"):
        openspec_run.run_fork(tmp_path, "status")
    assert time.monotonic() - started < 20
    hung = [call for call in fork_calls(tmp_path / "bin") if call["argv"][0] == "status"]
    assert len(hung) == 1 and not process_alive(hung[0]["pid"])


def test_no_paths_keeps_the_closing_backtick(tmp_path):
    """Сценарий «Абсолютные пути в выводе форка»: путь в обратных апострофах снимается, закрывающий апостроф остаётся."""
    got = openspec_run.no_paths(r"Рабочее дерево `X:\a`, ветка и `/srv/x/y` тут", tmp_path)
    assert got == "Рабочее дерево `<путь>`, ветка и `<путь>` тут"
