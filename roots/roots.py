# -*- coding: utf-8 -*-
"""Корни улик и поиск цитат — модуль `roots` (F-34): константа `ROOT`, файл корней
`tools/journal-roots.json` (`default_roots`, `project_roots`), разрешение пути улики (`_resolve`),
ссылки на файлы (`file_links`, `project_href`) и сверка цитаты с файлом (`find_quote`). Ничего из
файлов журнала не импортирует: от него зависят остальные, он не зависит ни от кого."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import quote

__all__ = [
    "ROOT", "ROOTS_PATH", "UNUSABLE_ROOTS", "OUTSIDE_ROOT", "NOT_CHECKED", "VERDICT_OUTSIDE",
    "change_of", "default_roots", "project_roots", "find_quote", "file_links", "project_href",
]


# Каталог над каталогом кода (F-40): в исходнике — корень репозитория (над `roots/`), в установке — `.symphysis`
# (над `tools/`); `<root>` файла корней раскрывается от него, файл корней в обеих раскладках — `tools/journal-roots.json`.
ROOT = Path(__file__).resolve().parent.parent
ROOTS_PATH = ROOT / "tools" / "journal-roots.json"


# --- корни и сверка цитат --------------------------------------------------

def _expand_value(value: str) -> Path:
    """`<home>` и `~` — домашний каталог; `<root>` — ROOT (каталог над каталогом кода), хвост
    после него разрешается (`<root>/..` — каталог над ROOT)."""
    if value.startswith("<root>"):
        return (ROOT / value[len("<root>"):].lstrip("/\\")).resolve()
    if value.startswith("<home>"):
        value = str(Path.home()) + value[len("<home>"):]
    return Path(value).expanduser()


def change_of(journal_path: Path) -> tuple[Path, str] | None:
    """Корень проекта и имя изменения из пути журнала: `<корень>/openspec/changes/[archive/]<имя>/<журнал>`. Корень не из
    каталога вызова: у вызова может быть свой проект с тем же именем (F-58). Журнал в другом месте — `None`."""
    folder = Path(os.path.abspath(journal_path)).parent
    changes = folder.parent.parent if folder.parent.name == "archive" else folder.parent
    if changes.name == "changes" and changes.parent.name == "openspec":
        return changes.parent.parent, folder.name
    return None


def _roots_from_file(roots_file: Path | None) -> dict[str, Path]:
    raw = json.loads(Path(roots_file or ROOTS_PATH).read_text(encoding="utf-8"))
    return {prefix: _expand_value(value) for prefix, value in raw.items()}


def _inside(path: Path, root: Path) -> bool:
    return Path(os.path.abspath(path)).resolve().is_relative_to(root.resolve())


UNUSABLE_ROOTS = (OSError, ValueError, AttributeError, RuntimeError)   # файла нет, не JSON, не та форма, `~` без домашнего каталога


def _roots_around(path: Path) -> dict[str, Path] | None:
    """Файл корней лежит вне проекта: его корни, только если он называет `""` и `path` внутри этого корня (F-104). У файла клона ядра
    `""` нет, поэтому он инструментами вне проекта и считается. Негодный файл здесь не нужен и команду не роняет: `None`."""
    try:
        roots = _roots_from_file(None)
        return roots if "" in roots and _inside(path, roots[""]) else None
    except UNUSABLE_ROOTS:
        return None


def default_roots(roots_file: Path | None = None, journal_path: Path | None = None) -> dict[str, Path]:
    """Префикс пути улики -> каталог — только из файла корней (`tools/journal-roots.json`
    или `roots_file`); зашитых в код префиксов нет. Значение: `<root>`, `<home>`, `~` или
    путь; пустой префикс `""` — корень по умолчанию, если файл его называет.
    Порядок: явный `roots_file`; журнал не из `openspec/changes/` или файл корней внутри проекта из пути журнала — файл корней;
    файл вне проекта — см. `_roots_around`; иначе инструменты вне проекта (`symphysis.toolsPath`, F-93, F-104): единственный корень — проект."""
    where = change_of(journal_path) if journal_path is not None and roots_file is None else None
    if where is None or _inside(ROOTS_PATH, where[0]):
        return _roots_from_file(roots_file)
    return _roots_around(journal_path) or {"": where[0].resolve()}


def project_roots(project: Path) -> dict[str, Path]:
    """Те же корни для вызова без журнала (`step_help.py`): корень проекта известен по каталогу вызова. Порядок тот же:
    файл корней внутри проекта — его корни, негодный файл — проект; файл вне проекта — см. `_roots_around`; иначе только проект."""
    project = Path(project)
    own = {"": project.resolve()}
    if not _inside(ROOTS_PATH, project):
        return _roots_around(project) or own
    try:
        return {**own, **_roots_from_file(None)}   # файл без `""`: без префикса путь считается от проекта, а не от каталога установки
    except UNUSABLE_ROOTS:
        return own


OUTSIDE_ROOT = Path("<вне корня>")   # признак `_resolve`: путь выходит за корень, файл не читается
BINARY_PROBE = 8192                   # байт NUL в первых 8 КиБ — файл бинарный (F-42)
VERDICT_OUTSIDE = "вне корня"
VERDICT_BINARY = "не проверить: бинарный файл"
VERDICT_NOT_UTF8 = "не проверить: не UTF-8"
VERDICT_UNREADABLE = "не проверить: файл не читается"   # права, чужая блокировка: сигнал, не стоп
NOT_CHECKED = (VERDICT_BINARY, VERDICT_NOT_UTF8, VERDICT_UNREADABLE)
RE_CODE_SPAN = re.compile(r"`([^`]+)`")   # та же разметка, что у `md()` страницы
RE_LINE_TAIL = re.compile(r":\d+(?:-\d+)?$")


def _resolve(path: str, roots: dict[str, Path]) -> Path | None:
    """Файл улики по самому длинному подходящему префиксу: `None` — корня для пути нет,
    `OUTSIDE_ROOT` — путь выходит за корень. Разделители путей нормализуются (обратная косая -> прямая);
    хвост с `..`, абсолютный хвост и файл, который после `resolve()` (регистр диска,
    ссылки и junction разрешены) лежит вне `resolve()`-нутого корня, — «вне корня»."""
    path = path.replace("\\", "/")
    for prefix in sorted(roots, key=len, reverse=True):
        if not path.startswith(prefix.replace("\\", "/")):
            continue
        tail = path[len(prefix):]
        if ".." in tail.split("/") or Path(tail).is_absolute() or tail.startswith("/"):
            return OUTSIDE_ROOT
        root = roots[prefix].resolve()
        file = (root / tail).resolve()
        # корень-файл (`CLAUDE.md`): хвост пуст, файл совпадает с корнем
        return file if file == root or file.is_relative_to(root) else OUTSIDE_ROOT
    return None


def _walk_references(value, paths: set[str]) -> None:
    """Пути из поля `path` и текст в backticks, без хвоста `:строка`; команда или обычное слово отсеются проверкой файла."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "path" and isinstance(item, str):
                paths.add(item)
            else:
                _walk_references(item, paths)
    elif isinstance(value, list):
        for item in value:
            _walk_references(item, paths)
    elif isinstance(value, str):
        paths.update(RE_LINE_TAIL.sub("", code) for code in RE_CODE_SPAN.findall(value))


def _relative_link(path: str, bases: list[dict[str, Path]], here: Path, encode: bool = True) -> str | None:
    """Относительный адрес от каталога `here`: первая база, где это файл внутри корня. Недопустимое имя и другой диск — без ссылки.
    `encode=False` — путь как есть (для плагина), без `quote`."""
    for roots in bases:
        try:
            file = _resolve(path, roots)
            if file is None or file == OUTSIDE_ROOT or not file.is_file():
                continue
            href = os.path.relpath(file, here).replace(os.sep, "/")
            return quote(href, safe="/") if encode else href
        except (OSError, ValueError):
            continue
    return None


def file_links(journal: dict, roots: dict[str, Path], change_dir: Path, out: Path | None, *others,
               from_project: bool = False) -> dict[str, str]:
    """Карта «путь из журнала -> адрес от страницы» для страницы `out`: путь улики или файла справки и текст в backticks
    из журнала и из `others` (атаки, снимок справки), если это существующий файл внутри корней улик или каталога изменения.
    Абсолютных путей в карте нет: страницу можно коммитить; адрес ссылки на странице берётся только отсюда.
    `from_project=True` (F-44): значение от корня `""` (без него — `ROOT`, каталог над каталогом кода), прямые слеши, без кодирования;
    `out` не нужен. `../` бывает только у префикса файла корней на соседний каталог."""
    paths: set[str] = set()
    for value in (journal, *others):
        _walk_references(value, paths)
    bases = [roots, {"": Path(change_dir).resolve()}]
    here = Path(roots.get("", ROOT)).resolve() if from_project else Path(out).resolve().parent
    found = {path: _relative_link(path, bases, here, encode=not from_project) for path in sorted(paths)}
    return {path: href for path, href in found.items() if href}


def project_href(roots: dict[str, Path], out: Path) -> str | None:
    """Адрес корня проекта от страницы `out`: пустой префикс файла корней, без него `ROOT` — каталог над каталогом кода.
    Корень на другом диске — `None`."""
    root = roots.get("", ROOT)
    try:
        return quote(os.path.relpath(Path(root).resolve(), Path(out).resolve().parent).replace(os.sep, "/"), safe="/") + "/"
    except (OSError, ValueError):
        return None


def _read_text(file: Path) -> tuple[str | None, str]:
    """(текст, вердикт): текст `None` — файл читать как текст нельзя, вердикт называет причину."""
    try:
        data = file.read_bytes()
    except OSError:
        return None, VERDICT_UNREADABLE
    if b"\x00" in data[:BINARY_PROBE]:
        return None, VERDICT_BINARY
    try:
        return data.decode("utf-8-sig"), ""
    except UnicodeDecodeError:
        return None, VERDICT_NOT_UTF8


def _match_lines(lines: list[str], quote: list[str]) -> int | None:
    """Номер первой строки совпадения (с 1): однострочная цитата — подстрока строки файла;
    многострочная — подряд идущие строки: первая цитаты — суффикс строки файла, средние равны,
    последняя — префикс следующей. Символы сравниваются как есть."""
    n = len(quote)
    for i, line in enumerate(lines):
        if n == 1:
            if quote[0] in line:
                return i + 1
        elif (i + n <= len(lines) and line.endswith(quote[0]) and lines[i + 1:i + n - 1] == quote[1:-1]
              and lines[i + n - 1].startswith(quote[-1])):
            return i + 1
    return None


def find_quote(path: str, quote: str, roots: dict[str, Path]) -> tuple[int | None, str]:
    """(строка, вердикт): сверка без нормализации по строкам файла, окончания строк в сравнение
    не входят. Нет строки — вердикт называет причину; «не проверить: …» — файл не текст."""
    file = _resolve(path, roots)
    if file is None:
        return None, "корня для пути нет"
    if file is OUTSIDE_ROOT:
        return None, VERDICT_OUTSIDE
    if not file.is_file():
        return None, "файла нет"
    text, verdict = _read_text(file)
    if text is None:
        return None, verdict
    quote_lines = quote.splitlines()
    line = _match_lines(text.splitlines(), quote_lines) if quote_lines else None
    return (line, "сверено") if line is not None else (None, "цитаты нет дословно")
