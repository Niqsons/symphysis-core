"""`openspec/schemas/symphysis/steps.md`: раздел на шаг и подразделы (F-20, F-27), имена скиллов и файлов сверены со
скиллами модулей и `schema.yaml` (тест-страховка F-68). Содержание не проверяется: человек ещё будет его менять."""
import fnmatch
import json
import re

# conftest — первым: он ставит каталоги модулей в sys.path и при запуске одного файла (pytest.ini, pythonpath)
from conftest import ROOT, skill_dirs
import openspec_run
import step_help

STEPS_MD = ROOT / "openspec" / "schemas" / "symphysis" / "steps.md"
SCHEMA_YAML = ROOT / "openspec" / "schemas" / "symphysis" / "schema.yaml"
SKILLS = {path.name: path for path in skill_dirs()}   # скиллы всех модулей по имени (F-67 A)
REQUIRED = ("Зачем", "Механики", "Если пропустить", "Что смотреть", "Команда")

# Файлы, которых нет ни в схеме, ни в скиллах: имя страницы задаёт спека `decision-viewer`,
# каталоги общих спек и архива ведёт сам форк.
OUTSIDE_SCHEMA = ("symphysis.html", "openspec/specs/", "openspec/changes/archive/<дата>-<имя>/")

FILE_TOKEN = re.compile(r"`([^`\s]*(?:/|\.[a-z]+)[^`\s]*)`")
SKILL_TOKEN = re.compile(r"`(symphysis-[\w-]+)`")


def steps_text() -> str:
    return STEPS_MD.read_bytes().decode("utf-8").replace("\r\n", "\n")


def schema_text() -> str:
    return SCHEMA_YAML.read_bytes().decode("utf-8").replace("\r\n", "\n")


def artifact_ids() -> list[str]:
    return re.findall(r"^  - id: (\S+)$", schema_text(), re.M)


def section_problems(text: str, artifacts: list[str]) -> list[str]:
    """Что не так с разделами: шаг без раздела, раздел без шага, раздел без названия или подраздела. Каждая строка
    называет раздел; подраздел только с заголовком не считается написанным."""
    sections = step_help.parse_steps(text)
    known = [*artifacts, "viewer", *step_help.AFTER_ARTIFACTS]
    problems = [f"{step}: нет раздела" for step in known if step not in sections]
    problems += [f"{step}: раздел без шага" for step in sections if step not in known]
    for step, parts in sections.items():
        if not parts["title"]:
            problems.append(f"{step}: нет названия")
        problems += [f"{step}: нет подраздела «{title}»" for title in REQUIRED
                     if not parts.get(step_help.SUBSECTIONS[title])]
    return problems


def dangling_names(text: str) -> list[str]:
    """Имена, которых нет: скилл в backticks без каталога скилла в модулях, файл в «Что смотреть» без места в схеме и скиллах."""
    schema = schema_text()
    skills = "\n".join(file.read_text(encoding="utf-8") for file in (skill / "SKILL.md" for skill in SKILLS.values()) if file.is_file())
    outputs = [glob.replace("**/", "") for glob in re.findall(r'^    generates: "?(.+?)"?$', schema, re.M)]
    assert outputs, "в schema.yaml не нашлись выходы артефактов"
    missing = [name for name in SKILL_TOKEN.findall(text) if not (name in SKILLS and (SKILLS[name] / "SKILL.md").is_file())]
    for step, parts in step_help.parse_steps(text).items():
        for name in FILE_TOKEN.findall(parts.get("what_to_check", "")):
            plain = re.sub(r"<[^>]+>", "x", name)
            if not (any(fnmatch.fnmatch(plain, glob) for glob in outputs) or name in schema or name in skills
                    or name in OUTSIDE_SCHEMA):
                missing.append(f"{step}: {name}")
    return missing


def test_every_step_has_a_full_section():
    assert section_problems(steps_text(), artifact_ids()) == []


def test_native_workflow_names_match_selected_compiler_bundle():
    """Таблица справки называет реальные носители каждого клиента, а не Claude aliases для всех."""
    bundle = json.loads((ROOT / "installer" / "generated" / "workflow-carriers.json").read_text(encoding="utf-8"))
    text = steps_text()
    for workflow in ("new", "continue", "apply", "sync", "archive", "propose", "explore", "update"):
        row = next(line for line in text.splitlines() if line.startswith(f"| {workflow} |"))
        assert f"`/opsx:{workflow}`" in row
        assert f"`/opsx-{workflow}`" in row
        codex = next(item for item in bundle["files"] if item["clientId"] == "codex" and item["id"] == workflow)
        assert f"`${codex['relativePath'].split('/')[0]}`" in row
    for parts in step_help.parse_steps(text).values():
        command = parts.get("command", "")
        if "/opsx:" in command:
            assert "из таблицы выше" in command


def test_sections_go_in_order_of_display():
    """`viewer` сразу после `decisions`: круг идёт на нескольких шагах, а страница у него одна."""
    order = []
    for artifact in artifact_ids():
        order.append(artifact)
        if artifact == step_help.VIEWER_AFTER:
            order.append("viewer")
    assert list(step_help.parse_steps(steps_text())) == [*order, *step_help.AFTER_ARTIFACTS]


def test_new_artifact_without_text():
    """Сценарий «Новый артефакт без текста»."""
    assert section_problems(steps_text(), [*artifact_ids(), "new-artifact"]) == ["new-artifact: нет раздела"]


def test_section_without_subsection():
    """Сценарий «Раздел без подраздела»."""
    text = steps_text()
    start = text.index("### Если пропустить", text.index("## design\n"))
    end = text.index("### Что смотреть", start)
    assert section_problems(text[:start] + text[end:], artifact_ids()) == ["design: нет подраздела «Если пропустить»"]


def test_section_without_step():
    """Раздела без шага быть не должно: текст остался от снятого артефакта."""
    problems = section_problems(steps_text() + "\n## ghost\n\nПризрак\n", artifact_ids())
    assert "ghost: раздел без шага" in problems


def how_to_prepare_span(text: str) -> tuple[int, int]:
    start = text.index("### Как готовить\n", text.index("## intent\n"))
    return start, text.index("\n## ", start)


def test_intent_has_how_to_prepare():
    assert step_help.parse_steps(steps_text())["intent"]["how_to_prepare"]


def test_rewritten_how_to_prepare_stays_green():
    """Сценарий «Текст поменялся»: проверяется наличие подраздела, а не его слова."""
    text = steps_text()
    start, end = how_to_prepare_span(text)
    rewritten = text[:start] + "### Как готовить\n\nСовсем другие слова.\n" + text[end:]
    assert section_problems(rewritten, artifact_ids()) == []
    assert step_help.parse_steps(rewritten)["intent"]["how_to_prepare"] == "Совсем другие слова."


def test_intent_without_how_to_prepare_is_visible():
    text = steps_text()
    start, end = how_to_prepare_span(text)
    assert "how_to_prepare" not in step_help.parse_steps(text[:start] + text[end:])["intent"]


def test_names_in_the_real_file_exist():
    """Тест-страховка F-68, зелёная половина."""
    assert dangling_names(steps_text()) == []


def test_missing_skill_is_named():
    """Тест-страховка F-68: назван скилл, которого нет."""
    assert dangling_names(steps_text() + "\n`symphysis-no-such-skill`\n") == ["symphysis-no-such-skill"]


def test_missing_file_is_named():
    """Тест-страховка F-68: в «Что смотреть» назван файл, которого нет."""
    text = steps_text().replace("### Что смотреть\n", "### Что смотреть\n\n`no-such-file.md`\n", 1)
    assert dangling_names(text) == ["intent: no-such-file.md"]


def test_skill_named_in_the_schema_is_in_the_text():
    """Обратная сторона F-68: скилл, который шаг зовёт по схеме, назван и в его разделе."""
    sections = step_help.parse_steps(steps_text())
    schema = schema_text()
    for block in re.split(r"(?=^  - id: )", schema, flags=re.M)[1:]:
        step = re.match(r"  - id: (\S+)", block)[1]
        named = set(re.findall(r"`(symphysis-[\w-]+)`", block))
        assert named <= set(SKILL_TOKEN.findall(sections[step]["mechanics"])), step


def test_every_section_names_a_file_to_look_at():
    """«Что смотреть» называет файлы: на вопрос намерения «какие файлы и где смотреть» нельзя ответить общими словами."""
    for step, parts in step_help.parse_steps(steps_text()).items():
        assert FILE_TOKEN.search(parts["what_to_check"]), step


def test_text_does_not_say_the_step_is_running():
    """Требование «Справка не выдаёт наличие файла за сделанную работу»: справка не знает, идёт ли шаг прямо сейчас."""
    assert "выполняется" not in steps_text()


def test_text_has_no_absolute_paths():
    """Текст шага попадает в снимок на странице, а она отслеживается git (F-51)."""
    assert openspec_run.ABSOLUTE_PATH.search(steps_text()) is None


def test_parser_reads_crlf_and_skips_fenced_headings():
    text = ("# Шапка\r\n\r\n## a\r\n\r\nНазвание\r\n\r\n### Команда\r\n\r\n```\r\n## не раздел\r\n```\r\n\r\n"
            "### Чужой\r\n\r\nмимо\r\n")
    assert step_help.parse_steps(text) == {"a": {"title": "Название", "command": "```\n## не раздел\n```"}}


def test_apply_and_archive_sections_name_the_freeze():
    """`trace-snapshot`: «Перед первой задачей», «Снимка нет» (F-134, F-139): механика заморозки и ссылка на отчёт
    названы в разделах `apply` и `archive` — их текст отдаёт справка шага."""
    sections = step_help.parse_steps(steps_text())
    for step in ("apply", "archive"):
        mechanics = sections[step]["mechanics"]
        assert "заморозк" in mechanics.lower() and "`graph/report.md`" in mechanics, step
        assert "symphysis trace freeze" in mechanics, step
    assert "когда отмечена последняя задача, модель зовёт" in sections["apply"]["mechanics"]


def test_attack_artifacts_section_names_the_four_lenses():
    """F-55: раздел `attack-artifacts` называет все четыре линзы артефактов, `rule-compliance` — четвёртой."""
    mechanics = step_help.parse_steps(steps_text())["attack-artifacts"]["mechanics"]
    line = next(l for l in mechanics.splitlines() if "Линзы артефактов:" in l)
    positions = [line.index(f"`{lens}`") for lens in ("scenario-run", "claim-extraction", "trace-link", "rule-compliance")]
    assert positions == sorted(positions)
