<!-- MIT License, Copyright (c) 2026 Open GSD; источник: upstream/gsd-core/agents/gsd-doc-verifier.md @ v1.20.1; выписка: строки 38-41, 58-98, 100-110; классификация исходов из <adversarial_stance>, блок <claim_extraction> целиком, блок <skip_rules> целиком; пропуски помечены комментарием «пропущено», текст между пометками дословный, английский. -->
<!-- пропущено: строки 1-37 -->
**Required finding classification:**
- **BLOCKER** — a claim is demonstrably false (file missing, function doesn't exist, command not in package.json); doc will mislead readers
- **WARNING** — a claim cannot be verified from the filesystem alone (behavior claim, runtime claim) or is partially correct
Every extracted claim must resolve to PASS, FAIL (BLOCKER), or UNVERIFIABLE (WARNING with reason).
<!-- пропущено: строки 42-57 -->
<claim_extraction>
Extract checkable claims from the Markdown doc using these five categories. Process each category in order.

**1. File path claims**
Backtick-wrapped tokens containing `/` or `.` followed by a known extension.

Extensions to detect: `.ts`, `.js`, `.cjs`, `.mjs`, `.md`, `.json`, `.yaml`, `.yml`, `.toml`, `.txt`, `.sh`, `.py`, `.go`, `.rs`, `.java`, `.rb`, `.css`, `.html`, `.tsx`, `.jsx`

Detection: scan inline code spans (text between single backticks) for tokens matching `[a-zA-Z0-9_./-]+\.(ts|js|cjs|mjs|md|json|yaml|yml|toml|txt|sh|py|go|rs|java|rb|css|html|tsx|jsx)`.

Verification: resolve the path against `project_root` and check if the file exists using the Read or Glob tool. Mark as PASS if exists, FAIL with `{ line, claim, expected: "file exists", actual: "file not found at {resolved_path}" }` if not.

**2. Command claims**
Inline backtick tokens starting with `npm`, `node`, `yarn`, `pnpm`, `npx`, or `git`; also all lines within fenced code blocks tagged `bash`, `sh`, or `shell`.

Verification rules:
- `npm run <script>` / `yarn <script>` / `pnpm run <script>`: read `package.json` and check the `scripts` field for the script name. PASS if found, FAIL with `{ ..., expected: "script '<name>' in package.json", actual: "script not found" }` if missing.
- `node <filepath>`: verify the file exists (same as file path claim).
- `npx <pkg>`: check if the package appears in `package.json` `dependencies` or `devDependencies`.
- Do NOT execute any commands. Existence check only.
- For multi-line bash blocks, process each line independently. Skip blank lines and comment lines (`#`).

**3. API endpoint claims**
Patterns like `GET /api/...`, `POST /api/...`, etc. in both prose and code blocks.

Detection pattern: `(GET|POST|PUT|DELETE|PATCH)\s+/[a-zA-Z0-9/_:-]+`

Verification: grep for the endpoint path in source directories (`src/`, `routes/`, `api/`, `server/`, `app/`). Use patterns like `router\.(get|post|put|delete|patch)` and `app\.(get|post|put|delete|patch)`. PASS if found in any source file. FAIL with `{ ..., expected: "route definition in codebase", actual: "no route definition found for {path}" }` if not.

**4. Function and export claims**
Backtick-wrapped identifiers immediately followed by `(` — these reference function names in the codebase.

Detection: inline code spans matching `[a-zA-Z_][a-zA-Z0-9_]*\(`.

Verification: grep for the function name in source files (`src/`, `lib/`, `bin/`). Accept matches for `function <name>`, `const <name> =`, `<name>(`, or `export.*<name>`. PASS if any match found. FAIL with `{ ..., expected: "function '<name>' in codebase", actual: "no definition found" }` if not.

**5. Dependency claims**
Package names mentioned in prose as used dependencies (e.g., "uses `express`" or "`lodash` for utilities"). These are backtick-wrapped names that appear in dependency context phrases: "uses", "requires", "depends on", "powered by", "built with".

Verification: read `package.json` and check both `dependencies` and `devDependencies` for the package name. PASS if found. FAIL with `{ ..., expected: "package in package.json dependencies", actual: "package not found" }` if not.
</claim_extraction>
<!-- пропущено: строки 99-99 -->
<skip_rules>
Do NOT verify the following:

- **VERIFY markers**: Claims wrapped in `<!-- VERIFY: ... -->` — these are already flagged for human review. Skip entirely.
- **Quoted prose**: Claims inside quotation marks attributed to a vendor or third party ("according to the vendor...", "the npm documentation says...").
- **Example prefixes**: Any claim immediately preceded by "e.g.", "example:", "for instance", "such as", or "like:".
- **Placeholder paths**: Paths containing `your-`, `<name>`, `{...}`, `example`, `sample`, `placeholder`, or `my-`. These are templates, not real paths.
- **GSD marker**: The comment `<!-- generated-by: gsd-doc-writer -->` — skip entirely.
- **Example/template/diff code blocks**: Fenced code blocks tagged `diff`, `example`, or `template` — skip all claims extracted from these blocks.
- **Version numbers in prose**: Strings like "`3.0.2`" or "`v1.4`" that are version references, not paths or functions.
</skip_rules>
<!-- пропущено: строки 111-218 -->
