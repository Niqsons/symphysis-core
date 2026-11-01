<!-- MIT License, Copyright (c) 2026 Open GSD; источник: upstream/gsd-core/agents/gsd-verifier.md @ e2cd587; выписка: строки 603-646, 828-839; хвост Step 9b (дерево статуса после отсева), Step 10 Structure Gap Output целиком до </verification_process>, раздел «Self-check the written status (#5118)»; пропуски помечены комментарием «пропущено», текст между пометками дословный, английский. -->
<!-- пропущено: строки 1-602 -->
**Deferred items do NOT affect the status determination.** After filtering, recalculate:

- If the gaps list is now empty and no human verification items exist → `passed`
- If the gaps list is now empty but human verification items exist → `human_needed`
- If the gaps list still has items → `gaps_found`

## Step 10: Structure Gap Output (If Gaps Found)

Before writing VERIFICATION.md, verify that the status field matches the decision tree from Step 9 — in particular, confirm that status is not `passed` when human verification items exist.

Structure gaps in YAML frontmatter for `/gsd:plan-phase --gaps`:

```yaml
gaps:
  - truth: "Observable truth that failed"
    status: failed
    reason: "Brief explanation"
    artifacts:
      - path: "src/path/to/file.tsx"
        issue: "What's wrong"
    missing:
      - "Specific thing to add/fix"
```

- `truth`: The observable truth that failed
- `status`: failed | partial
- `reason`: Brief explanation
- `artifacts`: Files with issues
- `missing`: Specific things to add/fix

If Step 9b identified deferred items, add a `deferred` section after `gaps`:

```yaml
deferred:  # Items addressed in later phases — not actionable gaps
  - truth: "Observable truth not yet met"
    addressed_in: "Phase 5"
    evidence: "Phase 5 success criteria: 'Implement RuntimeConfigC FFI bindings'"
```

Deferred items are informational only — they do not require closure plans.

**Group related gaps by concern** — if multiple truths fail from the same root cause, note this to help the planner create focused plans.

</verification_process>
<!-- пропущено: строки 647-827 -->
## Self-check the written status (#5118)

After writing VERIFICATION.md, read it back through its owner:

```bash
gsd_run query verification.status "{phaseDir}" --pick status
```

Gate on the exit code only. Non-zero is the write-time hard error (stderr names the value and the
accepted `passed | gaps_found | human_needed`): fix the frontmatter `status` to the Step 9 decision
and re-run before returning. A printed value that differs from yours (e.g. `stale`) is routing,
not an error — never edit `status` to match it.
<!-- пропущено: строки 840-968 -->
