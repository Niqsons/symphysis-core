# Spec Delta

## Purpose
<!-- Только для новой capability: одно-два предложения (от 50 символов) о том, для чего она. У существующей capability раздел удали. -->

## ADDED Requirements

### Requirement: <имя требования>
Система SHALL <наблюдаемое поведение>.
<!-- проба краёв: форма=<numeric-range | collection | text | stateful | io>, исходы: <по кандидатам: Specify | Dismiss с причиной | Backstop | Defer; записи журнала F-NN> -->
<!-- проба запретов: исходы: <по кандидатам: Specify | Dismiss с причиной | Backstop | Defer; записи журнала F-NN; канон — в security.md, не здесь> -->

#### Scenario: <имя сценария>
- **GIVEN** <исходное состояние — необязательно>
- **WHEN** <условие>
- **THEN** <наблюдаемый результат>

<!-- Для существующей capability вместо ADDED (или рядом): `## MODIFIED Requirements` — требование целиком, со всеми сценариями;
     `## REMOVED Requirements` — с **Reason** и **Migration**; `## RENAMED Requirements` — FROM / TO. -->
