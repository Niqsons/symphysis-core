<!-- MIT License, Copyright (c) 2026 Open GSD; источник: upstream/gsd-core/gsd-core/workflows/discuss-phase.md @ v1.20.1; взяты разделы: <philosophy> (строки 52–60), <scope_guardrail> (62–80), <gray_area_identification> (82–99). Текст дословный, английский; пропуски помечены комментариями. -->

<!-- строки 1–51 (шапка loop-host, <purpose>, <required_reading>, <progressive_disclosure>, <downstream_awareness>) не взяты -->

<philosophy>
**User = founder/visionary. Claude = builder.**

The user knows: how they imagine it working, what it should look/feel like, what's essential vs nice-to-have, specific behaviors or references they have in mind.

The user doesn't know (and shouldn't be asked): codebase patterns (researcher reads the code), technical risks (researcher identifies these), implementation approach (planner figures this out), success metrics (inferred from the work).

Ask about vision and implementation choices. Capture decisions for downstream agents.
</philosophy>

<scope_guardrail>
**CRITICAL: No scope creep.** The phase boundary comes from ROADMAP.md and is FIXED. Discussion clarifies HOW to implement what's scoped, never WHETHER to add new capabilities.

**Allowed (clarifying ambiguity):** "How should posts be displayed?" (layout), "What happens on empty state?" (within the feature).

**Not allowed (scope creep):** "Should we also add comments?" / "What about search/filtering?" / "Maybe include bookmarking?" — those are new capabilities and belong in their own phase.

**Heuristic:** Does this clarify how we implement what's already in the phase, or does it add a new capability that could be its own phase?

**When user suggests scope creep:**
```
"[Feature X] would be a new capability — that's its own phase.
Want me to note it for the roadmap backlog?

For now, let's focus on [phase domain]."
```

Capture the idea in a "Deferred Ideas" section. Don't lose it, don't act on it.
</scope_guardrail>

<gray_area_identification>
Gray areas are **implementation decisions the user cares about** — things that could go multiple ways and would change the result.

1. Read the phase goal from ROADMAP.md
2. Understand the domain — something users SEE / CALL / RUN / READ / something being ORGANIZED — and let that drive what kinds of decisions matter
3. Generate phase-specific gray areas (not generic categories)

**Don't use generic category labels** (UI, UX, Behavior). Generate specific gray areas. Examples:

```
Phase: "User authentication"     → Session handling, Error responses, Multi-device policy, Recovery flow
Phase: "Organize photo library"  → Grouping criteria, Duplicate handling, Naming convention, Folder structure
Phase: "CLI for database backups"→ Output format, Flag design, Progress reporting, Error recovery
Phase: "API documentation"       → Structure/navigation, Code examples depth, Versioning approach, Interactive elements
```

**Claude handles these (don't ask):** technical implementation details, architecture patterns, performance optimization, scope (roadmap defines this).
</gray_area_identification>

<!-- строки 100–520 (<answer_validation>, <process>, <success_criteria>) не взяты: шаги GSD над ROADMAP/CONTEXT.md в symphysis не применяются -->
