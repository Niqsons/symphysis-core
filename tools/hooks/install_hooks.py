#!/usr/bin/env python3
"""Ставит хуки гейта имён в `.git/hooks` общего каталога проекта.

Хук лежит там, а не подключается относительным `core.hooksPath`: при относительном пути ветка старше хука в своём
worktree пушится без проверки. Файл `.git/hooks` не версионируется, поэтому его ставят этим шагом на каждой машине.

    python tools/hooks/install_hooks.py --pre-commit           ядро: pre-commit и pre-push
    python tools/hooks/install_hooks.py --project ../symphysis-vscode     плагин: pre-push
"""
import argparse
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "gate_hook.py"
MARK = "# symphysis: хук гейта имён, ставит tools/hooks/install_hooks.py"


def stub(mode: str) -> str:
    return f'#!/bin/sh\n{MARK}\nexec python "{HOOK.as_posix()}" {mode} "$@"\n'


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Ставит хуки гейта имён в .git/hooks общего каталога проекта.")
    ap.add_argument("--project", default=".", help="каталог проекта")
    ap.add_argument("--pre-commit", action="store_true", help="поставить и pre-commit")
    args = ap.parse_args()
    project = Path(args.project).resolve()
    common = subprocess.run(["git", "-C", str(project), "rev-parse", "--git-common-dir"], capture_output=True, text=True, encoding="utf-8")
    if common.returncode != 0:
        print(f"[!!] не репозиторий git: {project}")
        return 2
    hooks = (project / common.stdout.strip()).resolve() / "hooks"
    hooks.mkdir(exist_ok=True)
    modes = ["pre-push", *(["pre-commit"] if args.pre_commit else [])]
    for mode in modes:
        target = hooks / mode
        if target.exists() and MARK not in target.read_text(encoding="utf-8", errors="replace"):
            print(f"[!!] {mode}: уже есть чужой хук, не перезаписан: {target}")
            return 2
    for mode in modes:
        target = hooks / mode
        target.write_text(stub(mode), encoding="utf-8", newline="\n")
        target.chmod(0o755)
        print(f"[ok] {mode}: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
