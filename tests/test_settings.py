"""Настройки `symphysis.yaml`: чтение скриптом, файл случаев, вход для модели."""
import ast
import base64
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from conftest import FIX, ROOT

import symphysis_config

TOOL = ROOT / "tools" / "symphysis_config.py"
JOURNAL_TOOL = ROOT / "tools" / "journal.py"
CASES = json.loads((FIX / "settings-cases.json").read_text(encoding="utf-8"))
ALL_ON = {"failure_branches": True, "assumptions": True, "edge_probe": True}
# Водители (Р11-A): атака и исследование по умолчанию вкл, пробы и опись выкл.
DRIVER_DEFAULTS = {"driver_attack": True, "driver_probes": False, "driver_consequences": False,
                   "driver_research": True}
NO_PACKAGE = "symphysis.yaml: нет пакета PyYAML — выполнить: python -m pip install pyyaml"


def write_case(project, case):
    if case["bytes_b64"] is not None:
        (project / "symphysis.yaml").write_bytes(base64.b64decode(case["bytes_b64"]))


def composition_line(expected):
    on = lambda key: "вкл" if expected.get(key, DRIVER_DEFAULTS.get(key)) else "выкл"
    return (f"[..] symphysis.yaml: ветки отказа {on('failure_branches')}, допущения {on('assumptions')}, "
            f"проба краёв {on('edge_probe')}, водители: атака {on('driver_attack')}, "
            f"пробы {on('driver_probes')}, опись {on('driver_consequences')}, "
            f"исследование {on('driver_research')}")


def run_config(*args, env=None):
    return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8", env=env)


def without_yaml(tmp_path):
    """Окружение, где `import yaml` падает: заглушка `yaml.py` стоит раньше настоящего пакета."""
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "yaml.py").write_text('raise ImportError("заблокирован тестом")\n', encoding="utf-8")
    return dict(os.environ, PYTHONPATH=str(blocked))


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_shared_cases(tmp_path, case):
    """Файл случаев: состав и сигналы; Backstop F-50."""
    write_case(tmp_path, case)
    got = symphysis_config.read_settings(tmp_path)
    assert (got.failure_branches, got.assumptions, got.edge_probe) == (
        case["failure_branches"], case["assumptions"], case["edge_probe"])
    for key, default in DRIVER_DEFAULTS.items():
        assert getattr(got, key) == case.get(key, default), key
    assert got.signals == case["signals"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_cli_prints_composition_and_signals(tmp_path, case):
    write_case(tmp_path, case)
    done = run_config("--project", tmp_path)
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == [composition_line(case), *(f"[!!] {s}" for s in case["signals"])]


def test_drivers_defaults_and_toggles(tmp_path):
    """Р11-A: без ключа атака и исследование идут водителю, пробы и опись — в главной нити; `true` включает
    выключенное по умолчанию, `false` выключает включённое, недопустимое значение оставляет умолчание."""
    got = symphysis_config.read_settings(tmp_path)
    assert {k: getattr(got, k) for k in DRIVER_DEFAULTS} == DRIVER_DEFAULTS
    (tmp_path / "symphysis.yaml").write_text("drivers:\n  attack: false\n  probes: true\n  consequences: yes\n",
                                             encoding="utf-8")
    got = symphysis_config.read_settings(tmp_path)
    assert (got.driver_attack, got.driver_probes, got.driver_consequences, got.driver_research) == (
        False, True, False, True)
    assert got.signals == ["symphysis.yaml: недопустимое значение yes"]
    done = run_config("--project", tmp_path)
    assert done.stdout.splitlines()[0].endswith("водители: атака выкл, пробы вкл, опись выкл, исследование вкл")


def test_lone_surrogate_in_a_value_is_a_signal_not_a_crash(tmp_path):
    """С4: значение с одиночным суррогатом печатается с экранированием, код 0, сигнал напечатан."""
    (tmp_path / "symphysis.yaml").write_bytes(b'edge_probe:\n  enabled: "\\uD800"\n')
    done = run_config("--project", tmp_path)
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines()[0].startswith("[..] symphysis.yaml:")
    assert any(line.startswith("[!!] symphysis.yaml:") and "недопустимое значение" in line
               for line in done.stdout.splitlines()), done.stdout


def test_alias_chain_prints_fast(tmp_path):
    """Цепочка алиасов на 12 уровней: значение в сигнале называется словом, а не печатается целиком."""
    levels = ["a0: &a0 [x, x]"] + [f"a{i}: &a{i} [*a{i - 1}, *a{i - 1}]" for i in range(1, 12)]
    (tmp_path / "symphysis.yaml").write_text(
        "\n".join(levels) + "\nedge_probe:\n  enabled: *a11\n", encoding="utf-8")
    started = time.monotonic()
    done = run_config("--project", tmp_path)
    assert time.monotonic() - started < 1
    assert done.returncode == 0, done.stderr
    assert "[!!] symphysis.yaml: недопустимое значение составное" in done.stdout.splitlines()


def test_strict_gives_code_two_only_with_signals(tmp_path):
    (tmp_path / "symphysis.yaml").write_text("edge_probe:\n  enabled: false\n", encoding="utf-8")
    assert run_config("--project", tmp_path, "--strict").returncode == 0
    (tmp_path / "symphysis.yaml").write_text("edge_probe:\n  enabled: no\n", encoding="utf-8")
    assert run_config("--project", tmp_path).returncode == 0
    assert run_config("--project", tmp_path, "--strict").returncode == 2


def test_no_file_means_all_on(tmp_path):
    """Сценарий «Файла нет»."""
    got = symphysis_config.read_settings(tmp_path)
    assert (got.failure_branches, got.assumptions, got.edge_probe, got.signals) == (True, True, True, [])


def test_missing_key_keeps_the_rest_on(tmp_path):
    """Сценарий «Ключа нет»."""
    (tmp_path / "symphysis.yaml").write_text("consequences:\n  assumptions: false\n", encoding="utf-8")
    got = symphysis_config.read_settings(tmp_path)
    assert (got.failure_branches, got.assumptions, got.edge_probe, got.signals) == (True, False, True, [])


def test_invalid_value_turns_nothing_off_and_signals(tmp_path):
    """Сценарий «Значение не из true и false»: у скрипта код 0, с `--strict` 2."""
    (tmp_path / "symphysis.yaml").write_text("consequences:\n  assumptions: выкл\n", encoding="utf-8")
    done = run_config("--project", tmp_path)
    assert done.returncode == 0
    assert "[!!] symphysis.yaml: недопустимое значение выкл" in done.stdout.splitlines()
    assert "допущения вкл" in done.stdout
    assert run_config("--project", tmp_path, "--strict").returncode == 2


def test_no_pyyaml_means_all_on_and_signal(tmp_path):
    """Сценарий «Нет пакета PyYAML»: файл с выключенной пробой, всё включено, сигнал называет команду."""
    (tmp_path / "symphysis.yaml").write_text("edge_probe:\n  enabled: false\n", encoding="utf-8")
    env = without_yaml(tmp_path)
    done = run_config("--project", tmp_path, env=env)
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == [composition_line(ALL_ON), f"[!!] {NO_PACKAGE}"]
    assert run_config("--project", tmp_path, "--strict", env=env).returncode == 2


def test_no_pyyaml_without_file_is_silent(tmp_path):
    """Импорт идёт только при чтении файла (F-113): нет файла — читать нечем не нужно, сигнала нет."""
    project = tmp_path / "p"
    project.mkdir()
    done = run_config("--project", project, "--strict", env=without_yaml(tmp_path))
    assert done.returncode == 0 and done.stdout.splitlines() == [composition_line(ALL_ON)]


def test_import_yaml_only_inside_a_function():
    """F-113: на уровне модуля пакета нет, иначе скрипт падал бы при импорте."""
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    top = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
           and n.col_offset == 0]
    names = {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module for n in top if isinstance(n, ast.ImportFrom)}
    assert "yaml" not in names
    source = TOOL.read_text(encoding="utf-8")
    assert "yaml.load(text, Loader=yaml.BaseLoader)" in source


def test_unparsed_file_means_all_on(tmp_path):
    """Сценарий «Файл не разбирается»: код 0, с `--strict` 2."""
    (tmp_path / "symphysis.yaml").write_text("edge_probe:\n\tenabled: false\n", encoding="utf-8")
    done = run_config("--project", tmp_path)
    assert done.returncode == 0
    assert done.stdout.splitlines() == [composition_line(ALL_ON), "[!!] symphysis.yaml: не разбирается"]
    assert run_config("--project", tmp_path, "--strict").returncode == 2


def test_model_learns_composition_from_the_script(tmp_path):
    """Сценарий «Модель узнаёт состав скриптом»: `enabled: no` не выключает пробу, и об этом есть сигнал."""
    (tmp_path / "symphysis.yaml").write_text("edge_probe:\n  enabled: no\n", encoding="utf-8")
    done = run_config("--project", tmp_path)
    assert "проба краёв вкл" in done.stdout
    assert "[!!] symphysis.yaml: недопустимое значение no" in done.stdout


def test_journal_does_not_read_settings():
    """F-128.A: модули журнала не импортируют ни скрипт настроек, ни пакет."""
    for path in sorted((ROOT / "tools").glob("journal*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        assert not imported & {"yaml", "symphysis_config"}, path.name


def test_other_journal_commands_work_without_pyyaml(tmp_path):
    """Сценарий «Прочие команды журнала без пакета»: `apply`, `render-md`, `render-html` идут как прежде."""
    env = without_yaml(tmp_path)
    journal_file = tmp_path / "decisions.json"
    shutil.copy(FIX / "change-demo" / "decisions.json", journal_file)
    (tmp_path / "answers.md").write_text("- F-02: A — «да»\n", encoding="utf-8")

    def run_journal(*args):
        return subprocess.run([sys.executable, "-X", "utf8", str(JOURNAL_TOOL), *map(str, args)], capture_output=True,
                              text=True, encoding="utf-8", env=env)

    for args in (("apply", journal_file, tmp_path / "answers.md", "--dry-run"),
                 ("render-md", journal_file, "--out", tmp_path / "j.md"),
                 ("render-html", journal_file, "--out", tmp_path / "j.html")):
        done = run_journal(*args)
        assert done.returncode == 0, f"{args[0]}: {done.stdout}{done.stderr}"
    assert (tmp_path / "j.md").is_file() and (tmp_path / "j.html").is_file()


# --- корень проекта: параметр, префикс "" файла корней, ROOT (предположение е) ----

def installed_tools(project, roots):
    """Копия `tools/*.py` в `<project>/.symphysis/tools` с заданным файлом корней."""
    tools = project / ".symphysis" / "tools"
    tools.mkdir(parents=True)
    for path in (ROOT / "tools").glob("*.py"):
        shutil.copy(path, tools)
    if roots is not None:
        (tools / "journal-roots.json").write_text(json.dumps(roots), encoding="utf-8")
    return tools / "symphysis_config.py"


def run_tool(tool, *args):
    return subprocess.run([sys.executable, "-X", "utf8", str(tool), *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8")


def test_project_root_from_roots_file(tmp_path):
    """Установленная копия без параметра: корень — пустой префикс файла корней, проект над `.symphysis/`."""
    tool = installed_tools(tmp_path, {"": "<root>/.."})
    (tmp_path / "symphysis.yaml").write_text("edge_probe:\n  enabled: false\n", encoding="utf-8")
    assert "проба краёв выкл" in run_tool(tool).stdout


def test_project_root_falls_back_to_tools_parent(tmp_path):
    """Файл корней без пустого префикса — каталог над `tools/`, как `ROOT` журнала."""
    tool = installed_tools(tmp_path, {"docs/": "<root>/docs"})
    (tmp_path / ".symphysis" / "symphysis.yaml").write_text("edge_probe:\n  enabled: false\n", encoding="utf-8")
    assert "проба краёв выкл" in run_tool(tool).stdout


def test_project_root_without_roots_file(tmp_path):
    tool = installed_tools(tmp_path, None)
    (tmp_path / ".symphysis" / "symphysis.yaml").write_text("edge_probe:\n  enabled: false\n", encoding="utf-8")
    assert "проба краёв выкл" in run_tool(tool).stdout


def test_project_parameter_wins_over_roots_file(tmp_path):
    tool = installed_tools(tmp_path, {"": "<root>/.."})
    (tmp_path / "symphysis.yaml").write_text("edge_probe:\n  enabled: false\n", encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    assert "проба краёв вкл" in run_tool(tool, "--project", other).stdout


def test_project_that_is_not_a_directory_is_a_wrong_call(tmp_path):
    """Опечатка в пути не должна молча отвечать «всё включено»."""
    done = run_config("--project", tmp_path / "нет такого")
    assert done.returncode == 2 and "нет такого" in done.stderr and done.stdout == ""
