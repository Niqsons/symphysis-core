"""`tools/step_help.py`: текущий шаг конвейера и чей ход, страницы шагов, вызов форка. Форк подменён шимом
`tests/fixtures/fork-shim/`; сверка с настоящим форком — в конце файла."""
import ast
import datetime as dt
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

import journal_render
import step_help
from conftest import (ALL_STEPS, FORK_VERSION, OPTIONAL_ARTIFACTS, ROOT, SCHEMA_GRAPH, fake_apply, fake_status,
                      fake_status_all, fork_calls, fork_env, fork_record, fork_reply, install_fork_shim, journal_of, real_env,
                      real_fork, real_project, requires_fork, steps_text)

STEP_HELP = ROOT / "tools" / "step_help.py"
BEFORE_SPECS = ("intent", "decisions", "research", "proposal")
PLANNED = (*BEFORE_SPECS, "specs", "consequences", "design", "security", "tasks")

windows_only = pytest.mark.skipif(os.name != "nt", reason="разбор строки через cmd.exe бывает только на Windows")
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="нет node в PATH")


def make_project(path: Path, change="demo", steps=True) -> Path:
    change_dir = path / "openspec" / "changes" / change
    change_dir.mkdir(parents=True)
    if steps:
        schema = path / "openspec" / "schemas" / "symphysis"
        schema.mkdir(parents=True)
        (schema / "steps.md").write_text(steps_text(), encoding="utf-8")
    return path


def write_journal(project: Path, data, change="demo"):
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    (project / "openspec" / "changes" / change / "decisions.json").write_text(text, encoding="utf-8")


def open_fork(record_id="F-01") -> dict:
    return fork_record(record_id, chosen=None, A=[])


def parked_fork(record_id="F-02") -> dict:
    return {**fork_record(record_id, chosen=None, A=[]), "status": "припаркован"}


def run_help(project: Path, *args, env=None, timeout=60):
    """Вызов скрипта без `-X utf8`: UTF-8 на stdout держит он сам. Возвращает код, JSON и сам вызов."""
    done = subprocess.run([sys.executable, str(STEP_HELP), *args], cwd=project, env=env or fork_env(), capture_output=True,
                          timeout=timeout)
    assert b"Traceback" not in done.stderr, done.stderr.decode("utf-8", "replace")
    return done.returncode, json.loads(done.stdout.decode("utf-8")), done


def with_shim(tmp_path, done=(), ready=(), apply=None, files=None, journal=None, args=("--change", "demo"), **replies):
    """Проект `tmp_path/proj` и шим `tmp_path/bin` с ответами по сценарию; возвращает код и JSON."""
    project = make_project(tmp_path / "proj")
    if journal is not None:
        write_journal(project, journal)
    status = fake_status(project, done=done, ready=ready, files=files)
    install_fork_shim(tmp_path / "bin", status=fork_reply(status), apply=fork_reply(apply or fake_apply()), **replies)
    code, data, _ = run_help(project, *args, env=fork_env(tmp_path / "bin"))
    return code, data


def page(data: dict, step: str) -> dict:
    return next(item for item in data["steps"] if item["id"] == step)


def compute_with_limit(project: Path, env: dict, limit: int, change="demo"):
    """`compute` в своём интерпретаторе с пределом `limit` секунд: код выхода показывает и то, как он завершился."""
    script = ("import json, sys, step_help; step_help.FORK_TIMEOUT = int(sys.argv[2]); "
              "sys.stdout.buffer.write(json.dumps(step_help.compute(sys.argv[1], sys.argv[3])).encode('utf-8'))")
    started = time.monotonic()
    done = subprocess.run([sys.executable, "-c", script, str(project), str(limit), change], capture_output=True,
                          env={**env, "PYTHONPATH": str(ROOT / "tools")}, timeout=60)
    return time.monotonic() - started, done


def process_alive(pid: int) -> bool:
    if os.name == "nt":
        listed = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, errors="replace")  # вывод в OEM, не UTF-8
        return str(pid) in listed.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# --- 1.1 шим ----------------------------------------------------------------

def test_shim_answers_as_told_and_records_the_call(tmp_path):
    shim = install_fork_shim(tmp_path / "bin", status=fork_reply({"artifacts": []}, code=3, stderr="сбой"))
    env = fork_env(tmp_path / "bin", MARK="метка")
    version = subprocess.run([shim, "--version"], env=env, capture_output=True, cwd=tmp_path)
    assert version.returncode == 0 and version.stdout.decode().strip() == FORK_VERSION
    status = subprocess.run([shim, "status", "--change", "имя", "--json"], env=env, capture_output=True, cwd=tmp_path)
    assert status.returncode == 3 and json.loads(status.stdout) == {"artifacts": []}
    assert status.stderr.decode("utf-8") == "сбой"
    calls = fork_calls(tmp_path / "bin")
    assert [call["argv"] for call in calls] == [["--version"], ["status", "--change", "имя", "--json"]]
    assert calls[1]["env"]["MARK"] == "метка" and Path(calls[1]["cwd"]) == tmp_path


def test_shim_hangs_when_told(tmp_path):
    shim = install_fork_shim(tmp_path / "bin", status=fork_reply(hang=1))
    started = time.monotonic()
    subprocess.run([shim, "status"], env=fork_env(tmp_path / "bin"), capture_output=True, cwd=tmp_path)
    assert time.monotonic() - started >= 1


@windows_only
def test_shim_really_passes_the_line_through_cmd(tmp_path):
    """Контроль тестов об имени: список аргументов без оболочки через `.cmd` исполняет метасимвол, поэтому маркер
    в них что-то значит (`probes/cmd-shim-injection.txt`)."""
    shim = install_fork_shim(tmp_path / "bin")
    subprocess.run([shim, "status", "--change", "a&md,marker", "--json"], env=fork_env(tmp_path / "bin"),
                   capture_output=True, cwd=tmp_path)
    assert (tmp_path / "marker").is_dir()


# --- 1.2 вызов форка --------------------------------------------------------

def test_no_fork(tmp_path):
    """Сценарий «Форка нет»."""
    project = make_project(tmp_path / "proj")
    code, data, _ = run_help(project)
    assert code == 1
    assert "openspec не найден" in data["error"] and "SYMPHYSIS_OPENSPEC" in data["error"]
    assert data["change"] is None and data["current_step"] is None and data["versions"]["openspec"] is None


def test_no_fork_at_the_given_path(tmp_path):
    project = make_project(tmp_path / "proj")
    env = fork_env(SYMPHYSIS_OPENSPEC=str(tmp_path / "probe-machine-name" / "openspec"))
    code, data, done = run_help(project, env=env)
    assert code == 1 and "openspec не найден" in data["error"] and "SYMPHYSIS_OPENSPEC" in data["error"]
    assert b"probe-machine-name" not in done.stdout


def test_not_the_fork_on_path(tmp_path):
    """Сценарий «В `PATH` не форк»."""
    project = make_project(tmp_path / "proj")
    install_fork_shim(tmp_path / "bin", version="1.13.1")
    code, data, _ = run_help(project, env=fork_env(tmp_path / "bin"))
    assert code == 1 and "1.13.1" in data["error"] and "форк" in data["error"]
    assert data["versions"]["openspec"] == "1.13.1"
    assert [call["argv"] for call in fork_calls(tmp_path / "bin")] == [["--version"]]


def test_given_path_beats_path(tmp_path):
    """Сценарий «Заданный путь важнее `PATH`»."""
    project = make_project(tmp_path / "proj")
    install_fork_shim(tmp_path / "other", version="9.9.9-symphysis.9", status_all=fork_reply(fake_status_all()))
    chosen = install_fork_shim(tmp_path / "chosen", version="1.0.0-symphysis.1", status_all=fork_reply(fake_status_all()))
    code, data, _ = run_help(project, env=fork_env(tmp_path / "other", SYMPHYSIS_OPENSPEC=str(chosen)))
    assert code == 0 and data["versions"]["openspec"] == "1.0.0-symphysis.1"
    assert fork_calls(tmp_path / "other") == [] and fork_calls(tmp_path / "chosen")


def test_shim_on_path_is_found(tmp_path):
    """Сценарий «Шим на Windows»: в `PATH` только `openspec.cmd`, на остальных системах — исполняемый `openspec`."""
    project = make_project(tmp_path / "proj")
    install_fork_shim(tmp_path / "bin", status_all=fork_reply(fake_status_all()))
    code, data, _ = run_help(project, env=fork_env(tmp_path / "bin"))
    assert code == 0 and data["error"] is None and data["versions"]["openspec"] == FORK_VERSION


def test_js_without_node_is_a_plain_failure(tmp_path):
    """F-56: `.js` идёт через `node`; его нет — сбой называется как любой незапустившийся вызов, своего текста нет."""
    project = make_project(tmp_path / "proj")
    script = tmp_path / "openspec.js"
    script.write_text("", encoding="utf-8")
    code, data, _ = run_help(project, env=fork_env(SYMPHYSIS_OPENSPEC=str(script), PATH=str(tmp_path)))
    assert code == 1 and "openspec --version" in data["error"] and "не запустился" in data["error"]


@requires_node
def test_js_goes_through_node(tmp_path):
    project = make_project(tmp_path / "proj")
    script = tmp_path / "openspec.js"
    script.write_text('console.log(process.argv[2] === "--version" ? "1.0.0-symphysis.1" : \'{"changes": []}\');\n',
                      encoding="utf-8")
    env = {**os.environ, "SYMPHYSIS_OPENSPEC": str(script)}
    code, data, _ = run_help(project, env=env)
    assert code == 0 and data["versions"]["openspec"] == "1.0.0-symphysis.1"


@windows_only
@pytest.mark.parametrize("folder, symbol", [("a&md,marker2", "&"), ("a^b", "^"), ("a%b", "%")])
@pytest.mark.parametrize("found_by", ["SYMPHYSIS_OPENSPEC", "PATH"])
def test_shim_path_with_a_cmd_metacharacter_is_refused(tmp_path, folder, symbol, found_by):
    """Слово человека: `cmd.exe` разбирает и путь к `.cmd`, проба показала, что хвост после `&` исполняется с `cwd` проекта.
    Код 1, маркера нет, шим не вызван; символ назван, каталог нет (F-51)."""
    project = make_project(tmp_path / "proj")
    shim = install_fork_shim(tmp_path / folder)
    env = fork_env(SYMPHYSIS_OPENSPEC=str(shim)) if found_by == "SYMPHYSIS_OPENSPEC" else fork_env(tmp_path / folder)
    code, data, done = run_help(project, env=env)
    assert code == 1 and f"«{symbol}»" in data["error"] and "cmd.exe" in data["error"]
    assert "Перенеси" in data["error"], "причина и что делать"
    assert folder not in done.stdout.decode("utf-8")
    assert not (project / "marker2").exists() and not (project / "--version").exists()
    assert fork_calls(tmp_path / folder) == []


@pytest.mark.parametrize("symbol", ["&", "|", "<", ">", "^", "%", '"'])
@pytest.mark.parametrize("name", ["openspec.cmd", "openspec.bat", "OPENSPEC.CMD"])
def test_every_metacharacter_of_a_shim_path_is_named(symbol, name, monkeypatch):
    """Не все эти символы законны в имени каталога Windows, поэтому проверка на самой функции; файл не трогается и не запускается."""
    monkeypatch.setenv("SYMPHYSIS_OPENSPEC", f"a{symbol}b/{name}")
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    with pytest.raises(step_help.ForkError, match=f"«{re.escape(symbol)}»"):
        step_help._fork_command()


@windows_only
@pytest.mark.parametrize("folder", ["Program Files (x86)", "a(b)", "с пробелом"])
@pytest.mark.parametrize("found_by", ["SYMPHYSIS_OPENSPEC", "PATH"])
def test_brackets_and_spaces_in_a_shim_path_work(tmp_path, folder, found_by):
    """Скобки и пробелы законны: `Program Files (x86)` — обычное место для `openspec.cmd`."""
    project = make_project(tmp_path / "proj")
    shim = install_fork_shim(tmp_path / folder, status_all=fork_reply(fake_status_all()))
    env = fork_env(SYMPHYSIS_OPENSPEC=str(shim)) if found_by == "SYMPHYSIS_OPENSPEC" else fork_env(tmp_path / folder)
    code, data, _ = run_help(project, env=env)
    assert code == 0 and data["error"] is None and data["versions"]["openspec"] == FORK_VERSION
    assert fork_calls(tmp_path / folder)


@requires_node
def test_metacharacter_is_no_refusal_beyond_cmd_and_bat(tmp_path):
    """`.js` идёт через `node`, без `cmd.exe`: тот же символ в пути отказа не даёт, и хвост пути не исполняется."""
    project = make_project(tmp_path / "proj")
    folder = tmp_path / "a&md,marker2"
    folder.mkdir()
    script = folder / "openspec.js"
    script.write_text('console.log(process.argv[2] === "--version" ? "1.0.0-symphysis.1" : \'{"changes": []}\');\n',
                      encoding="utf-8")
    code, data, _ = run_help(project, env={**os.environ, "SYMPHYSIS_OPENSPEC": str(script)})
    assert code == 0 and data["versions"]["openspec"] == "1.0.0-symphysis.1"
    assert not (project / "marker2").exists()


def test_hung_fork_is_taken_down_with_its_tree(tmp_path):
    """Сценарий «`openspec` завис»: вызов снят, `error` называет команду и предел, дочерний процесс шима не пережил снятие."""
    project = make_project(tmp_path / "proj")
    install_fork_shim(tmp_path / "bin", status=fork_reply(hang=50))
    elapsed, done = compute_with_limit(project, fork_env(tmp_path / "bin"), limit=3)
    assert done.returncode == 0, done.stderr
    assert elapsed < 20
    error = json.loads(done.stdout)["error"]
    assert "openspec status" in error and "3 с" in error
    hung = [call for call in fork_calls(tmp_path / "bin") if call["argv"][0] == "status"]
    assert len(hung) == 1 and not process_alive(hung[0]["pid"])


def install_node_script_shim(directory: Path, line: str) -> Path:
    """Шим, где `line` — вызов node: `{node}` подставляется абсолютным путём, `PATH` у вызова урезан."""
    directory.mkdir(parents=True)
    node = shutil.which("node")
    if os.name == "nt":
        shim = directory / "openspec.cmd"
        shim.write_text(f"@{line.format(node=node)}\r\n", encoding="utf-8")
    else:
        shim = directory / "openspec"
        shim.write_text(f"#!/bin/sh\n{line.format(node=node)}\n", encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    return shim


@requires_node
def test_hung_node_under_shim_returns_before_plugin_limit(tmp_path):
    """Тест-страховка F-66: node под шимом держит канал вывода 40 с; плагин ждёт Python 30 с, предел скрипта 15 с.
    Простой `subprocess.run(timeout=15)` здесь вернётся только с node, на 40-й секунде."""
    project = make_project(tmp_path / "proj")
    install_node_script_shim(tmp_path / "bin", '"{node}" -e "setTimeout(()=>{{}},40000)"')
    started = time.monotonic()
    code, data, _ = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert time.monotonic() - started < 30
    assert code == 1 and "openspec --version" in data["error"] and "15 с" in data["error"]


@requires_node
def test_descendant_holding_the_pipe_does_not_delay_return(tmp_path):
    """Шим вышел, а потомок жив и держит канал вывода: снимать по номеру уже некого, возврат всё равно ограничен,
    и интерпретатор завершается штатно с оставленным чтением канала."""
    project = make_project(tmp_path / "proj")
    start = 'start "" /b "{node}"' if os.name == "nt" else '"{node}"'
    tail = "" if os.name == "nt" else " &"
    install_node_script_shim(tmp_path / "bin", start + ' -e "setTimeout(()=>{{}},15000)"' + tail)
    elapsed, done = compute_with_limit(project, fork_env(tmp_path / "bin"), limit=1)
    assert elapsed < 12
    assert done.returncode == 0 and b"Fatal" not in done.stderr, done.stderr
    error = json.loads(done.stdout)["error"]
    assert "openspec --version" in error and "1 с" in error


def test_telemetry_is_off_in_every_call(tmp_path):
    """Сценарий «Телеметрия форка подавлена»: включена в окружении, у каждого вызова 0."""
    project = make_project(tmp_path / "proj")
    write_journal(project, journal_of())
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))),
                      apply=fork_reply(fake_apply()), status_all=fork_reply(fake_status_all("demo")))
    code, _, _ = run_help(project, env=fork_env(tmp_path / "bin", OPENSPEC_TELEMETRY="1"))
    assert code == 0
    calls = fork_calls(tmp_path / "bin")
    assert len(calls) == 4, "--version, status --all, status, instructions apply"
    assert {call["env"]["OPENSPEC_TELEMETRY"] for call in calls} == {"0"}


def test_cyrillic_and_space_in_paths(tmp_path):
    """Тест-страховка F-44: проект с кириллицей и пробелом, путь к форку тоже; JSON как ожидается, байты UTF-8."""
    project = make_project(tmp_path / "Мой проект", change="имя")
    (project / "openspec" / "changes" / "имя" / "intent.md").write_text("намерение\n", encoding="utf-8")
    status = fake_status(project, change="имя", done=("intent",), ready=("decisions",))
    shim = install_fork_shim(tmp_path / "форк с пробелом", status=fork_reply(status), apply=fork_reply(fake_apply()))
    env = fork_env(SYMPHYSIS_OPENSPEC=str(shim), PYTHONIOENCODING="cp866")
    code, data, done = run_help(project, "--change", "имя", env=env)
    assert code == 0 and data["error"] is None
    assert data["change"] == "имя" and data["current_step"] == "decisions"
    assert page(data, "intent")["files"] == [{"path": "openspec/changes/имя/intent.md", "exists": True}]
    assert page(data, "intent")["texts"]["why"] == "why intent"
    assert "Мой проект".encode("utf-8") not in done.stdout and "форк с пробелом".encode("utf-8") not in done.stdout
    assert Path(fork_calls(tmp_path / "форк с пробелом")[0]["cwd"]) == project


@windows_only
def test_oem_message_of_cmd_is_readable(tmp_path):
    """Тест-страховка F-44: сообщение самого `cmd.exe` идёт в кодировке OEM, в `error` оно читается словами."""
    try:
        "сбой запуска".encode("oem")
    except UnicodeEncodeError:
        pytest.skip("в кодировке OEM этой машины нет кириллицы")
    project = make_project(tmp_path / "proj")
    install_fork_shim(tmp_path / "bin", status=fork_reply(code=1, stderr="сбой запуска\n", stderr_encoding="oem"))
    code, data, _ = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert code == 1 and "сбой запуска" in data["error"]


@pytest.mark.parametrize("reply", [fork_reply("это не JSON"), fork_reply(""), fork_reply("{обрыв"),
                                   fork_reply({"changeName": "demo"}), fork_reply({"artifacts": 5}),
                                   fork_reply(code=7, stderr="упал\n")],
                         ids=["мусор", "пусто", "обрыв", "без артефактов", "артефакты не список", "код возврата"])
def test_strange_answer_is_named_not_raised(tmp_path, reply):
    project = make_project(tmp_path / "proj")
    install_fork_shim(tmp_path / "bin", status=reply, apply=fork_reply(fake_apply()))
    code, data, _ = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert code == 1 and data["error"] and data["change"] is None and data["current_step"] is None
    assert page(data, "intent")["texts"]["why"] == "why intent"


def test_failed_apply_call_is_a_failure(tmp_path):
    project = make_project(tmp_path / "proj")
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))),
                      apply=fork_reply({"status": [{"message": "сбой задач"}]}, code=1))
    code, data, _ = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert code == 1 and "openspec instructions apply" in data["error"] and "сбой задач" in data["error"]


def test_fork_is_spawned_in_one_place():
    """Единственная функция вызова: второй `Popen` обошёл бы проверку имени, телеметрию и предел."""
    tree = ast.parse(STEP_HELP.read_text(encoding="utf-8"))
    spawns = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr == "Popen"]
    assert len(spawns) == 1


# --- 1.3 имя изменения ------------------------------------------------------

@pytest.mark.parametrize("name", ["a&echo.>marker", "a&md,marker", "a|md,marker", 'a"&md,marker', "имя пробел",
                                  "a\nb", "%PATH%", "a^b"])
def test_dangerous_name_from_argument_is_refused(tmp_path, name):
    """`.cmd` разбирает строку через `cmd.exe`: имя не доходит до шима и до файловой системы."""
    project = make_project(tmp_path / "proj")
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project)), apply=fork_reply(fake_apply()))
    code, data, _ = run_help(project, "--change", name, env=fork_env(tmp_path / "bin"))
    assert code == 1 and "не подходит" in data["error"]
    assert not list(project.glob("marker*"))
    assert [call["argv"] for call in fork_calls(tmp_path / "bin")] == [["--version"]]


def test_dangerous_name_from_the_fork_is_refused(tmp_path):
    """Каталог `a&md,marker` в чужом репозитории: имя приходит из ответа форка, скрипт сам передаёт его дальше."""
    project = make_project(tmp_path / "proj", change="a&md,marker")
    install_fork_shim(tmp_path / "bin", status_all=fork_reply(fake_status_all("a&md,marker")),
                      status=fork_reply(fake_status(project)), apply=fork_reply(fake_apply()))
    code, data, _ = run_help(project, env=fork_env(tmp_path / "bin"))
    assert code == 1 and "не подходит" in data["error"] and "a&md,marker" in data["error"]
    assert not (project / "marker").exists()
    assert [call["argv"] for call in fork_calls(tmp_path / "bin")] == [["--version"], ["status", "--all", "--json"]]


def test_refusal_stands_in_the_call_function_itself(tmp_path, monkeypatch):
    """Проверка в самой функции вызова, а не в разборе аргументов: обойти её негде."""
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("форк вызван с опасным именем"))
    with pytest.raises(step_help.ForkError, match="не подходит"):
        step_help.run_fork(tmp_path, "status", "--json", change="a&md,marker")


@pytest.mark.parametrize("name, decoy", [("..", "openspec/decisions.json"), ("..\\x", "openspec/x/decisions.json"),
                                         ("../x", "openspec/x/decisions.json"), (".hidden", None)])
def test_path_out_of_changes_is_refused(tmp_path, name, decoy):
    """Пути с `../`: журнал вне `openspec/changes/` не читается, форк с этим именем не зовётся."""
    project = make_project(tmp_path / "proj")
    if decoy:
        (project / decoy).parent.mkdir(parents=True, exist_ok=True)
        (project / decoy).write_text(json.dumps(journal_of(open_fork())), encoding="utf-8")
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))),
                      apply=fork_reply(fake_apply()))
    code, data, _ = run_help(project, "--change", name, env=fork_env(tmp_path / "bin"))
    assert code == 1 and "не подходит" in data["error"]
    assert data["forks"] is None and data["current_step"] is None
    assert [call["argv"] for call in fork_calls(tmp_path / "bin")] == [["--version"]]


@pytest.mark.parametrize("name", ["-x", "--all", "-"])
def test_leading_dash_is_refused(tmp_path, name):
    """Имя с начальным дефисом форк принял бы за ключ: шим с таким именем не вызван."""
    project = make_project(tmp_path / "proj", change=name)
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, change=name, ready=("intent",))),
                      apply=fork_reply(fake_apply()))
    code, data, _ = run_help(project, f"--change={name}", env=fork_env(tmp_path / "bin"))
    assert code == 1 and "не подходит" in data["error"]
    assert [call["argv"] for call in fork_calls(tmp_path / "bin")] == [["--version"]]


def test_leading_dash_from_the_fork_is_refused(tmp_path):
    """То же имя из ответа форка: каталог `-x` единственный активный, дальше имя не идёт."""
    project = make_project(tmp_path / "proj", change="-x")
    install_fork_shim(tmp_path / "bin", status_all=fork_reply(fake_status_all("-x")),
                      status=fork_reply(fake_status(project, change="-x", ready=("intent",))),
                      apply=fork_reply(fake_apply()))
    code, data, _ = run_help(project, env=fork_env(tmp_path / "bin"))
    assert code == 1 and "не подходит" in data["error"]
    assert [call["argv"] for call in fork_calls(tmp_path / "bin")] == [["--version"], ["status", "--all", "--json"]]


@pytest.mark.parametrize("name", ["step-help", "Add_Auth", "имя", "v1.2", "9a", "_x", "a-"])
def test_ordinary_names_pass(tmp_path, name):
    project = make_project(tmp_path / "proj", change=name)
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, change=name, ready=("intent",))),
                      apply=fork_reply(fake_apply()))
    code, data, _ = run_help(project, f"--change={name}", env=fork_env(tmp_path / "bin"))
    assert code == 0, data["error"]
    assert data["change"] == name
    assert ["status", "--json", "--change", name] in [call["argv"] for call in fork_calls(tmp_path / "bin")]


# --- 1.4 текущий шаг и чей ход ----------------------------------------------

def test_open_fork_with_next_step_ready(tmp_path):
    """Сценарий «Открытая развилка при готовом следующем шаге»."""
    code, data = with_shim(tmp_path, done=("intent", "decisions"), ready=("research",),
                           journal=journal_of(open_fork(), fork_record("F-03", "A", A=[])))
    assert code == 0
    assert data["current_step"] == "viewer" and data["turn"] == "human"
    assert data["forks"] == {"open": 1, "parked": 0} and data["next_by_status"] == "research"
    assert "1" in data["current_text"] and "research" in data["current_text"]


def test_parked_fork(tmp_path):
    """Сценарий «Припаркованная развилка»."""
    _, data = with_shim(tmp_path, done=("intent", "decisions"), ready=("research",), journal=journal_of(parked_fork()))
    assert data["forks"] == {"open": 0, "parked": 1}
    assert data["current_step"] == "research" and data["turn"] == "model"


def test_open_fact_is_not_an_open_fork(tmp_path):
    fact = {**fork_record("F-04", chosen=None, A=[]), "kind": "факт", "options": []}
    _, data = with_shim(tmp_path, done=("intent", "decisions"), ready=("research",), journal=journal_of(fact))
    assert data["forks"]["open"] == 0 and data["current_step"] == "research"


@pytest.mark.parametrize("text", ["{}", "{обрыв", "[]", '{"records": "x"}', '{"records": [1]}', '{"records": [{}]}', ""],
                         ids=["пустой объект", "синтаксис", "список", "записи строкой", "запись числом", "запись без полей",
                              "пустой файл"])
def test_unreadable_journal_does_not_read_as_zero(tmp_path, text):
    """Сценарий «Журнал не читается»."""
    code, data = with_shim(tmp_path, done=("intent", "decisions"), ready=("research",), journal=text)
    assert code == 0 and data["error"] is None
    assert data["current_step"] == "research" and data["turn"] == "model"
    assert data["forks"]["open"] == "журнал не читается"
    assert "журнал не читается" in data["current_text"].lower()
    assert page(data, "viewer")["state"] == "unknown"


def test_empty_journal_template_is_readable(tmp_path):
    _, data = with_shim(tmp_path, done=("intent", "decisions"), ready=("research",),
                        journal={"title": "", "source": "decisions.json", "intro": "", "records": []})
    assert data["forks"] == {"open": 0, "parked": 0}


def test_several_ready_after_specs(tmp_path):
    """Сценарий «Несколько готовых шагов после `specs`»: необязательная атака без файла не выбирается."""
    _, data = with_shim(tmp_path, done=(*BEFORE_SPECS, "specs"), ready=("attack-decisions", "consequences", "security"))
    assert data["current_step"] == "consequences" and data["turn"] == "model"
    assert data["next_by_status"] == "consequences"


def test_invoked_attack_is_picked(tmp_path):
    """Сценарий «Вызванная атака»."""
    _, data = with_shim(tmp_path, done=PLANNED, ready=("attack-artifacts",),
                        files={"attack-artifacts": ["attack/artifacts.md"]})
    assert data["current_step"] == "attack-artifacts" and data["turn"] == "model"


def test_tasks_in_progress(tmp_path):
    """Сценарий «Задачи идут»: невызванная атака готова к работе, но шагом не становится."""
    code, data = with_shim(tmp_path, done=PLANNED, ready=("attack-artifacts",),
                           apply=fake_apply("ready", total=5, complete=2))
    assert code == 0
    assert data["current_step"] == "apply" and data["turn"] == "model"
    assert data["tasks"] == {"state": "ready", "total": 5, "complete": 2, "remaining": 3}
    assert "2 из 5" in data["current_text"]
    assert page(data, "apply")["state"] == "ready"
    assert page(data, "sync")["state"] == "waiting"


def test_tasks_closed(tmp_path):
    """Сценарий «Задачи закрыты»."""
    _, data = with_shim(tmp_path, done=PLANNED, apply=fake_apply("all_done", total=5, complete=5))
    assert data["current_step"] == "sync" and page(data, "sync")["next"] == "archive"
    assert "скрипт не видит" in data["current_text"]
    assert page(data, "sync")["state"] == "ready"


def test_apply_blocked(tmp_path):
    """Сценарий «Реализация заблокирована»."""
    _, data = with_shim(tmp_path, done=(*BEFORE_SPECS, "specs", "consequences", "design", "tasks"),
                        apply=fake_apply("blocked", missing=["security"]))
    assert data["current_step"] == "apply"
    assert page(data, "apply")["waits_for"] == ["security"] and page(data, "apply")["state"] == "blocked"
    assert "security" in data["current_text"]


def test_no_active_changes(tmp_path):
    """Сценарий «Активных изменений нет»."""
    project = make_project(tmp_path / "proj")
    install_fork_shim(tmp_path / "bin", status_all=fork_reply(fake_status_all()))
    code, data, _ = run_help(project, env=fork_env(tmp_path / "bin"))
    assert code == 0 and data["error"] is None
    assert data["change"] is None and data["changes"] == []
    assert data["current_step"] == "intent" and data["turn"] == "human"
    assert data["forks"] is None and data["tasks"] is None
    assert page(data, "intent")["texts"]["how_to_prepare"] == "где искать материалы"
    assert page(data, "intent")["state"] is None


def test_just_created_change(tmp_path):
    """Сценарий «Изменение только что создано»."""
    code, data = with_shim(tmp_path, ready=("intent",))
    assert code == 0 and data["current_step"] == "intent" and data["turn"] == "human"
    assert data["forks"] == {"open": 0, "parked": 0}


def test_first_steps_skipped(tmp_path):
    """Сценарий «Первые шаги пропущены»."""
    _, data = with_shim(tmp_path, done=("proposal",), ready=("intent", "specs"))
    assert data["current_step"] == "intent" and data["turn"] == "human"
    assert page(data, "specs")["state"] == "ready"


def test_no_journal_yet(tmp_path):
    """Сценарий «Журнала ещё нет»."""
    code, data = with_shim(tmp_path, done=("intent",), ready=("decisions",))
    assert code == 0 and data["current_step"] == "decisions" and data["turn"] == "model"
    assert data["forks"] == {"open": 0, "parked": 0}
    assert page(data, "viewer")["state"] == "idle"


def test_one_active_change(tmp_path):
    """Сценарий «Одно активное изменение»."""
    _, data = with_shim(tmp_path, ready=("intent",), args=(), status_all=fork_reply(fake_status_all("demo")))
    assert data["change"] == "demo" and data["changes"] == ["demo"]
    argv = [call["argv"] for call in fork_calls(tmp_path / "bin")]
    assert ["status", "--json", "--change", "demo"] in argv
    assert ["instructions", "apply", "--json", "--change", "demo"] in argv


def test_two_active_changes(tmp_path):
    """Сценарий «Два активных изменения»."""
    _, data = with_shim(tmp_path, args=(), status_all=fork_reply(fake_status_all("demo", "other")))
    assert data["error"] is None
    assert data["change"] is None and data["current_step"] is None and data["turn"] is None
    assert data["changes"] == ["demo", "other"]
    assert [call["argv"] for call in fork_calls(tmp_path / "bin")] == [["--version"], ["status", "--all", "--json"]]


def test_broken_change_does_not_hide_the_others(tmp_path):
    """`status --all` при битом изменении даёт код 1, но имена называет все: список годен, сбой не шире этого изменения."""
    entries = {"changes": [{"changeName": "demo", "status": [{"message": "битый"}]},
                           {"changeName": "other", "artifacts": []}]}
    code, data = with_shim(tmp_path, args=(), status_all=fork_reply(entries, code=1))
    assert code == 0 and data["error"] is None and data["changes"] == ["demo", "other"]


def test_failed_listing_is_a_failure(tmp_path):
    failure = {"changes": [], "root": None, "status": [{"message": "No OpenSpec root found"}]}
    code, data = with_shim(tmp_path, args=(), status_all=fork_reply(failure, code=1))
    assert code == 1 and "openspec status --all" in data["error"] and "No OpenSpec root" in data["error"]


def test_no_such_change(tmp_path):
    """Сценарий «Изменения с таким именем нет»."""
    project = make_project(tmp_path / "proj")
    missing = {"status": [{"severity": "error", "code": "change_error",
                           "message": "Change 'other' not found. Available changes:\n  demo"}]}
    install_fork_shim(tmp_path / "bin", status=fork_reply(missing, code=1))
    code, data, _ = run_help(project, "--change", "other", env=fork_env(tmp_path / "bin"))
    assert code == 1 and "other" in data["error"]
    assert "\n" not in data["error"], "причина сбоя одной строкой"
    assert data["change"] is None


# --- 1.5 страница шага ------------------------------------------------------

def test_step_others_depend_on(tmp_path):
    """Сценарий «Шаг, от которого зависит другой»."""
    _, data = with_shim(tmp_path, done=(*BEFORE_SPECS, "specs", "consequences"), ready=("design",))
    design = page(data, "design")
    assert "tasks" in design["blocks"] and design["optional"] is False
    assert design["state"] == "ready"


def test_step_that_stops_apply(tmp_path):
    """Сценарий «Шаг останавливает реализацию»."""
    _, data = with_shim(tmp_path, done=(*BEFORE_SPECS, "specs"), ready=("security",))
    assert page(data, "security")["stops_apply"] is True
    assert page(data, "design")["stops_apply"] is False


def test_optional_step_not_invoked(tmp_path):
    """Сценарий «Необязательный шаг»: `proposal` требует атаку в графе, но невызванная не держит ничего."""
    _, data = with_shim(tmp_path, done=("intent", "decisions", "research"), ready=("attack-decisions", "proposal"))
    attack = page(data, "attack-decisions")
    assert attack["optional"] is True and attack["blocks"] == [] and attack["stops_apply"] is False
    assert page(data, "attack-artifacts")["stops_apply"] is False


def test_optional_step_invoked_holds_what_requires_it(tmp_path):
    _, data = with_shim(tmp_path, done=("intent", "decisions", "research"), ready=("attack-decisions",),
                        files={"attack-decisions": ["attack/decisions.md"]})
    assert page(data, "attack-decisions")["blocks"] == ["proposal"]


def test_files_exist_and_not_yet(tmp_path):
    """Сценарий «Файлов шага ещё нет и уже есть»."""
    _, data = with_shim(tmp_path, done=(*BEFORE_SPECS, "specs"), ready=("consequences", "security"),
                        files={"specs": ["specs/a/spec.md"]})
    assert page(data, "specs")["files"] == [{"path": "openspec/changes/demo/specs/a/spec.md", "exists": True}]
    assert page(data, "design")["files"] == [{"path": "openspec/changes/demo/design.md", "exists": False}]


def test_ends_of_the_list(tmp_path):
    """Сценарий «Концы списка»; `viewer` сразу после `decisions`."""
    _, data = with_shim(tmp_path, ready=("intent",))
    assert [item["id"] for item in data["steps"]] == ALL_STEPS
    assert data["steps"][0]["prev"] is None and data["steps"][-1]["next"] is None and data["steps"][-1]["id"] == "archive"
    assert page(data, "sync")["prev"] == "apply" and page(data, "viewer")["prev"] == "decisions"
    for left, right in zip(data["steps"], data["steps"][1:]):
        assert left["next"] == right["id"] and right["prev"] == left["id"]


def test_turn_of_each_step(tmp_path):
    _, data = with_shim(tmp_path, ready=("intent",))
    assert {item["id"] for item in data["steps"] if item["turn"] == "human"} == {"intent", "viewer"}


def test_no_steps_file(tmp_path):
    """Сценарий «Старая схема в проекте»: `steps.md` нет."""
    project = make_project(tmp_path / "proj", steps=False)
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))),
                      apply=fork_reply(fake_apply()))
    code, data, _ = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert code == 0 and data["current_step"] == "intent"
    design = page(data, "design")
    assert design["blocks"] == ["tasks", "attack-artifacts"] and design["files"]
    assert design["text_note"] == "текста нет" and design["texts"]["why"] == "" and design["texts"]["title"] == ""


def test_steps_file_without_the_section(tmp_path):
    """Сценарий «Старая схема в проекте»: раздела шага нет, у остальных текст на месте."""
    project = make_project(tmp_path / "proj")
    steps = project / "openspec" / "schemas" / "symphysis" / "steps.md"
    steps.write_text(steps_text([step for step in ALL_STEPS if step != "design"]), encoding="utf-8")
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))),
                      apply=fork_reply(fake_apply()))
    code, data, _ = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert code == 0
    assert page(data, "design")["text_note"] == "текста нет" and page(data, "design")["blocks"]
    assert page(data, "specs")["text_note"] is None and page(data, "specs")["texts"]["mechanics"] == "mechanics specs"


def test_text_in_output_when_fork_fails(tmp_path):
    """Сценарий «Текст в выводе при сбое»."""
    project = make_project(tmp_path / "proj")
    code, data, _ = run_help(project)
    assert code == 1 and "openspec не найден" in data["error"]
    assert page(data, "intent")["texts"]["how_to_prepare"] == "где искать материалы"
    assert page(data, "intent")["state"] is None


def test_no_section_of_intent_when_fork_fails(tmp_path):
    """Без `steps.md` и без форка страница `intent` всё равно есть и говорит, что текста нет."""
    project = make_project(tmp_path / "proj", steps=False)
    code, data, _ = run_help(project)
    assert code == 1
    assert [item["id"] for item in data["steps"]] == ["intent"]
    assert data["steps"][0]["text_note"] == "текста нет"


@pytest.mark.parametrize("states", [dict(ready=("intent",)), dict(done=("intent",), ready=("decisions",)),
                                    dict(done=PLANNED, apply=fake_apply("ready", total=2, complete=1)),
                                    dict(done=PLANNED, apply=fake_apply("all_done", total=2, complete=2))],
                         ids=["intent", "decisions", "apply", "sync"])
def test_wording_of_the_current_step(tmp_path, states):
    """Сценарий «Формулировка текущего шага»: текст называет следующий по файлам шаг, а не идущую работу."""
    _, data = with_shim(tmp_path, **states)
    assert "выполняется" not in data["current_text"]
    assert "по файлам" in data["current_text"] and data["current_step"] in data["current_text"]


def test_done_step_says_content_was_not_checked(tmp_path):
    _, data = with_shim(tmp_path, done=("intent",), ready=("decisions",))
    assert page(data, "intent")["file_note"] == "файл есть, содержание не проверялось"
    assert page(data, "decisions")["file_note"] is None and page(data, "viewer")["file_note"] is None


def test_command_gets_the_change_name(tmp_path):
    project = make_project(tmp_path / "proj")
    steps = project / "openspec" / "schemas" / "symphysis" / "steps.md"
    steps.write_text("## intent\n\nНамерение\n\n### Команда\n\n`/opsx:continue <имя>`\n", encoding="utf-8")
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))),
                      apply=fork_reply(fake_apply()))
    _, data, _ = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert page(data, "intent")["texts"]["command"] == "`/opsx:continue demo`"


def test_no_project_directory_in_output(tmp_path):
    """Требование «Снимок справки не несёт абсолютных путей»: пути от корня, каталога проекта в выводе нет."""
    project = make_project(tmp_path / "probe-machine-name")
    status = fake_status(project, done=("intent",), ready=("decisions",))
    install_fork_shim(tmp_path / "bin", status=fork_reply(status), apply=fork_reply(fake_apply()))
    code, data, done = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert code == 0 and b"probe-machine-name" not in done.stdout
    assert page(data, "intent")["files"] == [{"path": "openspec/changes/demo/intent.md", "exists": True}]


@pytest.mark.parametrize("reply", [
    lambda project: fork_reply({"status": [{"message": f"Schema not found in {project}\\openspec\\schemas"}]}, code=1),
    lambda project: fork_reply(code=1, stderr=f"Error: Cannot find module '{project}\\bin\\openspec.js'\n    at x\n"),
    lambda project: fork_reply(code=1, stderr=f"сбой {project}/openspec/changes/demo\n"),
], ids=["сообщение форка", "трассировка node", "прямые слеши"])
def test_failure_reason_has_no_directory(tmp_path, reply):
    """Сценарий «Причина сбоя без каталога»: и то, что напечатал сам форк."""
    project = make_project(tmp_path / "probe-machine-name")
    install_fork_shim(tmp_path / "bin", status=reply(project))
    code, data, done = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert code == 1 and data["error"] and b"probe-machine-name" not in done.stdout


def test_file_outside_the_root_gives_no_absolute_path(tmp_path):
    project = make_project(tmp_path / "proj")
    status = fake_status(project, ready=("intent",))
    status["artifactPaths"]["intent"]["existingOutputPaths"] = [str(tmp_path / "probe-machine-name" / "intent.md")]
    install_fork_shim(tmp_path / "bin", status=fork_reply(status), apply=fork_reply(fake_apply()))
    _, data, done = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert b"probe-machine-name" not in done.stdout
    assert page(data, "intent")["files"] == [{"path": "intent.md", "exists": True}]


def test_root_is_nearest_openspec_above_the_call(tmp_path):
    """Корень — ближайший `openspec/` от каталога вызова, как у форка, и идёт в форк через `cwd`."""
    project = make_project(tmp_path / "proj")
    write_journal(project, journal_of(open_fork()))
    (project / "src" / "deep").mkdir(parents=True)
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))),
                      apply=fork_reply(fake_apply()))
    _, data, _ = run_help(project / "src" / "deep", "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert data["forks"]["open"] == 1 and page(data, "intent")["texts"]["why"] == "why intent"
    assert {Path(call["cwd"]) for call in fork_calls(tmp_path / "bin")} == {project}


def test_compute_takes_root_and_name(tmp_path, monkeypatch):
    """`render-html` зовёт расчёт как функцию: корень из пути журнала, а не каталог вызова."""
    project = make_project(tmp_path / "A")
    write_journal(project, journal_of(open_fork()))
    (tmp_path / "B").mkdir()
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))),
                      apply=fork_reply(fake_apply()))
    monkeypatch.chdir(tmp_path / "B")
    monkeypatch.delenv("SYMPHYSIS_OPENSPEC", raising=False)  # `fork_env` её убирает только из словаря, а расчёт идёт в этом процессе
    for key, value in fork_env(tmp_path / "bin").items():
        monkeypatch.setenv(key, value)
    data = step_help.compute(project, "demo")
    assert data["error"] is None and data["current_step"] == "viewer"
    assert {Path(call["cwd"]) for call in fork_calls(tmp_path / "bin")} == {project}


# --- 1.6 вывод и область ----------------------------------------------------

def test_output_shape(tmp_path):
    code, data = with_shim(tmp_path, done=("intent",), ready=("decisions",))
    assert code == 0
    assert data["contract"] == journal_render.CONTRACT
    assert dt.datetime.fromisoformat(data["taken_at"]).tzinfo is not None
    assert data["versions"] == {"openspec": FORK_VERSION, "symphysis": None}
    assert set(data) == {"contract", "taken_at", "versions", "change", "changes", "error", "current_step", "current_text",
                         "turn", "next_by_status", "forks", "tasks", "steps"}
    assert data["changes"] is None, "при --change список не считается"
    assert set(page(data, "design")) == {"id", "state", "turn", "optional", "blocks", "stops_apply", "waits_for", "files",
                                         "file_note", "texts", "text_note", "prev", "next"}
    assert set(page(data, "design")["texts"]) == {"title", "why", "mechanics", "if_skipped", "what_to_check", "command",
                                                  "how_to_prepare"}


def test_help(tmp_path):
    """Сценарий «Вызов `--help`»."""
    done = subprocess.run([sys.executable, "-X", "utf8", str(STEP_HELP), "--help"], capture_output=True, text=True,
                          encoding="utf-8", cwd=tmp_path)
    assert done.returncode == 0
    for word in ("Звать, когда", "Коды:", "только расчёт", "страницу не собирает"):
        assert word in done.stdout, word


def tree_of(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None for path in root.rglob("*")}


def test_project_tree_stays_the_same(tmp_path):
    """Сценарий «Дерево проекта не меняется»."""
    project = make_project(tmp_path / "proj")
    write_journal(project, journal_of(open_fork()))
    before = tree_of(project)
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, done=("intent", "decisions"))),
                      apply=fork_reply(fake_apply()))
    code, _, _ = run_help(project, "--change", "demo", env=fork_env(tmp_path / "bin"))
    assert code == 0 and tree_of(project) == before


def test_skills_do_not_know_the_script():
    """Сценарий «Скиллы о скрипте не знают»."""
    files = [ROOT / "openspec" / "schemas" / "symphysis" / "schema.yaml", *(ROOT / "skills").rglob("*")]
    named = [path for path in files if path.is_file() and b"step_help" in path.read_bytes()]
    assert named == []


def test_symphysis_version_absent_is_null(tmp_path):
    """Сценарий «Файла версии нет»."""
    code, data = with_shim(tmp_path, ready=("intent",))
    assert code == 0 and data["versions"]["symphysis"] is None and data["error"] is None


def copy_of_tools(directory: Path) -> Path:
    directory.mkdir()
    for name in ("step_help.py", "journal_render.py", "journal_model.py"):
        shutil.copy(ROOT / "tools" / name, directory)
    return directory / "step_help.py"


def test_symphysis_version_is_read_from_next_to_tools_and_not_compared(tmp_path):
    """Версия из файла рядом с инструментами; расхождение с форком не даёт ни ошибки, ни предупреждения."""
    script = copy_of_tools(tmp_path / "tools")
    (tmp_path / "tools" / "symphysis-version.txt").write_text("0.1.0+aa50e8f\n", encoding="utf-8")
    project = make_project(tmp_path / "proj")
    install_fork_shim(tmp_path / "bin", version="9.9.9-symphysis.9", status_all=fork_reply(fake_status_all()))
    done = subprocess.run([sys.executable, str(script)], cwd=project, env=fork_env(tmp_path / "bin"), capture_output=True)
    assert done.returncode == 0, done.stderr
    data = json.loads(done.stdout.decode("utf-8"))
    assert data["versions"] == {"openspec": "9.9.9-symphysis.9", "symphysis": "0.1.0+aa50e8f"}
    assert data["error"] is None and "верси" not in data["current_text"]


# --- 1.7 настоящий форк -----------------------------------------------------

def touch_files(project: Path, *rels: str, change="demo"):
    for rel in rels:
        path = project / "openspec" / "changes" / change / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")


def step_named_by_command(status: dict) -> str | None:
    """Шаг, который называет `nextSteps`: тот же выбор у `/opsx:continue` без имени."""
    for sentence in status["nextSteps"]:
        found = re.search(r"openspec instructions (\S+) --change", sentence)
        if found:
            return found.group(1)
    return None


PLANNED_FILES = ("intent.md", "decisions.json", "research/none.md", "proposal.md", "specs/a/spec.md", "consequences.md",
                 "design.md", "security.md")


@requires_fork
@pytest.mark.parametrize("files", [
    (),
    ("intent.md",),
    ("proposal.md",),
    PLANNED_FILES[:2],
    PLANNED_FILES[:4],
    PLANNED_FILES[:5],
    PLANNED_FILES[:6],
    PLANNED_FILES[:7],
    PLANNED_FILES,
    (*PLANNED_FILES, "tasks.md", "attack/artifacts.md"),
], ids=["пусто", "intent", "только proposal", "журнал", "proposal", "specs", "consequences", "design", "security",
        "атака без вердикта"])
def test_current_step_matches_the_command(tmp_path, files):
    """Сценарий «Текущий шаг совпадает с командой»: журнал `x` не разбирается, открытых нет."""
    project, env = real_project(tmp_path, "demo")
    touch_files(project, *files)
    code, data, _ = run_help(project, "--change", "demo", env=env)
    assert code == 0, data["error"]
    status = json.loads(real_fork(project, env, "status", "--change", "demo", "--json"))
    assert data["current_step"] == step_named_by_command(status)


@requires_fork
def test_current_step_after_planning_matches_the_command(tmp_path):
    project, env = real_project(tmp_path, "demo")
    touch_files(project, *PLANNED_FILES)
    (project / "openspec" / "changes" / "demo" / "tasks.md").write_text("- [x] 1.1 а\n- [ ] 1.2 б\n", encoding="utf-8")
    code, data, done = run_help(project, "--change", "demo", env=env)
    assert code == 0, data["error"]
    status = json.loads(real_fork(project, env, "status", "--change", "demo", "--json"))
    assert step_named_by_command(status) == "apply" == data["current_step"]
    assert data["tasks"] == {"state": "ready", "total": 2, "complete": 1, "remaining": 1}
    (project / "openspec" / "changes" / "demo" / "tasks.md").write_text("- [x] 1.1 а\n- [x] 1.2 б\n", encoding="utf-8")
    _, data, _ = run_help(project, "--change", "demo", env=env)
    assert data["current_step"] == "sync" and data["tasks"]["state"] == "all_done"


@requires_fork
def test_shapes_of_the_fake_match_the_fork(tmp_path):
    """Шим отдаёт поля, какие отдаёт форк: иначе зелёные выше ничего не доказывают."""
    project, env = real_project(tmp_path, "demo")
    real = json.loads(real_fork(project, env, "status", "--change", "demo", "--json"))
    fake = fake_status(project)
    assert set(fake) <= set(real)
    assert [a["id"] for a in real["artifacts"]] == list(SCHEMA_GRAPH)
    assert {a["id"]: (a["requires"], a["outputPath"]) for a in real["artifacts"]} == SCHEMA_GRAPH
    assert real["applyRequires"] == fake["applyRequires"]
    assert [a["id"] for a in real["artifacts"] if a.get("optional")] == list(OPTIONAL_ARTIFACTS)
    assert set(fake["artifactPaths"]["intent"]) == set(real["artifactPaths"]["intent"])
    assert set(fake_apply()) <= set(json.loads(real_fork(project, env, "instructions", "apply", "--change", "demo", "--json")))


@requires_fork
def test_active_changes_on_the_real_fork(tmp_path):
    """Сценарии о числе активных изменений: `status --all --json` у настоящего форка."""
    project, env = real_project(tmp_path)
    code, data, _ = run_help(project, env=env)
    assert (code, data["change"], data["changes"], data["current_step"]) == (0, None, [], "intent")
    real_fork(project, env, "new", "change", "demo", "--schema", "symphysis")
    code, data, _ = run_help(project, env=env)
    assert (code, data["change"], data["current_step"], data["turn"]) == (0, "demo", "intent", "human")
    real_fork(project, env, "new", "change", "other", "--schema", "symphysis")
    code, data, _ = run_help(project, env=env)
    assert (code, data["change"], data["current_step"]) == (0, None, None)
    assert sorted(data["changes"]) == ["demo", "other"]


@requires_fork
def test_no_openspec_at_all_on_the_real_fork(tmp_path):
    """Каталог без `openspec/`: для форка это пустой неявный корень, изменений нет, сбоя нет."""
    (tmp_path / "empty").mkdir()
    code, data, _ = run_help(tmp_path / "empty", env=real_env(tmp_path))
    assert (code, data["error"], data["change"], data["current_step"]) == (0, None, None, "intent")


@requires_fork
def test_no_such_change_on_the_real_fork(tmp_path):
    project, env = real_project(tmp_path, "demo")
    code, data, _ = run_help(project, "--change", "other", env=env)
    assert code == 1 and "other" in data["error"] and "openspec status" in data["error"]


@requires_fork
def test_dangerous_directory_on_the_real_fork(tmp_path):
    """Каталог `a&md,marker` виден настоящему форку, но имя дальше него не идёт."""
    project, env = real_project(tmp_path)
    (project / "openspec" / "changes" / "a&md,marker").mkdir()
    code, data, _ = run_help(project, env=env)
    assert code == 1 and "не подходит" in data["error"]
    assert not (project / "marker").exists()


@requires_fork
def test_real_fork_paths_are_from_the_root(tmp_path):
    """Сценарий «Каталог с заметным именем» на настоящем форке, сценарий «Файлов шага ещё нет и уже есть»."""
    project, env = real_project(tmp_path, "demo", name="probe-machine-name")
    touch_files(project, "intent.md", "specs/a/spec.md")
    code, data, done = run_help(project, "--change", "demo", env=env)
    assert code == 0 and b"probe-machine-name" not in done.stdout
    assert page(data, "intent")["files"] == [{"path": "openspec/changes/demo/intent.md", "exists": True}]
    assert page(data, "specs")["files"] == [{"path": "openspec/changes/demo/specs/a/spec.md", "exists": True}]
    assert page(data, "design")["files"] == [{"path": "openspec/changes/demo/design.md", "exists": False}]
    assert page(data, "research")["files"] == [{"path": "openspec/changes/demo/research/**/*.md", "exists": False}]
    assert page(data, "intent")["file_note"] == "файл есть, содержание не проверялось"
    assert page(data, "security")["stops_apply"] is True


@requires_fork
def test_empty_file_reads_as_done_with_a_note(tmp_path):
    """Сценарий «Пустой файл шага», половина данных: показ на странице — в тестах панели."""
    project, env = real_project(tmp_path, "demo")
    touch_files(project, *PLANNED_FILES[:7])
    (project / "openspec" / "changes" / "demo" / "design.md").write_bytes(b"")
    _, data, _ = run_help(project, "--change", "demo", env=env)
    assert page(data, "design")["state"] == "done"
    assert page(data, "design")["file_note"] == "файл есть, содержание не проверялось"


@requires_fork
def test_real_schema_and_real_texts_fit_together(tmp_path):
    """Настоящий граф и настоящий `steps.md`: у всех шагов есть текст, порядок показа тот же, имя в команде подставлено."""
    project, env = real_project(tmp_path, "demo")
    code, data, _ = run_help(project, "--change", "demo", env=env)
    assert code == 0 and [item["id"] for item in data["steps"]] == ALL_STEPS
    assert [item["id"] for item in data["steps"] if item["text_note"]] == []
    assert page(data, "specs")["texts"]["command"] == "`/opsx:continue demo`"
    assert page(data, "intent")["texts"]["how_to_prepare"]
    assert "выполняется" not in json.dumps(data, ensure_ascii=False)


# --- обзор: шим npm зовёт голый `node`, а `cmd.exe` ищет его сначала в `cwd` ----------------------------------------

def hostile_node_project(tmp_path: Path) -> tuple[Path, Path, dict]:
    """Проект с `node.cmd` в корне, пишущим маркер, и форк под настоящим `.cmd`-шимом, что зовёт голое `node`, как шим npm
    без `node.exe` рядом. Окружение вызова без `NoDefaultCurrentDirectoryInExePath`: среда агента или человека может
    его задавать, а тест проверяет, что скрипт ставит его сам."""
    project = make_project(tmp_path / "proj")
    write_journal(project, journal_of())
    (project / "node.cmd").write_text("@echo hostile> marker.txt\r\n@exit /b 0\r\n", encoding="utf-8")
    shim = tmp_path / "bin" / "openspec.cmd"
    shim.parent.mkdir()
    shim.write_text("@node %*\r\n", encoding="utf-8")
    env = {key: value for key, value in fork_env(shim.parent).items() if key.lower() != "nodefaultcurrentdirectoryinexepath"}
    return project, shim.parent, env


@windows_only
def test_environment_of_the_check_has_no_guard_variable(tmp_path):
    """Контроль: без охранной переменной `cmd.exe` берёт `node.cmd` из `cwd` — иначе тесты ниже зелёные и без правки."""
    project, _, env = hostile_node_project(tmp_path)
    assert not any(key.lower() == "nodefaultcurrentdirectoryinexepath" for key in env)
    subprocess.run("node", cwd=project, env=env, shell=True, capture_output=True)
    assert (project / "marker.txt").exists()


@windows_only
def test_step_help_does_not_run_node_cmd_from_the_project_root(tmp_path):
    project, _, env = hostile_node_project(tmp_path)
    run_help(project, "--change", "demo", env=env)
    assert not (project / "marker.txt").exists()


@windows_only
def test_render_html_does_not_run_node_cmd_from_the_project_root(tmp_path):
    project, _, env = hostile_node_project(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    journal_file = project / "openspec" / "changes" / "demo" / "decisions.json"
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "journal.py"), "render-html", str(journal_file), "--out",
                           str(project / "openspec" / "changes" / "demo" / "decisions.html")], cwd=elsewhere, env=env,
                          capture_output=True)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert not (project / "marker.txt").exists()


@requires_node
def test_js_route_runs_node_by_absolute_path(tmp_path, monkeypatch):
    """Маршрут `.js`: `node` берётся из PATH до вызова, а не ищется заново в `cwd` проекта."""
    script = tmp_path / "openspec.js"
    script.write_text("", encoding="utf-8")
    monkeypatch.setenv("SYMPHYSIS_OPENSPEC", str(script))
    command = step_help._fork_command()
    assert command[1] == str(script) and os.path.isabs(command[0])
    assert Path(command[0]).samefile(shutil.which("node"))


def test_tools_inside_the_project_leave_no_bytecode(tmp_path):
    """Скрипт пишет только в stdout (F-50): при инструментах внутри дерева проекта `__pycache__` рядом не появляется,
    хотя интерпретатор по умолчанию его пишет. Переменную человека `PYTHONDONTWRITEBYTECODE` тест снимает."""
    project = make_project(tmp_path / "proj")
    (project / ".symphysis").mkdir()
    script = copy_of_tools(project / ".symphysis" / "tools")
    install_fork_shim(tmp_path / "bin", status=fork_reply(fake_status(project, ready=("intent",))),
                      apply=fork_reply(fake_apply()))
    env = {k: v for k, v in fork_env(tmp_path / "bin").items() if k != "PYTHONDONTWRITEBYTECODE"}
    done = subprocess.run([sys.executable, str(script), "--change", "demo"], cwd=project, env=env, capture_output=True)
    assert done.returncode == 0, done.stderr
    assert not list(project.rglob("__pycache__")) and not list(project.rglob("*.pyc"))


def test_failure_keeps_texts_with_the_name_filled_in(tmp_path, monkeypatch):
    """Сбой форка при известном изменении: заголовок `steps.md` обещает подстановку, `<имя>` в текстах не остаётся.
    Без имени (`--change` не дан) буквальное `<имя>` законно."""
    project = make_project(tmp_path / "proj")
    (project / "openspec" / "schemas" / "symphysis" / "steps.md").write_text(
        steps_text().replace("why intent", "why intent <имя>"), encoding="utf-8")
    for key, value in fork_env().items():
        monkeypatch.setenv(key, value)
    named = step_help.compute(project, "demo")
    assert named["error"] is not None
    assert "<имя>" not in json.dumps(named["steps"], ensure_ascii=False) and "demo" in json.dumps(named["steps"])
    assert "<имя>" in json.dumps(step_help.compute(project)["steps"], ensure_ascii=False)


@windows_only
@requires_node
def test_js_route_does_not_find_node_cmd_in_the_working_directory(tmp_path):
    """Маршрут `.js`: `shutil.which` на Windows ищет и в каталоге вызова, пока охранной переменной нет в окружении самого
    процесса; `node.cmd` из корня чужого проекта не запускается, вызывается настоящий `node` из `PATH`."""
    project = make_project(tmp_path / "proj")
    (project / "node.cmd").write_text("@echo hostile> marker.txt\r\n@exit /b 0\r\n", encoding="utf-8")
    script = tmp_path / "openspec.js"
    script.write_text('console.log(process.argv[2] === "--version" ? "1.0.0-symphysis.1" : \'{"changes": []}\');\n',
                      encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key.lower() != "nodefaultcurrentdirectoryinexepath"}
    env["SYMPHYSIS_OPENSPEC"] = str(script)
    code, data, _ = run_help(project, env=env)
    assert not (project / "marker.txt").exists()
    assert code == 0 and data["versions"]["openspec"] == "1.0.0-symphysis.1"
