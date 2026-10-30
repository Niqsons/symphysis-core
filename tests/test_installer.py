"""Единый гейт: Node-тесты инсталлятора запускаются из pytest."""
import shutil
import subprocess
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parent.parent / "installer"


@pytest.mark.skipif(shutil.which("node") is None, reason="node не найден в PATH")
def test_installer_node_tests_pass():
    node = shutil.which("node")
    # Node >=22 не принимает `node --test test/` (каталог читается как модуль) —
    # автообнаружение без аргумента находит test/**.
    r = subprocess.run(
        [node, "--test"], cwd=INSTALLER, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0, r.stdout + r.stderr
