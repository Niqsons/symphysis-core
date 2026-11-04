# Ручная проба F-32 в интерактивном клиенте. Шаг 1: создаёт временный проект без хуков и печатает его путь.
# Аргумент: каталог, в котором создать проект. Не %TEMP%: в нём cd агента не держится, и шаг 9 ничего не покажет.
# Порядок и что было в claude -p (research/F-32-probe/run.txt):
#  1. py -3.13 interactive-setup.py <каталог>           запомни путь проекта
#  2. в этом каталоге запусти claude, прими доверие к каталогу, напиши «Привет», дождись ответа
#  3. из другого терминала: py -3.13 interactive-install.py <путь>     подожди 10 с
#  4. py -3.13 interactive-append.py <путь> deep        подожди 15 с. В -p агент сам хода не начал
#  5. py -3.13 interactive-append.py <путь> root        подожди 15 с. В -p тоже нет
#  6. напиши агенту «Ок», дождись ответа. В -p новый UserPromptSubmit сработал
#  7. снова deep и root с паузой 15 с. В -p ничего
#  8. напиши /compact, дождись конца; снова deep, подожди 15 с. В -p агент начал ход
#  9. попроси агента выполнить `cd .symphysis`; снова deep, подожди 15 с. В -p агент хода не начал
# 10. выйди из claude; py -3.13 interactive-show.py <путь> печатает, какие обработчики запускались и когда
# 11. удали каталог проекта и его запись в ~/.claude/projects (каталог с rhcc-probe-i в имени)
import pathlib, sys, tempfile

sys.stdout.reconfigure(encoding="utf-8")
project = pathlib.Path(tempfile.mkdtemp(prefix="rhcc-probe-i-", dir=sys.argv[1]))
(project / ".symphysis" / "viewer").mkdir(parents=True)
(project / ".symphysis" / "viewer" / "events.jsonl").write_text("", encoding="utf-8")
(project / "events.jsonl").write_text("", encoding="utf-8")
(project / ".claude").mkdir()
print(project.as_posix())
