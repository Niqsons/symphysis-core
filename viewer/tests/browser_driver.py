"""Изолированный запуск Node-драйвера и его процессов Chrome."""
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    # Job Object удерживает потомков после выхода Node и адресуется handle,
    # поэтому завершение не зависит от того, переиспользован ли его PID.
    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
            ("flags", wintypes.DWORD), ("min_ws", ctypes.c_size_t), ("max_ws", ctypes.c_size_t),
            ("active_limit", wintypes.DWORD), ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD),
        ]

    class _Limits(ctypes.Structure):
        _fields_ = [
            ("basic", _BasicLimits), ("io", ctypes.c_ulonglong * 6),
            ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t),
        ]

    class _Accounting(ctypes.Structure):
        _fields_ = [
            ("times", ctypes.c_longlong * 4), ("faults", wintypes.DWORD),
            ("total", wintypes.DWORD), ("active", wintypes.DWORD), ("terminated", wintypes.DWORD),
        ]

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _create = _kernel.CreateJobObjectW
    _create.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    _create.restype = wintypes.HANDLE
    _set_info = _kernel.SetInformationJobObject
    _set_info.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    _query = _kernel.QueryInformationJobObject
    _query.argtypes = (*_set_info.argtypes, ctypes.c_void_p)
    _assign = _kernel.AssignProcessToJobObject
    _assign.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    _terminate = _kernel.TerminateJobObject
    _terminate.argtypes = (wintypes.HANDLE, wintypes.UINT)
    _close = _kernel.CloseHandle
    _close.argtypes = (wintypes.HANDLE,)

    class _Job:
        def __init__(self):
            self.handle = _create(None, None)
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            limits = _Limits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not _set_info(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                error = ctypes.WinError(ctypes.get_last_error())
                self.close()
                raise error

        def attach(self, proc):
            if not _assign(self.handle, int(proc._handle)):
                raise ctypes.WinError(ctypes.get_last_error())

        def active(self):
            counts = _Accounting()
            if not _query(self.handle, 1, ctypes.byref(counts), ctypes.sizeof(counts), None):
                raise ctypes.WinError(ctypes.get_last_error())
            return counts.active

        def stop(self):
            if self.active() and not _terminate(self.handle, 1):
                raise ctypes.WinError(ctypes.get_last_error())
            deadline = time.monotonic() + 5
            while self.active() and time.monotonic() < deadline:
                time.sleep(0.05)
            return self.active() == 0

        def close(self):
            _close(self.handle)


def _await_driver(proc, timeout):
    if os.name == "nt":
        proc.wait(timeout=timeout)
        return
    # Не забираем статус лидера до очистки его группы: PID/PGID остаётся
    # зарезервированным, даже если Node уже вышел.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if hasattr(os, "waitid"):
            if os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                return
        else:  # Python до 3.13 на macOS.
            if not _live_group(proc.pid, leader_only=True):
                return
        time.sleep(0.05)
    raise subprocess.TimeoutExpired(proc.args, timeout)


def _live_group(pgid, *, leader_only=False):
    # На Unix уже завершённый потомок может оставаться зомби до того, как
    # его новый родитель заберёт статус. Он больше не держит профиль.
    columns = ["-p", str(pgid), "-o", "pgid=", "-o", "stat="] if leader_only else ["-A", "-o", "pgid=", "-o", "stat="]
    result = subprocess.run(["ps", *columns], capture_output=True, text=True, timeout=5)
    if result.returncode and not (leader_only and result.returncode == 1 and not result.stdout):
        raise OSError(f"ps: {result.stderr.strip()}")
    return any(group == str(pgid) and not status.startswith("Z")
               for group, status in (line.split() for line in result.stdout.splitlines() if line.strip()))


def _stop(proc, job):
    if job is not None:
        return job.stop()
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + 5
    while _live_group(proc.pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def _remove_profile(root):
    deadline = time.monotonic() + 5
    while True:
        try:
            shutil.rmtree(root)
        except OSError as error:
            if time.monotonic() >= deadline:
                return f"профиль остался ({root}): {error}"
            time.sleep(0.05)
        else:
            return "профиль удалён"


def _run(args, env, timeout, stdout, stderr):
    job = None
    proc = None
    timed_out = False
    cleanup = None
    try:
        if os.name == "nt":
            job = _Job()
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                env=env, start_new_session=os.name != "nt")
        if job is not None:
            try:
                job.attach(proc)
            except OSError as error:
                # Драйвер ещё ждёт разрешения и не запускал браузер.
                proc.kill()
                proc.wait(timeout=5)
                raise OSError(f"Не удалось изолировать браузерный драйвер: {error}") from error
        try:
            try:
                proc.stdin.write(b"1")
                proc.stdin.close()
            except BrokenPipeError:
                pass  # Статус преждевременного выхода ниже.
            _await_driver(proc, timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
    finally:
        try:
            if proc is not None:
                try:
                    stopped = _stop(proc, job)
                    cleanup = "процессы завершены" if stopped else "остались процессы запуска"
                except (OSError, subprocess.TimeoutExpired) as error:
                    cleanup = f"завершение процессов не подтверждено: {error}"
        finally:
            if job is not None:
                job.close()
            if proc is not None:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    cleanup = "выход браузерного драйвера не подтверждён"
                finally:
                    proc.stdin.close()
    return proc.returncode, timed_out, cleanup


def run_browser_driver(args, *, timeout, temp_dir=None):
    root = Path(tempfile.mkdtemp(prefix="browser-driver-", dir=temp_dir))
    env = {**os.environ, **dict.fromkeys(("TEMP", "TMP", "TMPDIR"), str(root)), "SYMPHYSIS_BROWSER_WAIT": "1"}
    try:
        # Файлы вывода можно закрыть, даже если потомок пережил драйвер.
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            code, timed_out, process_cleanup = _run(args, env, timeout, stdout, stderr)
            stdout.seek(0)
            stderr.seek(0)
            out = stdout.read().decode("utf-8")
            err = stderr.read().decode("utf-8", errors="replace").strip()
    finally:
        profile_cleanup = _remove_profile(root)
    problem = None
    if timed_out:
        problem = f"таймаут браузерного драйвера ({timeout} с)"
    elif code != 0:
        problem = f"браузерный драйвер завершился с кодом {code}"
    if problem:
        raise AssertionError(f"{problem}\n{err}\nОчистка: {process_cleanup}; {profile_cleanup}")
    if process_cleanup != "процессы завершены" or profile_cleanup != "профиль удалён":
        raise AssertionError(f"Очистка: {process_cleanup}; {profile_cleanup}")
    return out
