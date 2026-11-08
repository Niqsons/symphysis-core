# Отчёт по изменению attack-lens-conventions

## Находки openspec validate

[!!] openspec validate: INFO artifact-attack/spec.md: Archive would refuse this delta: artifact-attack ADDED failed for header "### Requirement: Линза правил составления сверяет артефакт с правилами его шага" - already exists
[!!] openspec validate: INFO decision-viewer/spec.md: Archive would refuse this delta: decision-viewer ADDED failed for header "### Requirement: Списки линз режима «атака»" - already exists
[!!] openspec validate: INFO plugin-core-contract/spec.md: Archive would refuse this delta: plugin-core-contract ADDED failed for header "### Requirement: Новая линза поднимает номер контракта" - already exists

## Сигналы графа

Сигналов графа нет.

## Расхождения сценариев MODIFIED

[!!] сценарий MODIFIED с прежним именем и другим текстом: decision-viewer/Режим «атака» группирует строки по линзам и держит слуг вне списка отдельно/Текст записи у строки — specs/decision-viewer/spec.md:18
[!!] сценарий MODIFIED с прежним именем и другим текстом: decision-viewer/Режим «атака» группирует строки по линзам и держит слуг вне списка отдельно/Внесённое уходит из промпта — specs/decision-viewer/spec.md:23
[!!] сценарий MODIFIED с прежним именем и другим текстом: decision-viewer/Режим «атака» группирует строки по линзам и держит слуг вне списка отдельно/Спор становится словом — specs/decision-viewer/spec.md:28
[!!] сценарий MODIFIED с прежним именем и другим текстом: decision-viewer/Режим «атака» группирует строки по линзам и держит слуг вне списка отдельно/Ответ к записи без решения — specs/decision-viewer/spec.md:33
[!!] сценарий MODIFIED с прежним именем и другим текстом: decision-viewer/Режим «атака» группирует строки по линзам и держит слуг вне списка отдельно/Два ответа к одному решению — specs/decision-viewer/spec.md:38

Служебных задач: 8 (2.2, 3.2, 5.1, 5.2, 5.3, 6.2, 6.3, 6.4).

## Корни без коммита

Корень `playground/` вне git или без каталога: коммит не записан.
Корень `md4h/` вне git или без каталога: коммит не записан.
Корень `calibration/` вне git или без каталога: коммит не записан.
Корень `archive/` вне git или без каталога: коммит не записан.
