"""Проба F-21, пункт 2: расклад по требованиям MODIFIED и дочерним ADDED («Часть требования») дельты изменения:
ссылки дельты по форме, числа отсечения (база снимка для MODIFIED; для дочернего — запись родителя, как в `cut`),
совпадения числа дельты с числом отсечения и форма этого числа в мастере на коммите снимка (голое / с буквой /
с именем журнала), вопрос записи своего журнала по этому номеру и что с совпадением делает правило A.
Вызов: python -X utf8 layout.py <инструменты> <корень пробы> <изменение> <каталог архива в проекте>."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import refparse  # noqa: E402

tools, root, change, archive = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
tg = refparse.load_trace_graph(tools)
base_dir = root / "openspec" / "changes" / change
base = tg.saved_base(base_dir)
report = (archive / "graph" / "report.md").read_text(encoding="utf-8").splitlines()
signalled = [line for line in report if "требование без записи" in line]
journal = json.loads((base_dir / "decisions.json").read_text(encoding="utf-8"))
questions = {int(r["id"].split("-")[1]): r["question"] for r in journal["records"]}


def master_forms(cap: str, name: str) -> dict[int, set[str]]:
    rel = f"openspec/specs/{cap}/spec.md"
    if not (root / rel).is_file():
        return {}
    lines = tg._master_lines(root, rel)
    mask = tg._fence_mask(lines)
    req = next((r for r in tg.parse_spec("\n".join(lines)).requirements if r.name == name), None)
    forms: dict[int, set[str]] = {}
    if req:
        for _, line in tg._requirement_body(lines, mask, req.line):
            for ref in refparse.refs(line):
                forms.setdefault(ref[0], set()).add(refparse.form(ref))
    return forms


def short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 90 else text[:89] + "…"


def verdict(ref, forms: dict[int, set[str]]) -> str:
    n, letter, j = ref
    if j is not None and j != change:
        return "A: ссылка с чужим именем журнала — связи и сигнала не даёт"
    key = refparse.form((n, letter, None))
    if key in forms.get(n, set()):
        return "A: голый против голого — отсекается, как сейчас"
    return "A: ключи разные — связь появится"


print(f"# Расклад {change}: дельта против базы снимка и мастера на коммите {json.loads((base_dir / 'graph' / 'req-graph.json').read_text(encoding='utf-8-sig'))['roots'][0]['commit'][:7]}")
print(f"# Строк «требование без записи» в graph/report.md: {len(signalled)}")
for spec in sorted((base_dir / "specs").glob("*/spec.md")):
    cap = spec.parent.name
    text = tg._read_text(base_dir, f"specs/{cap}/spec.md")
    parsed = tg.parse_spec(text)
    lines = tg._spec_lines(text)
    mask = tg._fence_mask(lines)
    names = {r.name: r for r in parsed.requirements}
    for req in parsed.requirements:
        body = tg._requirement_body(lines, mask, req.line)
        refs = [(n, r) for n, line in body for r in refparse.refs(line)]
        parent_line = next((line for _, line in body if tg._PARENT.match(line)), None)
        if req.section == "MODIFIED":
            entry = base.get(cap, {}).get(req.name)
            source = "база снимка" if entry else "в базе нет — живой мастер"
            entry = entry or tg.master_base(root, cap).get(req.name)
            forms = master_forms(cap, req.name)
            role = "MODIFIED"
        elif req.section == "ADDED" and parent_line:
            m = tg._PARENT.match(parent_line)
            pcap = m.group(1) or cap
            pname, _, _ = tg._take_name(parent_line, m.end(), set(names) | set(tg.master_base(root, pcap)))
            parent = names.get(pname) if pcap == cap else None
            if parent is not None and parent.section != "MODIFIED":
                entry, source = None, f"родитель «{pname}» — {parent.section} этого изменения, отсечения нет"
            else:
                entry = base.get(pcap, {}).get(pname) or tg.master_base(root, pcap).get(pname)
                source = f"родитель `{pcap}`: «{pname}» ({'база снимка' if base.get(pcap, {}).get(pname) else 'живой мастер'})"
            forms = master_forms(pcap, pname)
            role = "дочернее ADDED"
        else:
            continue
        hit = any(f"{cap}/{req.name} — " in s for s in signalled)
        print()
        print(f"## {cap}/{req.name} [{role}] — specs/{cap}/spec.md:{req.line}; сигнал «требование без записи»: {'ДА' if hit else 'нет'}")
        print(f"ссылки дельты: {', '.join(f'{refparse.form(r)} (стр. {n})' for n, r in refs) or '—'}")
        numbers = sorted(entry["numbers"]) if entry else []
        print(f"числа отсечения ({source}): {numbers}")
        if not refs:
            print("совпадений нет: ссылок в теле нет")
            continue
        for n, r in refs:
            if r[0] in numbers:
                print(f"  совпадение {refparse.form(r)} (стр. {n}): в мастере {sorted(forms.get(r[0], set())) or '—'}; "
                      f"своя запись F-{r[0]:02d}: «{short(questions.get(r[0], '— нет в журнале'))}»; {verdict(r, forms)}")
        rest = [refparse.form(r) for _, r in refs if r[0] not in numbers]
        print(f"  без совпадения (связь или «неизвестный номер» уже сейчас): {', '.join(rest) or '—'}")
