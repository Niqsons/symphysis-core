# FileChanged пробы: код 2 и текст в stderr байтами UTF-8, как пишет настоящий hook.py.
import json, os, pathlib, sys, time

root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".")
log = os.environ.get("FC_PROBE_LOG") or str(root / "probe.log")
data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
with open(log, "a", encoding="utf-8") as f:
    f.write(f"{time.time():.1f} FileChanged event={data.get('event')} file={os.path.basename(data.get('file_path', ''))}\n")
text = ("Человек внёс решения кнопкой «Внести» в просмотрщике журнала: изменение demo. "
        "Ответ человека лежит в файле openspec/changes/demo/answers/2026-11-04.md. Открой этот файл.\n")
sys.stderr.buffer.write(text.encode("utf-8"))
sys.stderr.buffer.flush()
sys.exit(2)
