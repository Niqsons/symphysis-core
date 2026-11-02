# Spec Delta

## MODIFIED Requirements

### Requirement: `install` ставит схему, скиллы и инструменты в проект и сливает конфиг
Команда `symphysis install --project <dir> [--skills-dir <dir>]…` SHALL положить схему в `openspec/schemas/symphysis/`, скиллы в каждый `--skills-dir` (по умолчанию `.claude/skills`), инструменты в `.symphysis/` и создать или слить `openspec/config.yaml` (`schema` → `symphysis`, `rules` объединяются, прочее сохраняется); повторный запуск SHALL ничего не менять, отличающийся файл SHALL пропускаться с подсказкой `--force`, файл корней SHALL NOT перезаписываться (журнал `symphysis-schema`: F-15.C, F-16.B). Файл mermaid закреплённой версии SHALL ставиться в `.symphysis/tools/` и SHALL NOT лежать в git ядра (F-49, F-53). Каталог `.symphysis/viewer/` с черновиками человека SHALL NOT стираться и при `--force` (`docs/repo-contract.md`, F-20).
<!-- проба краёв: форма=io, stateful, collection, исходы: F-100 Specify, F-101 Specify; снято: idempotency — сценарий «Повторная установка» и подсказка `--force` -->
<!-- проба запретов: исходы: F-113 Dismiss; канон — F-117 → security.md -->

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

#### Scenario: Файл mermaid в проекте
- **GIVEN** проект без установки
- **WHEN** выполняется `install`
- **THEN** в `.symphysis/tools/` лежит файл mermaid закреплённой версии, а страница журнала рисует схему

#### Scenario: Файл mermaid не в git ядра
- **GIVEN** репозиторий ядра после сборки поставки
- **WHEN** выполняется `git ls-files`
- **THEN** файла mermaid в списке нет

#### Scenario: Черновики переживают обновление
- **GIVEN** `.symphysis/viewer/` с черновиком человека
- **WHEN** выполняется `install --force`
- **THEN** черновик байт в байт прежний

#### Scenario: Файла mermaid нет при сборке поставки
- **GIVEN** файла mermaid нет в зависимостях сборки
- **WHEN** идёт `sync-payload.js`
- **THEN** код не ноль и названа причина, поставка не собрана

#### Scenario: Файл mermaid пропал из проекта
- **GIVEN** проект без файла mermaid
- **WHEN** выполняется `symphysis check`
- **THEN** строка-сигнал `[..]`, код прежний: страница работает и с текстом
