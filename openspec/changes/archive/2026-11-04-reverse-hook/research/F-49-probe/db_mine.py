# Только чтение общей базы opencode: сессии, чей каталог лежит во временном каталоге пробы. Записи не меняются.
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
mark = sys.argv[1]
p = os.path.expanduser("~/.local/share/opencode/opencode.db").replace("\\", "/")
c = sqlite3.connect(f"file:///{p}?mode=ro", uri=True)
mine = [r[0] for r in c.execute("select id from session_v2 where directory like ?", (f"%{mark}%",))]
print("ids:" + " ".join(mine))
for t in ("session_v2", "project", "project_directory"):
    print(t, c.execute(f"select count(*) from {t}").fetchone()[0])
print("suspended", c.execute("select count(*) from session_v2 where time_suspended is not null").fetchone()[0])
print("project_mine", c.execute("select count(*) from project where worktree like ?", (f"%{mark}%",)).fetchone()[0] if any(r[1] == "worktree" for r in c.execute("pragma table_info(project)")) else "нет поля worktree")
