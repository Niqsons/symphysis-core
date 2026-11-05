#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Справка о шаге конвейера: какой шаг следующий по файлам и чей ход — по выводу форка, журналу и задачам (F-19, F-23).

Расчёт отделён от разбора аргументов: `compute(корень, имя)` зовёт и `render-html` (F-34). Скрипт пишет только в stdout,
файлов проекта не меняет и шага не останавливает (F-50). Форк зовёт общий модуль `openspec_run` (F-138): поиск форка,
проверка имени изменения (`security.md`), телеметрия (F-57), предел и снятие дерева процессов (F-43, F-66). Абсолютных
путей в выводе нет, страница со снимком отслеживается git (F-51)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # скрипт пишет только в stdout (F-50): `__pycache__` в проекте от него не появляется
from journal_render import CONTRACT  # noqa: E402
from openspec_run import FORK_TIMEOUT, SAFE_NAME, ForkError, ForkReply, no_paths, run_fork  # noqa: E402

__all__ = ["compute", "parse_steps", "build_parser", "main"]

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
    if current == "apply":  # счётчик задач живёт в шапке, в тексте его нет (F-55)
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


SKILL_NAME = re.compile(r"`(symphysis-[\w-]+)`")
PROJECT_SKILL_DIRS = (".claude/skills", ".opencode/skills", ".agents/skills")
INSTALL_SKILL_DIRS = (*PROJECT_SKILL_DIRS, "skills")  # R16: в клоне ядра скиллы лежат в `skills/`, в установке — как в проекте


def _find_skill(name: str, root: Path, install_dir: Path | None) -> dict:
    """Файл скилла: сначала проект, затем каталог установки; путь с `/` от того каталога, где найден (F-46, F-56)."""
    for base, label, dirs in ((root, "project", PROJECT_SKILL_DIRS), (install_dir, "install", INSTALL_SKILL_DIRS)):
        if base is None:
            continue
        for directory in dirs:
            if (base / directory / name / "SKILL.md").is_file():
                return {"name": name, "path": f"{directory}/{name}/SKILL.md", "base": label}
    return {"name": name, "path": None, "base": None}


def _add_skills(steps: list[dict], root: Path, install_dir: Path | None) -> None:
    """Поле `skills` у каждого шага: имена `symphysis-*` в обратных кавычках из его текстов, по одной записи на имя."""
    for page in steps:
        names = dict.fromkeys(name for text in page["texts"].values() for name in SKILL_NAME.findall(text))
        page["skills"] = [_find_skill(name, root, install_dir) for name in names]


def _file_links(out: dict, root: Path, change: str | None) -> dict:
    """Карта ссылок общим кодом ядра, корни те же, что у `view-json` (F-44, F-104): файлы шагов, текст шагов в обратных кавычках,
    проектные скиллы. Файл скилла из каталога установки сюда не идёт: плагин открывает его по `skills` (F-91)."""
    from journal_apply import file_links, project_roots
    change_dir = root / "openspec" / "changes" / change if change and SAFE_NAME.fullmatch(change) else root   # отвергнутое имя каталогом не становится
    skills = [{"path": skill["path"]} for page in out["steps"] for skill in page["skills"] if skill["base"] == "project"]
    try:
        return file_links({}, project_roots(root), change_dir, None, [{**page, "skills": []} for page in out["steps"]],
                          out["current_text"], skills, from_project=True)
    except (OSError, ValueError):  # ссылки справке не нужны для работы: без карты всё остаётся текстом
        return {}


def compute(root: Path | str, change: str | None = None, install_dir: Path | str | None = None) -> dict:
    """Данные справки: `_compute` плюс поля `skills` у шагов и `file_links`, они считаются и при сбое расчёта.
    `install_dir` — где после проекта искать скиллы; корень и остальные поля он не меняет, без него ищется только в проекте."""
    root = Path(root)
    result = _compute(root, change)
    _add_skills(result["steps"], root, None if install_dir is None else Path(install_dir))
    result["file_links"] = _file_links(result, root, result["change"] or change)
    return result


def _compute(root: Path, change: str | None) -> dict:
    """Данные справки для проекта в `root`; корень идёт в форк через `cwd`. Сбой не бросается, а идёт в поле `error`:
    тексты шагов при этом остаются в выводе (F-34, F-54). `changes` считается только без `change`."""
    out = {"contract": CONTRACT, "taken_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "versions": {"openspec": None, "symphysis": _symphysis_version()}, "change": None, "changes": None,
           "error": None, "current_step": None, "current_text": None, "turn": None, "next_by_status": None, "forks": None,
           "tasks": None, "steps": _pages_without_graph(_read_steps(root, DEFAULT_SCHEMA), change)}
    try:
        version = run_fork(root, "--version")
        if version.code != 0:
            raise ForkError(f"`{version.label}` упал с кодом {version.code}: {_reason(None, version)}")
        out["versions"]["openspec"] = no_paths(_first_line(version.out, version.err), root)
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
        return {**out, "error": no_paths(str(e), root)}
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
    ap.add_argument("--install-dir", metavar="КАТАЛОГ", type=Path,
                    help="где после проекта искать файлы скиллов шагов (клон ядра или установка); без него — только в проекте; "
                         "корень проекта и остальной вывод он не меняет")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = compute(find_root(Path.cwd()), args.change, args.install_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["error"] else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
