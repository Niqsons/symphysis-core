# -*- coding: utf-8 -*-
"""Проба F-49: хук настоящего opencode во временном проекте. Файл кладётся в `.opencode/plugins/` без правки `opencode.json`, сервер свой (--standalone),
наружу уходит только тестовый вопрос. След — probe.log рядом, пути заменены метками; временный проект снимается."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
LOG = HERE / "probe.log"
MODEL = "ollama-cloud/deepseek-v4.1-flash"
QUESTION = "Какие служебные метки ты видишь в своих инструкциях? Перечисли только метки. Если их нет, ответь словом НЕТ."
PLUGIN = r"""
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

export default {
  id: "symphysis-hook-probe",
  async setup(ctx) {
    const file = path.join(ctx.location.directory, "hook-trace.jsonl");
    const log = (row) => fs.appendFileSync(file, JSON.stringify(row) + "\n", "utf8");
    let python = null;
    try { python = execFileSync(process.env.PROBE_PYTHON, ["--version"], { encoding: "utf8" }).trim(); } catch (e) { python = "сбой: " + e.message; }
    log({ at: "setup", bun: typeof Bun !== "undefined", node: process.versions.node, python, directory: ctx.location.directory, keys: Object.keys(ctx.session ?? {}) });
    await ctx.session.hook("prompt", async (event) => {
      log({ at: "prompt", keys: Object.keys(event), sessionID: event.sessionID, text: event.prompt?.text });
      try {
        await ctx.session.instructions.entry.put({ sessionID: event.sessionID, key: "symphysis", value: "Служебная метка: ШИПОВНИК-3131" });
        log({ at: "instructions.entry.put", ok: true });
      } catch (e) { log({ at: "instructions.entry.put", ok: false, error: String(e) }); }
    });
    await ctx.session.hook("context", (event) => {
      log({ at: "context", sessionID: event.sessionID, system: event.system?.length });
      event.system.push({ type: "text", text: "Служебная метка: ЖИМОЛОСТЬ-4242" });
    });
  },
};
"""

work = Path(tempfile.mkdtemp(prefix="symphysis opencode проба "))
plugins = work / ".opencode" / "plugins"
plugins.mkdir(parents=True)
(plugins / "symphysis-hook.js").write_text(PLUGIN, encoding="utf-8")
env = {k: v for k, v in os.environ.items() if not k.startswith(("ELECTRON_", "VSCODE_", "CLAUDE")) and k not in ("NoDefaultCurrentDirectoryInExePath", "PYTHONIOENCODING")}
env["PROBE_PYTHON"] = sys.executable
OPENCODE = shutil.which("opencode.cmd") or shutil.which("opencode")
out = []
home = str(Path.home())


def clean(text):
    text = str(text)
    for value, mark in ((str(work), "<проект>"), (home, "<home>")):
        for form in (value.replace("\\", "\\\\\\\\"), value.replace("\\", "\\\\"), value, value.replace("\\", "/")):
            text = text.replace(form, mark)
    return text


def trace():
    file = work / "hook-trace.jsonl"
    if not file.exists():
        return []
    rows = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()]
    file.unlink()
    return rows


def run(name, *extra):
    cmd = [OPENCODE, "run", "--standalone", "--format", "json", "--print-logs", "--log-level", "warn", "-m", MODEL, *extra, QUESTION]
    try:
        done = subprocess.run(cmd, cwd=work, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=240)
        code, stdout, stderr = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as e:
        code, stdout, stderr = "timeout", (e.stdout or b"").decode("utf-8", "replace"), (e.stderr or b"").decode("utf-8", "replace")
    session, texts = None, []
    for line in stdout.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        found = row.get("sessionID") or row.get("session_id") or (row.get("session") or {}).get("id") if isinstance(row, dict) else None
        session = session or found
        if isinstance(row, dict) and isinstance(row.get("text"), str):
            texts.append(row["text"])
        elif isinstance(row, dict) and isinstance(row.get("part"), dict) and isinstance(row["part"].get("text"), str):
            texts.append(row["part"]["text"])
    errors = [line[:160] for line in stderr.splitlines() if "loading plugin" in line or "level=ERROR" in line]
    out.append(clean(json.dumps({"case": name, "code": code, "session": session, "reply": "".join(texts)[:400], "trace": trace(), "stdout_lines": len(stdout.splitlines()),
                                 "stdout_head": stdout[:300] if not texts else "", "log_lines": errors[:12]}, ensure_ascii=False)))
    return session


try:
    version = subprocess.run([OPENCODE, "--version"], env=env, capture_output=True, encoding="utf-8", errors="replace").stdout.strip()
    out.append(json.dumps({"case": "версии", "opencode": version, "model": MODEL}, ensure_ascii=False))
    subprocess.run(["git", "init", "-q"], cwd=work, env=env, check=True)
    session = run("новая сессия: файл в .opencode/plugins, без opencode.json")
    state = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=work, env=env, capture_output=True, encoding="utf-8", errors="replace").stdout.splitlines()
    out.append(json.dumps({"case": "git после запроса", "git_status": state, "project_files": sorted(p.relative_to(work).as_posix() for p in work.rglob("*") if p.is_file() and ".git/" not in p.as_posix() and "/.git" not in p.as_posix())[:30]}, ensure_ascii=False))
    if session:
        run("та же сессия", "--session", session)
finally:
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    shutil.rmtree(work, ignore_errors=True)
print(LOG.read_text(encoding="utf-8"))
