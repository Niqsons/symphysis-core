// Прогон скрипта просмотрщика без браузера: узлы документа — заглушки, итог — HTML карточек,
// оглавления, сводки, панелей режимов «проверка» и «атака», переключателя и промпта возврата одним JSON в stdout.
// Падение скрипта шаблона — код 1 и стек в stderr.
// Использование: node viewer-smoke.js <файл.html> [<состояние.json>]
// Состояние — то, что просмотрщик хранит в браузере (localStorage) под главным ключом; в итог (`saved`) попадает
// последнее сохранённое под ним. Необязательный ключ `__suffixes__` состояния задаёт значения ключей с суффиксом:
// `":mode"` — строка режима, `":attack"` — объект споров по строкам атаки, `":lens"` — выбранная линза фильтра атаки; сохранённое под `:attack` — `savedAttack`.
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync(process.argv[2], 'utf8');
const parsed = process.argv[3] ? JSON.parse(fs.readFileSync(process.argv[3], 'utf8')) : null;
const suffixes = (parsed && parsed.__suffixes__) || {};
if (parsed) delete parsed.__suffixes__;
const stored = parsed ? JSON.stringify(parsed) : null;
let saved = null, savedAttack = null;
const script = html.slice(html.indexOf('<script>') + '<script>'.length, html.lastIndexOf('</script>'));

const suffix = k => k.slice(k.lastIndexOf(':'));
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
  localStorage: {
    getItem(k) {
      const s = suffix(k);
      if (s === ':outh') return null;
      if (s in suffixes) return typeof suffixes[s] === 'string' ? suffixes[s] : JSON.stringify(suffixes[s]);
      return s === ':mode' || s === ':attack' || s === ':lens' ? null : stored;
    },
    setItem(k, v) {
      const s = suffix(k);
      if (s === ':attack') savedAttack = v;
      else if (s !== ':outh' && s !== ':mode' && s !== ':lens') saved = v;
    },
  },
  navigator: {}, Blob: function () {}, URL: { createObjectURL() { return ''; } },
  alert() {}, confirm() { return false; }, setTimeout() {},
};
vm.runInNewContext(script, context);
process.stdout.write(JSON.stringify({
  cards: nodes.cards.innerHTML, toc: nodes.toc.innerHTML, stats: nodes.stats.innerHTML, saved,
  modes: node('modes').innerHTML, check: node('viewCheck').innerHTML, attack: node('viewAttack').innerHTML,
  out: node('out').value, savedAttack,
}));
