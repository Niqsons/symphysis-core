"""Схема OpenSpec `symphysis`: граф артефактов, как его разбирает CLI форка."""
import json
import os
import re
import shutil
import subprocess

import pytest

import journal
from conftest import FORK_BIN, ROOT, requires_fork

SCHEMAS = ROOT / "openspec" / "schemas"
TEMPLATES = SCHEMAS / "symphysis" / "templates"
SCHEMA_YAML = SCHEMAS / "symphysis" / "schema.yaml"

TEMPLATE_FILES = ["decisions.json", "research.md", "attack-decisions.md", "attack-artifacts.md",
                  "proposal.md", "spec.md", "design.md", "security.md", "tasks.md"]

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


# --- шаблоны артефактов ----------------------------------------------------

def template_text(name):
    """Текст шаблона с переводами строк LF: `.md` в рабочей копии CRLF, тест от них не зависит."""
    return (TEMPLATES / name).read_bytes().decode("utf-8").replace("\r\n", "\n")


def frontmatter(text):
    """Текст между первой парой строк `---`."""
    assert text.startswith("---\n"), text[:40]
    return text[4:text.index("\n---\n", 3)]


def last_line(text):
    return [line for line in text.splitlines() if line.strip()][-1]


def headings(text, level):
    return re.findall(rf"^{'#' * level} (.+?)\s*$", text, re.M)


def section(text, title):
    """Тело раздела `## <title>` до следующего `## ` или конца файла."""
    return re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.M | re.S).group(1)


def schema_block(artifact_id):
    """Блок артефакта в schema.yaml: от `- id:` до следующего артефакта или `apply:`."""
    text = SCHEMA_YAML.read_bytes().decode("utf-8").replace("\r\n", "\n")
    m = re.search(rf"^  - id: {re.escape(artifact_id)}\n(.*?)(?=^  - id: |^apply:)", text, re.M | re.S)
    assert m, f"в schema.yaml нет артефакта {artifact_id}"
    return m.group(1)


def test_templates_exist_and_decisions_template_valid():
    missing = [n for n in TEMPLATE_FILES if not (TEMPLATES / n).is_file()]
    assert not missing, f"нет шаблонов: {missing}"
    assert sorted(p.name for p in TEMPLATES.iterdir()) == sorted(TEMPLATE_FILES), \
        "общий attack.md заменён двумя шаблонами, лишних файлов нет"
    template = journal.load_journal(TEMPLATES / "decisions.json")
    assert template == {"title": "", "source": "decisions.json", "intro": "", "records": []}
    assert journal.validate_journal(template) == []
    for name in ("attack-decisions.md", "attack-artifacts.md"):
        assert template_text(name).startswith("---\nstatus:"), name


ATTACK_COLUMNS = ["Утверждение", "Раздел", "Опора есть / нет", "Чем закрыть"]


@pytest.mark.parametrize("name", ["attack-decisions.md", "attack-artifacts.md"])
def test_attack_templates_table_and_verdict_rule(name):
    text = template_text(name)
    assert frontmatter(text).splitlines()[0] == "status: gaps_found"
    header = [row for row in text.splitlines() if row.startswith("|")][0]
    assert [c.strip() for c in header.strip("|").split("|")] == ATTACK_COLUMNS
    closing = last_line(text)
    assert "passed" in closing and "без опоры" in closing, closing


def test_attack_decisions_template_names_single_target():
    fm = frontmatter(template_text("attack-decisions.md")).splitlines()
    assert "target: decisions.json" in fm
    assert any(line.startswith("target_sha256:") for line in fm), fm


def test_attack_artifacts_template_lists_targets():
    fm = frontmatter(template_text("attack-artifacts.md")).splitlines()
    assert "targets:" in fm and not any(line.startswith("target") and not line.startswith("targets:")
                                        for line in fm), fm
    paths = [m.group(1) for line in fm if (m := re.match(r"\s+- path: (\S+)", line))]
    assert paths[0].startswith("specs/") and paths[1:] == ["design.md", "security.md", "tasks.md"], paths
    assert len([line for line in fm if re.match(r"\s+sha256:", line)]) == len(paths)


def test_research_template_shape():
    text = template_text("research.md")
    fm = frontmatter(text)
    genre_line = re.search(r"^genre:.*$", fm, re.M).group(0)
    for genre in ("устройство", "размещение", "края", "проверка", "аналоги"):
        assert genre in genre_line, genre
    assert re.search(r"^question: F-NN$", fm, re.M) and re.search(r"^brief:", fm, re.M), fm
    assert headings(text, 2) == ["Найдено", "Не найдено", "Вопросы, которые открылись"]
    assert "путь:строка" in text and "«цитата»" in text
    assert "не найдено" in text and "искал: " in text and "<шаблон" in text


def test_spec_template_uses_openspec_delta_grammar():
    text = template_text("spec.md")
    assert "## ADDED Requirements" in text.splitlines()
    assert re.search(r"^### Requirement: ", text, re.M) and re.search(r"^#### Scenario: ", text, re.M)
    for keyword in ("SHALL", "**GIVEN**", "**WHEN**", "**THEN**"):
        assert keyword in text, keyword
    assert "<!-- проба краёв: " in text and "<!-- проба запретов: " in text


def test_design_template_marks_generated_sections():
    text = template_text("design.md")
    assert headings(text, 2) == ["Context", "Goals / Non-Goals", "Decisions", "Risks / Trade-offs",
                                 "Migration Plan", "Open Questions"]
    for title in ("Decisions", "Risks / Trade-offs", "Open Questions"):
        assert "генерируется `py -3.13 .symphysis/tools/journal.py render-design`" in section(text, title), title
    for title in ("Context", "Goals / Non-Goals"):
        assert "render-design" not in section(text, title), title


def test_security_template_is_canon_checklist():
    text = template_text("security.md")
    rows = [[c.strip() for c in row.strip("|").split("|")] for row in text.splitlines() if row.startswith("|")]
    assert rows[0] == ["Пункт", "Применимо / неприменимо — причина", "Чем проверено"]
    items = " ".join(r[0] for r in rows[2:])
    for item in ("Инъекции через содержимое файлов", "Пути с `../`", "Токены и срок их жизни",
                 "Права", "Бинарные файлы"):
        assert item in items, item
    assert "не записывается в журнал" in text


def test_proposal_template_keeps_headings_the_cli_parses():
    text = template_text("proposal.md")
    assert headings(text, 2) == ["Why", "What Changes", "Capabilities", "Impact"]
    assert headings(text, 3) == ["New Capabilities", "Modified Capabilities"]


def test_tasks_template_follows_openspec_checkbox_grammar():
    text = template_text("tasks.md")
    assert re.findall(r"^## (\d+)\. ", text, re.M) == ["1", "2"]
    assert re.findall(r"^- \[ \] (\d+\.\d+) ", text, re.M) == ["1.1", "1.2", "2.1", "2.2"]
    assert "проверка:" in text


# --- schema.yaml: шаблоны, пути скриптов, формулировки ---------------------

def test_schema_points_each_artifact_at_its_own_template():
    for artifact_id, template in {"decisions": "decisions.json", "research": "research.md",
                                  "attack-decisions": "attack-decisions.md", "proposal": "proposal.md",
                                  "specs": "spec.md", "design": "design.md", "security": "security.md",
                                  "tasks": "tasks.md", "attack-artifacts": "attack-artifacts.md"}.items():
        assert re.search(rf"^    template: {re.escape(template)}$", schema_block(artifact_id), re.M), artifact_id


def test_instructions_call_journal_by_installed_path():
    text = SCHEMA_YAML.read_bytes().decode("utf-8")
    assert ".symphysis/tools/journal.py" in schema_block("decisions")
    assert ".symphysis/tools/journal.py" in schema_block("design")
    bare = re.findall(r"(?<!\.symphysis/)tools/journal\.py", text)
    assert bare == [], f"путь скрипта без .symphysis/: {bare}"


def test_instruction_wording_from_task7_review():
    assert ("форк OpenSpec symphysis считает артефакт готовым только с `status: passed`"
            in schema_block("attack-artifacts"))
    security = schema_block("security")
    assert "Канон (OWASP, инъекции, пути, токены) не записывается в журнал, а отмечается здесь" in security
    assert "prohibition probe" not in security
    research = schema_block("research")
    assert "«не найдено»" in research and "«искал: <шаблоны дословно>»" in research


@requires_fork
@pytest.mark.parametrize("artifact_id, name", [("attack-decisions", "attack-decisions.md"),
                                               ("attack-artifacts", "attack-artifacts.md")])
def test_instructions_return_attack_template_of_own_artifact(tmp_path, artifact_id, name):
    proj = make_project(tmp_path)
    out = run_openspec(proj, "instructions", artifact_id, "--change", "demo", "--json")
    assert out["template"].replace("\r\n", "\n") == template_text(name)


@requires_fork
def test_filled_templates_pass_openspec_validate(tmp_path):
    """Грамматику proposal, spec и tasks разбирает CLI: заполненные шаблоны проходят `validate --strict`,
    комментарии с пробами между требованием и сценарием ему не мешают."""
    proj = make_project(tmp_path)
    change = proj / "openspec" / "changes" / "demo"
    fill = lambda text: re.sub(r"<(?!!--)[^<>\n]*>", "заполнено", text)
    why = "Нужно проверить, что шаблоны схемы разбираются CLI так же, как шаблоны spec-driven."
    purpose = "Проверка формы шаблона spec.md на живом разборе CLI форка OpenSpec: грамматика требований."
    files = {
        "proposal.md": fill(template_text("proposal.md")).replace("## Why\n", f"## Why\n\n{why}\n")
                                                          .replace("## What Changes\n", "## What Changes\n\n- Новая capability.\n"),
        "specs/demo-cap/spec.md": fill(template_text("spec.md")).replace("## Purpose\n", f"## Purpose\n{purpose}\n")
                                                              .replace("Система SHALL заполнено.", "Система SHALL работать."),
        "tasks.md": fill(template_text("tasks.md")),
    }
    for name, text in files.items():
        (change / name).parent.mkdir(parents=True, exist_ok=True)
        (change / name).write_text(text, encoding="utf-8", newline="\n")
    out = run_openspec(proj, "validate", "demo", "--strict", "--json")
    assert out["summary"]["totals"] == {"items": 1, "passed": 1, "failed": 0}, out
