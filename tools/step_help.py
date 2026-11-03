#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Справка о шаге конвейера: какой шаг следующий по файлам и чей ход — по выводу форка, журналу и задачам (F-19, F-23).

Расчёт отделён от разбора аргументов: `compute(корень, имя)` зовёт и `render-html` (F-34). Скрипт пишет только в stdout,
файлов проекта не меняет и шага не останавливает (F-50). Форк зовёт одна функция `run_fork`: поиск форка, проверка имени
изменения (`security.md`), телеметрия (F-57), предел и снятие дерева процессов (F-43, F-66). Абсолютных путей в выводе нет,
страница со снимком отслеживается git (F-51)."""
from __future__ import annotations

import argparse
import datetime as dt
import errno
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

sys.dont_write_bytecode = True  # скрипт пишет только в stdout (F-50): `__pycache__` в проекте от него не появляется
from journal_render import CONTRACT  # noqa: E402

__all__ = ["ForkError", "compute", "run_fork", "parse_steps", "build_parser", "main"]

FORK_TIMEOUT = 15  # секунд на вызов форка (F-43); плагин ждёт Python 30 с
KILL_TIMEOUT = 5   # секунд на `taskkill`
PIPE_TIMEOUT = 2   # секунд на каналы вывода после снятия: потомок вне дерева может держать их и дальше

# Имя изменения в вызове форка и в пути журнала. `.cmd` разбирает строку через `cmd.exe` и без `shell=True`, разделитель
# пути и точка в начале дали бы выход из `openspec/changes/`, а начальный дефис форк принял бы за ключ (`security.md`).
SAFE_NAME = re.compile(r"\w[\w.-]*")

# Что `cmd.exe` прочёл бы в пути к `.cmd` или `.bat` как команду или подстановку: хвост после `&` исполняется с `cwd` проекта,
# а шим npm ещё раз разворачивает путь без кавычек (`SET dp0=%~dp0`). Скобки и пробелы законны: `Program Files (x86)`.
SHIM_UNSAFE = re.compile(r'[&|<>^%"]')

VERSION_FILE = "symphysis-version.txt"
DEFAULT_SCHEMA = "symphysis"

UNREADABLE = "журнал не читается"
FILE_NOT_CHECKED = "файл есть, содержание не проверялось"
NO_TEXT = "текста нет"

# Шаги вне графа схемы: `viewer` идёт сразу после `decisions`, остальные в конце (F-27).
VIEWER_AFTER = "decisions"
AFTER_ARTIFACTS = ("apply", "sync", "archive")
HUMAN_STEPS = ("intent", "viewer")

# Подразделы `steps.md` -> ключи вывода.
SUBSECTIONS = {"Зачем": "why", "Механики": "mechanics", "Если пропустить": "if_skipped", "Что смотреть": "what_to_check",
               "Команда": "command", "Как готовить": "how_to_prepare"}
NO_TEXTS = {"title": "", **{key: "" for key in SUBSECTIONS.values()}}

# Абсолютный путь в тексте форка: диск, UNC или корень POSIX. Пробелы тут не ловятся, поэтому известные каталоги
# снимаются раньше, по значению (`_no_paths`).
ABSOLUTE_PATH = re.compile(r"""[A-Za-z]:[\\/][^\s"'«»,;]*|\\\\[^\s"'«»,;]+|(?<![\w.~:/>-])/[^\s"'«»,;:/]+/[^\s"'«»,;:]*""")


class ForkError(Exception):
    """Сбой вызова форка; текст идёт в поле `error`."""


class ForkReply(NamedTuple):
    code: int
    out: str
    err: str
    label: str  # команда для сообщений, без каталога (F-51)


# --- вызов форка -------------------------------------------------------------

def _find_on_path(name: str) -> str | None:
    """Первый `openspec` из PATH: на Windows по PATHEXT, как `findOnPath` инсталлятора, чтобы найти `.cmd`-шим."""
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
        file = _find_on_path("openspec")
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
        node = _find_on_path("node")
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


def run_fork(root: Path | str, *args: str, change: str | None = None) -> ForkReply:
    """Единственный вызов форка; `change` становится `--change <имя>` только здесь и только после проверки: имя бывает
    из аргумента, из пути журнала и из ответа самого форка. Код выхода не судит: это делают вызывающие."""
    if change is not None:
        if not SAFE_NAME.fullmatch(change):
            raise ForkError(f"Имя изменения «{change}» не подходит: начало — буква, цифра или «_», дальше ещё «-» и точка. "
                            "Форк не вызван: переименуй каталог изменения.")
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


def _first_json(text: str) -> dict | None:
    """Первый объект JSON в выводе: перед ним форк может напечатать строку-предупреждение."""
    start = text.find("{")
    if start < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(text[start:])[0]
    except ValueError:
        return None


def _first_line(*texts: str) -> str:
    return next((line.strip() for text in texts for line in text.splitlines() if line.strip()), "")


def _reason(data: dict | None, reply: ForkReply) -> str:
    """Причина сбоя одной строкой: сообщение форка из JSON, иначе первая строка потоков."""
    try:
        message = data["status"][0]["message"]
    except (TypeError, KeyError, IndexError):
        message = _first_line(reply.err, reply.out)
    return " ".join(str(message).split()) or "причины форк не назвал"


def _fork_json(root: Path | str, *args: str, change: str | None = None, usable_on_failure: str | None = None) -> dict:
    """Ответ форка объектом JSON. Ненулевой код — сбой, кроме случая, когда в ответе непустое поле `usable_on_failure`."""
    reply = run_fork(root, *args, change=change)
    data = _first_json(reply.out)
    if reply.code != 0 and not (data and usable_on_failure and data.get(usable_on_failure)):
        raise ForkError(f"`{reply.label}` упал с кодом {reply.code}: {_reason(data, reply)}")
    if data is None:
        raise ForkError(f"`{reply.label}` ответил не JSON: это не тот форк или его вывод испорчен. "
                        "Проверь команду в терминале.")
    return data


def _no_paths(text: str, root: Path | str) -> str:
    """Текст для вывода без абсолютных путей: и свой, и напечатанный форком (F-51)."""
    known = [os.path.abspath(root), os.getcwd(), str(Path.home())]
    if os.environ.get("SYMPHYSIS_OPENSPEC"):
        known.append(os.path.dirname(os.path.abspath(os.environ["SYMPHYSIS_OPENSPEC"])))
    for folder in sorted((folder for folder in known if len(folder) > 3), key=len, reverse=True):
        text = text.replace(folder, "<каталог>").replace(folder.replace("\\", "/"), "<каталог>")
    return ABSOLUTE_PATH.sub("<путь>", text)


def _active_changes(root: Path | str) -> list[str]:
    """Имена активных изменений. `status --all`, а не `status`: без `--change` тот отказывает уже на одном изменении.
    Битое изменение даёт код 1, но имена `--all` называет все; сбой назовёт вызов этого изменения."""
    data = _fork_json(root, "status", "--all", "--json", usable_on_failure="changes")
    return [entry["changeName"] for entry in data["changes"]]


# --- файлы проекта ------------------------------------------------------------

def _count_forks(root: Path, change: str) -> dict:
    """Развилки журнала: открытой считается только `status: открыт`, припаркованные отдельно (F-40). Журнала ещё нет —
    нули; журнал не читается — слова вместо чисел, а не «открытых 0» (F-41)."""
    path = root / "openspec" / "changes" / change / "decisions.json"
    if not path.is_file():
        return {"open": 0, "parked": 0}
    try:
        with path.open(encoding="utf-8-sig") as file:
            statuses = [rec["status"] for rec in json.load(file)["records"] if rec["kind"] == "развилка"]
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return {"open": UNREADABLE, "parked": UNREADABLE}
    return {"open": statuses.count("открыт"), "parked": statuses.count("припаркован")}


def parse_steps(text: str) -> dict[str, dict]:
    """Разделы `steps.md`: `## <id>` -> `{"title", <ключи подразделов>}`. Ключа нет — подраздела в файле нет;
    неизвестный подраздел пропускается. Строки внутри ``` разметкой не считаются."""
    sections: dict[str, dict] = {}
    lines_of: list[str] | None = None
    in_fence = False
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith("```"):
            in_fence = not in_fence
        heading = None if in_fence else re.fullmatch(r"(##|###) (.+?)\s*", line)
        if heading and heading[1] == "##":
            sections[heading[2]] = {"title": []}
            current, lines_of = sections[heading[2]], sections[heading[2]]["title"]
        elif heading and sections:
            key = SUBSECTIONS.get(heading[2])
            lines_of = current.setdefault(key, []) if key else None
        elif lines_of is not None:
            lines_of.append(line)
    return {step: {key: "\n".join(lines).strip() for key, lines in parts.items()} for step, parts in sections.items()}


def _read_steps(root: Path, schema: str) -> dict[str, dict]:
    """Тексты шагов из схемы проекта. Файла нет или он не читается — текстов нет, данные графа остаются (старая схема)."""
    if not SAFE_NAME.fullmatch(schema):
        return {}
    try:
        return parse_steps((root / "openspec" / "schemas" / schema / "steps.md").read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError):
        return {}


def _symphysis_version() -> str | None:
    """Версия из файла рядом с инструментами: справочно, ни с чем не сравнивается (F-27, F-36)."""
    try:
        return Path(__file__).resolve().with_name(VERSION_FILE).read_text(encoding="utf-8-sig").strip() or None
    except (OSError, UnicodeDecodeError):
        return None


def _from_root(path: str, base: str) -> str:
    """Абсолютный путь форка -> от корня проекта, прямыми слешами. Вне корня — только имя файла (F-51)."""
    try:
        rel = os.path.relpath(path, base)
    except ValueError:  # другой диск
        rel = os.path.basename(path)
    if rel.startswith(".."):
        rel = os.path.basename(path)
    return rel.replace("\\", "/")


# --- страницы шагов -----------------------------------------------------------

def _not_invoked(artifact: dict) -> bool:
    """Необязательный артефакт без файла: зовётся только по имени и ничего не держит (`isNotInvokedOptional` форка)."""
    return artifact.get("optional") is True and artifact.get("fileExists") is False


def _page(step: str, texts: dict[str, dict], change: str | None = None) -> dict:
    """Страница шага без данных графа: то, что известно и без форка."""
    section = texts.get(step)
    filled = {**NO_TEXTS, **(section or {})}
    if change is not None:
        filled = {key: value.replace("<имя>", change) for key, value in filled.items()}
    return {"id": step, "state": None, "turn": "human" if step in HUMAN_STEPS else "model", "optional": False, "blocks": [],
            "stops_apply": False, "waits_for": [], "files": [], "file_note": None, "texts": filled,
            "text_note": None if section else NO_TEXT, "prev": None, "next": None}


def _linked(pages: list[dict]) -> list[dict]:
    for left, right in zip(pages, pages[1:]):
        left["next"], right["prev"] = right["id"], left["id"]
    return pages


def _pages_without_graph(texts: dict[str, dict], change: str | None = None) -> list[dict]:
    """Список шагов, когда графа нет: нет изменения или форк упал. Страница `intent` есть всегда: её открывает кнопка
    (F-54). Имя известно `render-html` и `--change`: оно подставляется и здесь, без имени `<имя>` остаётся."""
    return _linked([_page(step, texts, change) for step in ("intent", *(step for step in texts if step != "intent"))])


def _artifact_files(artifact: str, status: dict, base: str) -> list[dict]:
    """Настоящие файлы артефакта, а если их нет — путь, куда он ляжет (F-28)."""
    paths = status["artifactPaths"][artifact]
    existing = paths["existingOutputPaths"]
    if existing:
        return [{"path": _from_root(path, base), "exists": True} for path in existing]
    return [{"path": _from_root(paths["resolvedOutputPath"], base), "exists": False}]


def _artifact_page(artifact: dict, status: dict, base: str, page: dict) -> dict:
    """Что заблокируется, необязателен ли шаг и держит ли он `apply` — из графа, не из текста (F-25). Невызванная атака
    ничего не держит, хотя `requires` её называет: так считает сам форк."""
    step = artifact["id"]
    idle = _not_invoked(artifact)
    page.update(state=artifact["status"], optional=artifact.get("optional") is True,
                blocks=[] if idle else [a["id"] for a in status["artifacts"] if step in a["requires"]],
                stops_apply=not idle and step in status["applyRequires"], waits_for=artifact.get("missingDeps", []),
                files=_artifact_files(step, status, base),
                file_note=FILE_NOT_CHECKED if artifact["status"] == "done" else None)
    return page


def _service_state(step: str, forks: dict, tasks: dict) -> str:
    """Состояние шага вне графа. `sync` и `archive` файлов не оставляют: сделаны ли они, скрипт не видит (F-13)."""
    if step == "viewer":
        return "unknown" if forks["open"] == UNREADABLE else "ready" if forks["open"] else "idle"
    if step == "apply":
        return tasks["state"]
    return "ready" if tasks["state"] == "all_done" else "waiting"


def _pages(root: Path, change: str, status: dict, forks: dict, tasks: dict, missing: list[str]) -> list[dict]:
    texts = _read_steps(root, status.get("schemaName") or DEFAULT_SCHEMA)
    base = status.get("planningHome", {}).get("root") or str(root)
    pages = []
    for artifact in status["artifacts"]:
        pages.append(_artifact_page(artifact, status, base, _page(artifact["id"], texts, change)))
        if artifact["id"] == VIEWER_AFTER:
            pages.append({**_page("viewer", texts, change), "state": _service_state("viewer", forks, tasks)})
    for step in AFTER_ARTIFACTS:
        pages.append({**_page(step, texts, change), "state": _service_state(step, forks, tasks),
                      "waits_for": missing if step == "apply" else []})
    return _linked(pages)


# --- текущий шаг --------------------------------------------------------------

def _next_by_status(status: dict, tasks: dict) -> str:
    """Первый `ready`, кроме необязательного без файла, как у `/opsx:continue` (F-55); таких нет — `apply`, после закрытых
    задач `sync`."""
    for artifact in status["artifacts"]:
        if artifact["status"] == "ready" and not _not_invoked(artifact):
            return artifact["id"]
    return "sync" if tasks["state"] == "all_done" else "apply"


def _current_text(current: str, by_status: str, forks: dict, tasks: dict, missing: list[str]) -> str:
    """Шаг называется следующим по файлам, а не идущим: готовность в `status` — это наличие файла (F-19, F-24)."""
    turn = "ход человека" if current in HUMAN_STEPS else "ход модели"
    if current == "viewer":
        text = (f"Следующий шаг по файлам — `viewer`, {turn}: открытых развилок {forks['open']}, решаются на странице "
                f"журнала. После них по файлам идёт `{by_status}`.")
    else:
        text = f"Следующий шаг по файлам — `{current}`, {turn}."
    if current == "apply":
        text += f" Задач закрыто {tasks['complete']} из {tasks['total']}."
        if missing:
            text += f" Реализацию держит: {', '.join(missing)}."
    if current == "sync":
        text += " Задачи закрыты. Сделана ли синхронизация, скрипт не видит: признака в файлах нет."
    if forks["open"] == UNREADABLE:
        text += f" Открытые развилки не посчитаны: {UNREADABLE}."
    return text


def _snapshot(root: Path, change: str, status: dict, apply: dict) -> dict:
    """Поля вывода об одном изменении из ответов форка. Журнал читается только здесь: имя уже прошло `run_fork`."""
    forks = _count_forks(root, change)
    tasks = {"state": apply["state"], "total": apply["progress"]["total"], "complete": apply["progress"]["complete"],
             "remaining": apply["progress"]["remaining"]}
    missing = apply.get("missingArtifacts", [])
    by_status = _next_by_status(status, tasks)
    current = "viewer" if forks["open"] != UNREADABLE and forks["open"] > 0 else by_status
    return {"change": change, "current_step": current, "turn": "human" if current in HUMAN_STEPS else "model",
            "current_text": _current_text(current, by_status, forks, tasks, missing), "next_by_status": by_status,
            "forks": forks, "tasks": tasks, "steps": _pages(root, change, status, forks, tasks, missing)}


def _without_one_change(names: list[str]) -> dict:
    """Шаг без изменения: их нет — начало конвейера (F-33); их несколько — выбирает вызывающий (F-42)."""
    if not names:
        return {"current_step": "intent", "turn": "human",
                "current_text": "Активных изменений нет: следующий шаг по файлам — `intent`, ход человека."}
    return {"current_text": "Активных изменений несколько, шаг считается для одного: укажи его в --change."}


def compute(root: Path | str, change: str | None = None) -> dict:
    """Данные справки для проекта в `root`; корень идёт в форк через `cwd`. Сбой не бросается, а идёт в поле `error`:
    тексты шагов при этом остаются в выводе (F-34, F-54). `changes` считается только без `change`."""
    root = Path(root)
    out = {"contract": CONTRACT, "taken_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "versions": {"openspec": None, "symphysis": _symphysis_version()}, "change": None, "changes": None,
           "error": None, "current_step": None, "current_text": None, "turn": None, "next_by_status": None, "forks": None,
           "tasks": None, "steps": _pages_without_graph(_read_steps(root, DEFAULT_SCHEMA), change)}
    try:
        version = run_fork(root, "--version")
        if version.code != 0:
            raise ForkError(f"`{version.label}` упал с кодом {version.code}: {_reason(None, version)}")
        out["versions"]["openspec"] = _no_paths(_first_line(version.out, version.err), root)
        if "symphysis" not in version.out:
            raise ForkError(f"openspec не тот: `{version.label}` отвечает {out['versions']['openspec'] or 'пусто'}, нужен "
                            "форк symphysis. Поставь его по docs/GUIDE.md или задай SYMPHYSIS_OPENSPEC.")
        if change is None:
            out["changes"] = _active_changes(root)
            if len(out["changes"]) != 1:
                return {**out, **_without_one_change(out["changes"])}
            change = out["changes"][0]
        status = _fork_json(root, "status", "--json", change=change)
        apply = _fork_json(root, "instructions", "apply", "--json", change=change)
        return {**out, **_snapshot(root, change, status, apply)}
    except ForkError as e:
        return {**out, "error": _no_paths(str(e), root)}
    except (KeyError, TypeError, AttributeError, IndexError):
        return {**out, "error": "Ответ форка не той формы: это не тот форк или схема проекта его старше. "
                                "Проверь `openspec status --json` в терминале."}


# --- командная строка -----------------------------------------------------------

def find_root(start: Path) -> Path:
    """Корень проекта для вызова из командной строки — ближайший `openspec/` от каталога вызова, как у форка."""
    return next((folder for folder in (start, *start.parents) if (folder / "openspec").is_dir()), start)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="step_help",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Справка о шаге конвейера: какой шаг следующий по файлам, чей ход, тексты шагов и версии — "
                    "один JSON на stdout.\n"
                    "Область — только расчёт: страницу не собирает, файлов проекта не меняет, содержание шагов не проверяет.\n"
                    "Звать, когда человеку или плагину нужно узнать, где работа и чей ход. Перед шагом не звать: это справка,\n"
                    "а не гейт, и шаг, названный человеком, она не подменяет.",
        epilog="Порядок: корень — ближайший каталог с openspec/ от текущего; форк берётся из SYMPHYSIS_OPENSPEC, "
               "затем из PATH;\n"
               "  без --change берётся единственное активное изменение.\n"
               "Исходы: активных изменений нет — change null, текущий шаг intent; несколько — change и current_step null, имена\n"
               "  в changes; журнал не читается — код 0, вместо числа развилок слова; файла steps.md или раздела нет — код 0,\n"
               "  тексты пусты, text_note говорит, что текста нет; файла версии нет — versions.symphysis null.\n"
               "Коды: 0 — JSON напечатан, error пуст; 1 — JSON напечатан, error называет сбой: форка нет, не тот форк, вызов упал\n"
               f"  или не ответил за {FORK_TIMEOUT} с, в пути к шиму символ для cmd.exe, имя изменения не подходит, такого\n"
               "  изменения нет; 2 — вызов неверен.\n"
               "Маркеры: их нет, вывод только JSON; сбой — поле error, тексты шагов в выводе остаются.")
    ap.add_argument("--change", metavar="ИМЯ", help="имя изменения; без него — единственное активное")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = compute(find_root(Path.cwd()), args.change)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["error"] else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
