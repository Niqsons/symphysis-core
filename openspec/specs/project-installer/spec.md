# project-installer Specification

## Purpose
Установщик `@niqsons/symphysis`: кладёт схему, скиллы и инструменты журнала в проект, сливает конфиг, сверяет установку и версию форка; гейт называет, не чинит; F-15, F-16.

## Requirements

### Requirement: `install` ставит схему, скиллы и инструменты в проект и сливает конфиг
Команда `symphysis install --project <dir> [--skills-dir <dir>]…` SHALL положить схему в `openspec/schemas/symphysis/`, скиллы в каждый `--skills-dir` (по умолчанию `.claude/skills`), инструменты в `.symphysis/` и создать или слить `openspec/config.yaml` (`schema` → `symphysis`, `rules` объединяются, прочее сохраняется); повторный запуск SHALL ничего не менять, отличающийся файл SHALL пропускаться с подсказкой `--force` — при обновлении схемы каждый пропущенный файл схемы SHALL называться отдельной строкой, а `check` SHALL показывать расхождение байтов схемы как `[!!]`; файл корней SHALL NOT перезаписываться (F-15.C, F-16.B, F-50.E). Схема в payload SHALL нести артефакт `intent` и шаблон `intent.md`; вход изменения — `openspec/changes/<имя>/intent.md`; установщик SHALL NOT создавать и читать каталог `.gigacode/`; каталог инструментов SHALL оставаться `.symphysis/` (F-13.A, F-15.B).
<!-- проба краёв: форма=io, stateful, text, исходы: F-50 Specify -->
<!-- проба запретов: исходы: нет -->

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

#### Scenario: Раскладка входа
- **GIVEN** проект после `install` и новое изменение `openspec new change demo`
- **WHEN** выполняется `openspec status --change demo --json`
- **THEN** первым артефактом стоит `intent` с путём `openspec/changes/demo/intent.md`; каталога `.gigacode/` в проекте нет; инструменты лежат в `.symphysis/tools/`

#### Scenario: Обновление схемы
- **GIVEN** payload с новым `schema.yaml` (артефакт `intent`) и проект со старым `schema.yaml`
- **WHEN** выполняется `install` без `--force`
- **THEN** stdout называет `openspec/schemas/symphysis/schema.yaml` отдельной строкой «пропущен: отличается, нужен --force», `check` даёт `[!!] схема: байты отличаются от payload`, код 2; установка по инструкции с `--force` обновляет файл

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

### Requirement: Установка не включает телеметрию форка молча
Телеметрия форка SHALL быть выключена по умолчанию: `init` форка и `symphysis install` SHALL NOT включать её; `check` SHALL давать код 0 и `[..] telemetry: выключена` при выключенной или без конфига и `[!!] telemetry: включена — выключить: <команда>` при включённой; README называет, как выключить (F-21.A, F-51.E, F-57.E; symphysis-schema F-79).
<!-- проба краёв: форма=io, text, исходы: F-51 Specify -->
<!-- проба запретов: исходы: F-57 Specify; канон — F-58 → security.md -->

#### Scenario: Установка в чистом окружении
- **GIVEN** глобальный конфиг OpenSpec без ключа `telemetry`
- **WHEN** выполняется `install --project <dir>`
- **THEN** телеметрия остаётся выключенной: `openspec config list` не показывает включённой телеметрии, `check` даёт `[..] telemetry: выключена`, код 0 — предположение: способ выключения — запись `telemetry.enabled: false` при установке или сборка форка без телеметрии; решить в design

#### Scenario: Конфига OpenSpec нет
- **GIVEN** глобальный конфиг OpenSpec отсутствует (первый запуск)
- **WHEN** выполняется `check --project <dir>`
- **THEN** stdout содержит `[..] telemetry: конфиг OpenSpec не найден — появится после первого openspec init`, код 0

#### Scenario: Телеметрия включена
- **GIVEN** глобальный конфиг с включённой телеметрией и `anonymousId`
- **WHEN** выполняется `check --project <dir>`
- **THEN** stdout содержит `[!!] telemetry: включена — выключить: <команда из README>`; предположение: код 2 как у расхождений установки; решить
