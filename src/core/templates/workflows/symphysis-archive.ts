/**
 * Symphysis archive sequencing and result review.
 * Provenance: symphysis docs/skills-canon.md section 12;
 * fork-symphysis-flow portion 4. The graph remains advisory; a requested sync
 * must have a verified result before its change directory can move.
 */
import { SYMPHYSIS_TOOLS, SYMPHYSIS_GRAPH, SYMPHYSIS_RESULT_RULES } from './symphysis-sync.js';

export const SYMPHYSIS_ARCHIVE_PREPARE = `**Symphysis archive preparation:**

   If the status JSON's \`schemaName\` is exactly \`symphysis\`, you MUST do the following before the sync assessment, including an already-synced change or an eventual "Archive without syncing" choice. This step does not depend on the optional archive-input lookup or its guidance. These workflow steps own the operations: do not execute another copy merely because optional guidance repeats them.
${SYMPHYSIS_TOOLS}${SYMPHYSIS_GRAPH}   Read \`python "<toolsHome>/sync_check.py" "<name>" --json\` from \`planningHome.root\` as additional evidence for the assessment. Here a \`mismatch\` often means the delta still needs applying, not that sync is blocked. A \`review\`, missing checker or checker error needs the existing semantic assessment; show what could not be verified instead of pretending it matched. For other schemas, skip these Symphysis tools.

   For Symphysis, "Archive without syncing" MUST leave all main specs untouched: skip anchoring and post-sync verification, preserve that explicit choice and report "Sync skipped". A failed graph alone does not prevent this route. For "Archive now", verify the already-synced state using established reference origins; a late freeze of an anchored master does not prove the old origin of a bare number. Do not rename journal namespaces or remove all prefixes merely to make the comparison match.
`;

export const SYMPHYSIS_ARCHIVE_VERIFY = `   **Finish a requested Symphysis sync before moving the directory:**

   If \`schemaName\` is \`symphysis\` and sync was requested, the selected inline workflow and any inline fallback MUST finish anchoring before this comparison. Reuse a completed anchoring result only for the same planning root, change and exact capability scope. Otherwise run \`python "<toolsHome>/anchor_refs.py" "<name>"\` from \`planningHome.root\` with one \`--capability\` per selected capability and show its actual output; an anchoring failure stops this requested sync and archive. Never re-anchor excluded capabilities or take a replacement base after writing the master. The inline workflow's freeze is a freshness check before its own writes and reuses the saved base; it must not replace it with the synced master. "Archive now" only checks the already-synced state; it does not repair references by writing the master.

   If a requested inline sync supplied its actual completed checker JSON after anchoring, the resolved planning root/change/exact capability scope match, and neither master nor delta has been written since, you MUST reuse that result and its review conclusions; do not run the checker again merely to repeat it. A pre-sync assessment result cannot be reused after a master write. An absent, malformed, failed or differently scoped result is not a receipt.
   Otherwise run \`python "<toolsHome>/sync_check.py" "<name>" --json\` from \`planningHome.root\`, with one \`--capability\` per capability in the status inventory, and read its actual JSON. For "Archive now", run this check after the user's choice; its earlier pre-assessment result is not enough.
${SYMPHYSIS_RESULT_RULES}   Apply the same result review to "Archive now" before moving an already-synced change, using the capabilities from the status inventory. Keep "Archive without syncing" on its separate no-master-write route. A \`review\` needs explicit semantic/provenance conclusions, not an automatic success or failure. Only a verified synced state may be labelled "Synced to main specs".
`;
