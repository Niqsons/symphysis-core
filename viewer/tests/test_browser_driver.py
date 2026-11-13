import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import test_viewer_browser as viewer


@pytest.mark.skipif(viewer.node is None, reason="нужен Node для пробного драйвера")
@pytest.mark.parametrize("exit_early", [False, True], ids=["timeout", "driver-exited"])
def test_browser_cleans_only_its_child_and_profile(tmp_path, monkeypatch, exit_early):
    temp = tmp_path / "temp"
    temp.mkdir()
    foreign = temp / "symphysis-viewer-neighbor"
    foreign.mkdir()
    own = tmp_path / "profile.txt"
    child_pid = tmp_path / "child.pid"
    child_script = tmp_path / "child.cjs"
    child_script.write_text(
        "const fs = require('node:fs');\n"
        "fs.writeFileSync(process.env.CHILD_PID, String(process.pid));\n"
        "const guard = setInterval(() => { if (!fs.existsSync(process.env.CHILD_PID)) clearInterval(guard); }, 100);\n"
        "setTimeout(() => clearInterval(guard), 15000).unref();\n",
        encoding="utf-8",
    )
    script = tmp_path / "driver.cjs"
    script.write_text(
        "const fs = require('node:fs');\n"
        "const path = require('node:path');\n"
        "const os = require('node:os');\n"
        "const { spawn } = require('node:child_process');\n"
        "if (process.env.SYMPHYSIS_BROWSER_WAIT === '1') fs.readFileSync(0);\n"
        "const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'symphysis-viewer-'));\n"
        "fs.writeFileSync(process.env.PROFILE_FILE, dir);\n"
        "const child = spawn(process.execPath, [process.env.CHILD_SCRIPT], {stdio: 'ignore'});\n"
        "child.unref();\n"
        "const wait = setInterval(() => {\n"
        "  if (!fs.existsSync(process.env.CHILD_PID)) return;\n"
        "  clearInterval(wait);\n"
        "  if (process.env.DRIVER_EXITS === '1') {\n"
        "    console.error('EBUSY: lockfile');\n"
        "    process.exitCode = 1;\n"
        "  } else setTimeout(() => {}, 10000);\n"
        "}, 10);\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(viewer, "DRIVER", script)
    monkeypatch.setattr(viewer, "chrome", sys.executable)
    monkeypatch.setattr(viewer, "BROWSER_TIMEOUT", 2)
    monkeypatch.setenv("PROFILE_FILE", str(own))
    monkeypatch.setenv("CHILD_PID", str(child_pid))
    monkeypatch.setenv("CHILD_SCRIPT", str(child_script))
    monkeypatch.setenv("DRIVER_EXITS", "1" if exit_early else "0")
    with subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"]) as neighbor:
        try:
            with pytest.raises(AssertionError) as failed:
                viewer.browser(tmp_path / "unused.html", temp_dir=temp)
            pid = int(child_pid.read_text(encoding="ascii"))
            deadline = time.monotonic() + 5
            while _running(pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            assert not _running(pid)
            profile = Path(own.read_text(encoding="utf-8"))
            assert profile.is_relative_to(temp) and not profile.exists()
            assert ("EBUSY: lockfile" if exit_early else "таймаут") in str(failed.value)
            assert "процессы завершены" in str(failed.value)
            assert "профиль удалён" in str(failed.value)
            assert not any(path != foreign for path in temp.iterdir())
            assert neighbor.poll() is None
            assert foreign.is_dir()
        finally:
            neighbor.terminate()
            if child_pid.exists():
                # При RED самоограничение потомка сохраняет стенд без внешнего поиска и снятия процессов.
                child_pid.unlink()


def _running(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        process = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not process:
            assert ctypes.get_last_error() == 87  # ERROR_INVALID_PARAMETER: PID уже отсутствует.
            return False
        try:
            result = kernel.WaitForSingleObject(process, 0)
            assert result in (0, 258)
            return result == 258
        finally:
            kernel.CloseHandle(process)
    result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
    return result.returncode == 0 and not result.stdout.lstrip().startswith("Z")
