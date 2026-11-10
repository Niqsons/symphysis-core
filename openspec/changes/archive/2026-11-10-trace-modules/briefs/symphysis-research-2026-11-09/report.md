# Итог

жанр: устройство
находок 28
строк «не найдено» 3
проба да

## Файлы

- `openspec/changes/trace-modules/research/F-26.md`
- `openspec/changes/trace-modules/research/F-26-probe/probe.py`
- `openspec/changes/trace-modules/research/F-26-probe/write_report.py`
- `openspec/changes/trace-modules/research/F-26-probe/results.json`
- `openspec/changes/trace-modules/research/F-26-probe/summary.txt`
- `openspec/changes/trace-modules/research/F-26-probe/searches.txt`
- `openspec/changes/trace-modules/research/F-26-probe/verification.json`
- `openspec/changes/trace-modules/research/F-26-probe/results-first-run.json`
- `openspec/changes/trace-modules/research/F-26-probe/summary-first-run.txt`

## Вопросы человеку

- Какой контракт переносит логическое имя объявленного repo в локальный корень исследования: корни улик уже работают, `repos:` из старого разбора текущим читателем не принят? Источники: stores-and-context-pack, settings, roots; конструкция здесь не выбрана.
- Кто и каким способом дописывает расширение в существующий metadata, сохраняя сырые неизвестные ключи, если публичный writer их удаляет? Источники: change-metadata.ts и metadata-helper пробы.
- Как фиксируется результат анализа README при произвольной глубине и при отсутствии Git, учитывая, что текущий гейт ядра решает другую задачу? Источник: tests/repository_structure.py и module-detection пробы.
- Какой вход получает анализатор исходников, если planning root — store и затронуты несколько repo, а OpenSpec сам задачи по repo не маршрутизирует? Источник: agent-contract.md; момент анализа здесь не назначен.
- Области нет: нет; все inputs существуют.

## Сигналы

- Первый запуск пробы: exit 1; причина — `symphysis.yaml: нет пакета PyYAML — выполнить: python -m pip install pyyaml`. След сохранён. Повторный запуск: exit 0, с явно ограниченной проверкой `_apply` вместо успешного YAML-чтения.
- Ожидаемые отрицательные исходы: повторный new exit 1; module detector вне Git exit 128.
- Строк `[!!]` вызванные пробы не печатали. Критериев приёмки, оставшихся невыполненными в шагах 4–8, нет; все цитаты повторно сверены по строке.

## Не сделано

- Не назначены момент анализа, формат данных модулей и способ разрешения объявленного repo. Журнал, intent, specs и продуктовый код не менялись; коммиты не делались.
- Не читались личные symphysis.yaml, journal-roots.json и запрещённый список. Нет сети, установки, общей сборки и правок форка.
- Не проверены новый build, чужие схемы/hooks archive, реальные приватные repo, отсутствие Git executable и поведение модели; это пределы доказанного результата.
