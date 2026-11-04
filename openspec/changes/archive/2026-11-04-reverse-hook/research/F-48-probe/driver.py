# Проба F-48: что с сообщением FileChanged + asyncRewake, пока сессия занята, и при двух событиях подряд.
# Запуск: py -3.13 driver.py <случай> <cursor|last> <номер прогона>, случай: busy, idle0, idle03, idle1, during.
# След прогона пишется в $RH_SCRATCH, run_all.py сводит его в run.txt рядом и удаляет временный проект и запись сессии.
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, threading, time

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
PY = shutil.which("py") or "py"
CASE, MODE, RUN = sys.argv[1], sys.argv[2], sys.argv[3]
SCRATCH = pathlib.Path(os.environ["RH_SCRATCH"])  # сырые копии для разбора, вне дерева
A, B = "openspec/changes/demo/answers/2026-11-04.md", "openspec/changes/demo/answers/2026-11-04-2.md"


def hook_cmd(script, *args):
    return f'"{PY}" -3.13 -I -X utf8 "{HERE / script}"' + "".join(f" {a}" for a in args)


project = pathlib.Path(tempfile.mkdtemp(prefix="rhcc-probe-48-"))
viewer = project / ".symphysis" / "viewer"
viewer.mkdir(parents=True)
events = viewer / "events.jsonl"
events.write_text("", encoding="utf-8")
(project / A).parent.mkdir(parents=True)
(project / A).write_text("- F-01: A — первый ответ\n", encoding="utf-8")
(project / B).write_text("- F-02: B — второй ответ\n", encoding="utf-8")
(project / ".claude").mkdir()
(project / ".claude" / "settings.local.json").write_text(json.dumps({"hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "command": hook_cmd("start.py")}]}],
    "FileChanged": [{"matcher": "events.jsonl", "hooks": [
        {"type": "command", "command": hook_cmd("wake.py", MODE), "asyncRewake": True, "timeout": 30}]}],
    "PostToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": hook_cmd("read.py")}]}],
}}, ensure_ascii=False), encoding="utf-8")

# Родительская сессия не должна протекать в дочернюю: сокеты сообщений, порт IDE, номер сессии.
env = {k: v for k, v in os.environ.items() if not (k == "CLAUDECODE" or k.startswith("CLAUDE_"))}
raw_name = f"{CASE}-{MODE}-{RUN}"
proc = subprocess.Popen([shutil.which("claude"), "-p", "--input-format", "stream-json", "--output-format", "stream-json",
                         "--verbose", "--include-hook-events", "--model", "haiku",
                         "--setting-sources", "project,local", "--allowedTools", "Bash(sleep *)", "Read"],
                        cwd=project, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
t0 = time.time()
stream, results = [], []
last_activity = [time.time()]
first_tool_after = {}
raw_out = open(SCRATCH / f"{raw_name}.stream.jsonl", "wb")


def note(kind, text):
    stream.append((round(time.time() - t0, 1), kind, text))


def reader():
    for raw in proc.stdout:
        raw_out.write(raw)
        raw_out.flush()
        last_activity[0] = time.time()
        try:
            m = json.loads(raw.decode("utf-8"))
        except ValueError:
            continue
        kind = m.get("type")
        if kind == "result":
            results.append(time.time() - t0)
            note("result", f"ход №{len(results)} окончен")
        elif kind == "assistant":
            for b in m["message"]["content"]:
                if b.get("type") == "text" and b["text"]:
                    note("модель", b["text"][:240])
                if b.get("type") == "tool_use":
                    first_tool_after.setdefault(b["name"], time.time() - t0)
                    note("инструмент", f"{b['name']} {json.dumps(b['input'], ensure_ascii=False)[:160]}")
        elif kind == "system" and m.get("subtype") in ("hook_started", "hook_response"):
            if m.get("hook_event") == "FileChanged" or m.get("hook_name", "").startswith("FileChanged"):
                note(m["subtype"], json.dumps({k: m.get(k) for k in ("hook_name", "exit_code", "outcome") if k in m}, ensure_ascii=False))
        elif kind == "system" and m.get("subtype") == "task_notification":
            note("system", f"задача окончена: {m.get('summary')}")
        elif kind == "user" and isinstance(m.get("message", {}).get("content"), str):
            note("поток-user", m["message"]["content"][:200])


threading.Thread(target=reader, daemon=True).start()


def send(text):
    proc.stdin.write((json.dumps({"type": "user", "message": {"role": "user", "content": text}}, ensure_ascii=False) + "\n").encode("utf-8"))
    proc.stdin.flush()


def append(path, label):
    with open(events, "a", encoding="utf-8") as f:
        f.write(json.dumps({"change": "demo", "answers": path}) + "\n")
    last_activity[0] = time.time()
    note("ЗАПИСЬ", f"событие {label}, ходов окончено {len(results)}")


def wait_for(cond, limit):
    end = time.time() + limit
    while time.time() < end and not cond():
        time.sleep(0.1)
    return cond()


if CASE == "busy":
    send("Выполни инструментом Bash команду `sleep 20`, затем ответь одним словом: сделано.")
    wait_for(lambda: "Bash" in first_tool_after, 90)
    time.sleep(5)
    append(A, "A")
else:
    send("Ответь одним словом: готов")
    wait_for(lambda: results, 90)
    time.sleep(5)
    if CASE == "idle0":
        append(A, "A")
        append(B, "B")
    elif CASE == "idle1":
        append(A, "A")
        time.sleep(1)
        append(B, "B")
    elif CASE == "idle03":
        append(A, "A")
        time.sleep(0.3)
        append(B, "B")
    elif CASE == "during":
        before = len(stream)
        append(A, "A")
        # второе событие: первый инструмент хода, начатого первым
        wait_for(lambda: any(s[1] == "инструмент" for s in stream[before:]), 60)
        append(B, "B")

# Ждём тишины: пробуждение приходит с задержкой, а ход может начаться не сразу.
QUIET = 25
end = time.time() + 200
while time.time() < end and time.time() - last_activity[0] < QUIET:
    time.sleep(0.5)
proc.stdin.close()
try:
    proc.wait(timeout=20)
except subprocess.TimeoutExpired:
    proc.kill()
raw_out.close()


def clean(s):
    s = str(s)
    pr = str(project)
    for form in (pr, pr.replace("\\", "/"), pr.replace("\\", "\\\\")):
        s = s.replace(form, "<проект>")
    return s


log_lines = (project / "probe.log").read_text(encoding="utf-8").splitlines() if (project / "probe.log").exists() else []
logged = [json.loads(x) for x in log_lines]
for x in logged:
    x["t"] = round(x["t"] - t0, 1)
fc = [x for x in logged if x["ev"] == "FileChanged"]
reads = [x["file"] for x in logged if x["ev"] == "PostToolUse" and x.get("tool") == "Read"]

mangled = re.sub(r"[^A-Za-z0-9]", "-", str(project))
session_dir = pathlib.Path.home() / ".claude" / "projects" / mangled
transcript = []
if session_dir.exists():
    for f in session_dir.glob("*.jsonl"):
        shutil.copy(f, SCRATCH / f"{raw_name}.session.jsonl")
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            flat = json.dumps(r, ensure_ascii=False)
            if "Ответ человека лежит" in flat and r.get("type") != "assistant":
                paths = re.findall(r"answers/(2026-11-04(?:-2)?\.md)\. Открой", flat)
                kind = "/".join(str(x) for x in (r.get("type"), r.get("operation"), (r.get("attachment") or {}).get("type")) if x)
                transcript.append(f"{kind} origin={json.dumps(r.get('origin'), ensure_ascii=False)} файлы={paths}")

turns = len(results)
lines = [f"=== случай {CASE}, обработчик {MODE}, прогон {RUN}"]
for at, kind, text in stream:
    lines.append(f"  [{at}] {kind}: {clean(text)}".replace("\n", " "))
lines.append("--- журнал обработчиков (секунды от старта)")
lines += ["  " + clean(json.dumps(x, ensure_ascii=False)) for x in logged]
lines.append("--- запись сессии: строки с текстом пробуждения")
lines += ["  " + clean(t) for t in transcript]
lines.append(f"--- итог {CASE}/{MODE}/{RUN}: FileChanged запусков {len(fc)}; ходов всего {turns}; Read: {reads}")
lines.append("")
(SCRATCH / f"{raw_name}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print(raw_name, "FC", len(fc), "ходов", turns, "Read", reads)
(SCRATCH / f"{raw_name}.project.txt").write_text(str(project), encoding="utf-8")
