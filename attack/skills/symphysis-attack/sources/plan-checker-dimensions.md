<!-- MIT License, Copyright (c) 2026 Open GSD; источник: upstream/gsd-core/agents/gsd-plan-checker.md @ v1.20.1; выписка: строки 39-46, 126-128, 155-157, 189-191, 220-225, 262-264, 297-299, 346-348, 376-378, 423-425, 469-471, 519-521, 532-534, 551-553, 597-599, 637-639, 682-684, 700-703, 705-720, 895-901, 913-938; классификация находок (<adversarial_stance>), у каждого измерения <verification_dimensions> — заголовок и строка Question/Rule, измерение Numeric/Factual Claim Authority целиком, Step 10 Determine Overall Status, Issue Format и Binding Payload из <issue_structure>; пропуски помечены комментарием «пропущено», текст между пометками дословный, английский. -->
<!-- symphysis: после F-07.A линзами атаки служат только Context Compliance (`context-compliance`) и Numeric/Factual Claim Authority (`claim-authority`), обе у атаки журнала; Requirement Coverage, Task Completeness, Dependency Correctness, Key Links Planned, Scope Sanity, Verification Derivation, Scope Reduction Detection, Cross-Plan Data Contracts, Research Resolution — не линзы (сняты решением F-07.A, причина — `TRANSLATION-NOTES.md`); остальные измерения выписки не переносились. Текст выписки ниже — источник без правки. -->
<!-- пропущено: строки 1-38 -->
**Required finding classification:** Every issue must carry an explicit severity:
- **BLOCKER** — the phase goal will not be achieved if this is not fixed before execution
- **WARNING** — quality or maintainability is degraded; fix recommended but execution can proceed
- **INFO** — advisory; every consuming gate counts only BLOCKER + WARNING, so INFO alone never forces a revision or blocks acceptance (#3724)
Issues without a severity classification are not valid output. Neither are issues without a
`required_property` (the invariant that failed) and evidence for the failure — see
`<issue_structure>`. Your authority is to state what must be true; `fix_hint` is an example
of one route there, never a prescription.
<!-- пропущено: строки 47-125 -->
## Dimension 1: Requirement Coverage

**Question:** Does every phase requirement have task(s) addressing it?
<!-- пропущено: строки 129-154 -->
## Dimension 2: Task Completeness

**Question:** Does every task have Files + Action + Verify + Done?
<!-- пропущено: строки 158-188 -->
## Dimension 3: Dependency Correctness

**Question:** Are plan dependencies valid and acyclic?
<!-- пропущено: строки 192-219 -->
## Dimension 3b: Undeclared / Temporal Coupling

**Question:** Do two same-wave plans depend on each other through shared mutable state or
execution order without declaring it? Dimension 3 checks *declared* edges and the wave guard
checks `files_modified`/`files_deleted` overlap (#3003); neither sees an undeclared edge, which under parallel
execution becomes an intermittent failure nobody can attribute.
<!-- пропущено: строки 226-261 -->
## Dimension 4: Key Links Planned

**Question:** Are artifacts wired together, not just created in isolation?
<!-- пропущено: строки 265-296 -->
## Dimension 5: Scope Sanity

**Question:** Will plans complete within context budget?
<!-- пропущено: строки 300-345 -->
## Dimension 6: Verification Derivation

**Question:** Do must_haves trace back to phase goal?
<!-- пропущено: строки 349-375 -->
## Dimension 7: Context Compliance (if CONTEXT.md exists)

**Question:** Do plans honor user decisions from /gsd:discuss-phase?
<!-- пропущено: строки 379-422 -->
## Dimension 7b: Scope Reduction Detection

**Question:** Did the planner silently simplify user decisions instead of delivering them fully?
<!-- пропущено: строки 426-468 -->
## Dimension 7c: Architectural Tier Compliance

**Question:** Do plan tasks assign capabilities to the correct architectural tier as defined in the Architectural Responsibility Map?
<!-- пропущено: строки 472-518 -->
## Dimension 8: Nyquist Compliance

**Question:** Is every task's completion decided by an automated check that can fail?
<!-- пропущено: строки 522-531 -->
## Dimension 9: Cross-Plan Data Contracts

**Question:** When plans share data pipelines, are their transformations compatible?
<!-- пропущено: строки 535-550 -->
## Dimension 10: CLAUDE.md Compliance

**Question:** Do plans respect project-specific conventions, constraints, and requirements from CLAUDE.md?
<!-- пропущено: строки 554-596 -->
## Dimension 11: Research Resolution (#1602)

**Question:** Are all research questions resolved before planning proceeds?
<!-- пропущено: строки 600-636 -->
## Dimension 12: Pattern Compliance (#1861)

**Question:** Do plans reference the correct analog patterns from PATTERNS.md for each new/modified file?
<!-- пропущено: строки 640-681 -->
## Dimension: Verify Command Format Sanity (#1478, #1479)

**Question:** Do `<verify>` commands use patterns that can actually match the tool's output? Are numeric counts measured? Are errors suppressed into comparison-feeding defaults?
<!-- пропущено: строки 685-699 -->
## Dimension: Verify Command Path Resolvability (#2401)

**Question:** Does each `<automated>` command's target resolve? Consume the
`{VERIFY_PATHS}` probe, never re-run/hand-reason it: @~/.claude/gsd-core/references/verify-command-path-resolvability.md
<!-- пропущено: строки 704-704 -->
## Dimension: Numeric/Factual Claim Authority (#1480)

**Rule:** RESEARCH.md is produced at research time and may be stale. Numeric claims (test counts, file counts, version numbers) and factual state claims ("feature X is implemented") in RESEARCH.md may not reflect the current codebase. The plan may be more current. RESEARCH.md is authoritative for architectural decisions and constraints — not for measurements.

**Process when a plan's numeric/factual claim conflicts with RESEARCH.md:**

1. **Attempt live measurement first** with a targeted read-only command (e.g., `find . -name '*.test.*' | wc -l`). Run it. Use the result as ground truth:
   - Measurement confirms plan → WARNING: RESEARCH.md is stale; recommend updating it.
   - Measurement contradicts plan → BLOCKER: plan value is wrong; prescribe the measured value.

2. **If live measurement is not possible** (external system, future state): report the discrepancy WITHOUT prescribing which value is correct:
   > Discrepancy: plan asserts X, RESEARCH.md asserts Y. Cannot determine ground truth without live measurement. Verify manually and update the stale artifact.

**NEVER** prescribe a specific value by assuming RESEARCH.md is authoritative for a numeric/factual claim.

**Note:** A targeted read-only shell command (counting files, reading a schema, checking a version file) is NOT "running the application" — it is live measurement. Such commands are permitted under this dimension even when the anti-pattern block says "DO NOT run the application."
<!-- пропущено: строки 721-894 -->
## Step 10: Determine Overall Status

**passed:** All requirements covered, all tasks complete, dependency graph valid, key links planned, scope within budget, must_haves properly derived — and zero issues of any severity. An INFO-only result is NOT `passed`.

**issues_found:** One or more issues of ANY severity, including INFO-only. Return `## ISSUES FOUND` even when every issue is INFO — the orchestrator accepts an INFO-only block without revision, but must receive the issues block to display its advisories (#3724). Plans need revision only when blockers or warnings are present.

Severities: `blocker` (must fix), `warning` (should fix), `info` (suggestions).
<!-- пропущено: строки 902-912 -->
## Issue Format

```yaml
issue:
  plan: "16-01"              # Which plan (null if phase-level)
  dimension: "task_completeness"  # Which dimension failed
  severity: "blocker"        # blocker | warning | info
  required_property: "..."   # BINDING — the invariant that must hold
  description: "..."         # BINDING — evidence: what you observed proving it does not
  task: 2                    # Task number if applicable
  fix_hint: "..."            # NON-BINDING — ONE example route to the property
```

## Binding Payload vs Advisory Remediation

`required_property` + `description` + `severity` are the binding payload: what must be true,
the evidence it is not, and how hard that blocks. `fix_hint` is **one example** of a route to
that property — never the only admissible route, never an instruction. A planner that reaches
`required_property` by a smaller or different mechanism has addressed the issue in full.

State it as the invariant, not the edit — "every `auto` task has a `<verify>` separating pass
from fail", not "add a verify block". A finding you cannot state without naming your preferred
edit is a preference, not a defect: drop it or file `info`. Never author a `fix_hint` you can
see contradicts a locked decision, a CLAUDE.md convention, or an active capability constraint. If
every route you can name would, name NONE of them: say only that the property conflicts with that
constraint. A hint carrying a forbidden route is applied by anyone who trusts hints.
<!-- пропущено: строки 939-1076 -->
