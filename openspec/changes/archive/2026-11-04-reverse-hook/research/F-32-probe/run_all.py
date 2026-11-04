# Прогоняет случаи F-32 по четыре разом и сводит след в run.txt. Готовые прогоны из $RH_SCRATCH не повторяет.
# Запуск: RH_SCRATCH=<каталог> RH_BASE_OUTSIDE_TEMP=<каталог не в %TEMP%> py -3.13 run_all.py
import json, os, pathlib, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path(os.environ["RH_SCRATCH"])
CASES = ("control", "late-nodir", "late-nofile", "late-edit", "ups-hso", "ups-top", "cwd-control", "cwd-late",
         "seed-late", "compact-late", "clear-late", "config-late", "wake-busy", "late-nofile-nt", "cwd-control-nt", "cwd-late-nt", "control-cd-nt")
JOBS = [(c, str(r)) for c in CASES for r in (1, 2)]


def run(job):
    if (SCRATCH / f"f32-{job[0]}-{job[1]}.txt").exists():
        return
    done = subprocess.run([sys.executable, str(HERE / "driver.py"), *job], capture_output=True, encoding="utf-8")
    print(done.stdout.strip() or done.stderr[-800:], flush=True)


with ThreadPoolExecutor(4) as pool:
    list(pool.map(run, JOBS))

head = """Проба F-32: подхватывает ли идущая сессия хуки, появившиеся в .claude/settings.local.json после запуска.
2026-11-04, Claude Code 2.1.318, Windows 11, модель haiku, только claude -p --input-format stream-json --setting-sources project,local --allowedTools "Bash(cd *)" "Bash(sleep *)". Интерактивный клиент не проверен.
Сессия без хуков, после первого ответа файл настроек записывается через временный файл и замену, как у плагина. Проверки: запись в .symphysis/viewer/events.jsonl (глубокий) и в events.jsonl в рабочем каталоге (корневой), реплика.
Случаи:
control: хуки с начала: SessionStart отдаёт watchPaths, UserPromptSubmit пишет журнал, FileChanged matcher events.jsonl.
late-nodir: те же хуки, каталога .claude при запуске не было. late-nofile: каталог был, файла нет. late-edit: файл был без хуков.
ups-hso: поздний UserPromptSubmit отдаёт hookSpecificOutput.watchPaths. ups-top: то же верхним полем watchPaths.
cwd-control: CwdChanged с watchPaths с начала, реплика просит модель выполнить cd. cwd-late: тот же хук поздний.
seed-late: поздний FileChanged matcher events.jsonl|seed.txt, на seed.txt отдаёт watchPaths.
compact-late: поздние хуки как control, реплика /compact. clear-late: то же, реплика /clear. config-late: поздний ConfigChange отдаёт watchPaths, настройки правятся ещё раз.
wake-busy: хуки с начала, запись во время sleep 12, затем реплика и запись в простое: на чём запускается UserPromptSubmit.
Случаи с окончанием -nt: проект не в %TEMP%, а в каталоге рядом с ним, потому что внутри %TEMP% cd модели не держался и CwdChanged не срабатывал. control-cd-nt: хуки как control, без CwdChanged, реплика просит выполнить cd.
«по шагам»: какие обработчики запустились от этого шага до следующего. Время в секундах от запуска процесса. Каталог проекта заменён на <проект>.
Поле prompt обработчик стал писать не сразу: в случаях late-nodir, late-nofile, late-edit, ups-*, cwd-control, cwd-late, seed-late, compact-late, config-late его в журнале нет, вместо него там лишнее поле cfg. На остальное поведение обработчика это не влияет.

"""
KEYS = ("FileChanged: watching", "FileChanged: change", "Detected change to", "Settings changed from", "provided 1 watchPaths", "shell cwd read-back", "CwdChanged")


def client_lines(job):
    """Строки журнала клиента про настройки и наблюдатель: что клиент сам говорит о них."""
    log = SCRATCH / f"f32-{job[0]}-{job[1]}.debug.log"
    where = SCRATCH / f"f32-{job[0]}-{job[1]}.project.txt"
    if not log.exists() or not where.exists():
        return []
    project = where.read_text(encoding="utf-8").strip()
    out = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if any(k in line for k in KEYS) and "Hooks: " not in line:
            for form in (project, project.replace("\\", "/"), project.replace("\\", "\\\\")):
                line = line.replace(form, "<проект>")
            line = re.sub(r'"[^"]*py\.EXE" -3\.13 -I -X utf8 "[^"]*h\.py"', "h.py", line, flags=re.I)
            out.append("  " + line[11:23] + " " + line[24:][:150])
    # Что вернул Bash с командой cd: держится ли смена каталога.
    stream = SCRATCH / f"f32-{job[0]}-{job[1]}.stream.jsonl"
    cd_ids = set()
    for raw in stream.read_text(encoding="utf-8", errors="replace").splitlines() if stream.exists() else []:
        try:
            m = json.loads(raw)
        except ValueError:
            continue
        for b in (m.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and str((b.get("input") or {}).get("command", "")).startswith("cd "):
                cd_ids.add(b["id"])
            if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in cd_ids:
                text = str(b.get("content"))
                for form in (project, project.replace("\\", "/"), project.replace("\\", "\\\\")):
                    text = text.replace(form, "<проект>")
                out.append("  результат Bash с cd: " + (text or "пусто"))
    return out


parts = [head]
for job in JOBS:
    p = SCRATCH / f"f32-{job[0]}-{job[1]}.txt"
    if not p.exists():
        parts.append(f"=== {job}: следа нет\n\n")
        continue
    text = p.read_text(encoding="utf-8").rstrip("\n")
    parts.append(text + "\n--- журнал клиента (--debug-file): строки про настройки и наблюдатель, время суток\n"
                 + "".join(x + "\n" for x in client_lines(job)) + "\n")
parts.append("Вывод mount в Git Bash на этой машине, имя заменено: C:/Users/<имя>/AppData/Local/Temp on /tmp type ntfs (binary,noacl,posix=0,usertemp)\n")
(HERE / "run.txt").write_text("".join(parts), encoding="utf-8", newline="\n")
