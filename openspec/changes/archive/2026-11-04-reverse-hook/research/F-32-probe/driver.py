# Проба F-32: подхватывает ли идущая сессия хуки, появившиеся в .claude/settings.local.json после её запуска.
# Запуск: RH_SCRATCH=<каталог> py -3.13 driver.py <случай> <прогон>. След прогона в $RH_SCRATCH, run_all.py сводит его в run.txt.
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, threading, time

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
PY = shutil.which("py") or "py"
CASE, RUN = sys.argv[1], sys.argv[2]
SCRATCH = pathlib.Path(os.environ["RH_SCRATCH"])


def h(mode, **extra):
    return {"type": "command", "command": f'"{PY}" -3.13 -I -X utf8 "{HERE / "h.py"}" {mode}', **extra}


WAKE = h("wake", asyncRewake=True, timeout=30)
FC = [{"matcher": "events.jsonl", "hooks": [WAKE]}]
UPS = [{"hooks": [h("log")]}]
SS = [{"hooks": [h("watch-hso")]}]

# Случай: что в настройках, с начала ли, что было в .claude до установки.
BASE = {"SessionStart": SS, "UserPromptSubmit": UPS, "FileChanged": FC}
CASES = {
    "control": {"hooks": BASE, "from_start": True},
    "late-nodir": {"hooks": BASE, "before": "нет каталога"},
    "late-nofile": {"hooks": BASE, "before": "пустой каталог"},
    "late-edit": {"hooks": BASE, "before": "файл без хуков"},
    "ups-hso": {"hooks": {"UserPromptSubmit": [{"hooks": [h("watch-hso")]}], "FileChanged": FC}, "before": "пустой каталог"},
    "ups-top": {"hooks": {"UserPromptSubmit": [{"hooks": [h("watch-top")]}], "FileChanged": FC}, "before": "пустой каталог"},
    "cwd-control": {"hooks": {"CwdChanged": [{"hooks": [h("watch-hso")]}], "FileChanged": FC}, "from_start": True, "say": "cd"},
    "cwd-late": {"hooks": {"CwdChanged": [{"hooks": [h("watch-hso")]}], "FileChanged": FC}, "before": "пустой каталог", "say": "cd"},
    "seed-late": {"hooks": {"FileChanged": [{"matcher": "events.jsonl|seed.txt", "hooks": [WAKE]}]}, "before": "пустой каталог", "seed": True},
    "compact-late": {"hooks": BASE, "before": "пустой каталог", "say": "compact"},
    "config-late": {"hooks": {"ConfigChange": [{"hooks": [h("watch-hso")]}], "FileChanged": FC}, "before": "пустой каталог", "touch": True},
    "clear-late": {"hooks": BASE, "before": "пустой каталог", "say": "clear"},
    "wake-busy": {"hooks": BASE, "from_start": True, "busy": True},
    # Вне %TEMP%: внутри него cd не держался (клиент пишет «Shell cwd was reset»), и CwdChanged не срабатывал.
    "late-nofile-nt": {"hooks": BASE, "before": "пустой каталог", "outside_temp": True},
    "cwd-control-nt": {"hooks": {"CwdChanged": [{"hooks": [h("watch-hso")]}], "FileChanged": FC}, "from_start": True, "say": "cd", "outside_temp": True},
    "cwd-late-nt": {"hooks": {"CwdChanged": [{"hooks": [h("watch-hso")]}], "FileChanged": FC}, "before": "пустой каталог", "say": "cd", "outside_temp": True},
    "control-cd-nt": {"hooks": BASE, "from_start": True, "say": "cd", "outside_temp": True},
}
spec = CASES[CASE]

project = pathlib.Path(tempfile.mkdtemp(prefix="rhcc-probe-32-", dir=os.environ["RH_BASE_OUTSIDE_TEMP"] if spec.get("outside_temp") else None))
viewer = project / ".symphysis" / "viewer"
viewer.mkdir(parents=True)
deep = viewer / "events.jsonl"
root_ev = project / "events.jsonl"
seed = project / "seed.txt"
for p in (deep, root_ev, seed):
    p.write_text("", encoding="utf-8")
settings = project / ".claude" / "settings.local.json"


def write_settings(obj):
    # Через временный файл и замену, как writeProjectFile в плагине.
    settings.parent.mkdir(exist_ok=True)
    tmp = settings.with_name(settings.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, settings)


if spec.get("from_start"):
    write_settings({"hooks": spec["hooks"]})
elif spec["before"] == "пустой каталог":
    settings.parent.mkdir()
elif spec["before"] == "файл без хуков":
    write_settings({"permissions": {"allow": []}})

env = {k: v for k, v in os.environ.items() if not (k == "CLAUDECODE" or k.startswith("CLAUDE_"))}
name = f"{CASE}-{RUN}"
proc = subprocess.Popen([shutil.which("claude"), "-p", "--input-format", "stream-json", "--output-format", "stream-json",
                         "--verbose", "--include-hook-events", "--model", "haiku", "--setting-sources", "project,local",
                         "--allowedTools", "Bash(cd *)", "Bash(sleep *)", "--debug-file", str(SCRATCH / f"f32-{name}.debug.log")],
                        cwd=project, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
t0 = time.time()
stream, results, marks = [], [], []
last_activity = [time.time()]
raw_out = open(SCRATCH / f"f32-{name}.stream.jsonl", "wb")


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
                    note("модель", b["text"][:120])
                if b.get("type") == "tool_use":
                    note("инструмент", f"{b['name']} {json.dumps(b['input'], ensure_ascii=False)[:120]}")
        elif kind == "system" and m.get("subtype") == "hook_response":
            note("хук", f"{m.get('hook_name')} код {m.get('exit_code')}")
        elif kind == "system" and m.get("subtype") in ("compact_boundary",):
            note("система", m["subtype"])


threading.Thread(target=reader, daemon=True).start()


def send(text):
    proc.stdin.write((json.dumps({"type": "user", "message": {"role": "user", "content": text}}, ensure_ascii=False) + "\n").encode("utf-8"))
    proc.stdin.flush()
    note("РЕПЛИКА", text)


def wait_for(cond, limit):
    end = time.time() + limit
    while time.time() < end and not cond():
        time.sleep(0.1)


def settle(extra=12):
    """Ждём, пока всё уляжется: не меньше extra секунд тишины после шага."""
    last_activity[0] = time.time()
    end = time.time() + 120
    while time.time() < end and time.time() - last_activity[0] < extra:
        time.sleep(0.2)


def touch(path, label):
    """Шаг пробы: дописать строку и посмотреть, кто сработал."""
    marks.append((label, round(time.time() - t0, 1), time.time()))
    with open(path, "a", encoding="utf-8") as f:
        f.write('{"change": "demo"}\n')
    note("ЗАПИСЬ", label)
    settle()


def step(label):
    marks.append((label, round(time.time() - t0, 1), time.time()))


if spec.get("busy"):
    # Занятая сессия: запись во время sleep, смотрим, запустится ли UserPromptSubmit на доставке текста.
    send("Выполни инструментом Bash команду `sleep 12`, затем ответь одним словом: ок")
    wait_for(lambda: any(k == "инструмент" and "sleep" in t for _, k, t in stream), 60)
    time.sleep(3)
    touch(deep, "глубокий во время sleep")
    wait_for(lambda: results, 60)
    settle()
    send("Ответь одним словом: ок")
    wait_for(lambda: len(results) > 1, 60)
    settle()
    touch(deep, "глубокий в простое")
    proc.stdin.close()
    spec["done"] = True
else:
    send("Ответь одним словом: готов")
    wait_for(lambda: results, 90)
    time.sleep(1)
if not spec.get("from_start") and not spec.get("done"):
    step("установка")
    write_settings({"hooks": spec["hooks"]})
    note("УСТАНОВКА", "файл настроек с хуками записан")
    settle(10)
if spec.get("seed"):
    touch(seed, "корневой seed.txt")
if not spec.get("done"):
    touch(deep, "глубокий 1")
    touch(root_ev, "корневой 1")
if spec.get("touch"):
    step("вторая правка настроек")
    write_settings({"hooks": spec["hooks"], "permissions": {"allow": []}})
    note("УСТАНОВКА", "настройки правлены второй раз")
    settle(8)
    touch(deep, "глубокий после второй правки")
if not spec.get("done"):
    done = len(results)
    step("реплика")
    if spec.get("say") == "cd":
        send("Выполни инструментом Bash команду `cd .symphysis`, затем ответь одним словом: ок")
    elif spec.get("say") == "compact":
        send("/compact")
    elif spec.get("say") == "clear":
        send("/clear")
    else:
        send("Ответь одним словом: ок")
    wait_for(lambda: len(results) > done, 120 if spec.get("say") != "clear" else 20)
    settle(4)
    touch(deep, "глубокий 2")
    touch(root_ev, "корневой 2")
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


logged = []
log_dir = project / "probe-log"
if log_dir.exists():
    logged = sorted((json.loads(p.read_text(encoding="utf-8")) for p in log_dir.glob("*.json")), key=lambda x: x["t"])
for x in logged:
    x["rel"] = round(x["t"] - t0, 1)


def fired(label):
    i = next(i for i, m in enumerate(marks) if m[0] == label)
    start = marks[i][1]
    stop = marks[i + 1][1] if i + 1 < len(marks) else 10 ** 9
    return [x for x in logged if start <= x["rel"] < stop]


lines = [f"=== случай {CASE}, прогон {RUN}"]
for at, kind, text in stream:
    lines.append(f"  [{at}] {kind}: {clean(text)}".replace("\n", " "))
lines.append("--- журнал обработчиков (секунды от старта)")
for x in logged:
    lines.append("  " + clean(json.dumps({k: x[k] for k in ("rel", "ev", "mode", "source", "file", "change", "prompt") if x.get(k)}, ensure_ascii=False)))
lines.append("--- по шагам")
for label, at, _ in marks:
    got = fired(label)
    kinds = sorted({x["ev"] for x in got})
    lines.append(f"  {label} [{at}]: запусков {len(got)}: {kinds}")
lines.append(f"--- итог {CASE}/{RUN}: ходов всего {len(results)}")
lines.append("")
(SCRATCH / f"f32-{name}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
(SCRATCH / f"f32-{name}.project.txt").write_text(str(project), encoding="utf-8")
print(name, "; ".join(f"{m[0]}={sorted({x['ev'] for x in fired(m[0])}) or '-'}" for m in marks), "ходов", len(results))
