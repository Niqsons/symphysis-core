# Прогоняет случаи F-48 по четыре разом и сводит след в run.txt. Готовые прогоны из $RH_SCRATCH не повторяет.
# Запуск: RH_SCRATCH=<каталог> py -3.13 run_all.py
import os, pathlib, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path(os.environ["RH_SCRATCH"])
JOBS = [(c, m, str(r)) for c in ("busy", "idle0", "idle1", "during") for m in ("cursor", "last") for r in (1, 2)]
JOBS += [("busy", m, str(r)) for m in ("cursor", "last") for r in (3, 4)]  # в первых прогонах модель дважды отказалась читать файл
JOBS += [("idle03", m, str(r)) for m in ("cursor", "last") for r in (1, 2)]  # между «без паузы» и 1 с


def run(job):
    if (SCRATCH / f"{'-'.join(job)}.txt").exists():
        return
    done = subprocess.run([sys.executable, str(HERE / "driver.py"), *job], capture_output=True, encoding="utf-8")
    print(done.stdout.strip() or done.stderr[-800:], flush=True)


with ThreadPoolExecutor(4) as pool:
    list(pool.map(run, JOBS))

head = """Проба F-48: FileChanged с asyncRewake, пока сессия занята, и при двух событиях подряд.
2026-11-04, Claude Code 2.1.318, Windows 11, модель haiku, claude -p --input-format stream-json, сессия живёт, пока открыт вход.
Настройка: .claude/settings.local.json, --setting-sources project,local; SessionStart отдаёт watchPaths, FileChanged с matcher events.jsonl и asyncRewake, PostToolUse с matcher Read.
Обработчик cursor читает все строки от смещения, как read_unread в настоящем hook.py; обработчик last только последнюю строку файла. Нечего сказать: код 0.
Событие A указывает файл 2026-11-04.md, событие B файл 2026-11-04-2.md.
Случаи: busy: модель выполняет sleep 20, событие A на пятой секунде. idle0: простой, A и B без паузы. idle03: простой, A и B с паузой 0,3 с. idle1: простой, A и B с паузой 1 с. during: простой, A, затем B при первом инструменте хода от A.
Запись «ход №N окончен» значит сообщение result в потоке; первый ход начат репликой пробы, остальные начаты без реплики.
Записи сессии: type/operation/attachment и какие файлы названы в тексте. Время в секундах от запуска процесса. Каталог проекта заменён на <проект>.

"""
parts = [head]
for job in JOBS:
    p = SCRATCH / f"{'-'.join(job)}.txt"
    parts.append(p.read_text(encoding="utf-8") if p.exists() else f"=== {job}: следа нет\n\n")
(HERE / "run.txt").write_text("".join(parts), encoding="utf-8", newline="\n")
