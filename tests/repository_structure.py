"""Проверка структуры репозитория ядра: README корня, README модулей, места модулей, копии файлов.

Функции читают корень репозитория и файлы, которые знает git (`git ls-files`):
каталоги вне git (`upstream/`, `.symphysis/`, `__pycache__/`) в счёт не идут.
Каждая проверка возвращает список строк-замечаний; пустой список — зелёный.
Только стандартная библиотека: frontmatter разбирается вручную, загрузчика YAML нет —
содержимое README это данные, теги YAML не исполняются (security.md, «Инъекции через содержимое файлов»).
"""
import hashlib
import posixpath
import re
import subprocess
from pathlib import Path

KINDS = ("доменный", "технический")
MARKS = ("модуль", "контур разработки")
SCHEMA_MODULE = "openspec/schemas/symphysis"

# Строка README корня о каталоге: `[имя/](имя/) — модуль` (одна форма ссылки, F-50 B).
_ROOT_LINE = re.compile(r"^\s*(?:[-*]\s+)?\[[^\]]*/\]\(")
_ROOT_FULL = re.compile(r"^\s*(?:[-*]\s+)?\[([^\]]*)\]\(([^)]*)\)\s*—\s*(модуль|контур разработки)(?!\w)")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)\)")


class Repo:
    """Корень и файлы, известные git (индекс)."""

    def __init__(self, root):
        self.root = Path(root)
        out = subprocess.run(["git", "-C", str(self.root), "ls-files", "-z"], capture_output=True, check=True).stdout
        self.files = sorted(p for p in out.decode("utf-8").split("\0") if p)
        self.dirs = set()
        for f in self.files:
            parts = f.split("/")
            for i in range(1, len(parts)):
                self.dirs.add("/".join(parts[:i]))

    def top_dirs(self):
        return sorted(d for d in self.dirs if "/" not in d)

    def subdirs(self, d):
        """Вложенные каталоги первого уровня каталога `d` (только известные git)."""
        return sorted(x[len(d) + 1:] for x in self.dirs if x.startswith(d + "/") and "/" not in x[len(d) + 1:])

    def read(self, rel):
        return (self.root / rel).read_bytes().decode("utf-8-sig", errors="replace")


def split_frontmatter(text):
    """(строки frontmatter, тело) или (None, text), если README не начинается с `---`."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1:])
    return None, text


def parse_frontmatter(text):
    """Скалярные `name` и `kind` вручную. Возвращает (поля, ошибки); поля None — frontmatter нет."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        return None, []
    fields, errors = {}, []
    for line in fm:
        m = re.match(r"^(name|kind)\s*:(.*)$", line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if key in fields:
            errors.append(f"поле `{key}` повторено")
            continue
        if raw[:1] in ("'", '"'):
            end = raw.find(raw[0], 1)
            if end < 0:
                errors.append(f"поле `{key}`: незакрытая кавычка")
                continue
            value = raw[1:end]
        else:
            value = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
            if value[:1] in ("!", "&", "*", "|", ">", "[", "{", "%", "@", "`"):
                errors.append(f"поле `{key}`: тег или не скаляр YAML `{value}`")
                continue
        fields[key] = value
    return fields, errors


def _has_frontmatter(repo, rel_readme):
    fm, _ = split_frontmatter(repo.read(rel_readme))
    return fm is not None


def root_marks(repo):
    """Строки README корня о каталогах: ({каталог: пометка}, замечания)."""
    marks, problems = {}, []
    if "README.md" not in repo.files:
        return marks, ["README.md в корне: файла нет"]
    for n, line in enumerate(repo.read("README.md").splitlines(), 1):
        if not _ROOT_LINE.match(line):
            continue
        m = _ROOT_FULL.match(line)
        if not m or m.group(1) != m.group(2) or "/" in m.group(1)[:-1]:
            problems.append(f"README.md:{n}: строка не в форме `[имя/](имя/) — модуль|контур разработки`: {line.strip()}")
            continue
        marks[m.group(1)[:-1]] = m.group(3)
    return marks, problems


def check_root_readme(repo):
    """1.1: каждый каталог первого уровня из git назван в README корня с пометкой; обратная сверка;
    у каталога контура разработки нет README модуля."""
    marks, problems = root_marks(repo)
    tops = repo.top_dirs()
    for d in tops:
        if d not in marks:
            problems.append(f"{d}/: каталог первого уровня без строки в README корня")
    for d in sorted(marks):
        if d not in tops:
            problems.append(f"README.md: строка о каталоге `{d}/`, которого в корне нет")
    for d, mark in sorted(marks.items()):
        rd = f"{d}/README.md"
        if mark == "контур разработки" and rd in repo.files and _has_frontmatter(repo, rd):
            problems.append(f"{d}/: контур разработки с README модуля")
    return problems


def module_dirs(repo):
    """Каталоги, которые считаются модулями: помеченные «модуль» в README корня, каталог схемы
    и любой каталог глубже первого уровня с README, начинающимся frontmatter (поймать модуль не на месте)."""
    marks, _ = root_marks(repo)
    found = {d for d, m in marks.items() if m == "модуль" and d in repo.dirs}
    if SCHEMA_MODULE in repo.dirs:
        found.add(SCHEMA_MODULE)
    for f in repo.files:
        if f.endswith("/README.md"):
            d = f[:-len("/README.md")]
            if "/" in d and _has_frontmatter(repo, f):
                found.add(d)
    return sorted(found)


def check_module_frontmatter(repo):
    """1.2: frontmatter README модуля — `name` непустое, `kind` из двух значений, имена не повторяются."""
    problems, names = [], {}
    for d in module_dirs(repo):
        rd = f"{d}/README.md"
        if rd not in repo.files:
            problems.append(f"{d}/: у модуля нет README.md")
            continue
        fields, errors = parse_frontmatter(repo.read(rd))
        if fields is None:
            problems.append(f"{d}/: README модуля не начинается с frontmatter")
            continue
        problems += [f"{d}/: {e}" for e in errors]
        for key in ("name", "kind"):
            if key not in fields and not any(f"`{key}`" in e for e in errors):
                problems.append(f"{d}/: во frontmatter нет поля `{key}`")
        if "name" in fields:
            if not fields["name"].strip():
                problems.append(f"{d}/: пустое имя модуля")
            else:
                names.setdefault(fields["name"], []).append(d)
        if "kind" in fields and fields["kind"] not in KINDS:
            problems.append(f"{d}/: kind `{fields['kind']}` вне значений {', '.join(KINDS)}")
    for name, dirs in sorted(names.items()):
        if len(dirs) > 1:
            problems.append(f"имя модуля `{name}` повторено: " + ", ".join(f"{x}/" for x in dirs))
    return problems


def readme_dir_links(text, module):
    """Ссылки README на вложенные каталоги модуля: ([(имя, есть ли строка о нём)], [замечания о форме]).
    Путь нормализуется; ссылка, выходящая за каталог модуля, не засчитывается."""
    _, body = split_frontmatter(text)
    found, problems = [], []
    in_code = False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        for m in _LINK.finditer(line):
            label, href = m.group(1), m.group(2)
            if "://" in href or href.startswith(("#", "mailto:")) or not href.endswith("/"):
                continue
            norm = posixpath.normpath(posixpath.join(module, href))
            if not norm.startswith(module + "/"):
                continue
            rel = norm[len(module) + 1:]
            if "/" in rel:
                continue
            if label != href or href != rel + "/":
                problems.append(f"ссылка `[{label}]({href})` не в форме `[{rel}/]({rel}/)`")
                continue
            found.append((rel, bool(re.search(r"\w", line[m.end():]))))
    return found, problems


def check_nested_dirs(repo):
    """1.3: ссылка `[имя/](имя/)` и строка на каждый вложенный каталог из git; ссылка на отсутствующий — красный."""
    problems = []
    for d in module_dirs(repo):
        rd = f"{d}/README.md"
        if rd not in repo.files:
            continue
        links, form = readme_dir_links(repo.read(rd), d)
        problems += [f"{d}/: {p}" for p in form]
        linked = {}
        for rel, has_text in links:
            linked[rel] = linked.get(rel, False) or has_text
        real = set(repo.subdirs(d))
        for rel in sorted(real - set(linked)):
            problems.append(f"{d}/: вложенный каталог `{rel}/` не описан в README модуля")
        for rel in sorted(set(linked) - real):
            problems.append(f"{d}/: README ссылается на `{rel}/`, а каталога в модуле нет")
        for rel in sorted(real & set(linked)):
            if not linked[rel]:
                problems.append(f"{d}/: у ссылки на `{rel}/` нет строки о каталоге")
    return problems


def check_module_places(repo):
    """1.4: модуль — каталог первого уровня или `openspec/schemas/symphysis`; модуль в модуле — красный."""
    problems = []
    mods = module_dirs(repo)
    for d in mods:
        if "/" in d and d != SCHEMA_MODULE:
            problems.append(f"{d}/: модуль не на своём месте (первый уровень или {SCHEMA_MODULE}/)")
        for other in mods:
            if d.startswith(other + "/"):
                problems.append(f"{d}/: модуль внутри модуля {other}/")
    return problems


def check_copies(repo):
    """1.5: файл с одним содержимым (хеш байтов, без декодирования) в двух модулях — красный с обоими путями."""
    mods = module_dirs(repo)
    seen, problems = {}, []
    for f in repo.files:
        owner = max((m for m in mods if f.startswith(m + "/")), key=len, default=None)
        path = repo.root / f
        if owner is None or not path.is_file():
            continue
        data = path.read_bytes()
        if not data:
            continue
        h = hashlib.sha256(data).hexdigest()
        for prev_owner, prev in seen.get(h, []):
            if prev_owner != owner:
                problems.append(f"копия в двух модулях: {prev} и {f}")
        seen.setdefault(h, []).append((owner, f))
    return problems


def check_repository(root):
    repo = Repo(root)
    return (check_root_readme(repo) + check_module_frontmatter(repo) + check_nested_dirs(repo)
            + check_module_places(repo) + check_copies(repo))
