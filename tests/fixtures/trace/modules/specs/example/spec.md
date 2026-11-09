## ADDED Requirements

### Requirement: Module declaration
The graph SHALL retain explicit implementation declarations.

<!-- symphysis:implements {"modules":[{"repo":"core","module":"example"}],"files":[{"repo":"core","path":"main.py","module":"example"}]} -->

#### Scenario: Declared implementation
- **GIVEN** an explicit module declaration
- **WHEN** the graph is built
- **THEN** the implementation has declaration provenance
