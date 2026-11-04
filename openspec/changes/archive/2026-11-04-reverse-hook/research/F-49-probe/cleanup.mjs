// Удаляет сессии пробы F-49 из общей базы: только номера из её учёта и только командой opencode. Пишет итог в cleanup.txt.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { OPENCODE, WORK, baseEnv } from "./lib.mjs";

const empty = path.join(WORK, "empty");
fs.mkdirSync(empty, { recursive: true });
const dbNow = () => {
  const r = spawnSync("py", ["-3.13", "-I", path.join(WORK, "tools", "db_mine.py"), path.basename(WORK)], { encoding: "utf8", env: { ...process.env, PYTHONUTF8: "1" } });
  if (r.status !== 0) throw new Error(`db_mine: ${r.stderr}`);
  return r.stdout;
};
const log = [];
const before = dbNow();
const fromDb = (/^ids:(.*)$/m.exec(before)?.[1] ?? "").split(/\s+/).filter(Boolean);
const file = path.join(WORK, "sessions.txt");
const known = fs.existsSync(file) ? fs.readFileSync(file, "utf8").split(/\r?\n/).filter(Boolean) : [];
const ids = [...new Set([...known, ...fromDb])];
log.push(`в учёте пробы: ${known.length}; в базе с каталогом пробы: ${fromDb.length}; вне учёта: ${fromDb.filter((id) => !known.includes(id)).length}`);
log.push(`база до: ${before.replace(/^ids:.*\n/m, "").trim().split(/\r?\n/).join("; ")}`);
let failed = 0;
for (const id of ids) {
  const r = spawnSync(OPENCODE, ["session", "delete", "--standalone", id], { cwd: empty, env: baseEnv(), encoding: "utf8", timeout: 90000, windowsHide: true });
  const inDb = fromDb.includes(id);
  log.push(`${id} код ${r.status} ${inDb ? "был в базе" : "в базе уже не было"}`);
  if (r.status !== 0 && inDb) {
    failed += 1;
    log.push(`  stderr: ${String(r.stderr).slice(0, 200)}`);
  }
}
const after = dbNow();
const left = (/^ids:(.*)$/m.exec(after)?.[1] ?? "").split(/\s+/).filter(Boolean);
log.push(`база после: ${after.replace(/^ids:.*\n/m, "").trim().split(/\r?\n/).join("; ")}`);
log.push(`сессий пробы в базе осталось: ${left.length}`);
// Список сессий своими средствами клиента: из проекта пробы, номера чужих в след не идут.
const list = spawnSync(OPENCODE, ["session", "list", "--standalone"], { cwd: empty, env: baseEnv(), encoding: "utf8", timeout: 90000, windowsHide: true });
log.push(`opencode session list: код ${list.status}; номеров пробы в выводе: ${ids.filter((id) => String(list.stdout).includes(id)).length}`);
fs.writeFileSync(path.join(WORK, "cleanup.txt"), `${log.join("\n")}\n`, "utf8");
console.log(log.join("\n"));
process.exit(failed || left.length ? 1 : 0);
