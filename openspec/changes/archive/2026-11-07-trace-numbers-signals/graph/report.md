# Отчёт по изменению trace-numbers-signals

## Находки openspec validate

[!!] openspec validate: INFO record-anchors/spec.md: Archive would refuse this delta: record-anchors ADDED failed for header "### Requirement: Ссылка на запись несёт якорь изменения" - already exists
[!!] openspec validate: INFO trace-conventions/spec.md: Archive would refuse this delta: trace-conventions ADDED failed for header "### Requirement: Ссылка с именем другого изменения не ссылка этого журнала" - already exists
[!!] openspec validate: INFO trace-signals/spec.md: Archive would refuse this delta: trace-signals ADDED failed for header "### Requirement: Группы тяжести сигналов" - already exists

## Сигналы графа

### Опоры нет (2)

[!!] решение без требования и задачи: F-23.A Хеши у всех узлов графа: решение здесь, а реализация — здесь или в B-08? — decisions.json:984
[!!] решение без требования и задачи: F-38.A MODIFIED без следа стирает в мастере прежний след проб заменённого блока (так было дважды: −8 и −21 строк). С… — decisions.json:2059

## Расхождения сценариев MODIFIED

[!!] сценарий MODIFIED с прежним именем и другим текстом: trace-conventions/Требование называет свои записи журнала/Требование из решения — specs/trace-conventions/spec.md:8
[!!] сценарий MODIFIED с прежним именем и другим текстом: trace-conventions/Требование называет свои записи журнала/След пробы не заменяет номер в тексте — specs/trace-conventions/spec.md:19

Служебных задач: 8 (1.5, 2.3, 3.2, 5.1, 5.7, 7.1, 7.2, 7.3).

## Корни без коммита

Корень `playground/` вне git или без каталога: коммит не записан.
Корень `md4h/` вне git или без каталога: коммит не записан.
Корень `calibration/` вне git или без каталога: коммит не записан.
Корень `archive/` вне git или без каталога: коммит не записан.
