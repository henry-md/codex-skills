#!/usr/bin/env node
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { resolve, relative } from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

const repo = process.env.JEV_BROWSER_REPO || '/Users/henry/Developer/jev-browser-automation';
const [mode, ...args] = process.argv.slice(2);
if (!['mcp', 'do', 'run'].includes(mode)) {
  console.error('Usage: node browser.mjs mcp | do <url> <goal> [key=value ...] | run <flow.json> [--json]');
  process.exit(mode === '--help' ? 0 : 2);
}
const entry = resolve(repo, 'bin', mode === 'mcp' ? 'jev-browser-mcp.mjs' : 'jev-browser.mjs');
if (!existsSync(entry)) {
  console.error('Jev Browser checkout is missing. Set JEV_BROWSER_REPO to its installed path.');
  process.exit(1);
}

// The skill always starts current local code. A long-running MCP process still
// needs reconnecting after an update; closing only its browser cannot reload it.
const config = resolve(repo, 'tsconfig.json');
if (existsSync(config)) {
  const sources = [];
  const collect = directory => {
    if (!existsSync(directory)) return;
    for (const item of readdirSync(directory, { withFileTypes: true })) {
      const path = resolve(directory, item.name);
      if (item.isDirectory()) collect(path);
      else if (item.isFile() && item.name.endsWith('.ts')) sources.push(path);
    }
  };
  collect(resolve(repo, 'src')); collect(resolve(repo, 'bin'));
  const runtime = resolve(repo, 'dist', 'bin', mode === 'mcp' ? 'jev-browser-mcp.js' : 'jev-browser.js');
  const stamp = existsSync(runtime) ? statSync(runtime).mtimeMs : 0;
  const changedConfig = [config, resolve(repo, 'package.json'), resolve(repo, 'package-lock.json')]
    .some(path => existsSync(path) && statSync(path).mtimeMs > stamp);
  const changedSource = sources.some(path => {
    const output = resolve(repo, 'dist', relative(repo, path).replace(/\.ts$/, '.js'));
    return path.endsWith('.d.ts') ? statSync(path).mtimeMs > stamp
      : !existsSync(output) || statSync(path).mtimeMs > statSync(output).mtimeMs;
  });
  if (!stamp || changedConfig || changedSource) {
    const compiler = resolve(repo, 'node_modules/typescript/bin/tsc');
    if (!existsSync(compiler)) {
      console.error(`Jev Browser needs its local TypeScript compiler. Run npm ci in ${repo}.`);
      process.exit(1);
    }
    // Build before loading credentials, and keep compiler output off MCP stdout.
    const built = spawnSync(process.execPath, [compiler, '-p', config], { cwd: repo, encoding: 'utf8' });
    if (built.error || built.status !== 0) {
      console.error('Jev Browser build failed; refusing to run stale compiled code.');
      process.stderr.write(built.stdout ?? ''); process.stderr.write(built.stderr ?? '');
      if (built.error) console.error(built.error.message);
      process.exit(1);
    }
    process.stderr.write('[jev] Built the updated local browser runtime.\n');
  }
}
if (!process.env.TYPESAFE_API_KEY) {
  const file = process.env.JEV_CREDENTIALS_FILE || resolve(homedir(), '.config/jev/credentials.json');
  try { process.env.TYPESAFE_API_KEY = JSON.parse(readFileSync(file, 'utf8')).TYPESAFE_API_KEY; }
  catch { console.error('Jev credential unavailable; set TYPESAFE_API_KEY or configure the private credential file.'); process.exit(1); }
}
if (!process.env.TYPESAFE_API_KEY) { console.error('Jev credential is empty.'); process.exit(1); }
// The credential is loaded only into the child environment, never command arguments.
process.env.JEV_MODEL ||= 'jev-1.13.0';
process.env.JEV_API_URL = 'https://api.typesafe.ai/v1/systemone';
process.argv = [process.execPath, entry, ...(mode === 'mcp' ? [] : [mode, ...args])];
await import(pathToFileURL(entry).href);
