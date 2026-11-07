"""Проба F-21, шаг 8 скилла: сверка цитат research/F-21.md. Каждая строка «- `путь:строка` «цитата»» открывается на названной
строке; цитата должна стоять в ней дословно (подстрокой). Путь `research/…` — от каталога изменения, прочие — от корня
проекта; пометка «(на коммите `X`)» — строка берётся из `git show X:путь`. Вызов: python -X utf8 -B check-quotes.py <корень> <файл>."""
import re
import subprocess
import sys
from pathlib import Path

root, md = Path(sys.argv[1]), Path(sys.argv[2])
change_dir = md.parent.parent
pattern = re.compile(r"^- `([^`]+):(\d+)`(?: \(на коммите `([^`]+)`\))? «(.*?)»(?::| )")
ok = bad = 0
for line in md.read_text(encoding="utf-8").splitlines():
    m = pattern.match(line)
    if not m:
        continue
    path, number, commit, quote = m.group(1), int(m.group(2)), m.group(3), m.group(4)
    if commit:
        text = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{path}"], capture_output=True, encoding="utf-8").stdout
    else:
        file = (change_dir / path) if path.startswith("research/") else (root / path)
        text = file.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    hit = number <= len(lines) and quote in lines[number - 1]
    ok += hit
    bad += not hit
    if not hit:
        print(f"РАСХОЖДЕНИЕ {path}:{number}{' @' + commit if commit else ''}: «{quote[:80]}»")
print(f"цитат сверено: {ok + bad}, совпали: {ok}, разошлись: {bad}")
