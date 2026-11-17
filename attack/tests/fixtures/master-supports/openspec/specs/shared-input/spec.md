# Shared input

## Requirements

### Requirement: Stable input
The input SHALL preserve its public shape.

#### Scenario: Input remains usable
- **WHEN** a consumer reads the input
- **THEN** it receives the original value — без потери данных

#### Scenario: Unused sibling
- **WHEN** another consumer reads the input
- **THEN** it receives an independent value

### Requirement: Neighboring rule
The neighbor SHALL keep its own behavior.

#### Scenario: Neighbor remains independent
- **WHEN** the neighbor changes
- **THEN** the supported input remains usable
