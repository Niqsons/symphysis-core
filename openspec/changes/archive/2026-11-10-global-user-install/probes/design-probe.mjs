/** Read-only feasibility probe; no native installations, configs, or model calls. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const root = 'X:/symphysis-global-user-install';
const fork = path.join(root, 'upstream/openspec');
const load = (rel) => import(pathToFileURL(path.join(fork, 'dist', rel)).href);
const shared = await load('core/shared/skill-generation.js');
const { generateCommand } = await load('core/command-generation/generator.js');
const { claudeAdapter } = await load('core/command-generation/adapters/claude.js');
const { opencodeAdapter } = await load('core/command-generation/adapters/opencode.js');
const required = ['new', 'continue', 'apply', 'sync', 'archive'];
const skills = shared.getSkillTemplates(required);
const commands = shared.getCommandContents(required);
assert.deepEqual(skills.map((x) => x.workflowId).sort(), [...required].sort());
assert.deepEqual(commands.map((x) => x.id).sort(), [...required].sort());
let callbackInvoked = false;
const rendered = shared.generateSkillContent(skills[0].template, 'design-probe', (body) => {
  callbackInvoked = true;
  return body;
});
assert.equal(callbackInvoked, true);
assert.ok(rendered.includes('generatedBy: "design-probe"'));
const command = commands.find((x) => x.id === 'continue');
const claude = generateCommand(command, claudeAdapter);
const opencode = generateCommand(command, opencodeAdapter);
const slash = (x) => x.replaceAll('\\', '/');
assert.equal(slash(claude.path), '.claude/commands/opsx/continue.md');
assert.equal(slash(opencode.path), '.opencode/commands/opsx-continue.md');
const mermaid = fs.readFileSync(path.join(root, 'installer/node_modules/mermaid/dist/mermaid.min.js'));
const encoded = mermaid.toString('base64');
assert.equal(encoded.toLowerCase().includes('</script'), false);
assert.deepEqual(Buffer.from(encoded, 'base64'), mermaid);
const result = {
  requiredWorkflows: required,
  skillTemplateCount: skills.length,
  commandContentCount: commands.length,
  identityTransformCallbackInvoked: callbackInvoked,
  claudeContinuePath: slash(claude.path),
  opencodeContinuePath: slash(opencode.path),
  mermaidBytes: mermaid.length,
  mermaidBase64RoundTrip: true,
  generatedFilesInstalled: false,
  nativeClientsOrModelsRun: false,
  newGlobalHtmlLoaderExecuted: false,
};
fs.writeFileSync(path.join(root, 'openspec/changes/global-user-install/probes/design-results.json'),
  JSON.stringify(result, null, 2) + '\n', 'utf8');
process.stdout.write('Pinned dist exports and two command surfaces verified; mermaid base64 round-trip passed\n');
