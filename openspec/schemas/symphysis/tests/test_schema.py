"""Схема OpenSpec `symphysis`: граф артефактов, как его разбирает CLI форка."""
import hashlib
import json
import os
import re
import shutil
import subprocess

import pytest

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import FORK_BIN, ROOT, SCHEMAS, fork_record, journal_of, make_project, requires_fork, run_openspec, run_openspec_raw
import journal

TEMPLATES = SCHEMAS / "symphysis" / "templates"
SCHEMA_YAML = SCHEMAS / "symphysis" / "schema.yaml"
CHANGE_DEMO = ROOT / "tests" / "fixtures" / "change-demo"
CHANGE_DEMO_ATTACK = ROOT / "tests" / "fixtures" / "change-demo-attack"
CHANGE_DEMO_NONE = ROOT / "tests" / "fixtures" / "change-demo-none"
CONSEQUENCES_FILLED = ROOT / "tests" / "fixtures" / "consequences-filled"

TEMPLATE_FILES = ["intent.md", "decisions.json", "research.md", "attack-decisions.md", "attack-artifacts.md",
                  "proposal.md", "spec.md", "consequences.md", "design.md", "security.md", "tasks.md"]

ARTIFACT_IDS = ["intent", "decisions", "research", "attack-decisions", "proposal", "specs", "consequences",
                "design", "security", "tasks", "attack-artifacts"]

REQUIRES = {
    "intent": [],
    "decisions": ["intent"],
    "research": ["decisions"],
    "attack-decisions": ["research"],
    "proposal": ["research", "attack-decisions"],
    "specs": ["proposal"],
    "consequences": ["specs"],
    "design": ["proposal", "consequences"],
    "security": ["specs"],
    "tasks": ["specs", "design"],
    "attack-artifacts": ["specs", "design", "security", "tasks"],
}


@requires_fork
def test_schema_parses_in_fork(tmp_path):
    proj = make_project(tmp_path, schema="symphysis")
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    ids = [a["id"] for a in out["artifacts"]]
    assert ids == ARTIFACT_IDS
    assert out["artifacts"][0]["status"] == "ready" and out["artifacts"][1]["status"] == "blocked"
    assert out["artifacts"][0]["id"] == "intent"


@requires_fork
def test_graph_edges_and_apply_gate(tmp_path):
    proj = make_project(tmp_path)
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    assert out["schemaName"] == "symphysis"
    assert {a["id"]: a["requires"] for a in out["artifacts"]} == REQUIRES
    assert {a["id"]: a["outputPath"] for a in out["artifacts"]} == {
        "intent": "intent.md", "decisions": "decisions.json", "research": "research/**/*.md",
        "attack-decisions": "attack/decisions.md", "proposal": "proposal.md",
        "specs": "specs/**/*.md", "consequences": "consequences.md", "design": "design.md", "security": "security.md",
        "tasks": "tasks.md", "attack-artifacts": "attack/artifacts.md"}
    assert out["applyRequires"] == ["tasks", "security", "attack-artifacts"]


@requires_fork
def test_apply_waits_for_security_checklist(tmp_path):
    """Сценарий «Реализация ждёт чек-лист»: `tasks` от `security` не зависит, а путь через `attack-artifacts`
    необязателен, поэтому без строки в `apply.requires` шаг пропускается молча."""
    proj = make_project(tmp_path)
    change = proj / "openspec" / "changes" / "demo"
    for rel in ("intent.md", "decisions.json", "research/none.md", "proposal.md", "specs/a/spec.md", "consequences.md", "design.md"):
        (change / rel).parent.mkdir(parents=True, exist_ok=True)
        (change / rel).write_text("x\n", encoding="utf-8")
    (change / "tasks.md").write_text("- [ ] 1.1 задача\n", encoding="utf-8")
    blocked = run_openspec(proj, "instructions", "apply", "--change", "demo", "--json")
    assert blocked["state"] == "blocked"
    assert blocked["missingArtifacts"] == ["security"]
    (change / "security.md").write_text("x\n", encoding="utf-8")
    assert run_openspec(proj, "instructions", "apply", "--change", "demo", "--json")["state"] == "ready"


@requires_fork
def test_new_change_intent_first_and_attacks_optional(tmp_path):
    """Сценарий «Новое изменение»: изменение без файлов — `intent` готов, `decisions` ждёт, обе атаки
    `optional`, гейт apply называет `tasks` (невызванная атака его не держит, вызванная — держит)."""
    proj = make_project(tmp_path)
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    by_id = artifacts_by_id(out)
    assert by_id["intent"]["status"] == "ready"
    assert by_id["decisions"]["status"] == "blocked" and by_id["decisions"]["missingDeps"] == ["intent"]
    assert by_id["attack-decisions"]["optional"] is True and by_id["attack-artifacts"]["optional"] is True
    assert not any("optional" in by_id[i] for i in by_id if i not in ("attack-decisions", "attack-artifacts"))
    assert "tasks" in out["applyRequires"]


@requires_fork
def test_research_none_file_closes_research(tmp_path):
    """Нуль парковок и `research/none.md` — исход `research` законный: `done`, `attack-decisions`
    (optional) без файла не держит `proposal`: он `ready`."""
    proj = make_project(tmp_path, change_fixture=CHANGE_DEMO_NONE)
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    by_id = artifacts_by_id(out)
    assert [by_id[i]["status"] for i in ("intent", "decisions", "research")] == ["done"] * 3
    assert by_id["attack-decisions"]["optional"] is True and by_id["attack-decisions"]["fileExists"] is False
    assert by_id["proposal"]["status"] == "ready"


@requires_fork
def test_planning_complete_without_called_attacks(tmp_path):
    """«Планирование без вызванных атак»: все артефакты, кроме двух атак, — планирование завершено."""
    proj = make_project(tmp_path, change_fixture=CHANGE_DEMO_NONE)
    change = proj / "openspec" / "changes" / "demo"
    for name in ("proposal.md", "specs/demo-cap/spec.md", "consequences.md", "design.md", "security.md", "tasks.md"):
        (change / name).parent.mkdir(parents=True, exist_ok=True)
        (change / name).write_text("заготовка\n", encoding="utf-8", newline="\n")
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    assert out["isPlanningComplete"] is True, out
    by_id = artifacts_by_id(out)
    assert by_id["attack-artifacts"]["fileExists"] is False


def change_with_specs(tmp_path):
    """Изменение с готовыми `specs`, но без описи: файлы артефактов до `specs` включительно — заготовки."""
    proj = make_project(tmp_path, change_fixture=CHANGE_DEMO_NONE)
    change = proj / "openspec" / "changes" / "demo"
    for name in ("proposal.md", "specs/demo-cap/spec.md"):
        (change / name).parent.mkdir(parents=True, exist_ok=True)
        (change / name).write_text("заготовка\n", encoding="utf-8", newline="\n")
    return proj, change


@requires_fork
def test_design_waits_for_the_inventory(tmp_path):
    """Сценарий «Дизайн ждёт опись»."""
    proj, _ = change_with_specs(tmp_path)
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    by_id = artifacts_by_id(out)
    assert by_id["consequences"]["status"] == "ready"
    assert by_id["design"]["status"] == "blocked" and "consequences" in by_id["design"]["missingDeps"]
    assert out["isPlanningComplete"] is False


@requires_fork
def test_inventory_opens_design(tmp_path):
    """Сценарий «Опись открывает дизайн»: файл с причиной открывает так же (сценарии «Нуль механизмов»,
    «Все колонки выключены»)."""
    proj, change = change_with_specs(tmp_path)
    for text in ("**Причина:** механизмов нет, искал: `throw`\n", "**Причина:** все колонки выключены настройками\n",
                 "**Состав:** ветки отказа, допущения\n\n## Опись\n"):
        (change / "consequences.md").write_text(text, encoding="utf-8", newline="\n")
        by_id = artifacts_by_id(run_openspec(proj, "status", "--change", "demo", "--json"))
        assert by_id["consequences"]["status"] == "done" and by_id["design"]["status"] == "ready", text


@requires_fork
def test_inventory_instruction(tmp_path):
    """Сценарий «Инструкция шага»: вывод несёт шаблон и называет скилл шага."""
    proj, _ = change_with_specs(tmp_path)
    out = run_openspec(proj, "instructions", "consequences", "--change", "demo", "--json")
    assert out["template"].replace("\r\n", "\n") == template_text("consequences.md")
    assert "symphysis-consequences" in out["instruction"]
    plain = run_openspec(proj, "instructions", "consequences", "--change", "demo")
    assert "symphysis-consequences" in plain and "## Опись" in plain


@requires_fork
def test_change_started_before_the_artifact(tmp_path):
    """Сценарий «Изменение, начатое до артефакта»: файл с причиной написан до правки схемы, `status` не ломается,
    планирование считается как раньше."""
    proj, change = change_with_specs(tmp_path)
    for name in ("design.md", "security.md", "tasks.md"):
        (change / name).write_text("заготовка\n", encoding="utf-8", newline="\n")
    (change / "consequences.md").write_text("**Причина:** шаг появился позже\n", encoding="utf-8", newline="\n")
    out = run_openspec(proj, "status", "--change", "demo", "--json")
    by_id = artifacts_by_id(out)
    assert by_id["consequences"]["status"] == "done" and by_id["design"]["status"] == "done"
    assert out["isPlanningComplete"] is True, out


def test_inventory_declared_before_security_and_design():
    """Backstop F-62: `/opsx:continue` берёт следующий артефакт в порядке объявления, поэтому опись идёт раньше
    `security`, хотя он её не требует."""
    text = SCHEMA_YAML.read_bytes().decode("utf-8")
    order = re.findall(r"^  - id: (\S+)$", text, re.M)
    assert order.index("specs") < order.index("consequences") < order.index("design") < order.index("security")


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
    """F-06: instruction короткий и называет скилл по имени; intent, design, security, tasks —
    правила без скилла. Второй круг брейншторма стоит в конце research, атака журнала — в attack-decisions."""
    proj = make_project(tmp_path)
    text = {i: run_openspec(proj, "instructions", i, "--change", "demo", "--json")["instruction"]
            for i in ARTIFACT_IDS}
    for i, t in text.items():
        # Предел один на все шаги, слово владельца, 2026-11-05: «в 120 слов мало какая инструкция вмещается»
        assert len(t.split()) <= 150, f"{i}: {len(t.split())} слов"
    assert "symphysis-brainstorm" in text["decisions"]
    assert "symphysis-attack" in text["attack-decisions"] and "symphysis-attack" in text["attack-artifacts"]
    assert "symphysis-edge-probe" in text["specs"] and "symphysis-prohibition-probe" in text["specs"]
    assert "symphysis-consequences" in text["consequences"]
    assert text["research"].lstrip().startswith("Загрузи скилл `symphysis-research`")
    assert "symphysis config" in text["consequences"]
    assert "symphysis journal code-sites" in text["consequences"]
    for i in ("intent", "design", "security", "tasks"):
        assert "symphysis-" not in text[i], f"{i}: правила без скилла"
    # research: второй круг брейншторма стоит в конце, после правил отчётов и none.md
    research = text["research"]
    second = research.index("Второй круг брейншторма")
    assert research.index("research/<F-NN>.md") < research.index("research/none.md") < second
    assert second < research.index("агент", second) < research.index("research/", second) < research.index("symphysis-brainstorm")
    assert research.rstrip().endswith("«брейншторм закончен по решению человека».")
    # финальное ревью, minor 11: вопрос о новом круге — только без строки отказа в notes[]
    assert "Нет в `notes[]` строки «брейншторм закончен по решению человека» — спроси, нужен ли новый круг" in research
    assert "Записи с парковкой «агент» без `finding` при файлах `research/` — сначала второй круг" in text["proposal"]
    attack = text["attack-decisions"].lstrip()
    assert attack.startswith("Загрузи скилл `symphysis-attack`"), attack[:60]
    for gone in ("Второй круг", "брейншторм закончен", "новый круг"):
        assert gone not in attack, gone
    assert "status: passed | gaps_found" in attack
    assert "Начни интервью с `intent.md`" in text["decisions"]
    # F-24.E, финальное ревью П.3: пустой intent.md засчитан форком — decisions спрашивает намерение до круга
    assert ("`intent.md` пуст (0 байт или одна строка заголовка) — сначала спроси намерение и сохрани ответ "
            "дословно по шаблону, затем круг.") in text["decisions"]
    assert "дословно" in text["intent"] and "Содержания не пиши" in text["intent"]


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
VERDICT_RULE = ("`status: passed` ставится, только когда в таблице нет ни одной строки с тяжестью `блокер`; "
                "строки `предупреждение` идут человеку списком и `apply` не держат, строки `справка` не блокируют")


@pytest.mark.parametrize("name", ["attack-decisions.md", "attack-artifacts.md"])
def test_attack_templates_table_and_verdict_rule(name):
    text = template_text(name)
    assert frontmatter(text).splitlines()[0] == "status: gaps_found"
    header = [row for row in text.splitlines() if row.startswith("|")][0]
    assert [c.strip() for c in header.strip("|").split("|")] == ATTACK_COLUMNS
    for severity in ATTACK_SEVERITIES:
        assert severity in text, f"в шаблоне нет тяжести «{severity}»"
    assert "по спеке не выводится" in text, "в шаблоне нет строки воздержания"
    assert "повторить атаку по разделу" in text, "в закрытом списке закрытий нет «повторить атаку по разделу»"
    closing = last_line(text)
    assert closing == f"Вердикт: {VERDICT_RULE}.", closing
    assert "без опоры" not in text, "правило вердикта не считает «опору»: тяжесть несут только строки «нет»"


# Закрытые списки линз по файлу атаки — те же, что в SKILL.md `symphysis-attack` и в просмотрщике (F-07.A);
# линзы присутствия сняты.
TEMPLATE_LENSES = {"attack-decisions.md": ("context-compliance", "claim-authority", "claim-extraction", "coverage"),
                   "attack-artifacts.md": ("scenario-run", "claim-extraction", "trace-link", "rule-compliance")}
REMOVED_LENS_SLUGS = ("requirement-coverage", "task-completeness", "dependency-correctness", "key-links",
                      "scope-sanity", "verification-derivation", "scope-reduction", "data-contracts",
                      "research-resolution", "honest-verifier")


@pytest.mark.parametrize("name", TEMPLATE_LENSES)
def test_attack_templates_name_own_closed_lens_list(name):
    text = template_text(name)
    lenses = ", ".join(TEMPLATE_LENSES[name])
    assert f"закрытого списка скилла symphysis-attack для этого файла: {lenses}." in text, \
        f"шаблон {name} не называет свой список линз: {lenses}"
    for slug in REMOVED_LENS_SLUGS:
        assert slug not in text, f"в шаблоне {name} осталась снятая линза {slug}"


@pytest.mark.parametrize("name", TEMPLATE_LENSES)
def test_attack_templates_name_lens_composition(name):
    """`artifact-attack`: «Всё включено», «Выключена линза», «Выключены все линзы» (F-61, F-63, F-106):
    строка `**Состав:**` стоит в файле при любом составе, в ней только линзы этого файла."""
    text = template_text(name)
    lines = [line for line in text.splitlines() if line.startswith("**Состав:**")]
    assert len(lines) == 1, f"в шаблоне {name} нужна одна строка `**Состав:**`"
    assert lines[0] == "**Состав:** включены <слуги>; выключены <слуги или —>", lines[0]
    comment = next(line for line in text.splitlines() if line.startswith("<!-- Состав"))
    for token in ("symphysis config", "при любом составе", "и при всех включённых",
                  "выключенная линза строк не даёт", "таблица пуста", "заголовок остаётся", "status: passed",
                  "модель состав не меняет"):
        assert token in comment, f"в комментарии о составе шаблона {name} нет «{token}»"
    for slug in TEMPLATE_LENSES[name]:
        assert slug in comment, f"в комментарии о составе шаблона {name} нет линзы {slug}"
    other = next(n for n in TEMPLATE_LENSES if n != name)
    for slug in set(TEMPLATE_LENSES[other]) - set(TEMPLATE_LENSES[name]):
        assert slug not in comment, f"в шаблоне {name} линза чужого файла {slug}"


def test_attack_artifacts_template_goal_missing_is_claim_extraction():
    """`artifact-attack`: «Цели нет» — строка `claim-extraction`, не `coverage`."""
    text = template_text("attack-artifacts.md")
    assert "Цели нет — строка claim-extraction с именем файла, опора «нет: файла нет», тяжесть блокер" in text
    assert "trace-link" in text.split("| Утверждение |")[0], "комментарии шаблона не называют строку `trace-link`"
    assert "Строка rule-compliance" in text.split("| Утверждение |")[0], "комментарии шаблона не называют строку `rule-compliance`"


def test_attack_decisions_template_keeps_coverage_rows():
    text = template_text("attack-decisions.md")
    assert "линза coverage" in text, "в шаблоне журнала нет линзы `coverage` для строк «чисто» и «не пройдено»"
    assert "инварианта не несут" in text, "в шаблоне нет исключения для строк покрытия"


def test_attack_artifacts_template_covers_by_scenarios():
    """У артефактов строк `coverage` нет: покрытие держит `scenario-run` — каждый сценарий в строке,
    непройденный — «нет: не пройдено», механизм не назван — «нет: design не называет механизм»."""
    text = template_text("attack-artifacts.md")
    assert "coverage" not in text, "у артефактов строк покрытия `coverage` нет (F-07.A)"
    for token in ("каждый сценарий каждой спеки цели", "нет: не пройдено", "нет: design не называет механизм",
                  "исход совпал", "THEN"):
        assert token in text, f"в шаблоне артефактов нет «{token}»"


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
    assert paths[2:] == ["consequences.md", "design.md", "security.md", "tasks.md"], paths
    assert len([line for line in fm if re.match(r"\s+sha256:", line)]) == len(paths)


def test_research_template_shape():
    text = template_text("research.md")
    fm = frontmatter(text)
    genre_line = re.search(r"^genre:.*$", fm, re.M).group(0)
    for genre in ("устройство", "размещение", "края", "проверка", "аналоги"):
        assert genre in genre_line, genre
    assert re.search(r"^question: <F-NN>$", fm, re.M) and re.search(r"^brief:", fm, re.M), fm
    assert headings(text, 2) == ["Найдено", "Не найдено", "Проба", "Вопросы, которые открылись"]
    assert "путь:строка" in text and "«цитата»" in text
    assert "не найдено" in text and "искал: " in text and "<шаблон" in text


@pytest.mark.parametrize("name", ["research.md", "attack-decisions.md", "consequences.md"])
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


def test_spec_template_puts_the_trail_after_the_scenario():
    """Сценарий «Шаблон ставит след после сценария»: след в конце блока требования, в предел 500 символов не идёт."""
    text = template_text("spec.md")
    scenario = text.index("#### Scenario: ")
    assert scenario < text.index("<!-- проба краёв: ") and scenario < text.index("<!-- проба запретов: ")
    assert "проба краёв: выключена настройкой" in text


def test_consequences_template_shape():
    """4.2: `**Состав:**` одной строкой, три раздела, все формы строки описи."""
    text = template_text("consequences.md")
    assert headings(text, 2) == ["Опись", "Исключения", "Pre-mortem"]
    assert len(re.findall(r"^\*\*Состав:\*\* ", text, re.M)) == 1
    assert "- **<механизм>** — `путь:строка` «цитата»" in text
    for sub in ("при отказе:", "допущение:", "сценарий:", "кандидат: <F-NN>"):
        assert sub in section(text, "Опись"), sub
    assert "- **<механизм>** (`<путь>`) — допущение: " in text
    assert "- **<механизм>** (`<путь>`): веток отказа не найдено, искал: <шаблоны>" in text
    assert "выключены настройкой" in text


def test_consequences_template_reason_is_a_sample_not_a_line():
    """`**Причина:**` стоит образцом внутри комментария: шаблон, скопированный как есть, сверку мест не снимает."""
    text = template_text("consequences.md")
    assert "**Причина:** механизмов нет" in text and "**Причина:** все колонки выключены настройками" in text
    assert not re.search(r"^\s*\*\*Причина:\*\*", text, re.M)


def test_unfilled_consequences_template_keeps_the_sites_check(tmp_path):
    """Скрипт читает шаблон как опись без мест: `[!!]` на место, цитат в образцах нет."""
    file = tmp_path / "consequences.md"
    file.write_text(template_text("consequences.md"), encoding="utf-8")
    data = journal_of(fork_record("F-01", "A", A=["src/Foo.java"]))
    assert journal.check_consequences(data, file, {"": tmp_path}) == {
        "missing": ["consequences.md: src/Foo.java — нет ни разбора, ни исключения с причиной"], "unchecked": []}


def test_filled_consequences_sample_passes_the_checks():
    """4.2: заполненный образец по шаблону проходит обе проверки: разобранное место, место без веток, исключённое."""
    data = journal.load_journal(CONSEQUENCES_FILLED / "decisions.json")
    assert journal.validate_journal(data) == []
    roots = {"": CONSEQUENCES_FILLED}
    assert set(journal.code_sites(data, roots)["sites"]) == {"src/retry.js", "src/plain.js", "src/skipped.js"}
    assert journal.check_consequences(data, CONSEQUENCES_FILLED / "consequences.md", roots) == {
        "missing": [], "unchecked": []}
    assert journal.check_evidence(data, roots)["missing"] == []
    filled = lf_text(CONSEQUENCES_FILLED / "consequences.md")
    assert headings(filled, 2) == headings(template_text("consequences.md"), 2)
    assert re.search(r"^\*\*Состав:\*\* ветки отказа, допущения$", filled, re.M)


def test_filled_consequences_sample_breaks_on_a_wrong_quote(tmp_path):
    """Контроль образца: та же опись с испорченной цитатой даёт сигнал, значит прохождение выше не пустое."""
    filled = lf_text(CONSEQUENCES_FILLED / "consequences.md")
    good = "«if (attempts > limit || reply == null) return null;»"
    assert good in filled
    broken = tmp_path / "consequences.md"
    broken.write_text(filled.replace(good, "«if (attempts >= limit || reply == null) return null;»"), encoding="utf-8")
    data = journal.load_journal(CONSEQUENCES_FILLED / "decisions.json")
    result = journal.check_consequences(data, broken, {"": CONSEQUENCES_FILLED})
    assert result["missing"] == ["consequences.md: src/retry.js «if (attempts >= limit || reply == null) return null;» "
                                 "— цитаты нет дословно"]
def test_design_template_marks_generated_sections():
    text = template_text("design.md")
    assert headings(text, 2) == ["Context", "Goals / Non-Goals", "Decisions", "Risks / Trade-offs",
                                 "Migration Plan", "Open Questions"]
    for title in ("Decisions", "Risks / Trade-offs", "Open Questions"):
        assert "генерируется `symphysis journal render-design`" in section(text, title), title
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
    assert headings(text, 2) == ["Why", "What Changes", "Capabilities", "Impact", "Отступления от постановки"]
    assert headings(text, 3) == ["New Capabilities", "Modified Capabilities"]
    assert section(text, "Отступления от постановки").strip().splitlines()[-1] == "нет"
    assert "F-MM против F-NN" in text and "Уточнение без противоречия" in text


def test_proposal_deviations_come_from_the_deviation_field():
    """5.1, решения контроллера 3 и ruling (F-28.E): раздел «Отступления от постановки» перечисляет решённые
    развилки, чей выбранный вариант несёт поле `deviation` — строкой «F-MM против F-NN — <вариант>»."""
    comment = section(template_text("proposal.md"), "Отступления от постановки")
    instruction = " ".join(schema_block("proposal").split())
    for text in (comment, instruction):
        for token in ("чей выбранный вариант несёт поле `deviation`", "`addressee: постановка`",
                      "«F-MM против F-NN — <вариант>»"):
            assert token in text, token


def test_tasks_template_follows_openspec_checkbox_grammar():
    text = template_text("tasks.md")
    assert re.findall(r"^## (\d+)\. ", text, re.M) == ["1", "2"]
    assert re.findall(r"^- \[ \] (\d+\.\d+) ", text, re.M) == ["1.1", "1.2", "2.1", "2.2"]
    assert "проверка:" in text


def instruction_text(tmp_path, artifact_id):
    """Инструкция артефакта из `openspec instructions`, пробелы и переводы строк сжаты."""
    out = run_openspec(make_project(tmp_path), "instructions", artifact_id, "--change", "demo", "--json")
    return " ".join(out["instruction"].split())


def test_specs_instruction_names_record_numbers_and_splitting(tmp_path):
    """`trace-conventions`: «Требование из решения», «Требование не влезает в предел»,
    «Старое длинное требование в MODIFIED», «Условие пропало при делении» (F-44, F-76, F-77, F-91, F-117, F-150)."""
    text = instruction_text(tmp_path, "specs")
    for token in ("`(F-NN)`", "500 знаков", "дочернее", "Часть требования «имя».",
                  "``Часть требования `capability`: «имя».``", "MODIFIED", "сценарии родителя остаются при нём",
                  "условия не теряются", "свой номер", "номер берётся из журнала",
                  "записи нет — заведи кандидата", "номер без записи не ставь"):
        assert token in text, token
    assert len(text.split()) <= 150, len(text.split())


def test_tasks_instruction_names_scenario_form_and_service_mark(tmp_path):
    """`trace-conventions`: «Имя вписано ради отчёта» (F-42, F-43, F-89, F-90, F-115)."""
    text = instruction_text(tmp_path, "tasks")
    for token in ("`` `capability`: «сценарий» ``", "у каждого имени", "`` `служебная` ``", "в конце строки",
                  "потому что задача закрывает сценарий", "`` `a`: «А», `a`: «Б» ``"):
        assert token in text, token
    assert len(text.split()) <= 150, len(text.split())


FREEZE_COMMAND = "symphysis trace freeze"


def ready_apply_project(tmp_path):
    """Проект с изменением, у которого есть всё для `apply` и одна неотмеченная задача: состояние `ready`."""
    proj = make_project(tmp_path)
    change = proj / "openspec" / "changes" / "demo"
    for rel in ("intent.md", "decisions.json", "research/none.md", "proposal.md", "specs/a/spec.md",
                "consequences.md", "design.md", "security.md"):
        (change / rel).parent.mkdir(parents=True, exist_ok=True)
        (change / rel).write_text("x\n", encoding="utf-8")
    (change / "tasks.md").write_text("- [ ] 1.1 задача\n", encoding="utf-8")
    return proj


@requires_fork
def test_apply_instruction_calls_freeze_and_hands_link(tmp_path):
    """`trace-signals`: «Перед первой задачей», «После последней задачи», «Модель отдаёт отчёт», «Модель видит зазор»,
    «Решение Specify у записи `[сигнал]`»; `trace-snapshot`: «Перед первой задачей», «Последняя задача отмечена»
    (F-48, F-78, F-99, F-112, F-113, F-134). Прежние строки инструкции на месте, предел слов тот же."""
    out = run_openspec(ready_apply_project(tmp_path), "instructions", "apply", "--change", "demo", "--json")
    assert out["state"] == "ready"
    text = " ".join(out["instruction"].split())
    for token in (FREEZE_COMMAND + " <имя>", "Перед первой задачей", "последняя", "`graph/report.md`",
                  "без пересказа и без отбора строк", "не повод править спеки и задачи без слова человека",
                  "`[сигнал]`", "Specify", "`outcome`", "`<!-- F-NN -->`",
                  "Строки `предупреждение` в файлах `attack/*.md`", "Остановись, если упёрся в блокер"):
        assert token in text, token
    assert len(text.split()) <= 150, len(text.split())


def test_tasks_template_shows_scenario_form_and_service_mark():
    """`trace-conventions`: «Имя вписано ради отчёта» (F-42, F-43, F-90): образцы формы в двойных обратных кавычках."""
    text = template_text("tasks.md")
    assert "`` `capability`: «сценарий» ``" in text
    assert "`` `служебная` ``" in text
    assert not re.search(r"(?<!`)`служебная`$", text, re.M), "пометка в шаблоне не должна быть живой"


# --- schema.yaml: шаблоны, пути скриптов, формулировки ---------------------

def test_schema_points_each_artifact_at_its_own_template():
    for artifact_id, template in {"intent": "intent.md", "decisions": "decisions.json", "research": "research.md",
                                  "attack-decisions": "attack-decisions.md", "proposal": "proposal.md",
                                  "specs": "spec.md", "consequences": "consequences.md", "design": "design.md",
                                  "security": "security.md",
                                  "tasks": "tasks.md", "attack-artifacts": "attack-artifacts.md"}.items():
        assert re.search(rf"^    template: {re.escape(template)}$", schema_block(artifact_id), re.M), artifact_id


def test_instructions_use_selected_runtime_dispatcher():
    """Схема работает с global-only и local-only: runtime не ищется внутри store."""
    text = SCHEMA_YAML.read_bytes().decode("utf-8")
    assert "symphysis journal check" in schema_block("decisions")
    assert "symphysis journal render-design" in schema_block("design")
    assert "symphysis trace freeze" in text
    assert ".symphysis/tools/" not in text
    assert 'generates: "specs/**/*.md"' in text, "пути данных store должны сохраниться"


def test_specs_instruction_names_scenario_form_with_given():
    assert "в виде GIVEN / WHEN / THEN" in schema_block("specs")


def test_instruction_wording_from_task7_review():
    assert ("форк OpenSpec symphysis считает артефакт готовым только с `status: passed`"
            in schema_block("attack-artifacts"))
    security = schema_block("security")
    assert "Канон (OWASP, инъекции, пути, токены, чувствительные данные) не записывается в журнал, а отмечается здесь" in security
    assert "prohibition probe" not in security
    research = schema_block("research")
    assert "«не найдено»" in research and "«искал: <шаблоны дословно>»" in research


def test_research_instruction_and_template_carry_none_rule():
    """F-16.A: нуль парковок — `research/none.md` (`question: none`, отрицание по рецепту); первая парковка
    «агент» удаляет `none.md`. Оба правила — и в instruction, и в шаблоне."""
    for text in (schema_block("research"), template_text("research.md")):
        assert "research/none.md" in text and "question: none" in text
        assert "не найдено" in text and "искал: <шаблоны дословно>" in text
        assert "addressee: агент" in text
        assert "удали `none.md`" in text


def test_intent_template_and_instruction():
    text = template_text("intent.md")
    assert headings(text, 1) == ["Намерение: <имя изменения>"] and headings(text, 2) == ["Намерение", "Критерии готовности"]
    assert "Без критериев готовности" in text and "дословно" in text
    block = schema_block("intent")
    assert "generates: intent.md" in block and "template: intent.md" in block and "requires: []" in block
    assert "спроси намерение у человека" in block and "дословно" in block
    assert "optional: true" in schema_block("attack-decisions") and "optional: true" in schema_block("attack-artifacts")
    assert "optional" not in schema_block("proposal")
    assert re.search(r"requires:\n\s+- intent\n", schema_block("decisions"))
    assert re.search(r"requires:\n\s+- research\n\s+- attack-decisions\n", schema_block("proposal"))


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
    комментарии с пробами после сценария ему не мешают."""
    proj = make_project(tmp_path)
    write_filled_templates(proj, "Система SHALL работать.")
    out = run_openspec(proj, "validate", "demo", "--strict", "--json")
    assert out["summary"]["totals"] == {"items": 1, "passed": 1, "failed": 0}, out


def write_filled_templates(proj, requirement, edit_spec=lambda text: text):
    """Заполненные шаблоны proposal, spec и tasks изменения `demo`; `requirement` — текст требования,
    `edit_spec` правит готовый текст спеки."""
    change = proj / "openspec" / "changes" / "demo"
    fill = lambda text: re.sub(r"<(?!!--)[^<>\n]*>", "заполнено", text)
    why = "Нужно проверить, что шаблоны схемы разбираются CLI так же, как шаблоны spec-driven."
    purpose = "Проверка формы шаблона spec.md на живом разборе CLI форка OpenSpec: грамматика требований."
    spec = fill(template_text("spec.md")).replace("## Purpose\n", f"## Purpose\n{purpose}\n")
    files = {
        "proposal.md": fill(template_text("proposal.md")).replace("## Why\n", f"## Why\n\n{why}\n")
                                                          .replace("## What Changes\n", "## What Changes\n\n- Новая capability.\n"),
        "specs/demo-cap/spec.md": edit_spec(spec.replace("Система SHALL заполнено.", requirement)),
        "tasks.md": fill(template_text("tasks.md")),
    }
    for name, text in files.items():
        (change / name).parent.mkdir(parents=True, exist_ok=True)
        (change / name).write_text(text, encoding="utf-8", newline="\n")


def long_requirement_and_trail():
    """Текст требования на 400 символов и след проб на 200."""
    requirement = "Система SHALL работать " + "а" * 377
    trail = "<!-- проба краёв: " + "б" * 178 + " -->"
    assert (len(requirement), len(trail)) == (400, 200)
    return requirement, trail


@requires_fork
def test_long_trail_does_not_colour_validation(tmp_path):
    """Сценарий «Длинный след не красит валидацию»: след после сценария в предел не идёт."""
    proj = make_project(tmp_path)
    requirement, trail = long_requirement_and_trail()
    write_filled_templates(proj, requirement, edit_spec=lambda text: text.replace(
        "- **THEN** заполнено\n", f"- **THEN** заполнено\n{trail}\n", 1))
    out = run_openspec(proj, "validate", "demo", "--strict", "--json")
    assert out["summary"]["totals"] == {"items": 1, "passed": 1, "failed": 0}, out


@requires_fork
def test_trail_above_the_scenario_would_colour_validation(tmp_path):
    """Контроль сценария выше: тот же след над сценарием идёт в предел, и `--strict` отказывает. Без этого
    теста зелёное выше ничего не доказывает."""
    proj = make_project(tmp_path)
    requirement, trail = long_requirement_and_trail()
    write_filled_templates(proj, requirement, edit_spec=lambda text: text.replace(
        requirement + "\n", f"{requirement}\n{trail}\n", 1))
    out = run_openspec(proj, "validate", "demo", "--strict", "--json", returncode=1)
    assert out["summary"]["totals"]["failed"] == 1, out


# --- config.yaml проекта: rules на артефакт --------------------------------

CONFIG_SAMPLE = SCHEMAS / "symphysis" / "config.symphysis.yaml"   # образец конфига — файл модуля схемы (F-37 A)

DECISIONS_RULES = ["у каждого варианта улика — путь и цитата",
                   "маловероятный вариант показывается с причиной",
                   "адресат парковки — агент, человек, ИБ"]

FORCE_STANCE = "FORCE stance: считай каждое утверждение неподкреплённым, пока улика не доказала обратное"
# Правило «сначала запись» (D7, F-26): вывод модели — развилка, а не строка поставки; стоит у артефактов,
# в которые выбор модели попадает, минуя просмотрщик (две утечки 2026-10-30).
RECORD_FIRST = ("утверждение о механике, цели или ограничении без записи F-NN — предположение: "
                "сначала запись в журнал (развилка с рекомендацией), потом артефакт")

OTHER_RULES = {
    "specs": ["предположение помечается словом `предположение` и дорогой `проверить|решить`",
              "у каждого требования хотя бы один сценарий GIVEN/WHEN/THEN",
              "след проб — комментарии «проба краёв» и «проба запретов» — в общую спеку при синхронизации не переносится",
              "ссылки на записи этого изменения в общей спеке стоят в форме якоря `<изменение>/F-NN`; "
              "унаследованные голые ссылки и якоря других изменений сохраняют своё происхождение"],
    "proposal": [RECORD_FIRST],
    "design": ["решение излагается, не принимается", RECORD_FIRST],
    "tasks": [RECORD_FIRST],
    "attack-decisions": [FORCE_STANCE],
    "attack-artifacts": [FORCE_STANCE],
    "security": ["канон не чеканится в журнал"],
}


def sample_rules():
    """Правила образца `config.symphysis.yaml` словарём артефакт -> список строк, без YAML-библиотеки:
    форма файла — `rules:` → `  <артефакт>:` → `    - "<правило>"`; строка не по форме — AssertionError."""
    rules, key, inside = {}, None, False
    for line in CONFIG_SAMPLE.read_text(encoding="utf-8").splitlines():
        if line.startswith("rules:"):
            inside = True
            continue
        if not inside or not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            break
        if (m := re.match(r"^  (\S+):\s*$", line)):
            key = m.group(1)
            rules[key] = []
            continue
        m = re.match(r'^    - "(.*)"\s*$', line)
        assert m and key, f"строка правил не по форме: {line!r}"
        rules[key].append(m.group(1))
    return rules


def test_sample_config_rules_say_record_first():
    """Без форка: набор правил образца равен константам тестов; «сначала запись» — у proposal, design, tasks."""
    rules = sample_rules()
    assert rules == {"decisions": DECISIONS_RULES, **OTHER_RULES}
    for artifact in ("proposal", "design", "tasks"):
        assert RECORD_FIRST in rules[artifact], artifact
    assert rules["design"][0] == "решение излагается, не принимается"


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


def operation_guidance(project):
    return run_openspec(project, "instructions", "archive", "--change", "demo", "--json").get("operationGuidance")


@requires_fork
@pytest.mark.parametrize("config_path", [CONFIG_SAMPLE, ROOT / "openspec" / "config.yaml"], ids=["sample", "legacy-core"])
def test_archive_guidance_reaches_instructions(tmp_path, config_path):
    """`trace-snapshot`: «Снимка нет», «Снимок устарел», «Сборка не удалась», «Сборка при всех отмеченных задачах»,
    «Синхронизация внутри архивации» (F-49, F-75, F-127, F-128, F-139): подсказка операции — список строк ключа
    `operations.archive.guidance`, CLI отдаёт его полем `operationGuidance`."""
    proj = make_project(tmp_path, config=config_path.read_text(encoding="utf-8"))
    guidance = operation_guidance(proj)
    assert isinstance(guidance, list) and guidance and all(isinstance(g, str) for g in guidance)
    text = " ".join(guidance)
    # Existing local planning config is data; migrating the supplied sample must
    # not silently rewrite it. The fork still transports that legacy guidance.
    freeze_command = FREEZE_COMMAND if config_path == CONFIG_SAMPLE else "python .symphysis/tools/trace_graph.py freeze"
    for token in (freeze_command + " <имя>", "до выбора синхронизации", "Граф собран заново", "Снимок свежий", "`graph/report.md`",
                  "ошибку", "назови человеку", "архивацию не останавливай"):
        assert token in text, token


@requires_fork
def test_sample_config_with_operations_raises_no_warning(tmp_path):
    """Форма ключа `operations` верна: форк не предупреждает ни об ключе, ни о подсказке."""
    proj = sample_project(tmp_path)
    done = run_openspec_raw(proj, "instructions", "archive", "--change", "demo", "--json")
    stderr = done.stderr.lower()
    assert "guidance" not in stderr and "operation" not in stderr and "ignoring" not in stderr, done.stderr


# --- заполненное изменение: фикстура change-demo ----------------------------

def test_change_demo_journal_is_valid():
    """Журнал фикстуры проходит `validate_journal` без форка; номер исследования указывает на запись,
    которой адресована парковка «агент» (иначе фикстура непоследовательна)."""
    data = journal.load_journal(CHANGE_DEMO / "decisions.json")
    assert journal.validate_journal(data) == []
    records = {r["id"]: r for r in data["records"]}
    assert [(r["kind"], r["status"]) for r in records.values()] == [
        ("развилка", "решён"), ("развилка", "припаркован"), ("факт", "решён")]
    assert [p["addressee"] for p in records["F-02"]["parking"]] == ["агент"]
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
    assert by_id["proposal"]["status"] == "ready"


# --- вердикт держит граф: фикстура change-demo-attack ----------------------

def artifacts_by_id(status):
    return {a["id"]: a for a in status["artifacts"]}


def write_attack_decisions(proj, verdict):
    """`attack/decisions.md` изменения `demo`: шаблон схемы с `status: <verdict>` во frontmatter."""
    text = template_text("attack-decisions.md")
    opening = "---\nstatus: gaps_found\n"
    assert text.startswith(opening), text[:40]
    change = proj / "openspec" / "changes" / "demo"
    # хеш цели — SHA-256 сырых байтов журнала: пустой `target_sha256` форк читает как устаревший вердикт
    digest = hashlib.sha256((change / "decisions.json").read_bytes()).hexdigest()
    body = text[len(opening):].replace("target_sha256:\n", f"target_sha256: {digest}\n", 1)
    (change / "attack" / "decisions.md").write_text(f"---\nstatus: {verdict}\n" + body, encoding="utf-8", newline="\n")


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


# --- decision-scheme: схема не артефакт, ответ парковке «агент» добывает агент исследования (F-12, F-41, F-99, F-112) ---

def test_scheme_is_not_an_artifact_and_blocks_nothing(tmp_path):
    """Сценарий «Схемы нет»: без `scheme.md` ни один шаг не заблокирован из-за него."""
    proj = make_project(tmp_path)
    status = run_openspec(proj, "status", "--change", "demo", "--json")
    assert all("scheme" not in a["id"] for a in status["artifacts"])
    schema = (ROOT / "openspec" / "schemas" / "symphysis" / "schema.yaml").read_text(encoding="utf-8")
    assert "scheme.md" not in schema


def test_research_answer_may_come_from_a_probe():
    """Сценарии «Ответ добыт пробой», «Проба без следа», «Инструкция `research`»."""
    schema = (ROOT / "openspec" / "schemas" / "symphysis" / "schema.yaml").read_text(encoding="utf-8")
    research = schema[schema.index("- id: research"):schema.index("- id: attack-decisions")]
    for token in ("пробой", "раздел «Проба»", "«следа нет»", "не пишет вне `research/` и временного каталога"):
        assert token in research, f"в instruction research нет «{token}»"
    template = (ROOT / "openspec" / "schemas" / "symphysis" / "templates" / "research.md").read_text(encoding="utf-8")
    assert "## Проба" in template and "«следа нет»" in template


# --- parking-addressee-agent: адресат парковки — «агент», старое значение только у старых журналов (F-17.A) ---

OLD_ADDRESSEE_MARKS = ("«материалы»", "`материалы`", "addressee: материалы", "парковки — материалы", "к материалам")


def test_schema_texts_name_the_agent_addressee_not_the_old_value():
    """Сценарии «Отчёт по парковке», «Нуль парковок», «Парковка после none.md»: instruction `research` и `proposal`,
    `steps.md`, шаблон и оба конфига читают адресата `агент`; «материалы» остаётся только словом о материалах
    изменения («где искать материалы»), не значением адресата."""
    symphysis = ROOT / "openspec" / "schemas" / "symphysis"
    live = {
        "schema.yaml": (symphysis / "schema.yaml").read_text(encoding="utf-8"),
        "steps.md": (symphysis / "steps.md").read_text(encoding="utf-8"),
        "templates/research.md": template_text("research.md"),
        "config.symphysis.yaml": CONFIG_SAMPLE.read_text(encoding="utf-8"),
        "openspec/config.yaml": (ROOT / "openspec" / "config.yaml").read_text(encoding="utf-8"),
    }
    for name, text in live.items():
        for mark in OLD_ADDRESSEE_MARKS:
            assert mark not in text, f"{name}: старое значение адресата «{mark}»"
    research = schema_block("research")
    assert "На каждую парковку с адресатом «агент»" in research and "`addressee: агент`" in research
    assert "закрой записи с адресатом «агент»" in research
    assert "Записи с парковкой «агент» без `finding`" in schema_block("proposal")
    assert "парковка адресату `агент`, её разберёт исследование" in live["steps.md"]
    assert "Парковку адресату «агент» закрывает шаг `research`" in live["steps.md"]
    assert "где искать материалы" in live["steps.md"], "материалы изменения — другой смысл, слово остаётся"
    assert "Нуль парковок «агент»" in live["templates/research.md"]
    for name in ("config.symphysis.yaml", "openspec/config.yaml"):
        assert "адресат парковки — агент, человек, ИБ" in live[name], name
