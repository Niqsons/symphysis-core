# Spec Delta

## Purpose
Граф артефактов схемы `symphysis`: журнал первым, исследование по парковкам, атака до proposal и после tasks, реализация только после вердикта; F-04, F-05, F-13.

## ADDED Requirements

### Requirement: Граф схемы начинается журналом и кончается атакой артефактов
Схема `symphysis` SHALL задавать артефакты в порядке зависимостей `decisions` → `research` → `attack-decisions` → `proposal` → `specs` и `design` → `security`, `tasks` → `attack-artifacts`, и `apply` SHALL требовать `tasks` и `attack-artifacts` (F-04.A, F-13.B).
<!-- проба краёв: форма=collection, исходы: F-34 открыт, F-35 открыт -->
<!-- проба запретов: исходы: нет -->

#### Scenario: Новое изменение
- **GIVEN** проект с `schema: symphysis` в `openspec/config.yaml` и изменение, созданное `openspec new change <имя>`
- **WHEN** выполняется `openspec status --change <имя> --json`
- **THEN** `decisions` — `ready`, остальные восемь — `blocked`, `applyRequires` = `[tasks, attack-artifacts]`

#### Scenario: Схема проходит валидацию форка
- **GIVEN** каталог `openspec/schemas/symphysis/` в проекте
- **WHEN** выполняется `openspec schema validate symphysis --json`
- **THEN** `valid: true`, `issues: []`, и `schema which symphysis` называет источник `project`

### Requirement: Исследование — файл на каждую парковку «материалы» с жанром
Артефакт `research` SHALL требовать по файлу `research/<F-NN>.md` на каждую парковку журнала с адресатом «материалы»; файл SHALL нести frontmatter `genre` из `устройство | размещение | края | проверка | аналоги`, `question` и `brief`, находки с `путь:строка «цитата»` из прочитанного файла и отрицания по рецепту «не найдено» + «искал: <шаблоны дословно>» (F-05.C).
<!-- проба краёв: форма=collection, исходы: F-36 открыт, F-37 открыт -->
<!-- проба запретов: исходы: нет; канон — F-81 → security.md -->

#### Scenario: Отчёт по парковке
- **GIVEN** запись F-NN с парковкой `addressee: материалы`
- **WHEN** артефакт `research` считается сделанным
- **THEN** существует `research/F-NN.md` с `question: F-NN`, одним значением `genre` и хотя бы одной строкой «Найдено» или «Не найдено» с «искал»

#### Scenario: Отрицание без шаблонов не принимается
- **GIVEN** отчёт со строкой «не найдено» без строки «искал:»
- **WHEN** атака артефактов проходит раздел `research/`
- **THEN** строка «отрицание без шаблонов поиска» с опорой «нет» — предположение: атака артефактов по схеме не целит `research/` (цели — specs, design, security, tasks); решить: добавить ли `research/**/*.md` в цели `attack-artifacts`
