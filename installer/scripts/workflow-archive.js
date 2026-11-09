import fs from "node:fs";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { isFullyAbsolute } from "../lib/paths.js";

const decode = (bytes) => new TextDecoder("utf-8", { fatal: true }).decode(bytes);
const field = (header, start, length) => decode(header.subarray(start, start + length)).split("\0")[0];
function octal(header, start, length) {
  const value = field(header, start, length).trim();
  if (!/^[0-7]+$/.test(value)) throw new Error("Unsupported tar numeric field");
  const number = Number.parseInt(value, 8);
  if (!Number.isSafeInteger(number)) throw new Error("Oversized tar member");
  return number;
}

/** Validate the complete gzip/tar before extracting any file. The pinned npm archive uses regular ustar entries. */
export function workflowArchiveEntries(archive) {
  const tar = gunzipSync(archive, { maxOutputLength: 64 * 1024 * 1024 });
  const entries = [];
  const names = new Set();
  let offset = 0;
  let ended = false;
  while (offset + 512 <= tar.length) {
    const header = tar.subarray(offset, offset + 512);
    if (header.every((byte) => byte === 0)) {
      if (offset + 1024 > tar.length || !tar.subarray(offset).every((byte) => byte === 0)) throw new Error("Malformed tar ending");
      ended = true;
      break;
    }
    const checksum = octal(header, 148, 8);
    if (field(header, 257, 6) !== "ustar" || field(header, 263, 2) !== "00") throw new Error("Unsupported tar header format");
    let actual = 0;
    for (let index = 0; index < 512; index++) actual += index >= 148 && index < 156 ? 32 : header[index];
    if (actual !== checksum) throw new Error("Tar header checksum mismatch");
    const type = String.fromCharCode(header[156]);
    if (!["0", "\0", "5"].includes(type)) throw new Error("Tar links, extensions and special files are not accepted");
    if (field(header, 157, 100)) throw new Error("Unexpected tar link target");
    const prefix = field(header, 345, 155);
    let name = [prefix, field(header, 0, 100)].filter(Boolean).join("/");
    if (type === "5" && name.endsWith("/")) name = name.slice(0, -1);
    if (!name.startsWith("package/") && !(name === "package" && type === "5")) throw new Error("Tar member is outside package/");
    if (/[\\:<>"|?*\x00-\x1f\x7f]/.test(name) || name.split("/").some((part) => !part || part === "." || part === ".." || /[. ]$/.test(part) || /^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\.|$)/i.test(part))) throw new Error("Unsafe tar member name");
    const key = name.toLowerCase();
    if (names.has(key)) throw new Error("Duplicate tar member");
    names.add(key);
    const size = octal(header, 124, 12);
    if (type === "5" && size !== 0) throw new Error("Tar directory has content");
    if (offset + 512 + size > tar.length) throw new Error("Truncated tar member");
    entries.push({ name, directory: type === "5", bytes: Buffer.from(tar.subarray(offset + 512, offset + 512 + size)) });
    offset += 512 + Math.ceil(size / 512) * 512;
  }
  if (!ended) throw new Error("Tar archive has no complete ending");
  const files = new Set(entries.filter((entry) => !entry.directory).map((entry) => entry.name.toLowerCase()));
  for (const entry of entries) {
    const parts = entry.name.split("/");
    for (let count = 1; count < parts.length; count++) if (files.has(parts.slice(0, count).join("/").toLowerCase())) throw new Error("Tar file is used as a parent directory");
  }
  return entries;
}

export function workflowBuildPath(value) {
  if (!isFullyAbsolute(value)) throw new Error("Workflow build requires a fully absolute temporary path");
  const resolved = path.resolve(value);
  let cursor = path.parse(resolved).root;
  for (const part of resolved.slice(cursor.length).split(path.sep).filter(Boolean)) {
    cursor = path.join(cursor, part);
    const stat = fs.lstatSync(cursor, { throwIfNoEntry: false });
    if (!stat) break;
    if (stat.isSymbolicLink()) throw new Error("Workflow build path crosses a symlink/junction");
  }
  return resolved;
}

export function extractWorkflowArchive(entries, destination) {
  const base = workflowBuildPath(destination);
  for (const entry of entries) {
    const target = workflowBuildPath(path.join(base, ...entry.name.split("/")));
    if (!path.relative(base, target) || path.relative(base, target).startsWith("..")) throw new Error("Tar target escapes extraction root");
    if (entry.directory) fs.mkdirSync(target, { recursive: true });
    else {
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, entry.bytes, { flag: "wx", mode: 0o600 });
    }
  }
  return path.join(base, "package");
}

/** No recursive deletion through a link; only the explicit build tree is removed. */
export function removeWorkflowBuildTree(root) {
  workflowBuildPath(root);
  const files = [];
  const directories = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.isSymbolicLink()) throw new Error("Refusing cleanup through a workflow build link");
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) { walk(file); directories.push(file); }
      else if (entry.isFile()) files.push(file);
      else throw new Error("Unexpected workflow build object");
    }
  };
  walk(root);
  for (const file of files) fs.unlinkSync(file);
  for (const dir of directories) fs.rmdirSync(dir);
  fs.rmdirSync(root);
}
