#!/usr/bin/env python3
"""Хук гейта имён для ядра и плагина: `pre-commit` проверяет индекс, `pre-push` — то, что уходит.

Сам гейт не меняется: другие репозитории держат его копии, поэтому диапазон считается здесь, а гейту подаются файлы.
Дерево проверки — временный каталог с содержимым из git, не рабочая копия: уходит индекс и коммиты, а не то, что лежит
на диске. Без гейта или без его списка имён хук отказывает, а не пропускает.

Шаблон ключей задач живёт здесь, потому что гейт сверяет список строк, а ключ — это любой префикс с номером.
Подавить находку в строке можно меткой `gate-ok`, как у гейта.

Обойти сознательно: `--no-verify`.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GATE_DEFAULT = "X:/architecture-ways/tools/check_names.py"
ALLOW_FILES = ("allowed-hosts.txt", "allowed-lines.txt")
KEY = re.compile(r"\b([A-Z]{2,10})-\d{2,6}\b")
# Префиксы с номером, которые не ключи задач: стандарты, кодировки и номера в разобранных источниках.
KEY_ALLOW = {"SHA", "UTF", "ISO", "RFC", "CVE", "CWE", "PEP", "ADR", "PROB", "FF", "GPT", "HTTP", "TLS"}
BATCH = 200


def git(*args: str, text: bool = True, stdin: str | None = None):
    run = subprocess.run(["git", *args], capture_output=True, input=stdin.encode("utf-8") if stdin is not None else None)
    if run.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {run.stderr.decode('utf-8', 'replace').strip()}")
    return run.stdout.decode("utf-8", "replace") if text else run.stdout


def staged() -> list[tuple[str, bytes]]:
    names = git("diff", "--cached", "--name-only", "--diff-filter=ACM", "-z").split("\0")
    return [(n, git("show", f":{n}", text=False)) for n in names if n]


def remote_tracking_excluded(remote: str) -> list[str]:
    """`--remotes` принимает имя удалённого; при пуше по адресу отсечь нечего, и проверяется весь диапазон."""
    return ["--not", f"--remotes={remote}"] if re.fullmatch(r"[\w.-]+", remote) else []


def outgoing(remote: str, lines: list[str]) -> list[tuple[str, bytes]]:
    """Содержимое и сообщения коммитов, которых на удалённом ещё нет."""
    items: dict[str, tuple[str, bytes]] = {}
    for line in lines:
        parts = line.split()
        if len(parts) != 4 or set(parts[1]) == {"0"}:
            continue
        rev = [parts[1], *remote_tracking_excluded(remote)]
        for sha in git("rev-list", *rev).split():
            items[f"msg:{sha}"] = (f"commit-messages/{sha}.txt", git("log", "-1", "--format=%B", sha, text=False))
        objects = [o.split(" ", 1) for o in git("rev-list", "--objects", *rev).splitlines()]
        paths = {o[0]: o[1] for o in objects if len(o) == 2}
        if not paths:
            continue
        kinds = git("cat-file", "--batch-check=%(objectname) %(objecttype)", stdin="\n".join(paths) + "\n")
        for row in kinds.splitlines():
            sha, kind = row.split(" ", 1)
            if kind == "blob":
                items[sha] = (paths[sha], git("cat-file", "blob", sha, text=False))
    return list(items.values())


def key_findings(rel: str, data: bytes) -> list[str]:
    if b"\0" in data[:8000]:
        return []
    found = []
    for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
        if "gate-ok" in line:
            continue
        for match in KEY.finditer(line):
            if match.group(1) not in KEY_ALLOW:
                found.append(f"[!!] {rel}:{number}: [ключ задачи] {match.group(0)}")
    return found


def check(items: list[tuple[str, bytes]]) -> int:
    gate = os.environ.get("SYMPHYSIS_GATE") or GATE_DEFAULT
    if not os.path.isfile(gate):
        print(f"[!!] гейт не найден: {gate}. Хук отказывает, а не пропускает.")
        return 2
    if not items:
        return 0
    problems = [f for rel, data in items for f in key_findings(rel, data)]
    top = Path(git("rev-parse", "--show-toplevel").strip())
    tree = Path(tempfile.mkdtemp(prefix="gate-"))
    try:
        for name in ALLOW_FILES:
            source = top / "tools" / name
            if source.is_file():
                (tree / "tools").mkdir(exist_ok=True)
                shutil.copyfile(source, tree / "tools" / name)
        names = []
        for rel, data in items:
            target = tree / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            names.append(rel)
        code = 0
        env = dict(os.environ, PYTHONUTF8="1")
        for start in range(0, len(names), BATCH):
            run = subprocess.run([sys.executable, gate, *names[start:start + BATCH]], cwd=tree, env=env,
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
            if run.returncode != 0:
                print(run.stdout.rstrip())
                print(run.stderr.rstrip())
                code = max(code, run.returncode)
    finally:
        shutil.rmtree(tree, ignore_errors=True)
    for line in problems:
        print(line)
    return code or (1 if problems else 0)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Хук гейта имён: индекс перед коммитом, уходящий диапазон перед пушем.")
    ap.add_argument("mode", choices=["pre-commit", "pre-push"])
    ap.add_argument("remote", nargs="?", default="")
    ap.add_argument("url", nargs="?", default="")
    args = ap.parse_args()
    try:
        items = staged() if args.mode == "pre-commit" else outgoing(args.remote, sys.stdin.read().splitlines())
    except RuntimeError as error:
        print(f"[!!] {error}. Хук отказывает, а не пропускает.")
        return 2
    return check(items)


if __name__ == "__main__":
    sys.exit(main())
