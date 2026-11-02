#!/usr/bin/env node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { parseArgs } from "node:util";
import { fileURLToPath, pathToFileURL } from "node:url";
import { removeTree } from "./sync-payload.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(here, "..", "..");
const FORK_DIR = "upstream/openspec";
const win = process.platform === "win32";

const USAGE = `build-vendor — тарбол форка OpenSpec в vendor/ репозитория
Звать, когда версия форка изменилась и выпуск должен везти новый тарбол: после коммита
в форк и правки symphysis.openspecPin, перед коммитом vendor/.

Использование:
  node installer/scripts/build-vendor.js [--root <dir>]

Общие:
  --root <dir>  корень репозитория с upstream/openspec, vendor/ и installer/package.json;
                по умолчанию — каталог над installer/
  -h, --help    эта справка

Порядок: коммит в форк; версия форка равна symphysis.openspecPin; этот скрипт; гейт имён
  по распакованному тарболу; коммит vendor/.
Исходы: нет форка — ветка openspec-fork и команда получения в stderr; версия не равна пину
  или в форке незакоммиченные правки — причина в stderr; во всех трёх vendor/ не меняется.
  Иначе тарбол собран из коммита, прежний *.tgz удалён, в stdout хеш коммита и путь тарбола.
Коды: 0 — тарбол в vendor/; 1 — тарбол не собран; 2 — вызов неверен.
`;

/** Причина и шаг получения: и у скрипта, и у тестов инсталлятора, которым нужен форк (находка F-22). */
export function forkMissingMessage() {
  return [
    `нет форка OpenSpec в ${FORK_DIR}: он вне git ядра, в ветке openspec-fork.`,
    `Получить: git fetch origin openspec-fork && git worktree add ${FORK_DIR} FETCH_HEAD`,
    `Собрать (bin/openspec.js ждёт dist/): pnpm --dir ${FORK_DIR} install && pnpm --dir ${FORK_DIR} build`,
    "Зависимости инсталлятора: npm --prefix installer ci",
  ].join("\n");
}

/** Для тестов: форка нет — ошибка с причиной и шагом получения, а не чужой ENOENT позже. */
export function requireFork(forkBin) {
  if (!fs.existsSync(forkBin) || !fs.existsSync(path.join(path.dirname(forkBin), "..", "dist", "cli", "index.js"))) {
    throw new Error(forkMissingMessage());
  }
}

class Refusal extends Error {}

function git(fork, ...args) {
  const r = spawnSync("git", ["-C", fork, ...args], { encoding: "utf8" });
  if (r.error || r.status !== 0) throw new Refusal(`git ${args[0]} в ${FORK_DIR} не отработал: ${String(r.error?.message ?? r.stderr).trim()}`);
  return r.stdout;
}

/** `npm pack` запускает `prepare` форка: `dist/` собирается заново из этого коммита. */
function packInto(fork, dest) {
  const r = win
    ? spawnSync(`npm pack --pack-destination "${dest}"`, { cwd: fork, encoding: "utf8", shell: true })
    : spawnSync("npm", ["pack", "--pack-destination", dest], { cwd: fork, encoding: "utf8" });
  if (r.error || r.status !== 0) throw new Refusal(`npm pack не отработал: ${String(r.error?.message ?? r.stderr).trim()}`);
  const [name] = fs.readdirSync(dest).filter((f) => f.endsWith(".tgz"));
  if (!name) throw new Refusal("npm pack не оставил *.tgz");
  return name;
}

/** Собирает тарбол: проверки до всякой записи, а прежний *.tgz удаляется только после удачной сборки. */
export function buildVendor(root = ROOT) {
  const fork = path.join(root, ...FORK_DIR.split("/"));
  if (!fs.existsSync(path.join(fork, "package.json"))) throw new Refusal(forkMissingMessage());
  const pin = JSON.parse(fs.readFileSync(path.join(root, "installer", "package.json"), "utf8")).symphysis?.openspecPin;
  const { version } = JSON.parse(fs.readFileSync(path.join(fork, "package.json"), "utf8"));
  if (version !== pin) throw new Refusal(`версия форка ${version}, symphysis.openspecPin ${pin}: тарбол не собран`);
  const dirty = git(fork, "status", "--porcelain");
  if (dirty.trim()) throw new Refusal(`в ${FORK_DIR} незакоммиченные правки, тарбол не собран:\n${dirty.trimEnd()}`);
  const hash = git(fork, "rev-parse", "HEAD").trim();

  const staging = fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-vendor-pack-"));
  try {
    const name = packInto(fork, staging);
    const vendor = path.join(root, "vendor");
    fs.mkdirSync(vendor, { recursive: true });
    for (const old of fs.readdirSync(vendor)) if (old.endsWith(".tgz")) fs.unlinkSync(path.join(vendor, old));
    fs.copyFileSync(path.join(staging, name), path.join(vendor, name));
    return { hash, name, bytes: fs.statSync(path.join(vendor, name)).size };
  } finally {
    removeTree(staging);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let values;
  try {
    ({ values } = parseArgs({ options: { root: { type: "string" }, help: { type: "boolean", short: "h" } } }));
  } catch (e) {
    process.stderr.write(`${e.message}\n\n${USAGE}`);
    process.exit(2);
  }
  if (values.help) {
    process.stdout.write(USAGE);
    process.exit(0);
  }
  try {
    const { hash, name, bytes } = buildVendor(path.resolve(values.root ?? ROOT));
    process.stdout.write(`форк ${hash}\nтарбол vendor/${name}, ${Math.round(bytes / 1024)} КБ\n`);
  } catch (e) {
    if (!(e instanceof Refusal)) throw e;
    process.stderr.write(`${e.message}\n`);
    process.exit(1);
  }
}
