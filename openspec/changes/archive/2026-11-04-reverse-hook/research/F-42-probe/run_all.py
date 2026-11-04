# Прогоны пробы F-42 по очереди, след сводится в run.txt: 1 и 2 в корне проекта, sub1 и sub2 в подкаталоге git-репозитория.
# Готовые прогоны из $RH_SCRATCH не повторяет.
# Запуск: RH_SCRATCH=<каталог> py -3.13 run_all.py
import os, pathlib, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path(os.environ["RH_SCRATCH"])
RUNS = ("1", "2", "sub1", "sub2")
for run in RUNS:
    if not (SCRATCH / f"f42-run-{run}.txt").exists():
        subprocess.run([sys.executable, str(HERE / "driver.py"), run], check=True)

head = """Проба F-42: какие формы условия if у PostToolUse отсекают запуск обработчика на Windows.
2026-11-04, Claude Code 2.1.318, Windows 11, модель haiku, claude -p --input-format stream-json --setting-sources project,local --allowedTools Read.
Настройка: .claude/settings.local.json, PostToolUse с matcher Read и по обработчику на форму условия. Каждый запуск обработчика оставляет свой файл с номером формы и полученным file_path, считаются файлы.
Реплика на случай: вызвать Read ровно с указанной строкой file_path. Каждый случай читает свой файл. Рабочий каталог: <проект>. <вне-каталога>: второй временный каталог рядом с ним.
Строка «инструмент»: file_path в вызове модели. Строка «в обработчик пришло»: tool_input.file_path на входе обработчика.

"""
parts = [head]
for run in RUNS:
    parts.append((SCRATCH / f"f42-run-{run}.txt").read_text(encoding="utf-8") + "\n")
(HERE / "run.txt").write_text("".join(parts), encoding="utf-8", newline="\n")
