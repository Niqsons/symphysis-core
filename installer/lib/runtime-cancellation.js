import fs from "node:fs";
import path from "node:path";
import { isFullyAbsolute } from "./paths.js";

export class CancellationError extends Error {
  constructor(message) {
    super(message);
    this.name = "CancellationError";
    this.code = "cancellation-invalid";
    this.exitCode = 2;
    this.action = "Повтори запуск с действительным собственным файлом управления отменой";
  }
}

function noLinks(file) {
  let current = path.parse(file).root;
  const parts = file.slice(current.length).split(path.sep).filter(Boolean);
  for (let index = 0; index < parts.length; index++) {
    current = path.join(current, parts[index]);
    const stat = fs.lstatSync(current, { throwIfNoEntry: false });
    if (!stat || stat.isSymbolicLink() || (index < parts.length - 1 && !stat.isDirectory()) || (index === parts.length - 1 && !stat.isFile())) throw new CancellationError("Файл отмены отсутствует, проходит через ссылку/reparse либо имеет неподходящий тип");
  }
}

function readControl(file) {
  try {
    noLinks(file);
    const fd = fs.openSync(file, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0));
    let bytes;
    try {
      const stat = fs.fstatSync(fd);
      if (!stat.isFile() || stat.size > 65536) throw new CancellationError("Неверный размер или тип файла отмены");
      bytes = fs.readFileSync(fd);
    } finally { fs.closeSync(fd); }
    noLinks(file);
    const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!value || typeof value !== "object" || Array.isArray(value) || value.format !== 1 || typeof value.id !== "string" || !value.id || value.id.length > 256 || /\0/.test(value.id) || typeof value.token !== "string" || !/^(?:[a-f0-9]{2}){16,64}$/i.test(value.token) || typeof value.cancel !== "boolean") throw new CancellationError("Неверный формат файла отмены");
    return value;
  } catch (error) {
    if (error instanceof CancellationError) throw error;
    throw new CancellationError("Файл отмены недоступен либо не содержит допустимый UTF-8 JSON");
  }
}

/** Host-owned explicit control file; never consumes child stdin or writes protocol stdout. */
export function watchCancellation(env, onCancel) {
  const chosen = env?.SYMPHYSIS_CANCEL_FILE;
  if (chosen === undefined) return () => {};
  if (!isFullyAbsolute(chosen)) throw new CancellationError("SYMPHYSIS_CANCEL_FILE должен быть абсолютным путём существующего файла");
  if (typeof onCancel !== "function") throw new TypeError("onCancel must be a function");
  const file = path.resolve(chosen);
  const initial = readControl(file);
  let timer;
  let disposed = false;
  const dispose = () => { disposed = true; if (timer) clearInterval(timer); };
  const cancel = (error = null) => {
    if (disposed) return;
    dispose();
    onCancel(error);
  };
  if (initial.cancel) queueMicrotask(() => cancel());
  else {
    timer = setInterval(() => {
      let current;
      try {
        current = readControl(file);
        if (current.id !== initial.id || current.token !== initial.token) throw new CancellationError("Владелец файла отмены изменился во время выполнения");
      } catch (error) { cancel(error); return; }
      if (current.cancel) cancel();
    }, 100);
    timer.unref();
  }
  return dispose;
}
