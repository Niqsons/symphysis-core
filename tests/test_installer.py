"""Единый гейт: Node-тесты инсталлятора запускаются из pytest."""
import shutil
import subprocess
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parent.parent / "installer"


@pytest.mark.skipif(shutil.which("node") is None, reason="node не найден в PATH")
def test_installer_node_tests_pass():
    node = shutil.which("node")
    # Как `npm test` (`pretest`): payload пересобирается из корня до тестов. Без этого CLI-тест
    # `check` читает `installer/payload` (DEFAULT_PAYLOAD), устаревший после правки корня, и
    # зелен лишь когда `npm pack` из npx-тестов (`prepare`) успел пересобрать его раньше — гонка.
    sync = subprocess.run([node, "scripts/sync-payload.js"], cwd=INSTALLER, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    assert sync.returncode == 0, sync.stdout + sync.stderr
    # Node >=22 не принимает `node --test test/` (каталог читается как модуль) —
    # автообнаружение без аргумента находит test/**.
    r = subprocess.run(
        [node, "--test"], cwd=INSTALLER, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0, r.stdout + r.stderr
