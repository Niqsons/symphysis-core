// Ручная проба F-49: плагин для временного проекта. Строка в .symphysis/viewer/events.jsonl будит последнюю сессию каталога. Журнал: .symphysis/viewer/probe.log.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const VIEWER = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", ".symphysis", "viewer");
const EVENTS = path.join(VIEWER, "events.jsonl");
const LOG = path.join(VIEWER, "probe.log");
const log = (row) => fs.appendFileSync(LOG, `${new Date().toISOString()} ${JSON.stringify(row)}\n`, "utf8");
const size = () => (fs.existsSync(EVENTS) ? fs.statSync(EVENTS).size : 0);

export default {
  id: "f49-manual",
  async setup(ctx) {
    const directory = ctx.location.directory;
    log({ at: "setup", pid: process.pid, directory, argv: process.argv.slice(2, 5) });
    const stop = new AbortController();
    (async () => {
      for await (const ev of ctx.event.subscribe({ signal: stop.signal })) {
        if (/^session\.(created|viewed|deleted|inbox\.enqueued|inbox\.delivered|execution\.)/.test(ev.type)) log({ at: "event", type: ev.type, sessionID: ev.data?.sessionID, directory: ev.data?.location?.directory });
      }
    })().catch((e) => log({ at: "event-error", message: String(e) }));
    let offset = size();
    const wake = async (line) => {
      const row = JSON.parse(line);
      const list = await ctx.session.list({ directory, parentID: null, limit: 1, order: "desc" });
      const sessionID = list.data[0]?.id;
      log({ at: "latest", sessionID });
      if (!sessionID) return;
      const input = { sessionID, text: row.text };
      if (row.delivery) input.delivery = row.delivery;
      const res = await (row.op === "synthetic" ? ctx.session.synthetic({ ...input, description: "ручная проба: служебное" }) : ctx.session.prompt(input));
      log({ at: "admitted", op: row.op, delivery: res?.data?.delivery, id: res?.data?.id });
    };
    const scan = () => {
      const end = size();
      if (end <= offset) return;
      const text = fs.readFileSync(EVENTS).subarray(offset, end).toString("utf8");
      offset = end;
      for (const line of text.split("\n").filter(Boolean)) wake(line).catch((e) => log({ at: "error", name: e?.name, _tag: e?._tag, message: String(e?.message ?? e) }));
    };
    const watcher = fs.watch(VIEWER, scan);
    return () => {
      log({ at: "cleanup" });
      stop.abort();
      watcher.close();
    };
  },
};
