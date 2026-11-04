# Проба: будит ли FileChanged с asyncRewake простаивающую сессию Claude Code, что видит модель, откроет ли файл ответа.
import json, os, pathlib, shutil, subprocess, sys, tempfile, threading, time

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
PY = shutil.which("py") or "py"
MODEL = sys.argv[1]


def hook_cmd(script):
    return f'"{PY}" -3.13 -I "{HERE / script}"'


project = pathlib.Path(tempfile.mkdtemp(prefix="fc-probe-"))
viewer = project / ".symphysis" / "viewer"
viewer.mkdir(parents=True)
events = viewer / "events.jsonl"
events.write_text("", encoding="utf-8")
answers = project / "openspec" / "changes" / "demo" / "answers"
answers.mkdir(parents=True)
(answers / "2026-11-04.md").write_text("- F-01: A — (без слова)\n", encoding="utf-8")
log = project / "probe.log"
(project / ".claude").mkdir()
(project / ".claude" / "settings.json").write_text(json.dumps({
    "hooks": {
        "SessionStart": [{"hooks": [{"type": "command", "command": hook_cmd("start.py")}]}],
        "FileChanged": [{"matcher": "events.jsonl", "hooks": [
            {"type": "command", "command": hook_cmd("wake.py"), "asyncRewake": True, "timeout": 30}]}],
        "PostToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": hook_cmd("read.py")}]}],
    }}, ensure_ascii=False), encoding="utf-8")

env = dict(os.environ, FC_PROBE_LOG=str(log), FC_PROBE_EVENTS=str(events))
proc = subprocess.Popen([shutil.which("claude"), "-p", "--input-format", "stream-json", "--output-format", "stream-json",
                         "--verbose", "--model", MODEL, "--setting-sources", "project"],
                        cwd=project, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
results, assistant = [], []
t0 = time.time()


def reader():
    for raw in proc.stdout:
        try:
            m = json.loads(raw.decode("utf-8"))
        except ValueError:
            continue
        if m.get("type") == "result":
            results.append(time.time() - t0)
        if m.get("type") == "assistant":
            for b in m["message"]["content"]:
                if b.get("type") == "text" and b["text"]:
                    assistant.append((round(time.time() - t0, 1), b["text"]))
                if b.get("type") == "tool_use":
                    assistant.append((round(time.time() - t0, 1), f"<инструмент {b['name']}: {json.dumps(b['input'], ensure_ascii=False)[:120]}>"))


threading.Thread(target=reader, daemon=True).start()
first = {"type": "user", "message": {"role": "user", "content": "Ответь одним словом: готов"}}
proc.stdin.write((json.dumps(first, ensure_ascii=False) + "\n").encode("utf-8"))
proc.stdin.flush()
while not results and time.time() - t0 < 120:
    time.sleep(0.5)
time.sleep(5)
turns = len(results)
written_at = round(time.time() - t0, 1)
with open(events, "a", encoding="utf-8") as f:
    f.write(json.dumps({"change": "demo", "answers": "openspec/changes/demo/answers/2026-11-04.md"}) + "\n")
deadline = time.time() + 90
while time.time() < deadline and len(results) == turns:
    time.sleep(0.5)
print(f"[{MODEL}] событие на секунде {written_at}; новый ход без реплики: {len(results) > turns}")
for at, text in assistant:
    print(f"  [{at}] {text[:300]}")
proc.stdin.close()
try:
    proc.wait(timeout=20)
except subprocess.TimeoutExpired:
    proc.kill()
print("--- журнал хуков")
print(log.read_text(encoding="utf-8") if log.exists() else "журнала нет")
sessions = pathlib.Path.home() / ".claude" / "projects"
for d in sessions.glob(f"*{project.name}*"):
    for f in d.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            c = (r.get("message") or {}).get("content")
            if r.get("type") == "user" and isinstance(c, str) and "task-notification" in c:
                print("--- модель получила")
                print(c[:500])
print("--- проект:", project)
