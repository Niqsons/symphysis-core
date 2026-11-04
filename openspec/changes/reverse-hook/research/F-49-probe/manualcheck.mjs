// Проверка ручного плагина без модели и без сессий: загрузка, наблюдатель, отсутствие сессии в каталоге. Итог пишет в manual/check.txt без путей.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { TOOLS, newTrace, rest, sleep, startServer, stopServer } from "./lib.mjs";

const root = process.argv[2];
const events = path.join(root, ".symphysis", "viewer", "events.jsonl");
const traceDir = newTrace("manualcheck");
const server = await startServer(traceDir, { label: "serve-manual" });
try {
  const status = (await rest(server, "GET", "/api/location", { directory: root })).status;
  await sleep(3000);
  fs.appendFileSync(events, `${JSON.stringify({ op: "prompt", text: "проверка" })}\n`, "utf8");
  await sleep(3000);
  const log = fs.readFileSync(path.join(root, ".symphysis", "viewer", "probe.log"), "utf8").replaceAll(root.replaceAll("\\", "\\\\"), "<проект>").replaceAll(os.tmpdir().replaceAll("\\", "\\\\"), "<tmp>");
  const text = `Проверка manual-plugin.js без клиента и модели: opencode serve, GET /api/location с каталогом проекта (код ${status}), затем строка в events.jsonl. Сессии в проекте нет, поэтому latest пуст и вызова session.prompt нет.\n${log}`;
  fs.writeFileSync(path.join(TOOLS, "manual", "check.txt"), text, "utf8");
  console.log(text);
} finally {
  stopServer(server);
}
