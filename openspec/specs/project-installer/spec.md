# project-installer Specification

## Purpose
Установщик `@niqsons/symphysis`: кладёт схему, скиллы и инструменты журнала в проект, сливает конфиг, сверяет установку и версию форка; гейт называет, не чинит; F-15, F-16.

## Requirements

### Requirement: `install` ставит схему, скиллы и инструменты в проект и сливает конфиг
Команда `symphysis install --project <dir> [--skills-dir <dir>]…` SHALL положить схему в `openspec/schemas/symphysis/`, скиллы в каждый `--skills-dir` (по умолчанию `.claude/skills`), инструменты в `.symphysis/` и создать или слить `openspec/config.yaml` (`schema` → `symphysis`, `rules` объединяются, прочее сохраняется); повторный запуск SHALL ничего не менять, отличающийся файл SHALL пропускаться с подсказкой `--force`, файл корней SHALL NOT перезаписываться (F-15.C, F-16.B).
<!-- проба краёв: форма=io, stateful, text, исходы: F-55 открыт, F-56 открыт, F-57 открыт -->
<!-- проба запретов: исходы: F-79 открыт; канон — F-83 → security.md -->

#### Scenario: Проект с конфигом другой схемы
- **GIVEN** `openspec/config.yaml` со `schema: spec-driven` и комментариями
- **WHEN** выполняется `install --project <dir>`
- **THEN** `schema: symphysis`, `rules` symphysis добавлены, комментарии на месте, stdout — «config.yaml уже был: схема переключена с spec-driven на symphysis, rules добавлены»

#### Scenario: Повторная установка
- **GIVEN** проект после успешного `install`
- **WHEN** `install` выполняется снова
- **THEN** список записанных файлов пуст, `journal-roots.json` не тронут (его правки пользователя сохранены)

#### Scenario: Блок context при слиянии
- **GIVEN** существующий `config.yaml` без `context`
- **WHEN** выполняется `install`
- **THEN** `context` из `config.symphysis.yaml` в `config.yaml` не появляется — предположение: наблюдение прогона (шаг 5 дневника), слияние переносит только `schema` и `rules`; решить: переносить ли `context` при слиянии

### Requirement: `check` называет расхождения и версию форка, не чинит
Команда `symphysis check --project <dir>` SHALL проверить версию форка против пина `1.15.0-symphysis.1`, байты схемы, `schema: symphysis`, `SKILL.md` в каталогах скиллов, инструменты и Python и прогнать `journal.py check` по каждому `openspec/changes/*/decisions.json`; расхождения — строки `[!!]`, код 2; сигналы сверки — `[..]` без влияния на код; `check` SHALL NOT ничего менять (F-15.A «ГЕЙТ НАЗЫВАЕТ, А НЕ ЧИНИТ», F-15.C).
<!-- проба краёв: форма=text, io, исходы: F-58 открыт, F-59 открыт -->
<!-- проба запретов: исходы: нет -->

#### Scenario: Ванильный OpenSpec вместо форка
- **GIVEN** `SYMPHYSIS_OPENSPEC` указывает на ванильный `openspec` 1.15.0
- **WHEN** выполняется `check`
- **THEN** строка `[!!] openspec: версия 1.15.0, нужна 1.15.0-symphysis.1 (форк symphysis): <источник>`, код 2

#### Scenario: Установка цела
- **GIVEN** проект после `install` и форк по пину
- **WHEN** выполняется `check`
- **THEN** stdout — `check: ok`, код 0; журналы изменений дают строки `[..] <путь>: [ok] улик сверено N из M`
