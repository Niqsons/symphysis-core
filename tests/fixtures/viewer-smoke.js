// Прогон скрипта просмотрщика без браузера: узлы документа — заглушки, итог — HTML карточек,
// оглавления и сводки одним JSON в stdout. Падение скрипта шаблона — код 1 и стек в stderr.
// Использование: node viewer-smoke.js <файл.html> [<состояние.json>]
// Состояние — то, что просмотрщик хранит в браузере (localStorage); в итог попадает последнее сохранённое.
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync(process.argv[2], 'utf8');
const stored = process.argv[3] ? fs.readFileSync(process.argv[3], 'utf8') : null;
let saved = null;
const script = html.slice(html.lastIndexOf('<script>') + '<script>'.length, html.lastIndexOf('</script>'));

const nodes = {};
function node(id) {
  return nodes[id] || (nodes[id] = {
    id, innerHTML: '', textContent: '', value: '', dataset: {}, style: { setProperty() {} },
    classList: { add() {}, remove() {}, toggle() {} },
    querySelectorAll() { return []; }, querySelector() { return null; },
    addEventListener() {}, select() {}, click() {},
  });
}
const document = {
  getElementById: node, title: '', documentElement: { style: { setProperty() {} } },
  querySelectorAll() { return []; }, createElement() { return node('created'); }, execCommand() { return false; },
};
const context = {
  document, console,
  window: { addEventListener() {}, innerHeight: 800 },
  localStorage: { getItem(k) { return k.endsWith(':outh') ? null : stored; },
                  setItem(k, v) { if (!k.endsWith(':outh')) saved = v; } },
  navigator: {}, Blob: function () {}, URL: { createObjectURL() { return ''; } },
  alert() {}, confirm() { return false; }, setTimeout() {},
};
vm.runInNewContext(script, context);
process.stdout.write(JSON.stringify({
  cards: nodes.cards.innerHTML, toc: nodes.toc.innerHTML, stats: nodes.stats.innerHTML, saved,
}));
