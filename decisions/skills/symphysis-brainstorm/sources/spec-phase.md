<!-- MIT License, Copyright (c) 2026 Open GSD; источник: upstream/gsd-core/gsd-core/workflows/spec-phase.md @ e2cd587; взяты разделы: <purpose> (строки 1–6), <interview_perspectives> (25–52), Step 4 «Socratic Interview Loop» (134–187). Текст дословный, английский; пропуски помечены комментариями. -->

<purpose>
Clarify WHAT a phase delivers through a Socratic interview loop with quantitative ambiguity scoring.
Produces a SPEC.md with falsifiable requirements that discuss-phase treats as locked decisions.

This workflow handles "what" and "why" — discuss-phase handles "how".
</purpose>

<!-- строки 7–24 (<ambiguity_model>) не взяты: числовой гейт снят по F-07, см. TRANSLATION-NOTES.md -->

<interview_perspectives>
Rotate through these perspectives — each naturally surfaces different blindspots:

**Researcher (rounds 1–2):** Ground the discussion in current reality.
- "What exists in the codebase today related to this phase?"
- "What's the delta between today and the target state?"
- "What triggers this work — what's broken or missing?"

**Simplifier (round 2):** Surface minimum viable scope.
- "What's the simplest version that solves the core problem?"
- "If you had to cut 50%, what's the irreducible core?"
- "What would make this phase a success even without the nice-to-haves?"

**Boundary Keeper (round 3):** Lock the perimeter.
- "What explicitly will NOT be done in this phase?"
- "What adjacent problems is it tempting to solve but shouldn't?"
- "What does 'done' look like — what's the final deliverable?"

**Failure Analyst (round 4):** Find the edge cases that invalidate requirements.
- "What's the worst thing that could go wrong if we get the requirements wrong?"
- "What does a broken version of this look like?"
- "What would cause a verifier to reject the output?"

**Seed Closer (rounds 5–6):** Lock remaining undecided territory.
- "We have [dimension] at [score] — what would make it completely clear?"
- "The remaining ambiguity is in [area] — can we make a decision now?"
- "Is there anything you'd regret not specifying before planning starts?"
</interview_perspectives>

<!-- строки 53–133 (<process> Step 1–3: инициализация GSD, разведка кодовой базы, первая оценка неясности) не взяты -->

## Step 4: Socratic Interview Loop

**Max 6 rounds.** Each round: 2–3 questions max. End round after user responds.

**Round selection by perspective:**
- Round 1: Researcher
- Round 2: Researcher + Simplifier
- Round 3: Boundary Keeper
- Round 4: Failure Analyst
- Rounds 5–6: Seed Closer (focus on lowest-scoring dimensions)

**After each round:**
1. Update all 4 dimension scores from the user's answers
2. Calculate new ambiguity score
3. Display the updated scoring:

```
After round [N]:
  Goal Clarity:       [score] (min 0.75) [✓ or ↑ needed]
  Boundary Clarity:   [score] (min 0.70) [✓ or ↑ needed]
  Constraint Clarity: [score] (min 0.65) [✓ or ↑ needed]
  Acceptance Criteria:[score] (min 0.70) [✓ or ↑ needed]
  Ambiguity: [score] (gate: ≤ 0.20)
```

**Gate check after each round:**

If gate passes (ambiguity ≤ 0.20 AND all minimums met):

**If `--auto`:** Jump to Step 5.5.

**Otherwise:** AskUserQuestion:
- header: "Spec Gate Passed"
- question: "Ambiguity is [score] — requirements are clear enough to write SPEC.md. Proceed?"
- options:
  - "Yes — write SPEC.md" → Jump to Step 5.5
  - "One more round" → Continue interview
  - "Done talking — write it" → Jump to Step 5.5

**If max rounds reached (6) and gate not passed:**

**If `--auto`:** Write SPEC.md anyway — flag unresolved dimensions. Log: `[auto] Max rounds reached. Writing SPEC.md with [N] dimensions below minimum. Planner will need to treat these as assumptions.`

**Otherwise:** AskUserQuestion:
- header: "Max Rounds"
- question: "After 6 rounds, ambiguity is [score]. [List dimensions still below minimum.] What would you like to do?"
- options:
  - "Write SPEC.md anyway — flag gaps" → Write SPEC.md, mark unresolved dimensions in Ambiguity Report
  - "Keep talking" → Continue (no round limit from here)
  - "Abandon" → Exit without writing

**If `--auto` mode throughout:** Replace all AskUserQuestion calls above with Claude's recommended choice. Log decisions inline. Apply the same logic as `--auto` in discuss-phase.

**Text mode (`workflow.text_mode: true` or `--text` flag):** Use plain-text numbered lists instead of AskUserQuestion TUI menus.

<!-- строки 188–559 (Step 5.5–8, <critical_rules>, <success_criteria>) не взяты: пробы краёв и запретов — отдельные скиллы -->
