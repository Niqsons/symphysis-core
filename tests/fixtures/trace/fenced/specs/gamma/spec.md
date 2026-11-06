## ADDED Requirements

### Requirement: Требование с примерами
Система SHALL показывать примеры разметки.

Пример в блоке кода:

```markdown
## REMOVED Requirements

### Requirement: x

#### Scenario: в блоке кода
- **WHEN** не сценарий
```

#### Scenario: Первый сценарий
- **WHEN** a
- **THEN** b

~~~~text
#### Scenario: в блоке с тильдами
```
внутри длинного блока короткий не закрывает
```
### Requirement: y
~~~~

#### Scenario: Второй сценарий
- **WHEN** c
- **THEN** d

```
### Requirement: x
```

### Requirement: Реальное после блоков
Система SHALL остаться видимой после блоков кода.

#### Scenario: Сценарий реального
- **WHEN** e
- **THEN** f
