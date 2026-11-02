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
FORK_VERSION = re.compile(r"\d+\.\d+\.\d+-symphysis\.\d+")


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
