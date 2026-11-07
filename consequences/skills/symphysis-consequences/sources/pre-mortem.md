<!-- MIT License, Copyright (c) 2026 Open GSD; источник: upstream/gsd-core/gsd-core/references/thinking-models-planning.md @ v1.20.1; выписка: строки 7-15 и 73-80, Pre-Mortem Analysis и «When NOT to Think»; пропуски помечены комментарием «пропущено», текст между пометками дословный, английский. -->
<!-- пропущено: строки 1-6 -->
## Conflict Resolution

Pre-Mortem and Constraint Analysis both analyze risk at different granularities. Run Constraint Analysis FIRST (identify the hardest constraint), then Pre-Mortem (enumerate failure modes around that constraint and the rest of the plan).

## 1. Pre-Mortem Analysis

**Counters:** Optimistic plan decomposition that ignores failure modes.

Before finalizing this plan, assume it has already failed. List the 3 most likely reasons for failure -- missing dependency, wrong decomposition, underestimated complexity -- and add mitigation steps or acceptance criteria that would catch each failure early.
<!-- пропущено: строки 16-72 -->
## When NOT to Think

Skip structured reasoning models when the situation does not benefit from them:

- **Single-task plans** -- If the phase has one clear requirement and one obvious task, do not run Pre-Mortem or MECE analysis. Write the task directly.
- **Well-researched phases** -- If RESEARCH.md has HIGH-confidence recommendations for every decision and no `[NEEDS DECISION]` items, skip Base Rate Neglect Counter. The research already resolved uncertainty.
- **Revision iterations** -- When revising a plan based on checker feedback, focus on fixing the flagged issues. Do not re-run the full model suite on every revision pass -- apply only the model relevant to the specific issue (e.g., MECE if the checker found a coverage gap).
- **Boilerplate plans** -- Configuration changes, version bumps, documentation updates. These do not have failure modes worth pre-mortem analysis.
