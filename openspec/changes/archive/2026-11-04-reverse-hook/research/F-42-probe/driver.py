# Проба F-42: какие формы условия if у PostToolUse отсекают запуск обработчика на Windows.
# Запуск: RH_SCRATCH=<каталог> py -3.13 run_all.py. Таблица прогона в $RH_SCRATCH, run_all.py сводит её в run.txt рядом.
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, threading, time

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
PY = shutil.which("py") or "py"
RUN = sys.argv[1]
SCRATCH = pathlib.Path(os.environ["RH_SCRATCH"])

project = pathlib.Path(tempfile.mkdtemp(prefix="rhcc-probe-42-"))
outside = pathlib.Path(tempfile.mkdtemp(prefix="rhcc-probe-42x-"))
ans = project / "openspec" / "changes" / "demo" / "answers"
ext = outside / "openspec" / "changes" / "demo" / "answers"
for d in (ans, ext, project / "notes", project / "docs", project / "answers", project / ".claude"):
    d.mkdir(parents=True)


def posix(p):
    s = str(p).replace("\\", "/")
    return "/" + s[0].lower() + s[2:]


abs_answers_fwd = str(ans).replace("\\", "/")
# Метка, текст условия после разбора JSON: форма 4 с одной обратной косой, форма 5 с двумя.
FORMS = [
    ("нет-if", None),
    ("Read", "Read"),
    ("Read(**/answers/**)", "Read(**/answers/**)"),
    ("Read(**/answers/*.md)", "Read(**/answers/*.md)"),
    ("Read(**\\answers\\**)", "Read(**\\answers\\**)"),
    ("Read(**\\\\answers\\\\**)", "Read(**\\\\answers\\\\**)"),
    ("Read(./**/answers/**)", "Read(./**/answers/**)"),
    ("Read(/**/answers/**)", "Read(/**/answers/**)"),
    ("Read(answers/**)", "Read(answers/**)"),
    ("Read(//**/answers/**)", "Read(//**/answers/**)"),
    ("Read(//c/**/answers/**)", "Read(//c/**/answers/**)"),
    ("Read(C:/**/answers/**)", "Read(C:/**/answers/**)"),
    ("Read(C:\\**\\answers\\**)", "Read(C:\\**\\answers\\**)"),
    ("Read(//<проект>/openspec/changes/demo/answers/**)", f"Read(/{posix(ans)}/**)"),
    ("Read(<проект с C:/>/openspec/changes/demo/answers/**)", f"Read({abs_answers_fwd}/**)"),
    ("Read(<проект с C:\\>\\openspec\\changes\\demo\\answers\\**)", f"Read({ans}\\**)"),
]


def cmd(label):
    # В аргумент уходит номер формы: в самой метке косые и звёздочки, а команду разбирает оболочка.
    return f'"{PY}" -3.13 -I -X utf8 "{HERE / "log.py"}" f{[f[0] for f in FORMS].index(label)}'


hooks = []
for label, cond in FORMS:
    h = {"type": "command", "command": cmd(label)}
    if cond:
        h["if"] = cond
    hooks.append(h)
(project / ".claude" / "settings.local.json").write_text(json.dumps(
    {"hooks": {"PostToolUse": [{"matcher": "Read", "hooks": hooks}]}}, ensure_ascii=False), encoding="utf-8")

# Метка случая, файл, строка file_path для модели. Каждый случай читает свой файл: повторное чтение могло бы не дойти до инструмента.
CASES = []


def case(label, base, rel, make):
    f = base.joinpath(*rel.split("/"))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"проба {label}\n", encoding="utf-8")
    CASES.append((label, make(f)))


back = str
fwd = lambda f: str(f).replace("\\", "/")
SUB = RUN.startswith("sub")
if SUB:
    # Сессия начата в подкаталоге git-репозитория, настройки лежат в его корне: то, что будет при запуске агента не из корня.
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    case("в answers в корне репозитория, обратные", project, "openspec/changes/demo/answers/sub-root-back.md", back)
    case("в answers в корне репозитория, прямые", project, "openspec/changes/demo/answers/sub-root-fwd.md", fwd)
    case("в answers внутри рабочего подкаталога, обратные", project, "sub/answers/sub-in.md", back)
    case("вне answers, обратные", project, "notes/sub-out.md", back)
else:
    case("вне answers, обратные косые", project, "notes/out-back.md", back)
    case("вне answers, прямые косые", project, "notes/out-fwd.md", fwd)
    case("имя answers.md вне каталога answers, обратные", project, "docs/answers.md", back)
    case("имя answers.md вне каталога answers, прямые", project, "docs/answers2.md", fwd)
    case("в answers, обратные косые", project, "openspec/changes/demo/answers/in-back.md", back)
    case("в answers, прямые косые", project, "openspec/changes/demo/answers/in-fwd.md", fwd)
    case("в answers, относительный путь с прямыми", project, "openspec/changes/demo/answers/in-rel.md",
         lambda f: f.relative_to(project).as_posix())
    case("в answers, относительный путь с обратными", project, "openspec/changes/demo/answers/in-relb.md",
         lambda f: str(f.relative_to(project)))
    case("в answers, строчная буква диска", project, "openspec/changes/demo/answers/in-lower.md", lambda f: str(f)[0].lower() + str(f)[1:])
    case("в answers, путь вида /c/Users", project, "openspec/changes/demo/answers/in-msys.md", posix)
    case("в answers в корне проекта, обратные", project, "answers/top-back.md", back)
    case("в answers вне рабочего каталога, обратные", outside, "openspec/changes/demo/answers/x-back.md", back)
    case("в answers вне рабочего каталога, прямые", outside, "openspec/changes/demo/answers/x-fwd.md", fwd)

log = project / "probe-log"
env = {k: v for k, v in os.environ.items() if not (k == "CLAUDECODE" or k.startswith("CLAUDE_"))}
env["RH_F42_LOG"] = str(log)
proc = subprocess.Popen([shutil.which("claude"), "-p", "--input-format", "stream-json", "--output-format", "stream-json",
                         "--verbose", "--model", "haiku", "--setting-sources", "project,local", "--allowedTools", "Read"],
                        cwd=project / "sub" if SUB else project, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
results, tool_inputs = [], []


def reader():
    for raw in proc.stdout:
        try:
            m = json.loads(raw.decode("utf-8"))
        except ValueError:
            continue
        if m.get("type") == "result":
            results.append(1)
        if m.get("type") == "assistant":
            for b in m["message"]["content"]:
                if b.get("type") == "tool_use":
                    tool_inputs.append((b["name"], b["input"].get("file_path") or str(b["input"])))
        if m.get("type") == "user":
            for b in (m.get("message", {}).get("content") or []):
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                    tool_inputs.append(("ошибка", str(b.get("content"))[:200]))


threading.Thread(target=reader, daemon=True).start()
rows = []
project_dirs = set()
taken = set()


def log_lines():
    """Записи запусков, которых ещё не видели."""
    fresh = [p for p in sorted(log.glob("*.json")) if p.name not in taken] if log.exists() else []
    taken.update(p.name for p in fresh)
    return [p.read_text(encoding="utf-8") for p in fresh]


def clean(s):
    s = str(s)
    for base, name in ((project, "проект"), (outside, "вне-каталога")):
        pr = str(base)
        # Сначала особые написания: они остаются видны в следе.
        s = s.replace(posix(base), f"<{name} в виде /c/...>")
        s = s.replace(pr[0].lower() + pr[1:], f"<{name} со строчной c:>")
        for form in (pr, pr.replace("\\", "/"), pr.replace("\\", "\\\\")):
            s = s.replace(form, f"<{name}>")
    return s


for label, path in CASES:
    log_lines()
    had_tools = len(tool_inputs)
    done = len(results)
    prompt = f"Вызови инструмент Read один раз, параметр file_path ровно такой строкой, символ в символ: {path}\nПотом ответь одним словом: да"
    proc.stdin.write((json.dumps({"type": "user", "message": {"role": "user", "content": prompt}}, ensure_ascii=False) + "\n").encode("utf-8"))
    proc.stdin.flush()
    end = time.time() + 90
    while time.time() < end and len(results) == done:
        time.sleep(0.2)
    time.sleep(1)
    fired = [json.loads(x) for x in log_lines()]
    forms = {FORMS[int(x["form"][1:])][0] for x in fired}
    project_dirs.update(clean(x.get("project_dir")) for x in fired)
    rows.append({"случай": label, "модели сказано": clean(path),
                 "инструмент": "; ".join(f"{n}: {clean(v)}" for n, v in tool_inputs[had_tools:]),
                 "в обработчик пришло": "; ".join(sorted({clean(x["file_path"]) for x in fired})), "сработало": len(fired),
                 "формы": [f[0] for f in FORMS if f[0] in forms]})

proc.stdin.close()
try:
    proc.wait(timeout=20)
except subprocess.TimeoutExpired:
    proc.kill()

labels = [f[0] for f in FORMS]
out = [f"--- прогон {RUN}: строка на случай; + форма запустила обработчик, . не запустила"]
if SUB:
    out.append("Рабочий каталог: <проект>\\sub, настройки в <проект>\\.claude, <проект> git-репозиторий.")
    out.append(f"CLAUDE_PROJECT_DIR в обработчике: {sorted(project_dirs)}")
for i, lab in enumerate(labels):
    out.append(f"форма {i:2}: {lab}")
out.append("")
for r in rows:
    marks = "".join("+" if lab in r["формы"] else "." for lab in labels)
    out.append(f"случай: {r['случай']}")
    out.append(f"  модели сказано: {r['модели сказано']}")
    out.append(f"  инструмент: {r['инструмент']}")
    out.append(f"  в обработчик пришло: {r['в обработчик пришло']}")
    out.append(f"  формы 0-{len(labels) - 1}: {marks}  запусков {r['сработало']}")
(SCRATCH / f"f42-run-{RUN}.txt").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
(SCRATCH / f"f42-run-{RUN}.project.txt").write_text(f"{project}\n{outside}\n", encoding="utf-8")
