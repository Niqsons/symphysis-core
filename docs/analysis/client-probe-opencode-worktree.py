# -*- coding: utf-8 -*-
"""Проба opencode 2.2.5 к раундам ce91 (F5, F7) и 49a5 (F2): можно ли посадить субагента в свой worktree и что будет при зависании провайдера.

Одноразовая. Модель не нужна и наружу ничего не уходит: вместо провайдера локальная заглушка на 127.0.0.1, её ответы написаны здесь.
Рабочий opencode не затрагивается: запускается копия установленного exe во временном каталоге (по её пути снимаются зависшие процессы,
настоящие сессии не задеть), домашний каталог и XDG подменены на временные; до первой сессии `debug paths` обязан показать только
временные пути, иначе проба останавливается.

Запуск: python -X utf8 docs/analysis/client-probe-opencode-worktree.py [имена сценариев]; проверка самой заглушки без opencode: --selftest.
Вывод дублируется в client-probe-opencode-worktree-2026-11-03.txt рядом со скриптом."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OUT = Path(__file__).with_name("client-probe-opencode-worktree-2026-11-03.txt")
REAL_DIRS = [Path.home() / ".local" / "share" / "opencode", Path.home() / ".config" / "opencode"]
LEAD, CHILD = "ROLE_LEAD_MARKER", "ROLE_CHILD_MARKER"

T = Path(tempfile.mkdtemp(prefix="oc-wt-"))
BIN = T / "bin" / "opencode.exe"
out_file = None


def clean(text):
    text = str(text)
    for form in (str(T), str(T).replace("\\", "\\\\"), T.as_posix(), "/" + T.as_posix().replace(":", "", 1)):
        text = text.replace(form, "<T>")
    return text


def say(*parts):
    line = clean(" ".join(str(p) for p in parts))
    print(line, flush=True)
    if out_file:
        out_file.write(line + "\n")
        out_file.flush()


ENV = {**os.environ}
for key in ("HOME", "USERPROFILE"):
    ENV[key] = str(T / "home")
ENV.update(
    APPDATA=str(T / "home" / "AppData" / "Roaming"), LOCALAPPDATA=str(T / "home" / "AppData" / "Local"),
    TEMP=str(T / "tmp"), TMP=str(T / "tmp"),
    XDG_CONFIG_HOME=str(T / "xdg" / "config"), XDG_DATA_HOME=str(T / "xdg" / "data"),
    XDG_STATE_HOME=str(T / "xdg" / "state"), XDG_CACHE_HOME=str(T / "xdg" / "cache"),
    OPENCODE_DISABLE_AUTOUPDATE="1", OPENCODE_DISABLE_FREE_MODELS="1",
    GIT_AUTHOR_NAME="probe", GIT_AUTHOR_EMAIL="probe@example.com", GIT_COMMITTER_NAME="probe", GIT_COMMITTER_EMAIL="probe@example.com",
)


def text_of(message):
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return ""


# --- ответы заглушки

def tool(name, **args):
    return {"calls": [(name, args)]}


def calls(*pairs):
    return {"calls": list(pairs)}


def answer(text="done"):
    return {"text": text}


def execute(code):
    return tool("execute", code=code)


def create(name):
    return execute(f"return await tools.opencode.worktree_create({json.dumps({'name': name})})")


def move(directory, session=None):
    args = {"directory": directory, **({"sessionID": session} if session else {})}
    return execute(f"return await tools.opencode.session_move({json.dumps(args)})")


def spawn(key, background):
    args = dict(agent="child", description=f"child {key}", prompt=f"file={key}")
    if background:
        args["background"] = True
    return ("subagent", args)


TOP = "git rev-parse --show-toplevel"


def child_plain(ctx, step, key):
    return [tool("shell", command=TOP), tool("write", path=f"probe-{key}.txt", content="x"), tool("shell", command=TOP), answer()][min(step, 3)]


class Run:
    def __init__(self, lead, child, name=""):
        self.lead, self.child, self.name = lead, child, name
        self.dirs, self.sids, self.events, self.done = [], [], [], 0
        self.tools, self.paths, self.delay, self.stop = {}, set(), 0, threading.Event()
        self.t0 = time.time()

    def note(self, msgs):
        for m in msgs:
            if m.get("role") != "tool":
                continue
            text = text_of(m)
            for raw in re.findall(r'"directory"\s*:\s*"((?:[^"\\]|\\.)+)"', text):
                try:
                    value = json.loads(f'"{raw}"')
                except ValueError:
                    value = raw
                if value not in self.dirs:
                    self.dirs.append(value)
            for found in re.findall(r"Created worktree in (.+?)\.\s*$", text, re.M):
                if found not in self.dirs:
                    self.dirs.append(found)
            for sid in re.findall(r"ses_[0-9A-Za-z]+", text):
                if sid not in self.sids:
                    self.sids.append(sid)

    def decide(self, role, step, key):
        if role == "lead":
            return self.lead(self, step)
        if role == "child":
            return self.child(self, step, key)
        return answer("probe title")


RUN = None


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = json.dumps({"object": "list", "data": [{"id": "fake", "object": "model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        msgs = body.get("messages", [])
        whole = json.dumps(msgs, ensure_ascii=False)
        role = "lead" if LEAD in whole else "child" if CHILD in whole else "other"
        step = sum(1 for m in msgs if m.get("role") == "assistant")
        found = re.search(r"file=(\w+)", whole)
        key = found.group(1) if found else "-"
        run = RUN
        run.paths.add(self.path)
        run.note(msgs)
        results = [text_of(m) for m in msgs if m.get("role") == "tool"]
        users = [text_of(m) for m in msgs if m.get("role") == "user"]
        names = sorted(t.get("function", {}).get("name", "?") for t in body.get("tools", []) or [])
        run.tools.setdefault(role, (names, next((t["function"].get("description", "") for t in body.get("tools", []) or [] if t.get("function", {}).get("name") == "execute"), "")))
        run.events.append({
            "t": round(time.time() - run.t0, 1), "role": role, "step": step, "key": key,
            "result": results[-1][:300].replace("\n", " ") if results else "",
            "user": users[-1][:200].replace("\n", " ") if users else "",
        })
        action = run.decide(role, step, key)
        delay = action.get("delay", 0)
        if delay:
            time.sleep(delay)
        if action.get("hang") == "silent":
            run.stop.wait(action.get("limit", 120))
            self.close_connection = True
            return
        stream = bool(body.get("stream"))
        if action.get("hang") == "keepalive":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            try:
                while not run.stop.wait(1):
                    self.wfile.write(b": still in the provider queue\n\n")
                    self.wfile.flush()
            except OSError:
                pass
            self.close_connection = True
            return
        if "wait_children" in action:
            until = time.time() + action.get("limit", 45)
            while time.time() < until and run.done < action["wait_children"]:
                time.sleep(0.5)
            action = answer("children waited")
        if role == "child" and "text" in action:
            run.done += 1
        self.reply(action, stream, body.get("model", "fake"))

    def reply(self, action, stream, model):
        base = {"id": "chatcmpl-" + uuid.uuid4().hex[:12], "created": int(time.time()), "model": model}
        tool_calls = [
            {"index": i, "id": "call_" + uuid.uuid4().hex[:12], "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
            for i, (n, a) in enumerate(action.get("calls", []))
        ]
        finish = "tool_calls" if tool_calls else "stop"
        usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        if not stream:
            message = {"role": "assistant", "content": action.get("text")}
            if tool_calls:
                message["tool_calls"] = [{k: v for k, v in c.items() if k != "index"} for c in tool_calls]
            payload = json.dumps({**base, "object": "chat.completion", "choices": [{"index": 0, "message": message, "finish_reason": finish}], "usage": usage}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        chunk = {**base, "object": "chat.completion.chunk"}
        delta = {"role": "assistant", **({"content": action["text"]} if "text" in action else {}), **({"tool_calls": tool_calls} if tool_calls else {})}
        for piece in (
            {**chunk, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
            {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
            {**chunk, "choices": [], "usage": usage},
        ):
            self.wfile.write(b"data: " + json.dumps(piece).encode() + b"\n\n")
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True


server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
server.daemon_threads = True
PORT = server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()


def selftest():
    global RUN
    RUN = Run(lambda run, step: calls(spawn("one", True), spawn("two", False)), child_plain, "selftest")
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions",
        data=json.dumps({"stream": True, "model": "fake", "messages": [{"role": "system", "content": LEAD}, {"role": "user", "content": "go"}], "tools": [{"type": "function", "function": {"name": "execute", "description": "d"}}]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    raw = urllib.request.urlopen(request, timeout=10).read().decode()
    frames = [line[6:] for line in raw.splitlines() if line.startswith("data: ")]
    assert frames[-1] == "[DONE]", frames
    parsed = [json.loads(f) for f in frames[:-1]]
    got = parsed[0]["choices"][0]["delta"]["tool_calls"]
    assert [c["function"]["name"] for c in got] == ["subagent", "subagent"] and parsed[1]["choices"][0]["finish_reason"] == "tool_calls"
    assert json.loads(got[0]["function"]["arguments"])["background"] is True and RUN.events[0]["role"] == "lead"
    say("самопроверка заглушки: ок,", len(frames), "кадра")


def project(name):
    root = T / f"proj-{name}"
    (root / ".opencode" / "agents").mkdir(parents=True)
    stub = {"npm": "@ai-sdk/openai-compatible", "name": "stub", "options": {"baseURL": f"http://127.0.0.1:{PORT}/v1", "apiKey": "x"},
            "models": {"fake": {"name": "fake", "tool_call": True, "limit": {"context": 200000, "output": 8000}}}}
    slow = json.loads(json.dumps(stub))
    slow["options"].update(headerTimeout=3000, chunkTimeout=3000)
    total = json.loads(json.dumps(stub))
    total["options"].update(timeout=5000)
    (root / "opencode.json").write_text(json.dumps({
        "autoupdate": False, "share": "disabled",
        "model": "stub/fake", "small_model": "stub/fake", "permission": {"*": "allow", "external_directory": "allow"},
        "provider": {"stub": stub, "stubslow": slow, "stubtotal": total},
    }, indent=1), encoding="utf-8")
    (root / ".opencode" / "agents" / "lead.md").write_text(f"---\ndescription: lead\nmode: primary\n---\n{LEAD}\n", encoding="utf-8")
    model = "model: stubtotal/fake\n" if name == "stall-total" else "model: stubslow/fake\n" if name.startswith("stall") else ""
    (root / ".opencode" / "agents" / "child.md").write_text(f"---\ndescription: child worker\nmode: subagent\n{model}---\n{CHILD}\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(["git", *args], cwd=root, env=ENV, capture_output=True)
    return root


def kill_binary():
    exe = str(BIN).replace("'", "''")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -eq '{exe}' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -Confirm:$false }}"],
                   capture_output=True)


def scenario(name, title, lead, child, limit=90, wait_after=0, prepare=None):
    global RUN
    say(f"\n--- {name}. {title}")
    root = project(name)
    if prepare:
        prepare(root)
    RUN = Run(lead, child, name)
    proc = subprocess.Popen([str(BIN), "run", "--agent", "lead", "--model", "stub/fake", "--auto", "go"], cwd=root, env=ENV,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    try:
        output, _ = proc.communicate(timeout=limit)
        state = f"код {proc.returncode}"
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        output, _ = proc.communicate()
        state = f"снят по времени {limit} с"
    if wait_after:
        time.sleep(wait_after)
    RUN.stop.set()
    kill_binary()
    say(f"  opencode run: {state}, запросов к заглушке: {len(RUN.events)}, пути: {sorted(RUN.paths)}")
    if not RUN.events:
        say("  вывод opencode:", output[-1500:])
    for ev in RUN.events:
        if ev["role"] == "other":
            continue
        say(f"  {ev['t']:>6} с {ev['role']:<5} ход {ev['step']} {ev['key']:<5} результат: {ev['result'][:220]}")
    say("  каталоги worktree:", RUN.dirs, "| сессии:", len(RUN.sids))
    say("  worktree:", subprocess.run(["git", "worktree", "list"], cwd=root, env=ENV, capture_output=True, text=True).stdout.strip().replace("\n", " ; "))
    say("  файлы проб:", sorted(clean(p) for p in T.rglob("probe-*.txt")))
    for p in T.rglob("probe-*.txt"):
        p.unlink()
    return RUN


# --- сценарии


def s_discover():
    run = scenario("discover", "что видит модель: инструменты родителя и ребёнка",
                   lambda r, s: calls(spawn("one", False)) if s == 0 else answer(), lambda r, s, k: answer(), 60)
    for role, (names, desc) in run.tools.items():
        say(f"  инструменты {role}:", names)
        if desc:
            say(f"  execute у {role}:", desc[:900].replace("\n", " "))
    return bool(run.events)


def s_control():
    scenario("control", "без worktree: ребёнок на переднем плане, база для сравнения",
             lambda r, s: calls(spawn("ctl", False)) if s == 0 else answer(), child_plain)


def moved_by_parent(delay):
    def lead(r, s):
        if s == 0:
            return create(f"wt{int(delay)}")
        if s == 1:
            return calls(spawn("moved", True))
        if s == 2:
            return move(r.dirs[-1], r.sids[-1]) if r.dirs and r.sids else answer("нет каталога или сессии")
        return {"wait_children": 1, "limit": 30}

    def child(r, s, k):
        action = dict(child_plain(r, s, k))
        if s == 0 and delay:
            action["delay"] = delay
        return action
    return lead, child


def s_move_race():
    lead, child = moved_by_parent(0)
    scenario("move-race", "родитель двигает ребёнка сразу после запуска, ребёнок не ждёт: гонка с первым ходом", lead, child)


def s_move_late():
    lead, child = moved_by_parent(4)
    scenario("move-late", "то же, но первый ответ ребёнка задержан на 4 с: перемещение приходит раньше первого инструмента", lead, child)


def s_self_move():
    def lead(r, s):
        if s == 0:
            return create("self")
        return calls(spawn("self", False)) if s == 1 else answer()

    def child(r, s, k):
        if s == 0:
            return move(r.dirs[-1]) if r.dirs else answer("нет каталога")
        return child_plain(r, s - 1, k)
    scenario("self-move", "ребёнок первым ходом переходит в свой worktree сам", lead, child)


def s_step_in():
    def lead(r, s):
        return [create("step-a"), create("step-b"), lambda: move(r.dirs[0]), lambda: calls(spawn("a", True)),
                lambda: move(r.dirs[1]), lambda: calls(spawn("b", True)), lambda: {"wait_children": 2, "limit": 30}, lambda: answer()][min(s, 7)]

    def resolve(r, s):
        got = lead(r, s)
        return got() if callable(got) else got
    scenario("step-in", "родитель сам входит в worktree перед запуском: ребёнок наследует его каталог", resolve, child_plain)


def s_workdir():
    def lead(r, s):
        if s == 0:
            return create("wd")
        return calls(spawn("wd", False)) if s == 1 else answer()

    def child(r, s, k):
        target = r.dirs[-1] if r.dirs else "."
        return [tool("shell", command=TOP, workdir=target),
                tool("write", path=os.path.join(target, f"probe-{k}.txt"), content="x"),
                answer()][min(s, 2)]
    scenario("workdir", "без перемещения: ребёнок работает по абсолютным путям и workdir", lead, child)


def s_parallel():
    def child(r, s, k):
        action = dict(child_plain(r, s, k))
        if s == 0:
            action["delay"] = 3
        return action
    scenario("parallel", "два субагента одним ответом без background", lambda r, s: calls(spawn("p1", False), spawn("p2", False)) if s == 0 else answer(), child)


def stall(name, title, hang, limit):
    def lead(r, s):
        if s == 0:
            return calls(spawn("hang", True))
        if s == 1:
            return tool("shell", command=f'python -c "import time; time.sleep({limit - 25})"', timeout=0)
        return answer("lead saw this")
    run = scenario(name, title, lead, lambda r, s, k: {"hang": hang, "limit": limit}, limit)
    attempts = [e["t"] for e in run.events if e["role"] == "child"]
    say("  попыток запроса ребёнка:", len(attempts), "времена:", attempts)
    told = [e for e in run.events if e["role"] == "lead" and e["step"] >= 2]
    say("  родитель на следующем ходу получил:", told[-1]["user"] if told else "ещё не дошёл до следующего хода", "|", told[-1]["result"][:200] if told else "")


def s_stall_silent():
    stall("stall-silent", "провайдер молчит, даже заголовков нет; таймауты сокращены до 3 с", "silent", 95)


def s_stall_queue():
    stall("stall-queue", "длинная очередь: заголовки есть, идут только служебные комментарии; таймауты 3 с", "keepalive", 85)


def s_stall_total():
    stall("stall-total", "та же очередь, но у провайдера общий timeout 5 с", "keepalive", 85)


def s_pipeline():
    marks = {}

    def prepare(root):
        def g(*args):
            return subprocess.run(["git", *args], cwd=root, env=ENV, capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(T / "remote-pipe.git")], env=ENV, capture_output=True)
        g("remote", "add", "origin", str(T / "remote-pipe.git"))
        g("push", "-q", "-u", "origin", "main")
        g("remote", "set-head", "origin", "main")
        marks["A"] = g("rev-parse", "HEAD")
        g("switch", "-q", "-c", "feat")
        (root / "feature.txt").write_text("feature\n", encoding="utf-8")
        g("add", "-A")
        g("commit", "-qm", "B on feat, not pushed")
        marks["B"] = g("rev-parse", "HEAD")
        (root / "README.md").write_text("base\nuncommitted\n", encoding="utf-8")
        (root / "untracked.txt").write_text("untracked\n", encoding="utf-8")

    def lead(r, s):
        if s == 0:
            return create("pipe")
        if s == 1:
            return move(r.dirs[-1]) if r.dirs else answer("нет каталога")
        if s == 2:
            return calls(spawn("pipe", True))
        return {"wait_children": 1, "limit": 30}

    def child(r, s, k):
        return [tool("shell", command="git rev-parse HEAD; git status --short; git ls-files"),
                tool("write", path="probe-pipe.txt", content="x"),
                tool("shell", command="git add probe-pipe.txt; git commit -qm pipe; git rev-parse HEAD"),
                answer()][min(s, 3)]

    run = scenario("pipeline", "весь путь на opencode: база worktree_create при текущей ветке feat, коммит в дереве, вливание", lead, child, prepare=prepare)
    root = T / "proj-pipeline"
    seen = " ".join(e["result"] for e in run.events if e["role"] == "child")
    say("  A (main, удалённый):", marks["A"][:10], "| B (feat, текущая):", marks["B"][:10])
    say("  база дерева:", "B, текущая" if marks["B"] in seen else "A, удалённая" if marks["A"] in seen else "иная")
    shas = [x for x in re.findall(r"\b[0-9a-f]{40}\b", seen) if x not in marks.values()]
    say("  дерево:", subprocess.run(["git", "worktree", "list"], cwd=root, env=ENV, capture_output=True, text=True).stdout.strip().splitlines()[-1] if run.dirs else "нет")
    if shas:
        merged = subprocess.run(["git", "merge", "--no-edit", "-q", shas[-1]], cwd=root, env=ENV, capture_output=True, text=True)
        files = subprocess.run(["git", "ls-tree", "--name-only", "HEAD"], cwd=root, env=ENV, capture_output=True, text=True).stdout.split()
        say("  вливание коммита дерева в feat: код", merged.returncode, "| файл на месте:", "probe-pipe.txt" in files)
        say("  незакоммиченная правка родителя цела:", "uncommitted" in (root / "README.md").read_text(encoding="utf-8"))
    else:
        say("  коммита дерева нет, вливать нечего")


SCENARIOS = {f.__name__[2:].replace("_", "-"): f for f in (s_control, s_move_race, s_move_late, s_self_move, s_step_in, s_workdir, s_parallel, s_pipeline, s_stall_silent, s_stall_queue, s_stall_total)}


def fingerprint():
    return sorted((str(p), p.stat().st_mtime_ns) for root in REAL_DIRS if root.exists() for p in root.rglob("*") if p.is_file())


def installed_exe():
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, shell=True).stdout.strip()
    exe = Path(root) / "@opencode" / "cli" / "bin" / "opencode.exe"
    return exe if exe.exists() else None


def main():
    global out_file
    if "--selftest" in sys.argv:
        selftest()
        shutil.rmtree(T, ignore_errors=True)
        return 0
    source = installed_exe()
    if source is None:
        print("установленный opencode не найден")
        return 2
    BIN.parent.mkdir(parents=True)
    shutil.copy2(source, BIN)
    chosen = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_file = open(OUT, "a" if chosen else "w", encoding="utf-8", newline="\n")
    if chosen:
        say("\n=== дополнительный прогон:", " ".join(chosen))
    (T / "home").mkdir()
    (T / "tmp").mkdir()
    say("Проба 2026-11-03, opencode", subprocess.run([str(BIN), "--version"], env=ENV, cwd=T, capture_output=True, text=True).stdout.strip())
    selftest()
    before = fingerprint()
    r = subprocess.run([str(BIN), "debug", "paths"], env=ENV, cwd=T, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    paths = re.findall(r"[A-Za-z]:[\\/][^\s\"']+", r.stdout)
    outside = [p for p in paths if not os.path.normcase(os.path.normpath(p)).startswith(os.path.normcase(os.path.normpath(str(T))))]
    say("debug paths: код", r.returncode, "| путей", len(paths), "| вне временного каталога:", outside)
    if r.returncode != 0 or not paths or outside:
        say("СТОП: изоляция не подтверждена, сессий не запускаю.", r.stdout[-800:], r.stderr[-400:])
        shutil.rmtree(T, ignore_errors=True)
        return 2
    if not chosen and not s_discover():
        say("СТОП: заглушка не получила ни одного запроса, сценарии дальше бессмысленны.")
    else:
        for name, fn in SCENARIOS.items():
            if not chosen or name in chosen:
                fn()
    changed = sorted({str(a[0]) for a in set(map(tuple, fingerprint())) ^ set(map(tuple, before))})
    say("\nнастоящие каталоги opencode не изменились:", not changed, "| изменённых файлов:", len(changed))
    kill_binary()
    shutil.rmtree(T, ignore_errors=True)
    say("--- конец")
    out_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
