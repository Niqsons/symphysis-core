"""Проба F-21, пункт 3: патч правила A на копии trace_graph.py вне проекта. Читает <инструменты>/trace_graph.py, делает
точечные замены (каждый якорь должен встретиться ровно один раз) и пишет <инструменты-A>/trace_graph.py; соседние модули
копируются как есть. Правило A: ключ отсечения — (номер, буква варианта, имя журнала перед списком); ссылка с чужим
именем журнала в дельте — не ссылка этого журнала (ни связи, ни «неизвестный номер»); голый номер мастера против голого
своего отсекается, как сейчас. База снимка несёт только числа, поэтому ключи мастера берутся из живого мастера временного
корня — он стоит на коммите снимка (сверка — basecheck.py).
Вызов: python -X utf8 patch-rule-A.py <инструменты> <инструменты-A>."""
import shutil
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
for name in ("roots.py", "journal_model.py", "journal.schema.json", "openspec_run.py"):
    shutil.copy(src / name, dst / name)
text = (src / "trace_graph.py").read_text(encoding="utf-8")

REPLACEMENTS = [
    # R1: регэксп ссылки с буквой варианта, метка журнала, конец списка
    ('_REC_REF = re.compile(r"(?<![\\w-])F-(\\d+)(?!\\d)")',
     '_REC_REF = re.compile(r"(?<![\\w-])F-(\\d+)(?!\\d)(?:\\.([A-Z])(?![A-Za-z]))?")  # проба F-21, правило A: группа 2 — буква варианта\n'
     '_JOURNAL_LABEL = re.compile(r"журнал[а-я]*\\s+`([^`]+)`\\s*:")  # проба F-21: имя журнала перед списком ссылок\n'
     '_LIST_END = re.compile(r"[;)]")  # проба F-21: конец списка после метки журнала'),
    # R2: разбор полных ссылок рядом с _record_numbers
    ('    return [int(m.group(1)) for m in _REC_REF.finditer(text)]\n',
     '    return [int(m.group(1)) for m in _REC_REF.finditer(text)]\n'
     '\n'
     '\n'
     'def _record_refs(text: str, own: str | None = None) -> list[tuple[int, str | None, str | None]]:\n'
     '    """Проба F-21, правило A: ссылки `(номер, буква варианта или None, имя журнала или None)`; имя — из ближайшей слева\n'
     '    метки ``журнал `имя`:`` той же строки до `;`, `)` или конца строки; имя, равное `own`, — своё (None)."""\n'
     '    scopes = []\n'
     '    for m in _JOURNAL_LABEL.finditer(text):\n'
     '        end = _LIST_END.search(text, m.end())\n'
     '        scopes.append((m.end(), end.start() if end else len(text), m.group(1)))\n'
     '    out = []\n'
     '    for m in _REC_REF.finditer(text):\n'
     '        journal = next((name for start, stop, name in scopes if start <= m.start() < stop), None)\n'
     '        out.append((int(m.group(1)), m.group(2), None if journal == own else journal))\n'
     '    return out\n'),
    # R3: запись мастера несёт полные ссылки
    ('                "numbers": sorted({n for _, line in _requirement_body(lines, mask, req.line) for n in _record_numbers(line)}),\n',
     '                "numbers": sorted({n for _, line in _requirement_body(lines, mask, req.line) for n in _record_numbers(line)}),\n'
     '                "refs": sorted({r for _, line in _requirement_body(lines, mask, req.line) for r in _record_refs(line)}, key=str),  # проба F-21\n'),
    # R4: поле refs не ломает годность записи базы
    ('    return (isinstance(entry, dict) and set(entry) == {"numbers", "scenarios", "text", "traces"}',
     '    return (isinstance(entry, dict) and set(entry) - {"refs"} == {"numbers", "scenarios", "text", "traces"}'),
    # R5: запись базы без refs дополняется ссылками живого мастера (на коммите снимка)
    ('    def entry(self, cap: str, name: str) -> tuple[dict | None, bool]:\n'
     '        if name in self.saved.get(cap, {}):\n'
     '            return self.saved[cap][name], True\n'
     '        if cap not in self.live:\n'
     '            self.live[cap] = master_base(self.root, cap)\n'
     '        return self.live[cap].get(name), False\n',
     '    def entry(self, cap: str, name: str) -> tuple[dict | None, bool]:\n'
     '        if cap not in self.live:\n'
     '            self.live[cap] = master_base(self.root, cap)\n'
     '        if name in self.saved.get(cap, {}):\n'
     '            saved = self.saved[cap][name]\n'
     '            if "refs" not in saved:  # проба F-21: база снимка несёт только числа; ключи правила A — из мастера на коммите снимка\n'
     '                live = self.live[cap].get(name)\n'
     '                saved = {**saved, "refs": live["refs"] if live else [(n, None, None) for n in saved["numbers"]]}\n'
     '            return saved, True\n'
     '        return self.live[cap].get(name), False\n'),
    # R6: known — полные ключи; заявка rec знает своё изменение
    ('                    known = set(entry["numbers"])\n',
     '                    known = {(n, l, None if j == base.name else j) for n, l, j in entry["refs"]}  # проба F-21: полные ключи\n'),
    ('                                   "text": line, "skip": known})\n',
     '                                   "text": line, "skip": known, "own": base.name})  # проба F-21\n'),
    # R7: cut — полные ключи
    ('            cut.setdefault(claim["from"], set()).update(entry["numbers"])\n',
     '            cut.setdefault(claim["from"], set()).update((n, l, j) for n, l, j in entry["refs"])  # проба F-21: полные ключи\n'),
    # R8: put_records — чужая ссылка пропускается, ключ отсечения полный
    ('    def put_records(claim: dict, text: str, skip: set, by_place: bool = False) -> None:\n'
     '        for number in _record_numbers(text):\n'
     '            if number in skip:\n'
     '                continue\n',
     '    def put_records(claim: dict, text: str, skip: set, by_place: bool = False) -> None:\n'
     '        if claim["kind"] == "rec":  # проба F-21, правило A: чужая ссылка — не ссылка этого журнала; ключ отсечения полный\n'
     '            refs = [(n, l, j) for n, l, j in _record_refs(text, claim.get("own")) if j is None]\n'
     '            numbers = [n for n, l, j in refs if (n, l, None) not in skip]\n'
     '        else:\n'
     '            numbers = _record_numbers(text)\n'
     '        for number in numbers:\n'),
]
for old, new in REPLACEMENTS:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"якорь встречается {count} раз, нужен 1: {old[:70]!r}")
    text = text.replace(old, new)
(dst / "trace_graph.py").write_text(text, encoding="utf-8", newline="\n")
print(f"патч применён: {len(REPLACEMENTS)} замен, {dst / 'trace_graph.py'}")
