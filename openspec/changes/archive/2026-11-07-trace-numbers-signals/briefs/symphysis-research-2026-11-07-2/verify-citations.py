# Черновик водителя: сверка цитат research/F-24.md с файлами на названных строках и brief с brief.md.
import re
import sys
from pathlib import Path

ROOT = Path(r"X:\symphysis-trace-numbers-signals")
RESEARCH = ROOT / "openspec/changes/trace-numbers-signals/research/F-24.md"
BRIEF = ROOT / "openspec/changes/trace-numbers-signals/briefs/symphysis-research-2026-11-07-2/brief.md"

text = RESEARCH.read_text(encoding="utf-8")
cite = re.compile(r"^- `([^`]+):(\d+)` «(.*?)»: ", re.M)
bad, total = [], 0
cache = {}
for m in cite.finditer(text):
    path, line, quote = m.group(1), int(m.group(2)), m.group(3)
    total += 1
    f = ROOT / path
    if not f.is_file():
        bad.append((path, line, "файла нет"))
        continue
    if path not in cache:
        cache[path] = f.read_text(encoding="utf-8").split("\n")
    lines = cache[path]
    if line > len(lines):
        bad.append((path, line, "строки нет"))
        continue
    if quote not in lines[line - 1]:
        bad.append((path, line, "цитаты нет: " + lines[line - 1][:120]))
print("цитат:", total)
for b in bad:
    print("РАСХОЖДЕНИЕ:", b)

# brief frontmatter vs brief.md (всё под frontmatter brief)
brief_src = BRIEF.read_text(encoding="utf-8").split("\n")
end = [i for i, l in enumerate(brief_src) if l.strip() == "---"][1]
brief_body = brief_src[end + 1:]
while brief_body and brief_body[0] == "":
    brief_body.pop(0)
while brief_body and brief_body[-1] == "":
    brief_body.pop()
r = text.split("\n")
start = r.index("brief: |") + 1
stop = next(i for i in range(start, len(r)) if r[i] == "---")
block = [l[2:] if l.startswith("  ") else l for l in r[start:stop]]
while block and block[-1] == "":
    block.pop()
print("brief совпадает дословно:", block == brief_body)
if block != brief_body:
    for i, (a, b) in enumerate(zip(block, brief_body)):
        if a != b:
            print("первое расхождение, строка", i, repr(a[:80]), "|", repr(b[:80]))
            break
    print("длины:", len(block), len(brief_body))

# слова выбора вне цитат
stripped = cite.sub("", text)
for w in ("рекомендую", "выбрать вариант", "рекомендация —"):
    if w in stripped.lower():
        print("СЛОВО ВЫБОРА вне цитат:", w)
# счёт
print("строк «не найдено»:", len(re.findall(r"^- не найдено:", text, re.M)))
print("строк «искал:»:", len(re.findall(r"^  искал:", text, re.M)))
sys.exit(1 if bad else 0)
