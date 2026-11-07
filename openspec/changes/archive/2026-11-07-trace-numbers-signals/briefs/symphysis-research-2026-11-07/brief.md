---
skill: symphysis-research
artifact: research
change: trace-numbers-signals
question: F-21
inputs:
  - trace/trace_graph.py
  - trace/tests/test_trace_graph.py
  - openspec/specs/
  - openspec/changes/archive/2026-11-07-module-structure/
  - openspec/changes/archive/2026-11-06-trace-graph/
  - openspec/changes/archive/2026-11-03-step-help/
  - openspec/changes/trace-numbers-signals/intent.md
report: openspec/changes/trace-numbers-signals/briefs/symphysis-research-2026-11-07/report.md
---

Исполнить шаги 4–8 скилла `symphysis-research` по одной парковке.

Запись: `Как граф отличает номер своего журнала от номера мастер-текста при одном числе — у MODIFIED (`known`) и у дочернего ADDED (`cut`)?`

Слово человека: `«Прогнать сборку графа с правилом A на архивных изменениях `module-structure`, `trace-graph`, `step-help` (`trace_graph.py build` из архива, база — их `graph/req-graph.json`) и сравнить связи `traces` и сигналы «требование без записи» со снимками: какие связи появятся, какие пропадут, есть ли ложные. Посчитать по `openspec/specs/*/spec.md`, сколько голых номеров прежних изменений стоит в требованиях и сколько ссылок с именем журнала перед списком: насколько велика оставшаяся дыра голый-против-голого.»`

Правило A, которое человек выбрал (для пробы, не для выбора): ключ отсечения — номер с буквой варианта и с именем журнала, если оно стоит перед списком (``журнал `x`: F-23.A, F-45.E``); ссылка с чужим именем журнала не ссылка этого журнала ни в мастере, ни в дельте — связи и сигнала «неизвестный номер» не даёт; голый номер мастера против голого своего отсекается, как сейчас. Сегодняшний разбор — `_record_numbers` и `_REC_REF` в `trace/trace_graph.py` (буква варианта отбрасывается, имя журнала не читается), отсечение — `known` у MODIFIED из `entry["numbers"]` базы и `cut` у дочернего ADDED.

Выяснить:
1. Сколько ссылок на записи в мастер-спеках `openspec/specs/*/spec.md` стоят голым числом (`F-NN` или `F-NN.X` без имени журнала перед списком) и сколько с именем журнала (``журнал `имя`: F-NN, …``), по capability и всего; в скольких требованиях одно и то же число стоит и голым, и с именем чужого журнала (как `(F-26)` и `F-26.B` в `decision-viewer`). Счёт — пробой: скрипт во временном каталоге, след — файл со счётом и перечнем мест `путь:строка`.
2. По снимкам `graph/req-graph.json` и отчётам `graph/report.md` архивных изменений `module-structure` и `trace-graph`: какие требования MODIFIED и дочерние ADDED получили строку «требование без записи»; у каких из них в базе снимка (`base`) стоят числа, совпадающие с номером собственного журнала в тексте дельты `specs/<cap>/spec.md`; какие из этих совпадений в мастере на момент заморозки (`git show <roots[].commit>:openspec/specs/<cap>/spec.md`, коммит из снимка) стояли с именем чужого журнала или с буквой варианта, а какие голым числом. Это расклад «что закроет правило A, что останется».
3. Проба правила A: на временной копии `trace/trace_graph.py` вне проекта разбор ссылок учитывает букву варианта и имя журнала перед списком, `known` и `cut` сравнивают полные ссылки; сборка `build` для `module-structure` и `trace-graph` во временном корне (копия `openspec/specs` на коммите снимка, каталог изменения под `openspec/changes/<имя>`, база из их `req-graph.json`, файл корней рядом); сравнить связи `traces` от требований и строки «требование без записи» с сохранённым снимком и отчётом: какие связи появились, какие пропали, есть ли ложные (связь к записи своего журнала по номеру, который в дельте стоял как чужой). Вывод сборки и отчёта до и после — файлами следа.
4. `step-help` (архив 2026-11-03) снимка `graph/` не имеет: есть ли в его дельтах MODIFIED с номерами и что могло бы заменить базу; если для пункта 3 он непригоден — так и записать с причиной.

Область: `trace/trace_graph.py`, `trace/tests/test_trace_graph.py`, `openspec/specs/`, `openspec/changes/archive/2026-11-07-module-structure/`, `openspec/changes/archive/2026-11-06-trace-graph/`, `openspec/changes/archive/2026-11-03-step-help/`, `openspec/changes/trace-numbers-signals/intent.md`; история git файлов `openspec/specs/` и архива (`git log`, `git show`) — в область входит.

Жанр: `проверка`

Среда: корень проекта — `X:\symphysis-trace-numbers-signals` (worktree ветки `feat/trace-numbers-signals`); git — через `git -C X:\symphysis-trace-numbers-signals`. Установленные скрипты — `.symphysis/tools/`, исходник графа — `trace/trace_graph.py`; Python — `python -X utf8`. Шаблон `research.md` — поле `template` вывода `openspec instructions research --change trace-numbers-signals --json`. Временный каталог пробы — вне проекта (`%TEMP%`), в проект проба не пишет ничего, кроме `research/`.

Писать: `openspec/changes/trace-numbers-signals/research/F-21.md`, `openspec/changes/trace-numbers-signals/research/F-21-probe/`

Не делать: `decisions.json`, `specs/`, код проекта (в том числе `trace/trace_graph.py`: патч только на временной копии вне проекта), вопросы человеку, чтение вне области, выбор варианта.
