"""Проба F-21, пункт 1: счёт ссылок на записи в теле требований мастер-спек `openspec/specs/*/spec.md`.
Тело требования — как у `master_base` (`_requirement_body`: до следующего заголовка, без блоков кода и HTML-комментариев),
то есть ровно тот текст, из которого граф берёт `numbers` для отсечения `known`; преамбула capability и сценарии не считаются.
Вызов: python -X utf8 count-refs.py <корень проекта> <каталог инструментов пробы>."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import refparse  # noqa: E402

root, tools = Path(sys.argv[1]), Path(sys.argv[2])
tg = refparse.load_trace_graph(tools)

rows, named_places, both_places, all_places = [], [], [], []
total = dict(reqs=0, refs=0, bare=0, bare_letter=0, named=0, both=0, reqs_with_refs=0)
for spec in sorted((root / "openspec" / "specs").glob("*/spec.md")):
    cap = spec.parent.name
    rel = f"openspec/specs/{cap}/spec.md"
    lines = tg._master_lines(root, rel)
    mask = tg._fence_mask(lines)
    reqs = tg.parse_spec("\n".join(lines)).requirements
    row = dict(cap=cap, reqs=0, refs=0, bare=0, bare_letter=0, named=0, both=0, reqs_with_refs=0)
    for req in reqs:
        row["reqs"] += 1
        bare, named = {}, {}
        for number, line in tg._requirement_body(lines, mask, req.line):
            found = refparse.refs(line)
            if not found:
                continue
            b = [r for r in found if r[2] is None]
            n = [r for r in found if r[2] is not None]
            all_places.append(f"{rel}:{number} голые: {', '.join(refparse.form(r) for r in b) or '—'} | с именем: "
                              f"{', '.join(refparse.form(r) for r in n) or '—'}")
            for r in b:
                bare.setdefault(r[0], set()).add(refparse.form(r))
            for r in n:
                named.setdefault(r[0], set()).add(refparse.form(r))
                named_places.append(f"{rel}:{number} {refparse.form(r)}")
            row["refs"] += len(found)
            row["bare"] += len(b)
            row["bare_letter"] += sum(1 for r in b if r[1])
            row["named"] += len(n)
        if bare or named:
            row["reqs_with_refs"] += 1
        same = sorted(set(bare) & set(named))
        if same:
            row["both"] += 1
            both_places.append(f"{rel}:{req.line} «{req.name}»: " + "; ".join(
                f"F-{k:02d} голым {sorted(bare[k])} и с именем {sorted(named[k])}" for k in same))
    rows.append(row)
    for key in total:
        total[key] += row[key]

print("# Счёт ссылок на записи в теле требований openspec/specs/*/spec.md (рабочая копия, HEAD ветки feat/trace-numbers-signals)")
print("# Разбор — refparse.py: голая = без метки ``журнал `имя`:`` перед списком; «с буквой» — подмножество голых вида F-NN.X")
print()
print("capability | требований | с ссылками | ссылок | голых | из них с буквой | с именем журнала | требований с одним числом голым и с именем")
for r in rows:
    print(f"{r['cap']} | {r['reqs']} | {r['reqs_with_refs']} | {r['refs']} | {r['bare']} | {r['bare_letter']} | {r['named']} | {r['both']}")
print(f"ИТОГО | {total['reqs']} | {total['reqs_with_refs']} | {total['refs']} | {total['bare']} | {total['bare_letter']} | {total['named']} | {total['both']}")
print()
print(f"## Ссылки с именем журнала перед списком: {len(named_places)}")
for p in named_places:
    print(p)
print()
print(f"## Требования, где одно число стоит и голым, и с именем журнала: {len(both_places)}")
for p in both_places:
    print(p)
print()
print(f"## Все строки тел требований со ссылками: {len(all_places)}")
for p in all_places:
    print(p)
