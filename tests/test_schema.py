"""Схема OpenSpec `symphysis`: граф артефактов, как его разбирает CLI форка."""
import json
import os
import shutil
import subprocess

import pytest

from conftest import FORK_BIN, ROOT, requires_fork

SCHEMAS = ROOT / "openspec" / "schemas"

ARTIFACT_IDS = ["decisions", "research", "attack-decisions", "proposal", "specs",
                "design", "security", "tasks", "attack-artifacts"]

REQUIRES = {
    "decisions": [],
    "research": ["decisions"],
    "attack-decisions": ["research"],
    "proposal": ["attack-decisions"],
    "specs": ["proposal"],
    "design": ["proposal"],
    "security": ["specs"],
    "tasks": ["specs", "design"],
    "attack-artifacts": ["specs", "design", "security", "tasks"],
}


def run_openspec(project, *args):
    """`openspec <args>` из форка с `cwd=project`. С `--json` — разобранный JSON, иначе — stdout.
    Ненулевой код — AssertionError с обоими потоками. Конфиг и данные пользователя подменены
    пустыми каталогами рядом с проектом: пользовательская схема не заслонит проектную."""
    env = dict(os.environ,
               XDG_CONFIG_HOME=str(project.parent / "xdg-config"),
               XDG_DATA_HOME=str(project.parent / "xdg-data"),
               OPENSPEC_TELEMETRY="0", OPENSPEC_NO_UPDATE_CHECK="1",
               OPENSPEC_NO_COMPLETIONS="1", NO_COLOR="1")
    done = subprocess.run(["node", str(FORK_BIN), *args], cwd=project, env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL, timeout=120)
    assert done.returncode == 0, (f"openspec {' '.join(args)} -> код {done.returncode}\n"
                                  f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}")
    if "--json" not in args:
        return done.stdout
    # перед JSON CLI печатает строку-предупреждение («Schema commands are experimental…»)
    return json.JSONDecoder().raw_decode(done.stdout[done.stdout.index("{"):])[0]


def make_project(tmp_path, schema="symphysis", change="demo"):
    """Проект OpenSpec с пустым изменением: схема копируется из `openspec/schemas/<schema>`,
    `config.yaml` и изменение — через `openspec new change` (`openspec init` не нужен)."""
    src = SCHEMAS / schema
    assert src.is_dir(), f"нет схемы {src.relative_to(ROOT)}"
    proj = tmp_path / "proj"
    (proj / "openspec" / "specs").mkdir(parents=True)
    (proj / "openspec" / "changes").mkdir()
    (proj / "openspec" / "config.yaml").write_text(f"schema: {schema}\n", encoding="utf-8", newline="\n")
    shutil.copytree(src, proj / "openspec" / "schemas" / schema)
    run_openspec(proj, "new", "change", change, "--schema", schema)
    return proj


@requires_fork
def test_schema_parses_in_fork(tmp_path):
    proj = make_project(tmp_path, schema="symphysis")
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    ids = [a["id"] for a in out["artifacts"]]
    assert ids == ARTIFACT_IDS
    assert out["artifacts"][0]["status"] == "ready" and out["artifacts"][1]["status"] == "blocked"


@requires_fork
def test_graph_edges_and_apply_gate(tmp_path):
    proj = make_project(tmp_path)
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    assert out["schemaName"] == "symphysis"
    assert {a["id"]: a["requires"] for a in out["artifacts"]} == REQUIRES
    assert {a["id"]: a["outputPath"] for a in out["artifacts"]} == {
        "decisions": "decisions.json", "research": "research/**/*.md",
        "attack-decisions": "attack/decisions.md", "proposal": "proposal.md",
        "specs": "specs/**/*.md", "design": "design.md", "security": "security.md",
        "tasks": "tasks.md", "attack-artifacts": "attack/artifacts.md"}
    assert out["applyRequires"] == ["tasks", "attack-artifacts"]


@requires_fork
def test_schema_validate_accepts_symphysis(tmp_path):
    """`openspec schema validate` проверяет структуру, ссылки `requires`, `apply.tracks` и то,
    что файл каждого `template:` существует."""
    proj = make_project(tmp_path)
    out = run_openspec(proj, "schema", "validate", "symphysis", "--json")
    assert out["valid"] is True and out["issues"] == [], out
    where = run_openspec(proj, "schema", "which", "symphysis", "--json")
    assert where["source"] == "project", where


@requires_fork
def test_instructions_name_skills_and_stay_short(tmp_path):
    """F-06: instruction короткий и называет скилл по имени; research, design, security, tasks —
    правила без скилла. F-07: attack-decisions начинается со второго круга."""
    proj = make_project(tmp_path)
    text = {i: run_openspec(proj, "instructions", i, "--change", "demo", "--json")["instruction"]
            for i in ARTIFACT_IDS}
    for i, t in text.items():
        assert len(t.split()) <= 120, f"{i}: {len(t.split())} слов"
    assert "symphysis-brainstorm" in text["decisions"]
    assert "symphysis-attack" in text["attack-decisions"] and "symphysis-attack" in text["attack-artifacts"]
    assert "symphysis-edge-probe" in text["specs"] and "symphysis-prohibition-probe" in text["specs"]
    for i in ("research", "design", "security", "tasks"):
        assert "symphysis-" not in text[i], f"{i}: правила без скилла"
    second_round = text["attack-decisions"].lstrip()
    assert second_round.startswith("Второй круг"), second_round[:60]
    assert second_round.index("материалы") < second_round.index("research/") < second_round.index("symphysis-attack")
    assert "брейншторм закончен по решению человека" in second_round
    assert "status: passed | gaps_found" in text["attack-decisions"]
