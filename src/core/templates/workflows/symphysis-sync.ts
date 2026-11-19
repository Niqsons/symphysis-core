/**
 * Symphysis direct-sync sequencing; shared by skill and command templates.
 * Provenance: symphysis docs/skills-canon.md section 12 and
 * docs/analysis/fork-symphysis-flow-required-changes-2026-11-09.md section 3.
 * Other schemas keep the canonical OpenSpec merge without Python tools.
 */
export const SYMPHYSIS_TOOLS = `   - From the invocation directory, find the nearest ancestor containing \`.symphysis/tools/\` and keep its absolute path as \`toolsHome\`. Locate \`trace_graph.py\` and \`anchor_refs.py\` there. Do not guess another project's installation or install tools during sync.
`;

export const SYMPHYSIS_GRAPH = `   - Set the Python command's working directory to \`planningHome.root\`. Python tools do not accept \`--store\`.
   - If \`<toolsHome>/journal-roots.json\` exists, you MUST run the complete command \`python "<toolsHome>/trace_graph.py" freeze "<name>" --roots "<toolsHome>/journal-roots.json"\`.
   - Otherwise, run \`python "<toolsHome>/trace_graph.py" freeze "<name>"\` from the same planning root.
   - If the graph command succeeds and starts with "Граф собран заново", give the user the report link from its actual output, resolved against \`planningHome.root\`, without summarizing or filtering the report. For "Снимок свежий: обновлены только коммиты", do not emit a new report link.
   - If the graph tool is missing or fails, show the actual error and continue this workflow; do not claim a base was saved. A graph error alone is not a sync or archive gate. A late snapshot cannot recover the pre-sync master.
`;

export const SYMPHYSIS_PRE_SYNC = `**Preserve the Symphysis base before writing:**

   If the status JSON's \`schemaName\` is exactly \`symphysis\`, you MUST perform these steps before the first main-spec write; otherwise skip this block:
${SYMPHYSIS_TOOLS}   - Derive the selected capability names from exactly the delta paths selected in step 3. Before writing, run \`python "<toolsHome>/anchor_refs.py" --help\` and require support for \`--capability\`. If the anchoring tool is missing or incompatible, report the problem and stop before writing: an unscoped fallback could change excluded capabilities.
${SYMPHYSIS_GRAPH}   - If the graph command succeeded and retained evidence establishes this is the first sync of the selected blocks, run \`python "<toolsHome>/trace_graph.py" freeze "<name>" --confirmed-pre-sync\` before any write, appending one \`--capability "<selected-capability>"\` for each selected capability and the same roots argument when supplied. This records \`graph/pre-sync-base.json\` bound to the specific snapshot entries. For a repeated sync or unknown order, keep the ordinary snapshot without this flag and report the missing origin evidence. Current equality, a fresh ordinary freeze, and a late snapshot alone cannot establish origin. A failure to record provenance is reported like the graph failure above.
   - Before writing, retain the actual selected pre-sync master blocks as reference-provenance evidence. A snapshot taken after a write is not that evidence. If archive supplied pre-sync blocks, carry them through the inline result.
   - In the selected blocks, omit only probe-trail comments named "проба краёв" or "проба запретов". Preserve other comments, inherited bare references and foreign anchors; do not infer a journal namespace from the capability name.
`;

export const SYMPHYSIS_RESULT_RULES = `   - \`match\`: the scripted checks matched this scope; still perform the existing main-spec validation.
   - \`mismatch\`: show the findings and stop this sync as failed. Do not hand that result to archive.
   - \`review\`: resolve each finding using the delta, the genuine pre-sync snapshot and retained pre-sync master blocks. Compare the full reference (journal name, number and option letter). A current bare number and this change's anchor are equivalent only when that origin is established. Never strip arbitrary journal prefixes or infer a journal from a capability name. Report the evidence and conclusion; if any finding remains unresolved, report an unverified sync and stop before claiming success or archiving it.
   Retain the actual checker JSON (root, change, capabilities, status and findings) and any review conclusions for archive.
   If the checker is unavailable or errors, show the error and perform the existing semantic comparison explicitly; do not treat a failed lookup as \`match\`. A graph error or a \`review\` status alone is not an automatic archive gate: a concrete mismatch or an unverified requested sync is a different outcome.

`;

export const SYMPHYSIS_VERIFY = `   **Verify the selected Symphysis result:**

   If \`schemaName\` is \`symphysis\`, run \`python "<toolsHome>/sync_check.py" "<name>" --json\` from \`planningHome.root\`, appending exactly the selected \`--capability\` values used for anchoring. Read the JSON status, not just the process exit code:
${SYMPHYSIS_RESULT_RULES}
`;

export const SYMPHYSIS_POST_SYNC = `   **Anchor the selected Symphysis result before validation:**

   If \`schemaName\` is \`symphysis\`, you MUST run \`python "<toolsHome>/anchor_refs.py" "<name>"\` from \`planningHome.root\`, appending one \`--capability "<selected-capability>"\` for every capability selected in step 3. Never widen that set. Show the actual output. If anchoring fails, report sync as failed and stop; do not claim success or hand an incomplete sync to archive. Do not rewrite references by hand or take a replacement base from the already edited master.
${SYMPHYSIS_VERIFY}
`;
