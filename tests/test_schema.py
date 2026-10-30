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
CHANGE_DEMO = ROOT / "tests" / "fixtures" / "change-demo"
CHANGE_DEMO_ATTACK = ROOT / "tests" / "fixtures" / "change-demo-attack"

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


def run_openspec_raw(project, *args, returncode=0):
    """`openspec <args>` из форка с `cwd=project`: `CompletedProcess` с обоими потоками.
    Код выхода не равен ожидаемому `returncode` (по умолчанию 0) — AssertionError с обоими потоками.
    Конфиг и данные пользователя подменены пустыми каталогами рядом с проектом: пользовательская
    схема не заслонит проектную."""
    env = dict(os.environ,
               XDG_CONFIG_HOME=str(project.parent / "xdg-config"),
               XDG_DATA_HOME=str(project.parent / "xdg-data"),
               OPENSPEC_TELEMETRY="0", OPENSPEC_NO_UPDATE_CHECK="1",
               OPENSPEC_NO_COMPLETIONS="1", NO_COLOR="1")
    done = subprocess.run(["node", str(FORK_BIN), *args], cwd=project, env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL, timeout=120)
    assert done.returncode == returncode, (
        f"openspec {' '.join(args)} -> код {done.returncode}, ждали {returncode}\n"
        f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}")
    return done


def run_openspec(project, *args, returncode=0):
    """`openspec <args>` из форка с `cwd=project`. С `--json` — разобранный JSON, иначе — stdout."""
    done = run_openspec_raw(project, *args, returncode=returncode)
    if "--json" not in args:
        return done.stdout
    # перед JSON CLI печатает строку-предупреждение («Schema commands are experimental…»)
    return json.JSONDecoder().raw_decode(done.stdout[done.stdout.index("{"):])[0]


def make_project(tmp_path, schema="symphysis", change="demo", config=None, change_fixture=None):
    """Проект OpenSpec с пустым изменением: схема копируется из `openspec/schemas/<schema>`,
    изменение создаётся через `openspec new change` (`openspec init` не нужен). `config` — текст
    `openspec/config.yaml`; без него в конфиге одна строка `schema: <schema>`. `change_fixture` —
    каталог с файлами готового изменения: он копируется в `openspec/changes/<change>/` вместо
    `openspec new change`, так что `.openspec.yaml` берётся из фикстуры."""
    src = SCHEMAS / schema
    assert src.is_dir(), f"нет схемы {src.relative_to(ROOT)}"
    proj = tmp_path / "proj"
    (proj / "openspec" / "specs").mkdir(parents=True)
    (proj / "openspec" / "changes").mkdir()
    if config is None:
        config = f"schema: {schema}\n"
    (proj / "openspec" / "config.yaml").write_text(config, encoding="utf-8", newline="\n")
    shutil.copytree(src, proj / "openspec" / "schemas" / schema)
    if change_fixture is None:
        run_openspec(proj, "new", "change", change, "--schema", schema)
    else:
        assert change_fixture.is_dir(), f"нет фикстуры {change_fixture.relative_to(ROOT)}"
        shutil.copytree(change_fixture, proj / "openspec" / "changes" / change)
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

def lf_text(path):
    """Текст файла с переводами строк LF: `.md` в рабочей копии CRLF, тест от них не зависит."""
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def template_text(name):
    return lf_text(TEMPLATES / name)


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


# Колонки атаки: линза (слуг измерения GSD — просмотрщик группирует строки по нему, слово владельца
# 2026-10-30), инвариант и тяжесть — из классификации находок plan-checker (`agents/gsd-plan-checker.md:39-46`),
# остальное — форма разрыва verifier (`gsd-verifier.md:616-631`).
ATTACK_COLUMNS = ["Утверждение", "Раздел", "Линза", "Инвариант", "Тяжесть", "Опора есть / нет", "Чем закрыть"]
ATTACK_SEVERITIES = ("блокер", "предупреждение", "справка")
# Одно правило вердикта — дословно в обоих шаблонах и в SKILL.md (тяжесть несут только строки «нет»
# и «по спеке не выводится», строка «есть» — справка; ревью D4b, fix round 1).
VERDICT_RULE = ("`status: passed` ставится, только когда в таблице нет ни одной строки с тяжестью "
                "`блокер` или `предупреждение`; строки `справка` не блокируют")


@pytest.mark.parametrize("name", ["attack-decisions.md", "attack-artifacts.md"])
def test_attack_templates_table_and_verdict_rule(name):
    text = template_text(name)
    assert frontmatter(text).splitlines()[0] == "status: gaps_found"
    header = [row for row in text.splitlines() if row.startswith("|")][0]
    assert [c.strip() for c in header.strip("|").split("|")] == ATTACK_COLUMNS
    for severity in ATTACK_SEVERITIES:
        assert severity in text, f"в шаблоне нет тяжести «{severity}»"
    assert "по спеке не выводится" in text, "в шаблоне нет строки воздержания"
    assert "coverage" in text, "в шаблоне нет линзы `coverage` для строк «чисто» и «не пройдено»"
    assert "инварианта не несут" in text, "в шаблоне нет исключения для строк покрытия"
    assert "повторить атаку по разделу" in text, "в закрытом списке закрытий нет «повторить атаку по разделу»"
    closing = last_line(text)
    assert closing == f"Вердикт: {VERDICT_RULE}.", closing
    assert "без опоры" not in text, "правило вердикта не считает «опору»: тяжесть несут только строки «нет»"


def test_attack_decisions_template_names_single_target():
    fm = frontmatter(template_text("attack-decisions.md")).splitlines()
    assert "target: decisions.json" in fm
    assert any(line.startswith("target_sha256:") for line in fm), fm


def test_attack_artifacts_template_lists_targets():
    fm = frontmatter(template_text("attack-artifacts.md")).splitlines()
    assert "targets:" in fm and not any(line.startswith("target") and not line.startswith("targets:")
                                        for line in fm), fm
    paths = [m.group(1) for line in fm if (m := re.match(r"\s+- path: (\S+)", line))]
    # журнал — первым: он опора артефактов, его правка обесценивает и этот вердикт (ruling Task 19)
    assert paths[0] == "decisions.json" and paths[1].startswith("specs/"), paths
    assert paths[2:] == ["design.md", "security.md", "tasks.md"], paths
    assert len([line for line in fm if re.match(r"\s+sha256:", line)]) == len(paths)


def test_research_template_shape():
    text = template_text("research.md")
    fm = frontmatter(text)
    genre_line = re.search(r"^genre:.*$", fm, re.M).group(0)
    for genre in ("устройство", "размещение", "края", "проверка", "аналоги"):
        assert genre in genre_line, genre
    assert re.search(r"^question: <F-NN>$", fm, re.M) and re.search(r"^brief:", fm, re.M), fm
    assert headings(text, 2) == ["Найдено", "Не найдено", "Вопросы, которые открылись"]
    assert "путь:строка" in text and "«цитата»" in text
    assert "не найдено" in text and "искал: " in text and "<шаблон" in text


@pytest.mark.parametrize("name", ["research.md", "attack-decisions.md"])
def test_templates_mark_record_number_as_placeholder(name):
    """Номер записи в шаблоне — подстановка `<F-NN>`: голый `F-NN` читается как настоящий номер."""
    text = template_text(name)
    assert "<F-NN>" in text and re.findall(r"(?<!<)F-NN(?!>)", text) == [], name


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
    context = section(text, "Context")
    assert "рендер ставит сюда факты с уликами" in context.lower() and "после последнего рендера" in context


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


def test_specs_instruction_names_scenario_form_with_given():
    assert "в виде GIVEN / WHEN / THEN" in schema_block("specs")


def test_instruction_wording_from_task7_review():
    assert ("форк OpenSpec symphysis считает артефакт готовым только с `status: passed`"
            in schema_block("attack-artifacts"))
    security = schema_block("security")
    assert "Канон (OWASP, инъекции, пути, токены) не записывается в журнал, а отмечается здесь" in security
    assert "prohibition probe" not in security
    research = schema_block("research")
    assert "«не найдено»" in research and "«искал: <шаблоны дословно>»" in research


def test_research_instruction_marks_record_number_as_placeholder():
    """Как в шаблоне `research.md`: номер записи — подстановка `<F-NN>`, голый `F-NN` читается как настоящий."""
    research = schema_block("research")
    assert "`research/<F-NN>.md`" in research and "`question: <F-NN>`" in research
    assert re.findall(r"(?<!<)F-NN(?!>)", research) == []


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


# --- config.yaml проекта: rules на артефакт --------------------------------

CONFIG_SAMPLE = ROOT / "openspec" / "config.symphysis.yaml"

DECISIONS_RULES = ["у каждого варианта улика — путь и цитата",
                   "маловероятный вариант показывается с причиной",
                   "адресат парковки — материалы, человек, ИБ"]

FORCE_STANCE = "FORCE stance: считай каждое утверждение неподкреплённым, пока улика не доказала обратное"

OTHER_RULES = {
    "specs": ["предположение помечается словом `предположение` и дорогой `проверить|решить`",
              "у каждого требования хотя бы один сценарий GIVEN/WHEN/THEN"],
    "design": ["решение излагается, не принимается"],
    "attack-decisions": [FORCE_STANCE],
    "attack-artifacts": [FORCE_STANCE],
    "security": ["канон не чеканится в журнал"],
}


def sample_project(tmp_path):
    """Проект, в котором `openspec/config.yaml` — образец `config.symphysis.yaml`."""
    return make_project(tmp_path, config=CONFIG_SAMPLE.read_text(encoding="utf-8"))


@requires_fork
def test_rules_reach_instructions(tmp_path):
    proj = sample_project(tmp_path)
    out = run_openspec(proj, "instructions", "decisions", "--change", "demo", "--json")
    assert out["rules"] == DECISIONS_RULES
    assert "decisions.json" in out["context"]


@requires_fork
@pytest.mark.parametrize("artifact_id", sorted(OTHER_RULES))
def test_sample_rules_reach_their_artifact(tmp_path, artifact_id):
    proj = sample_project(tmp_path)
    out = run_openspec(proj, "instructions", artifact_id, "--change", "demo", "--json")
    assert out["rules"] == OTHER_RULES[artifact_id]


@requires_fork
def test_artifact_without_rules_gets_none(tmp_path):
    """CLI отдаёт `rules` только непустым: у артефакта без правил ключа нет."""
    proj = sample_project(tmp_path)
    out = run_openspec(proj, "instructions", "research", "--change", "demo", "--json")
    assert "rules" not in out, out.get("rules")


@requires_fork
def test_sample_config_raises_no_warning_about_rules(tmp_path):
    """Правило с неэкранированным `: ` YAML читает как отображение, и CLI отбрасывает весь список
    артефакта с предупреждением в stderr; ключ, которого нет в схеме, тоже предупреждает."""
    proj = sample_project(tmp_path)
    done = run_openspec_raw(proj, "instructions", "decisions", "--change", "demo", "--json")
    stderr = done.stderr.lower()
    assert "rules" not in stderr and "ignoring" not in stderr and "unknown" not in stderr, done.stderr


@requires_fork
def test_sample_config_selects_symphysis_schema(tmp_path):
    """`schema: symphysis` образца: изменение, созданное без `--schema`, берёт схему из конфига."""
    proj = sample_project(tmp_path)
    run_openspec(proj, "new", "change", "by-config")
    out = run_openspec(proj, "status", "--change", "by-config", "--json")
    assert out["schemaName"] == "symphysis"


# --- заполненное изменение: фикстура change-demo ----------------------------

def test_change_demo_journal_is_valid():
    """Журнал фикстуры проходит `validate_journal` без форка; номер исследования указывает на запись,
    которой адресована парковка «материалы» (иначе фикстура непоследовательна)."""
    data = journal.load_journal(CHANGE_DEMO / "decisions.json")
    assert journal.validate_journal(data) == []
    records = {r["id"]: r for r in data["records"]}
    assert [(r["kind"], r["status"]) for r in records.values()] == [
        ("развилка", "решён"), ("развилка", "припаркован"), ("факт", "решён")]
    assert [p["addressee"] for p in records["F-02"]["parking"]] == ["материалы"]
    report = lf_text(CHANGE_DEMO / "research" / "F-02.md")
    assert re.search(r"^question: F-02$", frontmatter(report), re.M)
    assert re.search(r"^genre: устройство$", frontmatter(report), re.M)
    assert headings(report, 2) == ["Найдено", "Не найдено", "Вопросы, которые открылись"]
    assert not (CHANGE_DEMO / "attack").exists() and not (CHANGE_DEMO / "proposal.md").exists()


@requires_fork
def test_status_after_research(tmp_path):
    """Журнал и исследование на месте, атаки нет: `attack-decisions` готов к работе, `proposal` ждёт его."""
    proj = make_project(tmp_path, change_fixture=CHANGE_DEMO)
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    by_id = {a["id"]: a for a in out["artifacts"]}
    assert out["schemaName"] == "symphysis"
    assert by_id["decisions"]["status"] == "done" and by_id["research"]["status"] == "done"
    assert by_id["attack-decisions"]["status"] == "ready"
    assert by_id["proposal"]["status"] == "blocked"
    assert by_id["proposal"]["missingDeps"] == ["attack-decisions"]


# --- вердикт держит граф: фикстура change-demo-attack ----------------------

def artifacts_by_id(status):
    return {a["id"]: a for a in status["artifacts"]}


def write_attack_decisions(proj, verdict):
    """`attack/decisions.md` изменения `demo`: шаблон схемы с `status: <verdict>` во frontmatter."""
    text = template_text("attack-decisions.md")
    opening = "---\nstatus: gaps_found\n"
    assert text.startswith(opening), text[:40]
    path = proj / "openspec" / "changes" / "demo" / "attack" / "decisions.md"
    path.write_text(f"---\nstatus: {verdict}\n" + text[len(opening):], encoding="utf-8", newline="\n")


def test_change_demo_attack_extends_change_demo():
    """Фикстура с черновиком атаки — копия `change-demo` и один файл `attack/decisions.md` без frontmatter."""
    def files(root):
        return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())

    def table_header(text):
        return [row for row in text.splitlines() if row.startswith("|")][0]

    base = files(CHANGE_DEMO)
    assert files(CHANGE_DEMO_ATTACK) == sorted(base + ["attack/decisions.md"])
    for name in base:
        assert (CHANGE_DEMO_ATTACK / name).read_bytes() == (CHANGE_DEMO / name).read_bytes(), name
    draft = lf_text(CHANGE_DEMO_ATTACK / "attack" / "decisions.md")
    assert not draft.startswith("---") and "status:" not in draft, draft[:60]
    assert headings(draft, 1) == ["Атака журнала решений"]
    assert table_header(draft) == table_header(template_text("attack-decisions.md"))


@requires_fork
def test_verdict_blocks_proposal(tmp_path):
    """Файл `attack/decisions.md` без вердикта артефакт не закрывает, и `proposal` ждёт: `ready` с
    `verdict: missing` и подсказкой в `nextSteps`. Дописали `status: passed` — `done`, `proposal` `ready`."""
    proj = make_project(tmp_path, change_fixture=CHANGE_DEMO_ATTACK)
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    by_id = artifacts_by_id(out)
    assert by_id["attack-decisions"]["status"] == "ready"
    assert by_id["attack-decisions"]["verdict"] == "missing"
    assert out["nextSteps"][0].startswith('Artifact "attack-decisions" exists but has no verdict'), out["nextSteps"]
    assert by_id["proposal"]["status"] == "blocked"
    assert by_id["proposal"]["missingDeps"] == ["attack-decisions"]
    assert "verdict" not in by_id["proposal"] and "verdict" not in by_id["research"]

    write_attack_decisions(proj, "passed")
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    by_id = artifacts_by_id(out)
    assert by_id["attack-decisions"]["status"] == "done"
    assert by_id["attack-decisions"]["verdict"] == "ok"
    assert by_id["proposal"]["status"] == "ready"
    assert not any(step.startswith('Artifact "attack-decisions"') for step in out["nextSteps"]), out["nextSteps"]


@requires_fork
def test_verdict_gaps_found_keeps_proposal_blocked(tmp_path):
    """Вердикт `gaps_found` — не тот, что требует схема: артефакт остаётся `ready` с `verdict: mismatch`,
    `proposal` не открывается, подсказка называет найденное значение."""
    proj = make_project(tmp_path, change_fixture=CHANGE_DEMO_ATTACK)
    write_attack_decisions(proj, "gaps_found")
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    by_id = artifacts_by_id(out)
    assert by_id["attack-decisions"]["status"] == "ready"
    assert by_id["attack-decisions"]["verdict"] == "mismatch"
    assert out["nextSteps"][0].startswith('Artifact "attack-decisions" has verdict status=gaps_found'), out["nextSteps"]
    assert by_id["proposal"]["status"] == "blocked"


@requires_fork
def test_validate_all_rejects_change_without_deltas(tmp_path):
    """`openspec validate --all` на изменении без specs завершается кодом 1, и причина одна: у изменения
    нет дельт. Это устройство CLI, а не дефект фикстуры: код 0 изменение получает, когда `specs/`
    написаны (`test_filled_templates_pass_openspec_validate`) или в `.openspec.yaml` стоит
    `skip_specs: true`. `validate` разбирает только дельты в `specs/` (`validateChangeDeltaSpecs`):
    proposal, журнал и исследование он не читает, и изменение без proposal находит по каталогу."""
    proj = make_project(tmp_path, change_fixture=CHANGE_DEMO)
    out = run_openspec(proj, "validate", "--all", "--json", returncode=1)
    assert out["summary"]["totals"] == {"items": 1, "passed": 0, "failed": 1}, out
    [item] = out["items"]
    assert (item["id"], item["type"], item["valid"]) == ("demo", "change", False), item
    [issue] = item["issues"]
    assert issue["level"] == "ERROR" and issue["path"] == "file", issue
    assert issue["message"].startswith("Change must have at least one delta. No deltas found."), issue
    assert '"skip_specs: true"' in issue["message"], issue
