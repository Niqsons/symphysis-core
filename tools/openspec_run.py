#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Общий запуск форка OpenSpec: его зовут `step_help.py` и скрипт графа (F-138). Форк зовёт одна функция `run_fork`: поиск
форка, проверка имени изменения (`security.md`), телеметрия (F-57), предел и снятие дерева процессов (F-43, F-66).
Правило имени изменения стоит отдельной функцией `check_change_name`: её зовёт `run_fork`, а вызывающему, который строит
путь по имени до вызова форка, она нужна раньше (F-59). `no_paths` снимает абсолютные пути с текста, который уходит в git
или на страницу (F-51). Только стандартная библиотека; файлов проекта модуль не трогает."""
from __future__ import annotations

import errno
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

sys.dont_write_bytecode = True  # как у скриптов, что его зовут: `__pycache__` в проекте от инструментов не появляется (F-50)

__all__ = ["ForkError", "ForkReply", "FORK_TIMEOUT", "SAFE_NAME", "ABSOLUTE_PATH", "check_change_name", "run_fork", "no_paths", "find_on_path"]

FORK_TIMEOUT = 15  # секунд на вызов форка (F-43); плагин ждёт Python 30 с
KILL_TIMEOUT = 5   # секунд на `taskkill`
PIPE_TIMEOUT = 2   # секунд на каналы вывода после снятия: потомок вне дерева может держать их и дальше

# Имя изменения в вызове форка и в пути журнала. `.cmd` разбирает строку через `cmd.exe` и без `shell=True`, разделитель
# пути и точка в начале дали бы выход из `openspec/changes/`, а начальный дефис форк принял бы за ключ (`security.md`).
SAFE_NAME = re.compile(r"\w[\w.-]*")

# Что `cmd.exe` прочёл бы в пути к `.cmd` или `.bat` как команду или подстановку: хвост после `&` исполняется с `cwd` проекта,
# а шим npm ещё раз разворачивает путь без кавычек (`SET dp0=%~dp0`). Скобки и пробелы законны: `Program Files (x86)`.
SHIM_UNSAFE = re.compile(r'[&|<>^%"]')

# Абсолютный путь в тексте форка: диск, UNC или корень POSIX. Пробелы тут не ловятся, поэтому известные каталоги
# снимаются раньше, по значению (`no_paths`).
ABSOLUTE_PATH = re.compile(r"""[A-Za-z]:[\\/][^\s"'`«»,;]*|\\\\[^\s"'`«»,;]+|(?<![\w.~:/>-])/[^\s"'`«»,;:/]+/[^\s"'`«»,;:]*""")


class ForkError(Exception):
    """Сбой вызова форка; текст идёт в поле `error`."""


class ForkReply(NamedTuple):
    code: int
    out: str
    err: str
    label: str  # команда для сообщений, без каталога (F-51)


# --- вызов форка -------------------------------------------------------------

def find_on_path(name: str) -> str | None:
    """Первый `name` из PATH: на Windows по PATHEXT, как `findOnPath` инсталлятора, чтобы найти `.cmd`-шим."""
    if os.name != "nt":
        return shutil.which(name)
    exts = [ext for ext in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if ext]
    for folder in filter(None, os.environ.get("PATH", "").split(os.pathsep)):
        for ext in exts:
            file = os.path.join(folder, name + ext)
            if os.path.isfile(file):
                return file
    return None


def _fork_command() -> list[str]:
    """Чем запускать форк: `SYMPHYSIS_OPENSPEC`, затем `PATH`. `.js` идёт через `node`, без него сбой виден как незапуск (F-56)."""
    chosen = os.environ.get("SYMPHYSIS_OPENSPEC")
    if chosen:
        # Абсолютный путь: у вызова свой cwd.
        file = os.path.abspath(chosen)
        if not os.path.exists(file):
            raise ForkError("openspec не найден: файла из SYMPHYSIS_OPENSPEC нет. Поправь переменную или убери её, "
                            "тогда форк возьмётся из PATH.")
    else:
        file = find_on_path("openspec")
        if not file:
            raise ForkError("openspec не найден: нет ни в SYMPHYSIS_OPENSPEC, ни в PATH. Поставь форк по docs/GUIDE.md "
                            "или задай SYMPHYSIS_OPENSPEC.")
    unsafe = SHIM_UNSAFE.search(file) if _is_shim(file) else None
    if unsafe:
        raise ForkError(f"openspec не запущен: в пути к шиму .cmd или .bat есть символ «{unsafe[0]}», cmd.exe прочёл бы его "
                        "как команду. Перенеси форк в каталог без этого символа или укажи другой через SYMPHYSIS_OPENSPEC.")
    if file.lower().endswith(".js"):
        # `node` берётся из PATH без каталога вызова: `shutil.which` и голое имя в `CreateProcess` смотрят в `cwd`, то есть
        # в корень чужого проекта. Нет node: обычный сбой запуска (F-56).
        node = find_on_path("node")
        if not node:
            raise FileNotFoundError(errno.ENOENT, "node не найден в PATH")  # `run_fork` назовёт это как любой незапуск
        return [node, file]
    return [file]


def _is_shim(file: str) -> bool:
    return file.lower().endswith((".cmd", ".bat"))


def _command_line(command: list[str]) -> list[str] | str:
    """Что отдать `Popen`. Шим на Windows — строкой с кавычками вокруг пути: `list2cmdline` ставит их только при пробеле,
    а `cmd.exe` читает и скобку, поэтому `a(b)\\openspec.cmd` без них не запустится. Кавычку в пути отвергает `SHIM_UNSAFE`."""
    if os.name == "nt" and _is_shim(command[0]):
        return f'"{command[0]}" {subprocess.list2cmdline(command[1:])}'
    return command


def _kill_tree(proc: subprocess.Popen) -> None:
    """Снимает зависший вызов с потомками: простой `kill` оставит node под `.cmd`, и тот удержит каналы вывода (F-66)."""
    try:
        if os.name == "nt":
            taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
            subprocess.run([str(taskkill), "/T", "/F", "/PID", str(proc.pid)], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=KILL_TIMEOUT,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        proc.kill()


def check_change_name(change: str) -> None:
    """Правило имени изменения (F-59): имя бывает из аргумента, из пути журнала и из ответа самого форка, а идёт в вызов
    `--change <имя>`, в позиционный аргумент `validate` и в путь под `openspec/changes/`. Негодное — `ForkError`, форк
    не вызван. Звать до построения любого пути и до вызова форка; `run_fork` зовёт ту же функцию для `change=`."""
    if not SAFE_NAME.fullmatch(change):
        raise ForkError(f"Имя изменения «{change}» не подходит: начало — буква, цифра или «_», дальше ещё «-» и точка. "
                        "Форк не вызван: переименуй каталог изменения.")


def run_fork(root: Path | str, *args: str, change: str | None = None) -> ForkReply:
    """Единственный вызов форка; `change` становится `--change <имя>` только здесь и только после проверки:
    `check_change_name`. Код выхода не судит: это делают вызывающие."""
    if change is not None:
        check_change_name(change)
        args = (*args, "--change", change)
    label = " ".join(("openspec", *args))
    # Без окна на Windows; на остальных своя группа процессов: её снимает `_kill_tree`.
    # `NoDefaultCurrentDirectoryInExePath`: шим npm без `node.exe` рядом зовёт голое `node`, `cmd.exe` ищет его сначала в `cwd`,
    # то есть в корне чужого проекта. Переменная выключает поиск в `cwd`; ключ снимается без учёта регистра, дубля в блоке нет.
    env = {key: value for key, value in os.environ.items() if key.lower() != "nodefaultcurrentdirectoryinexepath"}
    env.update(OPENSPEC_TELEMETRY="0", NoDefaultCurrentDirectoryInExePath="1")
    detached = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    try:
        proc = subprocess.Popen(_command_line([*_fork_command(), *args]), cwd=root,
                                env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, **detached)
    except OSError as e:
        raise ForkError(f"`{label}` не запустился: {e.strerror or type(e).__name__}. Проверь, запускается ли форк "
                        "в терминале.") from None
    try:
        out, err = proc.communicate(timeout=FORK_TIMEOUT)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            proc.communicate(timeout=PIPE_TIMEOUT)
        except subprocess.TimeoutExpired:
            pass  # канал держит потомок вне дерева: возврат важнее его вывода
        raise ForkError(f"`{label}` не ответил за {FORK_TIMEOUT} с, вызов снят. "
                        "Проверь эту команду в терминале.") from None
    return ForkReply(proc.returncode, _decoded(out), _decoded(err), label)


def _decoded(raw: bytes) -> str:
    """Вывод форка: UTF-8. Сообщения самого `cmd.exe` идут в кодировке OEM: без неё в `error` были бы кракозябры (F-44)."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("oem" if os.name == "nt" else "utf-8", "replace")


def no_paths(text: str, root: Path | str) -> str:
    """Текст для вывода без абсолютных путей: и свой, и напечатанный форком (F-51, F-59)."""
    known = [os.path.abspath(root), os.getcwd(), str(Path.home())]
    if os.environ.get("SYMPHYSIS_OPENSPEC"):
        known.append(os.path.dirname(os.path.abspath(os.environ["SYMPHYSIS_OPENSPEC"])))
    for folder in sorted((folder for folder in known if len(folder) > 3), key=len, reverse=True):
        text = text.replace(folder, "<каталог>").replace(folder.replace("\\", "/"), "<каталог>")
    return ABSOLUTE_PATH.sub("<путь>", text)
