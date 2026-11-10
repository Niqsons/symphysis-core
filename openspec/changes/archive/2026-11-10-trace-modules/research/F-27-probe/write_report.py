"""Generate the research with exact current source lines; verify every quotation."""
from pathlib import Path
import re

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "trace/trace_graph.py").is_file())
CHANGE = Path("openspec/changes/trace-modules")
BRIEF = CHANGE / "briefs/symphysis-research-2026-11-09-2/brief.md"
RESULT = CHANGE / "research/F-27-probe/results.txt"
brief = (ROOT / BRIEF).read_text(encoding="utf-8").split("---", 2)[2].strip()
findings = []


def quote(path, number, explanation):
    line = (ROOT / path).read_text(encoding="utf-8").splitlines()[number - 1]
    assert line
    findings.append((str(path), number, line))
    return f"- `{str(path).replace(chr(92), '/') }:{number}` «{line}»: {explanation}\n"


def result(label, explanation):
    lines = (ROOT / RESULT).read_text(encoding="utf-8").splitlines()
    index = next(i for i, line in enumerate(lines, 1) if line.startswith(label + ":"))
    return quote(RESULT, index, explanation)


body = "---\ngenre: устройство\nquestion: F-27\nbrief: |\n" + "\n".join("  " + line for line in brief.splitlines()) + "\n---\n\n"
body += "# F-27 · Какие потребители формата графа, правила снимка и списки установки затронет новая структурная ось?\n\n## Найдено\n\n"
body += "### 1. Потребители JSON и видов узлов\n\nВ разрешённой области постоянный JSON графа читают `saved_base` (база мастера), `check_graph_file` (форма, хеши, сравнение со свежей сборкой), `freeze_change` (проверка и обновление roots) в `trace/trace_graph.py`. `build_graph`/`_build_all`, `_resolve_claims`, `record_candidates`, `graph_signals`, `build_report`, `service_tasks` и экспорт работают с графом в памяти; `archive_gaps` проверяет наличие снимка, его содержимое не разбирает. `graph_signals` проверяет существующую поведенческую ось, обходами `req`, `scn`, `task`; отдельной структурной проверки сейчас нет. JSON из `build` также служит входом тестов.\n\n"
body += quote("trace/trace_graph.py", 352, "единственная объявленная версия текущего сборщика — 2; прежний формат 1 сознательно отвергается проверкой.")
body += quote("trace/trace_graph.py", 1066, "shape-проверка сверяет номер формата, но не запрещает добавочные верхние поля и не валидирует словарь kind; она проверяет типы пяти контейнеров и элементы sources.")
body += quote("trace/tests/test_trace_graph.py", 529, "тест закрепляет семь нынешних видов; соседние точные проверки состава полей стоят на строках 593 и 895, точный набор полей снимка — в trace/tests/test_trace_snapshot.py:80. Входные фикстуры находятся в tests/fixtures/trace (plain, fenced, removed-renamed, odd-headers), большинство сценариев графа строится make_change на временных данных.")
body += quote("trace/trace_graph.py", 1227, "фильтры capability и requirement присоединяют только эти четыре вида соседей. Для requirement ядро — req и scn, кандидаты присоединяют соседние req; для capability ядро берётся по capability. Структурный узел без такого поля в отбор не попадёт.")
body += quote("trace/trace_graph.py", 1272, "тип связи должен присутствовать в DIAGRAM[связи]; виды имеют такой же закрытый lookup в diagram_ident и _render. Это точки изменения именно текстового requirementDiagram. HTML-рендер новой оси здесь не реализуется.")
body += result("compatibility_summary", "на искусственном расширении format 2: добавочное верхнее поле проходит check и сохраняется при freeze; новый kind проходит shape, но check считает его и его ребро лишними, полный экспорт падает KeyError: module, оба фильтра узел исключают. Новое имя ребра отдельно падает KeyError: implements. Поэтому одинаковое число format само по себе совместимость расширенной семантики не доказывает; выбор новой версии или переговоров о возможностях этой пробой не сделан.")
body += "\n### 2. Что сохраняет снимок и чего он сейчас не замечает\n\n"
body += quote("trace/trace_graph.py", 1057, "sources — отсортированные относительные пути файлов артефактов внутри изменения и SHA-256 после нормализации переводов строк; исходники модулей, README и внешний код туда не включены. SOURCE_FILES перечисляет decisions/consequences/security/tasks, specs читаются отдельно; intent в REGISTRY имеет берёт: ничего.")
body += quote("trace/trace_graph.py", 515, "base — сведения о мастер-требовании (номера-якоря, хеши сценариев, текста и следов), а не копия исходников или структура модулей. _freeze_base сохраняет только MODIFIED, прежняя база не обновляется после sync; при отсутствии годной записи _Master читает живой мастер. При freeze без прежней базы уже синхронизированный целиком блок не становится базой.")
body += quote("trace/trace_graph.py", 1751, "roots хранит только префикс и HEAD. Абсолютный путь карты не переносится в JSON; root_commit не читает статус/dirty или содержимое файлов и требует именно корень git-дерева. Несуществующий клон даёт пустой commit, а не отказ.")
body += quote("trace/trace_graph.py", 1831, "при перестройке снимок объединяет граф, roots и base и обезличивает абсолютные пути. Ветка свежего снимка выше, 1825–1829, меняет только roots; check сравнивает sources и свежую сборку, коммиты корней он не проверяет.")
body += result("snapshot_bounds_summary", "временный модуль на глубине src/module-a: правка имени/рода в README после freeze и переезд каталога дают check=[] и action=commits, узлы неизменны; после README неизменен также report. Внешний отсутствующий клон не мешает freeze, пустой commit и префикс отмечены в отчёте. Проба не доказывает сохранение структурной оси — существующий сборщик её не видит.")
body += result("archive_compatibility_summary", "прочитаны девять настоящих снимков без записи: три format 1 и шесть format 2 (полный перечень в archive_formats следа). На копиях текущий читатель принимает форму format 2 и извлекает его base; format 1 разбирается как JSON, но проверка отвергает номер, saved_base возвращает пусто. Только временный format 1 пересобран freeze в 2. Следовательно, прежний поддерживаемый после будущего расширения формат здесь — нынешний 2; сохранённый 1 уже сейчас не является поддерживаемым форматом checker/base.")
body += "\nПредел воспроизводимости: сейчас можно восстановить поведенческие узлы по артефактам изменения и сохранённой базе, а hashes обнаружат изменение этих артефактов; сами bytes sources не хранятся. По текущим roots нельзя восстановить незакоммиченный README, снимок файлов/принадлежности, перемещение каталога или содержимое недоступного внешнего клона. Для воспроизведения структурной оси существенны именно прочитанные объявления README, размещение/идентичность модулей и файлов, источники и происхождение связей реализации/зависимостей, состояние доступности внешних источников и версия правил чтения. Это перечень выявленных потерь данных, не выбор формата хранения. Нынешний base этих сведений не несёт.\n\n"
body += "### 3. Упаковка, установленная копия и стенды\n\nДля нового runtime-файла в существующем модуле затрагиваются три независимых списка: включение исходника в payload, фильтр установки плоских tools, проверка установленного файла. Для нового верхнего модуля дополнительно значим список модулей тестового клона. Входное объявление клиента пока не определено, поэтому его конкретная проводка установкой из текущего кода не выводится. README собственной разработки в установленную плоскую tools-раскладку как модульное объявление не переносится.\n\n"
body += quote("installer/scripts/sync-payload.js", 45, "TOOLS_FILES перечисляет исходники явно, toolsFiles превращает их в tools/<basename>; новый Python рядом с trace_graph автоматически не попадёт в payload. Дубликаты basename проверяет uniqueNames. Отдельные ресурсы перечисляет FILES.")
body += quote("installer/lib/install.js", 179, "установка пропускает только разрешённые basename; одного добавления в payload недостаточно. Это чтение исходника, install не запускался.")
body += quote("installer/lib/check.js", 13, "TOOL_MODULES определяет наличие модулей установленной копии, включая trace_graph и openspec_run; новый обязательный runtime должен проверяться отдельно от работоспособности импортов.")
body += quote("installer/test/payload.test.js", 28, "FILES закрепляет ожидаемый trace_graph в payload; дополняющие проверки находятся в installer/test/install.test.js:128 и installer/test/check.test.js:184 (поставка и удалённые обязательные инструменты), а общий модульный набор check.test.js:171 перечисляет соседние модули.")
body += quote("installer/test-support/clone.js", 14, "SOURCE_MODULES — фиксированный набор каталогов образца клона; makeClone копирует их, схему и Mermaid, не произвольный новый модуль. В tests/test_flag_help.py:43 также закреплён набор исполняемых Python с CLI.")
body += quote("installer/test/layout-filter.test.js", 99, "стенд установленной плоской копии проверяет --help точек входа, остальные поставленные .py импортирует. Новый библиотечный файл не обязан быть CLI, но должен присутствовать и импортироваться. Формат структуры исходников отдельно закрепляют tests/test_repository_structure.py; это тесты самого symphysis, не доказательство поддержки любой глубины модулей клиентским сборщиком.")
body += "\n### 4. Настоящее требование для минимального dogfood\n\nОбнаружен проверяемый фрагмент настоящего требования `decision-viewer/Файлы на странице показаны ссылками`, который реализуют как минимум два модуля ядра: roots строит относительные адреса существующих файлов, viewer встраивает карту в страницу. Такая связь обоснована кодом функций и исполнением, а не тем, что файл встретился уликой в журнале. Графовой связи реализации существующий код от этого не создаёт.\n\n"
body += quote("openspec/specs/decision-viewer/spec.md", 123, "настоящее требование содержит одновременно сбор карты, границы корней, относительные пути и показ ссылок; это шире исследованного фрагмента.")
body += quote("roots/roots.py", 157, "контракт file_links охватывает пути улик, справку и текст backticks, существующий файл внутри корней или каталога изменения. _relative_link проверяет существование и делает os.path.relpath.")
body += quote("viewer/viewer_render.py", 110, "render_html сериализует переданную карту в обязательную метку шаблона; значение не вычисляется из упоминания README.")
body += quote("README.md", 18, "корневое описание объявляет roots модулем ядра; viewer также объявлен там отдельным модулем.")
body += quote("viewer/README.md", 2, "README viewer несёт явное имя; kind: доменный следует на строке 3. Это существующая декларация модуля, а не созданная для пробы.")
body += result("real_requirement_partial_dogfood", "проба исполняет реальные file_links и render_html на локальном файле и файле фикстурного внешнего репозитория: два относительных адреса встроены, абсолютных путей нет; после исчезновения внешнего каталога его ссылка исчезает. Шаблон синтетический из пяти обязательных меток. Это воспроизводимый минимальный фрагмент одного требования через два модуля; полный показ ссылки, выбор редактора, CLI и DOM не проверены. Соседний плагин не читался.")
body += "\n## Не найдено\n\n- не найдено: читатель JSON req graph в разрешённых decisions/journal_model.py, viewer/viewer_render.py и consequences/journal_sites.py. Их собственные kind относятся к журналу, а scheme_payload viewer — к scheme.md.\n  искал: `req-graph|trace_graph|requirementDiagram` в `decisions/journal_model.py`, `viewer/viewer_render.py`, `consequences/journal_sites.py`\n- не найдено: реализованное чтение README или структурных module/component/repository в нынешнем сборщике графа.\n  искал: `README|module|repository|component|structural` в `trace/trace_graph.py`\n- не найдено: контракт JSON req graph или requirementDiagram с соседним плагином в разрешённом контракте. Это не утверждение об отсутствии потребителей в соседнем репозитории.\n  искал: `req-graph|trace_graph|requirementDiagram` в `docs/repo-contract.md`; `FORMAT|format|graph|trace` в `docs/repo-contract.md`\n\n## Проба\n\n- Условия: `python -I -X utf8 openspec/changes/trace-modules/research/F-27-probe/run_probe.py`, код 0. Все изменения фикстур — в автоматически удаляемом TemporaryDirectory. Исходники импортируются без записи bytecode; корни передаются явно из временной обезличенной карты. Настройки и личные карты не читаются. `validate_findings` на время процесса заменён на `[]`: проверяется граф/freeze, настоящий OpenSpec validate не вызывается, его поведение и получение контекста моделью этой пробой не утверждаются.\n- След: `research/F-27-probe/run_probe.py`, `research/F-27-probe/results.txt`. Перезапуск создаёт след заново; реальные архивы только читаются.\n- Проверка цитат: `python -I -X utf8 openspec/changes/trace-modules/research/F-27-probe/write_report.py`; все 24 строки находок извлечены из прочитанных файлов и сверены с ними при генерации.\n- `[!!]` ожидаемые искусственные сигналы сохранены в results.txt: лишний module:demo, лишнее ребро implements и формат 1 против 2. KeyError пойманы для фиксации несовместимости, это не ошибки самого запуска пробы.\n\n## Вопросы, которые открылись\n\n- Какие реальные потребители и фиксированные списки инструментов есть в `X:/symphysis-vscode/test/core-files.mjs` и соответствующих файлах `X:/symphysis-giga/`, `X:/symphysis-opencode/`? Эти репозитории вне inputs, не читались; нынешний docs/repo-contract.md не даёт контракта графа.\n- Какие стенды копий потребуется обновить в `decisions/tests/test_journal_check.py`, `viewer/tests/test_viewer_page.py`, `settings/tests/test_settings.py`, `step-help/tests/test_step_help.py`? Это указатели из операционной памяти о списках, не проверенные находки; каталоги вне inputs не читались.\n- Каков фактический сквозной вызов `roots.file_links` → `viewer.render_html` в `cli/journal_cli.py` и показ ссылки в `viewer/playground-template.html`? Эти файлы вне inputs. Проба проверила два звена, но не всю реализацию требования и не браузер.\n- Какая идентичность структурных узлов и набор исходных данных должны пережить dirty README, перенос модуля и отсутствие внешнего клона? Источник вопроса — snapshot_bounds_summary; нынешние roots/sources/base этих различий не сохраняют. Решение здесь не принято.\n"
assert len(findings) == 24
for path, number, line in findings:
    assert (ROOT / path).read_text(encoding="utf-8").splitlines()[number - 1] == line
assert body.count("- не найдено:") == 3
(ROOT / CHANGE / "research/F-27.md").write_text(body, encoding="utf-8", newline="\n")
signals = "\n".join("- `" + line + "`" for line in (ROOT / RESULT).read_text(encoding="utf-8").splitlines() if "[!!]" in line)
report = f"""# F-27 · Отчёт водителя

## Итог

жанр: устройство
находок: 24
строк «не найдено»: 3
проба: да

## Файлы

- `openspec/changes/trace-modules/research/F-27.md`
- `openspec/changes/trace-modules/research/F-27-probe/run_probe.py`
- `openspec/changes/trace-modules/research/F-27-probe/results.txt`
- `openspec/changes/trace-modules/research/F-27-probe/write_report.py`

## Вопросы человеку

- Фактические потребители и списки поставки плагинов: `X:/symphysis-vscode/test/core-files.mjs`, соответствующие файлы GIGA/OpenCode — вне inputs.
- Стенды модульных тестов: `decisions/tests/test_journal_check.py`, `viewer/tests/test_viewer_page.py`, `settings/tests/test_settings.py`, `step-help/tests/test_step_help.py` — вне inputs, указатели не проверены.
- Полная проводка dogfood: `cli/journal_cli.py`, `viewer/playground-template.html` — вне inputs.
- Какие данные и идентичность сохранять при dirty README, перемещении и пропаже внешнего клона — открытая проектная развилка после пробы, здесь не решена.
- Отсутствующих inputs нет.

## Сигналы

Проба закончилась кодом 0. Ожидаемые сигналы искусственно испорченного снимка дословно в обезличенном следе:

{signals}

Критериев шагов 4–8, не выполненных в пределах brief, не выявлено. Чужие файлы, журнал и продуктовый код не правились. Файл отчёта в briefs разрешён самим brief.

## Не сделано

Не запускались install, prepare, sync-payload, сборка форка, общий pytest или настоящий OpenSpec validate. Проба подменяет только validate_findings в памяти; это не полная интеграционная проверка freeze с форком. Реальные архивы не переписывались. Полный CLI/DOM dogfood и соседние плагины не проверены. Проектные решения, новый формат/синтаксис объявлений и связи реализации в JSON не созданы; журнал не менялся, коммитов нет.
"""
(ROOT / BRIEF.parent / "report.md").write_text(report, encoding="utf-8", newline="\n")
print("quotes_verified=24; not_found=3; report_written=true")
