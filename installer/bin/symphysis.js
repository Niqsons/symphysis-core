#!/usr/bin/env node
import { runRuntimeCommand } from "../lib/runtime-cli.js";
import { runManagementCommand, MANAGEMENT_HELP } from "../lib/management-cli.js";

const args = process.argv.slice(2);
const management = await runManagementCommand(args);
if (management !== null) process.exit(management);
const runtime = await runRuntimeCommand(args);
if (runtime !== null) process.exit(runtime);
process.stderr.write(`${args.length ? `Неизвестная команда: ${args.join(" ")}\n\n` : ""}${MANAGEMENT_HELP}`);
process.exit(2);
