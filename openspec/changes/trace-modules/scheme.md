# Схема решения: trace-modules

Сценарий из intent: собрать ось «где код», связать её с требованиями и проверить результат на модулях symphysis. Источники связей и границы обхода выбираются в журнале; стрелки ниже обозначают целевые связи, а не уже принятый способ их получения.

```mermaid
flowchart TD
    declarations["Объявления компонентов и репозиториев"]
    roots["Локальное разрешение путей репозиториев"]
    readmes["README модулей: имя, род, граница"]
    artifacts["Артефакты изменения: требования, задачи, журнал"]
    component["Компонент"]
    repository["Репозиторий"]
    module["Модуль"]
    file["Файл реализации"]
    requirement["Требование: id без модуля"]
    relation["Подтверждённая связь реализации или кандидат"]
    dependency["Зависимость между модулями"]
    graph["Вычисляемый req graph"]
    signals["Отчёт и проверка: сигналы"]
    snapshot["Замороженный снимок с источниками"]
    diagram["Экспорт requirementDiagram"]
    dogfood["Проверка на настоящих модулях symphysis"]
    declarations --> component
    declarations --> repository
    roots --> repository
    component -->|содержит| repository
    repository --> readmes
    readmes --> module
    module -->|содержит| file
    artifacts --> requirement
    artifacts --> relation
    file --> relation
    module --> relation
    requirement --> relation
    module --> dependency
    component --> graph
    repository --> graph
    module --> graph
    file --> graph
    requirement --> graph
    relation --> graph
    dependency --> graph
    graph --> signals
    graph --> snapshot
    graph --> diagram
    graph --> dogfood
```
