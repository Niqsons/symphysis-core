---
name: openspec-continue-change
description: Continue working on an OpenSpec change by creating the next artifact. Use when the user wants to progress their change, create the next artifact, or continue their workflow. Also use when the user says "openspec continue" or "opsx continue".
allowed-tools: Bash(openspec:*)
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
---

Continue working on a change by creating the next artifact.

**Store selection:** If the user names a store (a store is a standalone OpenSpec repo registered on this machine) or the work lives in one, run `openspec store list --json` to discover registered store ids, then pass `--store <id>` on the commands that read or write specs and changes (`new change`, `status`, `instructions`, `list`, `show`, `validate`, `archive`, `doctor`, `context`, `schemas`, `view`). Once selected, treat `--store <id>` as sticky for the rest of the workflow. Every unscoped example of those commands below is shorthand: before running it, append the flag. For example, run `openspec status --change "<name>" --json --store "<id>"`, not the unscoped form shown below. Other commands do not take the flag. Hints printed by commands already carry the flag; keep it on follow-ups. Without a store, commands act on the nearest local `openspec/` root.

**Project check:** These steps expect a project that already uses OpenSpec. Before the first step that writes anything (`new change`, `archive`, `sync specs`, or authoring an artifact file), confirm the project has a root: run `openspec list --json` (with `--store <id>` when a store is selected, since the store is then the root) and read `root`. A root object means the project is set up. `"root": null` means it is not - there is no `openspec/` directory here, and a write such as `openspec new change` would create one as a side effect. The command also exits non-zero, which is that answer rather than a broken CLI, so read the JSON instead of retrying or working around it.

One `"root": null` is not about setup: when a `status` error message starts with `Declared in` or `Invalid store declaration in` and names this project's `openspec/config.yaml` (or `config.yml`), the project does use OpenSpec through a store it declares, which this machine cannot resolve (the store is not registered, or the `store:` line is malformed). Do not treat it as uninitialized and skip the branches below: stop before writing and show the user that error's `message` and `fix`.

Otherwise, with no root, what happens next depends on how this workflow was reached:

- **Auto-selected**: you chose this workflow yourself, without the user naming OpenSpec, naming this skill, or running its slash command. Stop using OpenSpec and answer the request normally, as you would with no OpenSpec installed. Do not ask them to set anything up and do not mention OpenSpec setup.
- **Explicit OpenSpec request**: the user named OpenSpec, named this skill, or ran its slash command. Stop before writing and ask how to proceed: set this project up (`openspec init`), target a store they already have (`--store <id>`), or continue without OpenSpec for this request. Wait for their answer.

In both branches, never create the root as a side effect: do not run `openspec init` until the user asks for it, do not hand-create `openspec/` files, and do not let a command create it.

**Input**: `/openspec-continue-change <change> [<artifact-id>]` - optionally specify a change name and, as a second argument, an artifact id. If the name is omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **Select the change**

   If a name is provided, use it. Otherwise:
   - Infer from conversation context if the user mentioned a change
   - Auto-select if only one active change exists
   - If ambiguous, run `openspec list --json` to get available changes sorted by most recently modified, and ask the user to select one

   When prompting, present the top 3-4 most recently modified changes as options, showing:
   - Change name
   - Status (e.g., "0/5 tasks", "complete", "no tasks")
   - How recently it was modified (from `lastModified` field)

   Mark the most recently modified change as "(Recommended)" since it's likely what the user wants to continue.

   Always announce: "Using change: <name>" and how to override (e.g., `/openspec-continue-change <other>`).

2. **Check current status**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand current state. The response includes:
   - `schemaName`: The workflow schema being used (e.g., "spec-driven")
   - `artifacts`: Array of artifacts with their status ("done", "skipped", "ready", "blocked")
   - `verdict` on an artifact: present only when its schema entry declares a verdict; `"ok"`, `"missing"` (file or frontmatter value absent), `"mismatch"` (wrong value) or `"stale"` (a target changed since the verdict)
   - `optional: true` and `fileExists` on an artifact: present only on optional artifacts; one without a file does not block and is not part of completion
   - **The next artifact** (when the invocation names none): the FIRST artifact with `status: "ready"`, skipping any with `optional: true` and `fileExists: false` (not invoked - created only by name). It is the artifact `nextSteps` names. An invoked optional artifact (`fileExists: true`) is picked like any other. A `done` artifact with `verdict: "stale"` is past its window - a signal, not a gate: it is never picked; mention it to the user, and re-run it only when the invocation names it
   - `isPlanningComplete`: Boolean indicating if all planning artifacts are complete. Older CLI versions expose the same value as `isComplete`.
   - `planningHome`, `changeRoot`, `artifactPaths`, and `actionContext`: path and scope context. Use these instead of assuming repo-local paths.

3. **Act based on status**:

   **If the invocation names an artifact** (`/openspec-continue-change <change> <artifact-id>`; the second argument is optional): compare the name with the `id` of every artifact in the status output exactly - case and hyphens included. If no `id` matches exactly, refuse: list every artifact `id`, write no file, do NOT pick a similar artifact, and STOP. If one matches, it is the ONLY artifact of this invocation, and these cases replace the checks below:
   - `status: "blocked"`: name its `missingDeps` and STOP
   - `verdict: "ok"` and the file exists: the verdict is valid (the target hashes match) - do NOT rewrite the file. Tell the user the verdict is valid, then get its instructions and execute them only for the rows not passed (the attack skill's step-1 rule)
   - `verdict: "mismatch"`, `"stale"`, or `"missing"` with an existing file: apply the verdict step below to this artifact
   - `status: "done"` without a `verdict` field, or `status: "skipped"`: tell the user the artifact is already done (or skipped by the change) and STOP - write nothing, do NOT rewrite its file
   - otherwise (`ready`, no file): create it from its instructions as in the ordinary branch below
   Then STOP. Without a name, work on the next artifact (step 2).

   ---

   **Before anything else, finish a partly written artifact**:
   - An artifact whose output is a glob pattern (e.g. `specs/**/*.md`) reads `done` as soon as one matching file exists, so a run interrupted while writing its files leaves it `done` with some still missing
   - For each such `done` artifact, first get its instructions and read any completed dependencies needed to determine the expected files. Then compare those files with `artifactPaths.<id>.existingOutputPaths`. For spec-driven's `specs`, read the proposal and check for one `specs/<capability-path>/spec.md` per capability it lists; resolve each expected path against `changeRoot` before comparing path identity, and verify each one remains inside `changeRoot` after resolving symlinks, both in its parent directories and in the file itself if it already exists
   - Never write an expected path that fails that check; stop and tell the user. If any are missing, write only the missing files, each at its checked path - when the `instruction` field delegates creation to a skill or command, invoke it only if it can write each file to its checked path; otherwise stop and tell the user - and STOP - that counts as this invocation's ONE artifact. If you cannot tell whether a file was left out on purpose, ask the user

   ---

   **If the next artifact (step 2) carries `verdict: "mismatch"`, `verdict: "stale"`, or `verdict: "missing"` while its file already exists (`artifactPaths.<artifact-id>.existingOutputPaths` in the status output is non-empty)**: do NOT rewrite the file. Get its instructions (`openspec instructions <artifact-id> --change "<name>" --json`) and follow them to produce the verdict — the instruction names the attack skill that writes `status: passed` or `status: gaps_found` into the file's frontmatter. Then re-run `openspec status --change "<name>" --json` and confirm the artifact now shows `verdict: "ok"` (and `status: "done"`); if it shows `gaps_found`, report the gaps to the user and STOP. `verdict: "stale"` means a target the verdict was written against has changed since: treat it like `mismatch` — do not rewrite the file blindly, run the artifact's instruction again in full. This counts as this invocation's ONE artifact — STOP after it. A verdict artifact with `verdict: "missing"` and no existing file is created like any other ready artifact (its instruction writes the file with its frontmatter) — the ordinary branch below applies.

   ---

   **If all planning artifacts are complete (`isPlanningComplete: true`, or legacy `isComplete: true`)**:
   - Congratulate the user
   - Show final status including the schema used
   - Suggest: "Planning is complete! You can now implement this change. Once implementation and any tracked work are complete, archive it."
   - STOP

   ---

   **If artifacts are ready to create** (status shows artifacts with `status: "ready"`):
   - Pick the next artifact (step 2) (if it carries `verdict: "mismatch"`, `verdict: "stale"`, or `verdict: "missing"` with an existing file, the verdict step above applies instead)
   - Get its instructions:
     ```bash
     openspec instructions <artifact-id> --change "<name>" --json
     ```
   - Parse the JSON. The key fields are:
     - `context`: Project background (constraints for you - do NOT include in output)
     - `rules`: Artifact-specific rules (constraints for you - do NOT include in output)
     - `template`: The structure to use for your output file
     - `instruction`: Schema-specific guidance
     - `resolvedOutputPath`: Resolved path or pattern to write the artifact
     - `dependencies`: Completed artifacts to read for context (entries with `skipped: true` have no files - do not look for them)
     - `skipped`/`warning`: present when the change declares skip_specs and this artifact must NOT be created - pick another artifact
   - **Create the artifact file**:
     - Read any completed dependency files for context - always re-read them from disk, even if you saw them earlier in the conversation (the user may have edited them)
     - Choose the output path before creating anything. If the `resolvedOutputPath` specified in instructions is a glob pattern, choose a concrete path inside `changeRoot` using the schema instruction and the change's context, and verify it remains inside `changeRoot` after resolving symlinks, both in its parent directories and in the file itself if it already exists; if it does not, stop and tell the user. Otherwise the output path is `resolvedOutputPath`
     - If the `instruction` field delegates creation to a specific skill or command, invoke it only if it can write the artifact to that output path; otherwise stop and tell the user
     - Otherwise, write it yourself:
       - Use `template` as the structure - fill in its sections
       - Apply `context` and `rules` as constraints when writing - but do NOT copy them into the file
       - Write the file to that output path
     - Either way, verify the artifact file exists at that output path
   - Show what was created and what's now unlocked
   - STOP after creating ONE artifact

   ---

   **If no artifacts are ready (all blocked)**:
   - This shouldn't happen with a valid schema
   - Show status and suggest checking for issues

4. **After creating an artifact, show progress**
   ```bash
   openspec status --change "<name>"
   ```

**Output**

After each invocation, show:
- Which artifact was created
- Schema workflow being used
- Current progress (N/M complete)
- What artifacts are now unlocked
- Prompt: "Want to continue? Just ask me to continue or tell me what to do next."

**Artifact Creation Guidelines**

The artifact types and their purpose depend on the schema. The `instruction` field from the instructions output is the authoritative guidance for each artifact - follow it even when the artifact has a familiar name (proposal.md, tasks.md, etc.), since custom schemas may define different content or a different process for the same file names.

If the `instruction` field directs you to use a specific skill or command to create the artifact, invoke it instead of writing the artifact directly - but only once you have chosen and checked the output path, and only if it can write there.

**Guardrails**
- Create ONE artifact per invocation
- Always read dependency artifacts before creating a new one - re-read from disk, not from conversation memory (files may have changed since you last saw them)
- Never skip artifacts or create out of order
- If context is unclear, ask the user before creating
- Verify the artifact file exists after writing before marking progress
- Use the schema's artifact sequence, don't assume specific artifact names
- **IMPORTANT**: `context` and `rules` are constraints for YOU, not content for the file
  - Do NOT copy `<context>`, `<rules>`, `<project_context>` blocks into the artifact
  - These guide what you write, but should never appear in the output
