import * as fs from 'node:fs';
import * as path from 'node:path';
import { getSchemaDir, resolveSchema, listSchemasWithInfo } from './resolver.js';
import { ArtifactGraph } from './graph.js';
import {
  detectAbsentOptional,
  detectCompleted,
  detectStaleSignals,
  staleVerdictTarget,
  verdictState,
  type StaleSignal,
} from './state.js';
import { readFrontmatter } from './frontmatter.js';
import {
  isSpecsArtifactPath,
  resolveArtifactOutputPath,
  resolveArtifactOutputs,
} from './outputs.js';
import {
  formatUnknownChangeMetadataKeysMessage,
  readChangeMetadata,
  readUnknownChangeMetadataKeys,
  resolveSchemaForChange,
} from '../../utils/change-metadata.js';
import { FileSystemUtils } from '../../utils/file-system.js';
import {
  buildActionContext,
  buildNextSteps,
  summarizePlanningHome,
  type ActionContext,
  type PlanningHomeSummary,
} from '../change-status-policy.js';
import { readProjectConfig, validateConfigRules, type ProjectConfig } from '../project-config.js';
import type { ReferenceIndexEntry } from '../references.js';
import type { PlanningHome } from '../planning-home.js';
import type { ChangeMetadata } from '../change-metadata/index.js';
import type { Artifact, CompletedSet, VerdictStatus } from './types.js';

// Session-level cache for validation warnings (avoid repeating same warnings)
const shownWarnings = new Set<string>();

/**
 * Error thrown when loading a template fails.
 */
export class TemplateLoadError extends Error {
  constructor(
    message: string,
    public readonly templatePath: string
  ) {
    super(message);
    this.name = 'TemplateLoadError';
  }
}

/**
 * Change context containing graph, completion state, and metadata.
 */
export interface ChangeContext {
  /** The artifact dependency graph */
  graph: ArtifactGraph;
  /** Set of completed artifact IDs */
  completed: CompletedSet;
  /** Schema name being used */
  schemaName: string;
  /** Change name */
  changeName: string;
  /** Path to the change directory */
  changeDir: string;
  /** Project root directory */
  projectRoot: string;
  /** Resolved planning home for this change */
  planningHome?: PlanningHome;
  /** Parsed change metadata, when present */
  metadata?: ChangeMetadata;
  /** Non-fatal metadata diagnostics for text and JSON command surfaces */
  warnings?: string[];
  /**
   * Artifact IDs counted as complete only because the change declares
   * skip_specs, not because their files exist. Kept separate so status can
   * render them as skipped rather than done.
   */
  skippedArtifacts?: Set<string>;
  /**
   * Fork (symphysis, C7): optional artifacts whose output does not exist. They
   * are not in `completed`, yet satisfy their dependents' `requires` and are
   * left out of planning completeness (see `satisfiedArtifacts`).
   */
  absentOptionalArtifacts?: Set<string>;
  /**
   * Fork (symphysis, C11): verdict artifacts whose `stale` verdict is past its
   * window - the next step has begun - keyed by id with what began. They are
   * in `completed` (a signal, not a gate) and still report `verdict: "stale"`.
   */
  staleSignals?: Map<string, StaleSignal>;
}

export interface LoadChangeContextOptions {
  changeDir?: string;
  planningHome?: PlanningHome;
  /** Pre-read project config; suppresses schema resolution's fallback config read. */
  projectConfig?: ProjectConfig | null;
}

/**
 * Enriched instructions for creating an artifact.
 */
export interface ArtifactInstructions {
  /** Change name */
  changeName: string;
  /** Artifact ID */
  artifactId: string;
  /** Schema name */
  schemaName: string;
  /** Full path to change directory */
  changeDir: string;
  /** Resolved planning home for this change */
  planningHome?: PlanningHomeSummary;
  /** Output path pattern (e.g., "proposal.md") */
  outputPath: string;
  /** Absolute output path or glob pattern resolved under the change directory */
  resolvedOutputPath: string;
  /** Existing concrete output files for this artifact */
  existingOutputPaths: string[];
  /** Artifact description */
  description: string;
  /** Guidance on how to create this artifact (from schema instruction field) */
  instruction: string | undefined;
  /** Project context from config (constraints/background for AI, not to be included in output) */
  context: string | undefined;
  /** Artifact-specific rules from config (constraints for AI, not to be included in output) */
  rules: string[] | undefined;
  /** Referenced-store index (read-only upstream context; omitted when no references are declared) */
  references?: ReferenceIndexEntry[];
  /** Template content (structure to follow - this IS the output format) */
  template: string;
  /** Dependencies with completion status and paths */
  dependencies: DependencyInfo[];
  /** Artifacts that become available after completing this one */
  unlocks: string[];
  /** True when the change declares skip_specs and this artifact is skipped */
  skipped?: boolean;
  /** Present only when skipped: tells the consumer not to create the artifact */
  warning?: string;
  /** Non-fatal metadata diagnostics */
  warnings?: string[];
}

/**
 * Warning attached to instructions for an artifact skipped via skip_specs.
 * Carried in the JSON payload too, so agents driving the CLI with --json see
 * the same do-not-create signal as the text output.
 */
export const SKIP_SPECS_INSTRUCTIONS_WARNING =
  'This change declares skip_specs: true in .openspec.yaml (no spec-level behavior changes), so this artifact is skipped.\n' +
  'Do not create spec files - they will conflict with that marker. If requirements now change, remove skip_specs from .openspec.yaml and rerun this command.';

/**
 * Dependency information including path and description.
 */
export interface DependencyInfo {
  /** Artifact ID */
  id: string;
  /** Whether the dependency is completed */
  done: boolean;
  /** Relative output path of the dependency (e.g., "proposal.md") */
  path: string;
  /** Description of the dependency artifact */
  description: string;
  /** True when the dependency is satisfied via skip_specs - no files exist to read */
  skipped?: boolean;
  /** Fork (symphysis, C7): present, and `true`, only when the dependency is an
   * optional artifact. */
  optional?: true;
  /** Fork (symphysis, C7): whether the optional dependency's output exists;
   * without it the dependency is satisfied and has no files to read. */
  fileExists?: boolean;
}

/**
 * Status of a single artifact in the workflow.
 */
export interface ArtifactStatus {
  /** Artifact ID */
  id: string;
  /** Output path pattern */
  outputPath: string;
  /** Status: done, skipped (via skip_specs), ready, or blocked */
  status: 'done' | 'skipped' | 'ready' | 'blocked';
  /** Artifact IDs this artifact directly requires (its `requires` edges).
   * Present for every status so callers can compute the transitive required
   * set even when the artifact is already `done` (file-existence status does
   * not imply its dependencies exist). */
  requires: string[];
  /** Missing dependencies (only for blocked) */
  missingDeps?: string[];
  /** Fork (symphysis, C7): present, and `true`, only for artifacts whose schema
   * entry declares `optional: true`. */
  optional?: true;
  /** Fork (symphysis, C7): whether the optional artifact's output exists; only
   * alongside `optional`. Without the file the artifact is not invoked: it
   * blocks nothing and carries no `verdict`. */
  fileExists?: boolean;
  /** Fork (symphysis, C3, C7, C11): verdict state, only for artifacts whose schema
   * entry declares `verdict` and only while they are `done` (`ok`, or `stale`
   * past its window - a signal, not a gate) or `ready` (`missing` = no file or no
   * verdict key in it, `mismatch` = another value, `stale` = the value passes but
   * a declared target hash no longer matches, and the next step has not begun).
   * Omitted for `blocked` and `skipped` artifacts and for an optional artifact
   * without a file. Never `n/a`. */
  verdict?: VerdictStatus;
}

/**
 * Formatted change status.
 */
export interface ChangeStatus {
  /** Change name */
  changeName: string;
  /** Schema name */
  schemaName: string;
  /** Planning home facts (generated skills derive the archive dir
   * from planningHome.changesDir - a published agent contract). */
  planningHome?: PlanningHomeSummary;
  /** Full path to the change root */
  changeRoot: string;
  /** Absolute artifact path details keyed by artifact ID */
  artifactPaths: Record<string, ArtifactPathSummary>;
  /** Plain-language next steps for users and agents */
  nextSteps: string[];
  /** Machine-readable action constraints for agents */
  actionContext: ActionContext;
  /** Whether all planning artifacts are complete */
  isPlanningComplete: boolean;
  /** Compatibility alias for isPlanningComplete */
  isComplete: boolean;
  /** Artifact IDs required before apply phase (from schema's apply.requires) */
  applyRequires: string[];
  /** Status of each artifact */
  artifacts: ArtifactStatus[];
  /** Non-fatal metadata diagnostics */
  warnings?: string[];
}

export interface ArtifactPathSummary {
  outputPath: string;
  resolvedOutputPath: string;
  existingOutputPaths: string[];
}

/**
 * Loads a template from a schema's templates directory.
 *
 * @param schemaName - Schema name (e.g., "spec-driven")
 * @param templatePath - Relative path within the templates directory (e.g., "proposal.md")
 * @param projectRoot - Optional project root for project-local schema resolution
 * @returns The template content
 * @throws TemplateLoadError if the template cannot be loaded
 */
export function loadTemplate(
  schemaName: string,
  templatePath: string,
  projectRoot?: string
): string {
  const schemaDir = getSchemaDir(schemaName, projectRoot);
  if (!schemaDir) {
    throw new TemplateLoadError(
      `Schema '${schemaName}' not found`,
      templatePath
    );
  }

  const templatesDir = path.join(schemaDir, 'templates');
  const templatePathOnDisk = path.join(templatesDir, templatePath);

  try {
    FileSystemUtils.assertPathWithin(templatesDir, templatePathOnDisk);
  } catch (error) {
    throw new TemplateLoadError(
      error instanceof Error ? error.message : String(error),
      templatePathOnDisk
    );
  }

  if (!fs.existsSync(templatePathOnDisk)) {
    throw new TemplateLoadError(
      `Template not found: ${templatePathOnDisk}`,
      templatePathOnDisk
    );
  }

  const fullPath = FileSystemUtils.canonicalizeExistingPath(templatePathOnDisk);

  try {
    return fs.readFileSync(fullPath, 'utf-8');
  } catch (err) {
    const ioError = err instanceof Error ? err : new Error(String(err));
    throw new TemplateLoadError(
      `Failed to read template: ${ioError.message}`,
      fullPath
    );
  }
}

/**
 * Loads change context combining graph and completion state.
 *
 * Schema resolution order:
 * 1. Explicit schemaName parameter (if provided)
 * 2. Schema from .openspec.yaml metadata (if exists in change directory)
 * 3. Default 'spec-driven'
 *
 * @param projectRoot - Project root directory
 * @param changeName - Change name
 * @param schemaName - Optional schema name override. If not provided, auto-detected from metadata.
 * @returns Change context with graph, completed set, and metadata
 */
export function loadChangeContext(
  projectRoot: string,
  changeName: string,
  schemaName?: string,
  options: LoadChangeContextOptions = {}
): ChangeContext {
  const changeDir = FileSystemUtils.canonicalizeExistingPath(
    options.changeDir ?? path.join(projectRoot, 'openspec', 'changes', changeName)
  );

  const metadata = readChangeMetadata(changeDir, projectRoot) ?? undefined;
  const unknownMetadataKeys = readUnknownChangeMetadataKeys(changeDir);
  const warnings =
    unknownMetadataKeys.length > 0
      ? [formatUnknownChangeMetadataKeysMessage(unknownMetadataKeys)]
      : [];
  const resolvedSchemaName = resolveSchemaForChange(changeDir, schemaName, projectRoot, {
    metadata: metadata ?? null,
    projectConfig: options.projectConfig,
  });

  const schema = resolveSchema(resolvedSchemaName, projectRoot);
  const graph = ArtifactGraph.fromSchema(schema);
  const completed = detectCompleted(graph, changeDir);

  // Fork (symphysis, C11): a stale verdict past its window is a signal, not a
  // gate - the artifact counts as completed and still reports `stale`.
  const staleSignals = detectStaleSignals(graph, changeDir, schema.apply);
  for (const id of staleSignals.keys()) {
    completed.add(id);
  }

  // A change that declares skip_specs has no spec deltas by design, so
  // artifacts generating into specs/ count as complete; otherwise the graph
  // would block their dependents (e.g. tasks) on files that must not exist.
  // Tracked separately so status renders them as skipped, not done.
  const skippedArtifacts = new Set<string>();
  if (metadata?.skip_specs) {
    for (const artifact of graph.getAllArtifacts()) {
      if (isSpecsArtifactPath(artifact.generates) && !completed.has(artifact.id)) {
        completed.add(artifact.id);
        skippedArtifacts.add(artifact.id);
      }
    }
  }

  // Fork (symphysis, C7): optional artifacts nobody has written yet.
  const absentOptionalArtifacts = detectAbsentOptional(graph, changeDir);

  return {
    graph,
    completed,
    schemaName: resolvedSchemaName,
    changeName,
    changeDir,
    projectRoot,
    ...(options.planningHome ? { planningHome: options.planningHome } : {}),
    ...(metadata ? { metadata } : {}),
    ...(warnings.length > 0 ? { warnings } : {}),
    ...(skippedArtifacts.size > 0 ? { skippedArtifacts } : {}),
    ...(absentOptionalArtifacts.size > 0 ? { absentOptionalArtifacts } : {}),
    ...(staleSignals.size > 0 ? { staleSignals } : {}),
  };
}

/**
 * Fork (symphysis, C7): the artifacts that satisfy a dependency - the
 * completed ones (skipped included) and the optional ones without output.
 * An optional artifact with output satisfies a dependency only once it is
 * completed, verdict included. The artifact graph, planning completeness and
 * the apply gate all take dependencies from this one set.
 */
export function satisfiedArtifacts(context: ChangeContext): CompletedSet {
  return new Set([...context.completed, ...(context.absentOptionalArtifacts ?? [])]);
}

/**
 * Generates enriched instructions for creating an artifact.
 *
 * Instruction injection order:
 * 1. <context> - Project context from config (if present)
 * 2. <rules> - Artifact-specific rules from config (if present)
 * 3. <template> - Schema's template content
 *
 * @param context - Change context
 * @param artifactId - Artifact ID to generate instructions for
 * @param projectRoot - Project root directory (for reading config)
 * @returns Enriched artifact instructions
 * @throws Error if artifact not found
 */
export interface GenerateInstructionsOptions {
  /** Pre-read project config; suppresses the internal read (no double read). */
  projectConfig?: ProjectConfig | null;
  /** Referenced-store index assembled at the command boundary. */
  references?: ReferenceIndexEntry[];
}

export function generateInstructions(
  context: ChangeContext,
  artifactId: string,
  projectRoot?: string,
  options: GenerateInstructionsOptions = {}
): ArtifactInstructions {
  const artifact = context.graph.getArtifact(artifactId);
  if (!artifact) {
    throw new Error(`Artifact '${artifactId}' not found in schema '${context.schemaName}'`);
  }

  const templateContent = loadTemplate(context.schemaName, artifact.template, context.projectRoot);
  const dependencies = getDependencyInfo(
    artifact,
    context.graph,
    context.completed,
    context.skippedArtifacts,
    context.absentOptionalArtifacts
  );
  const unlocks = getUnlockedArtifacts(context.graph, artifactId);

  // Use projectRoot from context if not explicitly provided
  const effectiveProjectRoot = projectRoot ?? context.projectRoot;

  // Use the pre-read config when provided; otherwise read it here.
  let projectConfig = options.projectConfig ?? null;
  if (options.projectConfig === undefined && effectiveProjectRoot) {
    try {
      projectConfig = readProjectConfig(effectiveProjectRoot);
    } catch {
      // If config read fails, continue without config
    }
  }

  // Validate rules artifact IDs if config has rules (only once per session).
  // The rules map is global while each change can use a different schema, so a
  // key is only "unknown" when it matches no artifact in ANY available schema.
  if (projectConfig?.rules) {
    const validArtifactIds = new Set(
      listSchemasWithInfo(effectiveProjectRoot ?? undefined).flatMap((s) => s.artifacts)
    );
    const warnings = validateConfigRules(projectConfig.rules, validArtifactIds);

    // Show each unique warning only once per session
    for (const warning of warnings) {
      if (!shownWarnings.has(warning)) {
        console.warn(warning);
        shownWarnings.add(warning);
      }
    }
  }

  // Extract context and rules as separate fields (not prepended to template)
  const configContext = projectConfig?.context?.trim() || undefined;
  const rulesForArtifact =
    projectConfig?.rules && Object.hasOwn(projectConfig.rules, artifactId)
      ? projectConfig.rules[artifactId]
      : undefined;
  const configRules = rulesForArtifact && rulesForArtifact.length > 0 ? rulesForArtifact : undefined;

  return {
    changeName: context.changeName,
    artifactId: artifact.id,
    schemaName: context.schemaName,
    changeDir: context.changeDir,
    planningHome: summarizePlanningHome(context.planningHome),
    outputPath: artifact.generates,
    resolvedOutputPath: resolveArtifactOutputPath(context.changeDir, artifact.generates),
    existingOutputPaths: resolveArtifactOutputs(context.changeDir, artifact.generates),
    description: artifact.description,
    instruction: artifact.instruction,
    context: configContext,
    rules: configRules,
    ...(options.references !== undefined ? { references: options.references } : {}),
    ...(context.warnings ? { warnings: context.warnings } : {}),
    ...(context.skippedArtifacts?.has(artifact.id)
      ? { skipped: true, warning: SKIP_SPECS_INSTRUCTIONS_WARNING }
      : {}),
    template: templateContent,
    dependencies,
    unlocks,
  };
}

/**
 * Gets dependency info including paths and descriptions.
 */
function getDependencyInfo(
  artifact: Artifact,
  graph: ArtifactGraph,
  completed: CompletedSet,
  skippedArtifacts?: Set<string>,
  absentOptionalArtifacts?: Set<string>
): DependencyInfo[] {
  return artifact.requires.map(id => {
    const depArtifact = graph.getArtifact(id);
    return {
      id,
      done: completed.has(id),
      path: depArtifact?.generates ?? id,
      description: depArtifact?.description ?? '',
      ...(skippedArtifacts?.has(id) ? { skipped: true } : {}),
      // Fork (symphysis, C7): the same fields an optional artifact carries in status.
      ...(depArtifact?.optional
        ? { optional: true as const, fileExists: !absentOptionalArtifacts?.has(id) }
        : {}),
    };
  });
}

/**
 * Gets artifacts that become available after completing the given artifact.
 *
 * `getAllArtifacts()` already yields the schema's declaration order, so the list
 * is returned as collected: sorting it alphabetically would have `unlocks` name
 * the artifacts in a different order than `status` recommends them.
 */
function getUnlockedArtifacts(graph: ArtifactGraph, artifactId: string): string[] {
  const unlocks: string[] = [];

  for (const artifact of graph.getAllArtifacts()) {
    if (artifact.requires.includes(artifactId)) {
      unlocks.push(artifact.id);
    }
  }

  return unlocks;
}

/**
 * Fork (symphysis, C3): the `verdict` field of an artifact status.
 *
 * Empty for an artifact that declares no `verdict`. Only `done` and `ready`
 * artifacts carry it: a `blocked` one cannot be worked on yet and a `skipped`
 * one is not worked on, so what its file says would not be actionable.
 * `done` is `ok` (`detectCompleted` admits a verdict artifact only on `ok`),
 * or `stale` for a stale verdict past its window (C11); for `ready` it is what
 * the file says. An optional artifact without a file (C7) has no verdict to
 * report: it was not invoked.
 */
function verdictField(
  artifact: Artifact,
  status: 'done' | 'ready',
  changeDir: string,
  absentOptional: boolean,
  staleSignal: boolean
): Pick<ArtifactStatus, 'verdict'> {
  if (!artifact.verdict || absentOptional) {
    return {};
  }
  if (status === 'done') {
    return { verdict: staleSignal ? 'stale' : 'ok' };
  }
  const state = verdictState(artifact, changeDir);
  return state === 'n/a' ? {} : { verdict: state };
}

/**
 * Fork (symphysis, C7): the `optional` and `fileExists` fields of an artifact
 * status - only for artifacts whose schema entry declares `optional: true`, so
 * the status of every other artifact keeps its shape.
 */
function optionalFields(
  artifact: Artifact,
  absentOptional: boolean
): Pick<ArtifactStatus, 'optional' | 'fileExists'> {
  return artifact.optional ? { optional: true, fileExists: !absentOptional } : {};
}

/** Fork (symphysis, C7): why a stale verdict is stale, as `nextSteps` words it. */
const STALE_REASONS = {
  changed: 'changed since the verdict',
  outside: 'is outside the change directory',
  malformed: 'has no path or sha256',
} as const;

/**
 * Fork (symphysis, C3, C7): the next-step line for a ready verdict artifact
 * whose file is there but does not carry a passing verdict. It tells the agent
 * why the artifact is still `ready`. Without a file the generic next step
 * already says what to do, so there is no hint.
 */
function verdictHint(
  artifact: Artifact,
  state: 'missing' | 'mismatch' | 'stale',
  changeDir: string
): string | undefined {
  const verdict = artifact.verdict;
  if (!verdict) {
    return undefined;
  }
  const outputPath = resolveArtifactOutputPath(changeDir, artifact.generates);
  try {
    if (!fs.statSync(outputPath).isFile()) {
      return undefined;
    }
  } catch {
    return undefined;
  }

  if (state === 'missing') {
    return `Artifact "${artifact.id}" exists but has no verdict (${verdict.frontmatter}: ${verdict.value}) — run its instruction to produce one`;
  }

  if (state === 'stale') {
    const target = staleVerdictTarget(artifact, changeDir);
    if (!target) {
      return undefined;
    }
    return `Artifact "${artifact.id}" verdict is stale: ${target.path} ${STALE_REASONS[target.reason]} — run its instruction again`;
  }

  const actual = readFrontmatter(outputPath)?.[verdict.frontmatter];
  if (actual === undefined) {
    return undefined;
  }
  return `Artifact "${artifact.id}" has verdict ${verdict.frontmatter}=${String(actual)} but ${verdict.value} is required — run its instruction again`;
}

/**
 * Fork (symphysis, C11): the `nextSteps` line for a stale verdict past its
 * window - the next step has begun, so the verdict no longer gates.
 */
function staleSignalLine(id: string, signal: StaleSignal): string {
  const begun =
    'dependent' in signal
      ? `${signal.dependent} already exists`
      : `${signal.tracks} has a checked task`;
  return `Artifact "${id}" verdict is stale (signal, not a gate: ${begun}) — re-run it by name if needed`;
}

/**
 * Formats the status of all artifacts in a change.
 *
 * @param context - Change context
 * @returns Formatted change status
 */
export function formatChangeStatus(
  context: ChangeContext,
  options: { storeId?: string; implementationRoot?: string } = {}
): ChangeStatus {
  // Load schema to get apply phase configuration
  const schema = resolveSchema(context.schemaName, context.projectRoot);
  const applyRequires = schema.apply?.requires ?? schema.artifacts.map(a => a.id);

  const artifacts = context.graph.getAllArtifacts();
  // Fork (symphysis, C7): dependencies are met by `satisfied` (completed plus
  // optional artifacts without output); an artifact is done only when completed.
  const satisfied = satisfiedArtifacts(context);
  const ready = new Set(context.graph.getNextArtifacts(context.completed, satisfied));
  const blocked = context.graph.getBlocked(context.completed, satisfied);

  const artifactPaths: Record<string, ArtifactPathSummary> = {};
  const artifactStatuses: ArtifactStatus[] = artifacts.map(artifact => {
    artifactPaths[artifact.id] = {
      outputPath: artifact.generates,
      resolvedOutputPath: resolveArtifactOutputPath(context.changeDir, artifact.generates),
      existingOutputPaths: resolveArtifactOutputs(context.changeDir, artifact.generates),
    };
    const absentOptional = context.absentOptionalArtifacts?.has(artifact.id) ?? false;

    if (context.skippedArtifacts?.has(artifact.id)) {
      return {
        id: artifact.id,
        outputPath: artifact.generates,
        status: 'skipped' as const,
        requires: artifact.requires,
        ...optionalFields(artifact, absentOptional),
      };
    }

    if (context.completed.has(artifact.id)) {
      return {
        id: artifact.id,
        outputPath: artifact.generates,
        status: 'done' as const,
        requires: artifact.requires,
        ...optionalFields(artifact, absentOptional),
        ...verdictField(
          artifact,
          'done',
          context.changeDir,
          absentOptional,
          context.staleSignals?.has(artifact.id) ?? false
        ),
      };
    }

    if (ready.has(artifact.id)) {
      return {
        id: artifact.id,
        outputPath: artifact.generates,
        status: 'ready' as const,
        requires: artifact.requires,
        ...optionalFields(artifact, absentOptional),
        ...verdictField(artifact, 'ready', context.changeDir, absentOptional, false),
      };
    }

    return {
      id: artifact.id,
      outputPath: artifact.generates,
      status: 'blocked' as const,
      requires: artifact.requires,
      missingDeps: blocked[artifact.id] ?? [],
      ...optionalFields(artifact, absentOptional),
    };
  });

  // Sort by build order for consistent output
  const buildOrder = context.graph.getBuildOrder();
  const orderMap = new Map(buildOrder.map((id, idx) => [id, idx]));
  artifactStatuses.sort((a, b) => (orderMap.get(a.id) ?? 0) - (orderMap.get(b.id) ?? 0));
  // Fork (symphysis, C7): every artifact done, except optional ones without
  // output - those are not part of planning until someone writes them.
  const isComplete = context.graph.isComplete(satisfied);
  const artifactIds = artifactStatuses.map((artifact) => artifact.id);

  // Fork (symphysis, C3, C7): a hint per ready verdict artifact that has a file
  // but no passing verdict; the next-step policy leads with the one that
  // belongs to the artifact it recommends.
  const verdictHints = new Map<string, string>();
  for (const artifactStatus of artifactStatuses) {
    if (
      artifactStatus.status !== 'ready' ||
      (artifactStatus.verdict !== 'missing' &&
        artifactStatus.verdict !== 'mismatch' &&
        artifactStatus.verdict !== 'stale')
    ) {
      continue;
    }
    const artifact = context.graph.getArtifact(artifactStatus.id);
    const hint = artifact && verdictHint(artifact, artifactStatus.verdict, context.changeDir);
    if (hint) {
      verdictHints.set(artifactStatus.id, hint);
    }
  }

  return {
    changeName: context.changeName,
    schemaName: context.schemaName,
    planningHome: summarizePlanningHome(context.planningHome),
    changeRoot: context.changeDir,
    artifactPaths,
    isPlanningComplete: isComplete,
    isComplete,
    applyRequires,
    nextSteps: buildNextSteps({
      changeName: context.changeName,
      artifactStatuses,
      allArtifactsComplete: isComplete,
      ...(options.storeId ? { storeId: options.storeId } : {}),
      ...(verdictHints.size > 0 ? { verdictHints } : {}),
      // Fork (symphysis, C11): stale verdicts past their window, in build order.
      ...(context.staleSignals
        ? {
            signals: artifactStatuses.flatMap((artifactStatus) => {
              const signal = context.staleSignals?.get(artifactStatus.id);
              return signal ? [staleSignalLine(artifactStatus.id, signal)] : [];
            }),
          }
        : {}),
    }),
    actionContext: buildActionContext({
      projectRoot: context.projectRoot,
      artifactIds,
      ...(options.storeId
        ? {
            store: {
              id: options.storeId,
              ...(options.implementationRoot
                ? { implementationRoot: options.implementationRoot }
                : {}),
            },
          }
        : {}),
    }),
    artifacts: artifactStatuses,
    ...(context.warnings ? { warnings: context.warnings } : {}),
  };
}
