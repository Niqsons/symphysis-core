"""Руководство `docs/GUIDE.md`: гейт имён, выдержки из замеров, версия форка, адрес клона (F-57.C, F-98.A, F-104)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools" / "hooks"))

from gate_hook import GATE_DEFAULT  # noqa: E402  (после правки sys.path)

GUIDE = ROOT / "docs" / "GUIDE.md"
INSTALLER_PACKAGE = ROOT / "installer" / "package.json"
# Следы материалов замеров: имя прогона, скрипт и каталог плеча, пункты чек-листа.
MEASURE_SAMPLES = (r"c\d-[a-z]\d", r"arm\.ps1", r"judge/", r"П\d+", r"Т\d+")
TOKEN_ADDRESS = re.compile(r"://[^/]*@")
FORK_VERSION = re.compile(r"\d+\.\d+\.\d+[-+]symphysis\.\d+")


def text() -> str:
    return GUIDE.read_text(encoding="utf-8")


def measure_findings(body: str) -> list[str]:
    return [found.group(0) for sample in MEASURE_SAMPLES for found in re.finditer(sample, body)]


def token_addresses(body: str) -> list[str]:
    return [line for line in body.splitlines() if TOKEN_ADDRESS.search(line)]


def test_guide_passes_names_gate():
    configured = os.environ.get("SYMPHYSIS_GATE")
    gate = Path(configured or GATE_DEFAULT)
    if not gate.is_file():
        if configured:
            pytest.fail(f"SYMPHYSIS_GATE задан, файла нет: {gate}")
        pytest.skip(f"гейта имён на этой машине нет: {gate}; указать путь — SYMPHYSIS_GATE")
    run = subprocess.run([sys.executable, str(gate), GUIDE.relative_to(ROOT).as_posix()], cwd=ROOT,
                         env=dict(os.environ, PYTHONUTF8="1"), capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    assert run.returncode == 0, run.stdout + run.stderr


def test_guide_has_no_measure_excerpts():
    assert measure_findings(text()) == []


@pytest.mark.parametrize("sample", ["прогон c3-p2", "скрипт arm.ps1", "каталог judge/", "пункт П12", "пункт Т4"])
def test_measure_search_finds_each_sample(sample):
    assert measure_findings(sample)


def test_guide_fork_version_equals_pin():
    pin = json.loads(INSTALLER_PACKAGE.read_text(encoding="utf-8"))["symphysis"]["openspecPin"]
    versions = set(FORK_VERSION.findall(text()))
    assert versions == {pin}


def test_guide_has_no_address_with_credentials():
    assert token_addresses(text()) == []
    assert token_addresses("git clone https://user:secret@host.example/repo.git")  # gate-ok: эталон теста


def test_guide_names_the_package_pyyaml():
    assert set(re.findall(r"pip install ([\w.-]+)", text())) == {"pyyaml"}


GRAPH_HEADING = "## Граф трассируемости"


def graph_section() -> str:
    """Раздел руководства о графе: от своего заголовка до следующего `## `."""
    body = text()
    assert GRAPH_HEADING in body, "в руководстве нет раздела о графе"
    start = body.index(GRAPH_HEADING)
    following = re.search(r"^## ", body[start + len(GRAPH_HEADING):], re.MULTILINE)
    return body[start:start + len(GRAPH_HEADING) + following.start()] if following else body[start:]


def test_guide_tells_how_to_mark_a_warning_read():
    """attack-warning-read: разделы атак говорят, что предупреждение можно отметить прочитанным на странице, отметка уходит
    в `notes[]`, вердикт станет `stale` с составом «записей не добавлено», повтор назовёт прочитанные пометкой."""
    body = text()
    journal_attack = body.split("### Атака журнала, по желанию")[1].split("### Шаг `proposal`")[0]
    for name in ("прочитан", "notes[]", "записей не добавлено", "(прочитано)"):
        assert name in journal_attack, f"в разделе атаки журнала нет «{name}»"
    artifacts_attack = body.split("### Атака артефактов, по желанию")[1]
    assert "прочитан" in artifacts_attack.split("\n### ")[0], "в разделе атаки артефактов нет слова о прочтении"


def test_guide_graph_section_tells_what_the_graph_gives():
    """`onboarding-guide`: «Читатель ищет, что даёт граф» (F-04, F-05)."""
    section = graph_section()
    for name in ("symphysis trace report",   # команда отчёта
                 "build", "--out", "req-graph.json",                  # файл `--out`
                 "symphysis trace check",     # проверка файла
                 "--format mermaid", "requirementDiagram",           # текст диаграммы
                 "graph/", "report.md", "freeze",                    # каталог и заморозка
                 "/opsx:apply", "/opsx:archive",                     # шаги, где они появляются
                 "openspec validate",                                # связь с проверкой OpenSpec
                 "[сигнал]"):                                        # ответ на сигнал (F-47)
        assert name in section, name


def test_guide_graph_section_tells_how_links_resolve():
    """`onboarding-guide`: «Читатель ищет, что даёт граф» — правила разбора связей F-140–F-150."""
    section = graph_section()
    for name in ("F-NN", "служебная", "Часть требования «", "<!-- F-NN -->", "depends_on",
                 "границе слова", "самое длинное", "ближайший сценарий"):
        assert name in section, name


def test_guide_lens_section_tells_about_rule_compliance():
    """`attack-lens-conventions`: раздел о линзах называет `rule-compliance`, тяжести и выключение."""
    body = text()
    heading = "### Линзы `trace-link`, `rule-compliance` и настройки атаки"
    assert heading in body, "нет заголовка раздела о линзах"
    section = body.split(heading)[1].split("\n## ")[0]
    for name in ("правила составления", "блокер", "предупреждение (правило составления)",
                 "attack.rule-compliance: false", "MODIFIED", "мастер-спек"):
        assert name in section, f"в разделе о линзах нет «{name}»"
    assert "`attack.rule-compliance`," in section, "линза не в перечне остальных"


def test_guide_names_the_script_that_finds_changes_without_snapshot():
    """`onboarding-guide`: «Читатель ищет изменения без снимка» (F-62)."""
    section = graph_section()
    assert "symphysis trace archive-gaps" in section
    assert "symphysis check" in section
