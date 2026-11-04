// Проба F-49: плагин opencode только для временного проекта. Журнал пишет локально в F49_TRACE_DIR, наружу ничего не шлёт.
// Команды приходят строками events.jsonl (поле probe). Хук context стережёт, что ушло бы модели: чужие навыки и инструкции останавливают запрос до провайдера.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const TRACE_DIR = process.env.F49_TRACE_DIR;
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const VIEWER = path.join(ROOT, ".symphysis", "viewer");
const EVENTS = path.join(VIEWER, "events.jsonl");
const CONTROL = path.join(TRACE_DIR ?? ".", "control.json");
const TRACE = path.join(TRACE_DIR ?? ".", "trace.jsonl");
const NOISE = /(\.delta$|session\.usage\.updated$|^server\.heartbeat$)/;
const SKILLS_OK = new Set(["opencode", "report"]);

const trace = (row) => {
  if (!TRACE_DIR) return;
  fs.appendFileSync(TRACE, `${JSON.stringify({ t: Date.now(), pid: process.pid, ...row })}\n`, "utf8");
};
const control = () => {
  try {
    return JSON.parse(fs.readFileSync(CONTROL, "utf8"));
  } catch {
    return {};
  }
};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const brief = (s) => ({ id: s.id, parentID: s.parentID, directory: s.location?.directory, subpath: s.subpath, title: s.title, model: s.model, outcome: s.outcome, time: s.time });
const textOf = (content) => (typeof content === "string" ? content : (content ?? []).map((part) => part.text ?? `[${part.type}${part.name ? ` ${part.name}` : ""}]`).join(""));
const describe = (e) => ({ name: e?.name, _tag: e?._tag, message: String(e?.message ?? e).slice(0, 800), cause: e?.cause ? String(e.cause).slice(0, 400) : undefined });

export default {
  id: "f49-probe",
  async setup(ctx) {
    const copy = `${process.pid}-${Date.now() % 100000}`;
    const directory = ctx.location.directory;
    trace({ at: "setup", copy, directory, project: { id: ctx.location.project?.id, directory: ctx.location.project?.directory }, bun: !!process.versions.bun, argv: process.argv.slice(2, 5), ctx_keys: Object.keys(ctx) });
    const stop = new AbortController();
    let contexts = 0;

    (async () => {
      try {
        for await (const ev of ctx.event.subscribe({ signal: stop.signal })) {
          if (NOISE.test(ev.type)) continue;
          const d = ev.data ?? {};
          const row = { at: "event", copy, type: ev.type, sessionID: d.sessionID, event_location: ev.location?.directory };
          if (ev.type === "session.created") Object.assign(row, { location: d.location, parentID: d.parentID, subpath: d.subpath, keys: Object.keys(d) });
          if (ev.type === "session.inbox.enqueued") Object.assign(row, { inboxID: d.inboxID, item: d.item?.type, delivery: d.item?.delivery, text: String(d.item?.payload?.text ?? "").slice(0, 80) });
          if (ev.type === "session.inbox.delivered") Object.assign(row, { inboxID: d.inboxID });
          if (ev.type === "session.execution.interrupted") Object.assign(row, { reason: d.reason });
          if (ev.type === "session.execution.failed") Object.assign(row, { error: d.error });
          if (ev.type === "session.step.failed") Object.assign(row, { error: d.error });
          trace(row);
        }
        trace({ at: "event-stream-end", copy });
      } catch (e) {
        trace({ at: "event-stream-error", copy, error: describe(e) });
      }
    })();

    await ctx.session.hook("prompt", async (event) => {
      trace({ at: "hook.prompt", copy, sessionID: event.sessionID, messageID: event.messageID, delivery: event.delivery, metadata: event.metadata, text: String(event.prompt?.text ?? "").slice(0, 80) });
      const value = event.metadata?.instr;
      if (typeof value === "string") await ctx.session.instructions.entry.put({ sessionID: event.sessionID, key: "f49", value });
    });

    await ctx.session.hook("context", async (event) => {
      contexts += 1;
      const n = contexts;
      const system = event.system.map((part) => part.text ?? "").join("\n");
      const whole = `${system}\n${JSON.stringify(event.messages)}`;
      const skills = [...system.matchAll(/<skill>\s*<id>([^<]+)<\/id>/g)].map((m) => m[1]);
      const foreign = skills.filter((id) => !SKILLS_OK.has(id));
      const instructions = [...whole.matchAll(/Instructions from: ([^\n"\\]+)/g)].map((m) => m[1]);
      const claude = /CLAUDE\.md|[\\/]\.claude[\\/]/.test(whole);
      fs.writeFileSync(path.join(TRACE_DIR, `system-${event.sessionID}-${Date.now()}.txt`), system, "utf8");
      trace({ at: "hook.context", copy, n, sessionID: event.sessionID, agent: event.agent, model: event.model, system_chars: system.length, skills, instructions, tools: Object.keys(event.tools), messages: event.messages.map((m) => ({ role: m.role, text: textOf(m.content).slice(0, 400) })) });
      if (foreign.length || instructions.length || claude) {
        trace({ at: "guard.block", copy, sessionID: event.sessionID, foreign, instructions, claude });
        throw new Error("f49: запрос к модели остановлен сторожем");
      }
      const c = control();
      if (c.delayMs && !c.delayDone) {
        fs.writeFileSync(CONTROL, JSON.stringify({ ...c, delayDone: true }), "utf8");
        trace({ at: "delay.start", copy, sessionID: event.sessionID, ms: c.delayMs });
        await sleep(c.delayMs);
        trace({ at: "delay.end", copy, sessionID: event.sessionID });
      }
    });

    await ctx.session.hook("title", (event) => {
      event.result = "f49-проба";
    });
    await ctx.session.hook("model.request", (event) => {
      trace({ at: "hook.model.request", copy, sessionID: event.sessionID, kind: event.kind, model: event.model });
    });
    await ctx.session.hook("experimental.idle", (event) => {
      trace({ at: "hook.idle", copy, sessionID: event.sessionID, background: event.background.length });
    });
    await ctx.tool.hook("execute.after", (event) => {
      trace({ at: "tool.after", copy, sessionID: event.sessionID, tool: event.name ?? event.tool ?? event.id, input: event.input, status: event.status ?? "ok" });
    });

    const handle = async (cmd, source) => {
      const started = Date.now();
      trace({ at: "command", copy, op: cmd.op, tag: cmd.tag, source });
      try {
        if (cmd.op === "list") {
          const r = await ctx.session.list({ directory, parentID: null, limit: 10, order: "desc" });
          trace({ at: "list", copy, tag: cmd.tag, directory, data: r.data.map(brief), has_next: !!r.cursor?.next });
          return;
        }
        let sessionID = cmd.session;
        if (sessionID === "latest") {
          const r = await ctx.session.list({ directory, parentID: null, limit: 1, order: "desc" });
          sessionID = r.data[0]?.id;
          trace({ at: "latest", copy, tag: cmd.tag, directory, sessionID });
          if (!sessionID) return;
        }
        const input = { sessionID, text: cmd.text };
        for (const key of ["delivery", "resume", "metadata", "description"]) if (cmd[key] !== undefined) input[key] = cmd[key];
        const res = await (cmd.op === "synthetic" ? ctx.session.synthetic(input) : ctx.session.prompt(input));
        trace({ at: "admitted", copy, tag: cmd.tag, op: cmd.op, ms: Date.now() - started, res: res?.data ? { id: res.data.id, type: res.data.type, delivery: res.data.delivery, keys: Object.keys(res.data) } : res });
      } catch (e) {
        trace({ at: "command-error", copy, tag: cmd.tag, op: cmd.op, ms: Date.now() - started, error: describe(e) });
      }
    };

    const size = () => {
      try {
        return fs.statSync(EVENTS).size;
      } catch {
        return 0;
      }
    };
    let offset = size();
    const scan = (source) => {
      const end = size();
      if (end <= offset) return;
      const fd = fs.openSync(EVENTS, "r");
      const buf = Buffer.alloc(end - offset);
      fs.readSync(fd, buf, 0, buf.length, offset);
      fs.closeSync(fd);
      offset = end;
      trace({ at: "file-new-bytes", copy, source, bytes: buf.length });
      for (const line of buf.toString("utf8").split("\n").filter(Boolean)) {
        let row;
        try {
          row = JSON.parse(line);
        } catch {
          continue;
        }
        if (row.probe) void handle(row.probe, source);
      }
    };
    let watcher = null;
    try {
      watcher = fs.watch(VIEWER, (kind, name) => {
        trace({ at: "watch-fired", copy, kind, name: String(name) });
        scan("watch");
      });
      watcher.on?.("error", (e) => trace({ at: "watch-error", copy, error: describe(e) }));
    } catch (e) {
      trace({ at: "watch-failed", copy, error: describe(e) });
    }
    const poll = setInterval(() => scan("poll"), 1000);

    return () => {
      const keep = control().keepAfterCleanup === true;
      trace({ at: "cleanup", copy, directory, keep });
      if (keep) return;
      stop.abort();
      watcher?.close();
      clearInterval(poll);
    };
  },
};
