# -*- coding: utf-8 -*-
"""Проба Claude Code к раундам ce91 и 49a5: что является базой isolation: worktree, что получает родитель,
параллельный запуск из claude --agent и вливание веток. Одноразовая: только временный репозиторий с настоящим
удалённым (bare), модель haiku, настройки пользователя не читаются (--setting-sources project,local).
Показания берутся из журнала, который пишет сама команда субагента, и из git, а не из доклада модели."""
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

T = Path(tempfile.mkdtemp(prefix="cc-wt-"))
LOG = T / "probe.log"
CLAUDE = shutil.which("claude")
ENV = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT")}
ENV.update(GIT_AUTHOR_NAME="probe", GIT_AUTHOR_EMAIL="probe@example.com", GIT_COMMITTER_NAME="probe", GIT_COMMITTER_EMAIL="probe@example.com")


def clean(text):
    for form in (str(T), str(T).replace("\\", "\\\\"), T.as_posix(), "/" + T.as_posix().replace(":", "", 1), "/tmp/" + T.name):
        text = text.replace(form, "<T>")
    return text


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else f"[код {r.returncode}] {r.stderr.strip()}"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


LOGP = LOG.as_posix()
PROBE = f"""---
name: probe
description: Reports the git state of its working directory
isolation: worktree
tools: Bash
model: haiku
---

Run this one Bash command and return its output verbatim, nothing else:

{{ echo "HEAD=$(git rev-parse HEAD)"; echo "BRANCH=$(git branch --show-current)"; echo "PWD=$(pwd)"; echo "STATUS=$(git status --short | wc -l)"; echo "FILES=$(ls -A | tr '\\n' ',')"; }} | tee -a "{LOGP}"
"""
WRITER = f"""---
name: writer
description: Writes one file named in the prompt and commits it
isolation: worktree
tools: Bash
model: haiku
---

The prompt gives a file name N. Run this one Bash command with N substituted and return its output verbatim, nothing else:

{{ echo "START=$(date +%s)"; sleep 8; echo hello > N; git add N; git commit -qm "add N"; echo "HEAD=$(git rev-parse HEAD)"; echo "BRANCH=$(git branch --show-current)"; echo "END=$(date +%s)"; }} | tee -a "{LOGP}"
"""
LEAD = """---
name: lead
description: Probe lead
tools: Agent(writer), Bash
model: haiku
---

You only follow the user's request literally and report results verbatim.
"""

remote, work = T / "remote.git", T / "work"
git(T, "init", "--bare", "-q", "-b", "main", str(remote))
git(T, "clone", "-q", str(remote), str(work))
git(work, "switch", "-q", "-c", "main")
write(work / "README.md", "base\n")
write(work / ".gitignore", ".claude/worktrees/\n.claude/settings.local.json\nignored.txt\n")
write(work / ".claude/agents/probe.md", PROBE)
write(work / ".claude/agents/writer.md", WRITER)
write(work / ".claude/agents/lead.md", LEAD)
git(work, "add", "-A")
git(work, "commit", "-qm", "A on main")
git(work, "push", "-q", "-u", "origin", "main")
git(work, "remote", "set-head", "origin", "main")
A = git(work, "rev-parse", "HEAD")
git(work, "switch", "-q", "-c", "feat")
write(work / "feature.txt", "feature\n")
git(work, "add", "-A")
git(work, "commit", "-qm", "B on feat, not pushed")
B = git(work, "rev-parse", "HEAD")
write(work / "README.md", "base\nuncommitted\n")
write(work / "untracked.txt", "untracked\n")
write(work / "ignored.txt", "ignored\n")
print("Проба 2026-11-03,", subprocess.run([CLAUDE, "--version"], env=ENV, capture_output=True, text=True).stdout.strip())
print(f"A (main, в удалённом) = {A[:10]}; B (feat, текущая, не в удалённом) = {B[:10]}")
print("В дереве родителя: незакоммиченная правка README.md, untracked.txt, игнорируемый ignored.txt; origin/HEAD =", git(work, "rev-parse", "--abbrev-ref", "origin/HEAD"))


def walk(obj, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "worktree" in k.lower():
                found.append((k, v))
            walk(v, found)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, found)


def run(title, prompt, *extra):
    print(f"\n--- {title}")
    LOG.write_text("", encoding="utf-8")
    t0 = time.time()
    r = subprocess.run(
        [CLAUDE, "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", "haiku",
         "--setting-sources", "project,local", "--strict-mcp-config", "--no-session-persistence",
         "--allowedTools", "Agent", "Bash", *extra],
        cwd=work, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    final, statuses, calls, wt_keys, keys = None, [], [], [], set()
    for line in r.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        walk(ev, wt_keys) if ev.get("type") != "system" else None
        if ev.get("type") == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Agent":
                    calls.append({k: c["input"].get(k) for k in ("subagent_type", "run_in_background", "isolation") if k in c["input"]})
        if ev.get("type") == "user" and isinstance(ev.get("tool_use_result"), dict):
            tur = ev["tool_use_result"]
            if "agentId" in tur:
                statuses.append(tur.get("status"))
                keys |= set(tur)
        if ev.get("type") == "result":
            final = ev
    time.sleep(2)
    log = LOG.read_text(encoding="utf-8")
    print(f"код {r.returncode}, {time.time() - t0:.0f} с, стоимость {round((final or {}).get('total_cost_usd') or 0, 4)}, отказов прав: {len((final or {}).get('permission_denials') or [])}")
    print("  вызовы Agent:", calls, "| статусы:", statuses)
    print("  ключи результата у родителя:", sorted(keys))
    print("  поля про worktree в событиях:", clean(json.dumps(sorted({(k, str(v)) for k, v in wt_keys}), ensure_ascii=False))[:400])
    return dict(line.split("=", 1) for line in log.splitlines() if "=" in line), log


def label(sha):
    return {A: "A (main, удалённый)", B: "B (feat, текущая)"}.get(sha, f"иной {sha[:10]}")


def show(vals):
    print("  журнал субагента: база", label(vals.get("HEAD", "")), "| ветка", vals.get("BRANCH"), "| каталог", clean(vals.get("PWD", "")), "| незакоммиченных", vals.get("STATUS"), "| файлы", vals.get("FILES"))


PROMPT = "Call the probe subagent once with the prompt: report. Then stop."
vals, _ = run("1. умолчание: настройки нет, сессия на feat с незакоммиченной правкой", PROMPT)
show(vals)

write(work / ".claude/settings.local.json", json.dumps({"worktree": {"baseRef": "head"}}))
vals, _ = run("2. worktree.baseRef = head, та же сессия", PROMPT)
show(vals)

vals, _ = run("3. baseRef = head: родитель коммитит прямо перед вызовом субагента",
              "First run this Bash command: git commit --allow-empty -qm mid-session. Then call the probe subagent once with the prompt: report. Then stop.")
C = git(work, "rev-parse", "HEAD")
show(vals)
print("  HEAD родителя после коммита:", C[:10], "| совпал с базой субагента:", vals.get("HEAD") == C)

_, log = run("4. claude --agent lead: два writer одним сообщением, baseRef = head",
             "Launch two writer subagents at the same time, in one message: one with the prompt: file one.txt, another with the prompt: file two.txt. Wait for both. Then stop.",
             "--agent", "lead")
starts = [int(x.split("=")[1]) for x in log.splitlines() if x.startswith("START=")]
ends = [int(x.split("=")[1]) for x in log.splitlines() if x.startswith("END=")]
print("  начала:", starts, "концы:", ends, "| пересекаются:", len(starts) == 2 and max(starts) < min(ends))
print("  базы новых коммитов:", [git(work, "rev-parse", "--short=10", x.split("=")[1] + "~1") for x in log.splitlines() if x.startswith("HEAD=")], "| HEAD родителя:", git(work, "rev-parse", "--short=10", "HEAD"))
print("  worktree после работы:\n   ", clean(git(work, "worktree", "list")).replace("\n", "\n    "))

print("\n--- 5. вливание веток git-ом в рабочую ветку feat")
branches = [line.split("refs/heads/")[1] for line in git(work, "worktree", "list", "--porcelain").splitlines() if line.startswith("branch ") and "worktree-" in line]
for b in branches:
    print(f"  merge {b}:", clean(git(work, "merge", "--no-edit", "-q", b))[:200] or "ок")
print("  файлы в feat после вливания:", git(work, "ls-tree", "--name-only", "HEAD").replace("\n", " "))
print("  незакоммиченная правка родителя цела:", "uncommitted" in (work / "README.md").read_text(encoding="utf-8"))

shutil.rmtree(T, ignore_errors=True)
print("\n--- конец")
