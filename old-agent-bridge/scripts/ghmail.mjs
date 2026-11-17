#!/usr/bin/env node
// GitHub-issue mailbox transport for agent-bridge, for networks that block the Railway relay.
// One shared issue in a private repo; each message is one comment (JSON body) tagged with its channel.
// Usage: node ghmail.mjs pair|send|watch --channel N --from NAME [--text T] [--timeout S]
// Reads use ETag conditional requests: a 304 does not count against the GitHub rate limit.
import { execFileSync } from 'node:child_process';
import { createHash, randomBytes } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

const REPO = process.env.GHMAIL_REPO ?? 'henry-md/agent-bridge-mailbox';
const API = 'https://api.github.com';
const args = Object.fromEntries(process.argv.slice(3).reduce((a, v, i, all) => v.startsWith('--') ? [...a, [v.slice(2), all[i + 1]]] : a, []));
const cmd = process.argv[2], channel = args.channel, me = args.from;
if (!['pair', 'send', 'watch'].includes(cmd) || !/^\d{1,64}$/.test(channel ?? '') || !me) {
  console.error('usage: ghmail.mjs pair|send|watch --channel N --from NAME [--text T] [--timeout S]'); process.exit(2);
}
const token = process.env.GH_TOKEN ?? execFileSync('gh', ['auth', 'token', '--hostname', 'github.com'], { encoding: 'utf8' }).trim();
const headers = { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'agent-bridge-ghmail' };
const dir = join(homedir(), '.agent-bridge'); mkdirSync(dir, { recursive: true });
const stateFile = join(dir, `ghmail-${channel}-${me.replace(/\W/g, '_')}.json`);
const load = () => { try { return JSON.parse(readFileSync(stateFile, 'utf8')); } catch { return {}; } };
const save = (s) => writeFileSync(stateFile, JSON.stringify(s));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const gh = async (path, init = {}) => {
  const res = await fetch(API + path, { ...init, headers: { ...headers, ...init.headers, ...(init.body ? { 'Content-Type': 'application/json' } : {}) } });
  if (res.status !== 304 && !res.ok) throw new Error(`GitHub ${res.status} on ${init.method ?? 'GET'} ${path}: ${(await res.text()).slice(0, 200)}`);
  return res;
};

async function issueNumber() {
  const s = load(); if (s.issue) return s.issue;
  const title = 'mailbox';
  // One shared issue holds every channel (messages carry a channel field), so peers never race to create it.
  const lowest = async () => (await (await gh(`/repos/${REPO}/issues?state=open&per_page=100&direction=asc`)).json())
    .find((i) => i.title === title && !i.pull_request)?.number;
  let number = await lowest();
  if (!number) {
    const created = await (await gh(`/repos/${REPO}/issues`, { method: 'POST', body: JSON.stringify({ title }) })).json();
    await sleep(1000);
    number = Math.min(created.number, (await lowest()) ?? created.number); // the list can lag right after a create
  }
  save({ ...s, issue: number }); return number;
}
async function post(issue, message) {
  const res = await gh(`/repos/${REPO}/issues/${issue}/comments`, { method: 'POST', body: JSON.stringify({ body: JSON.stringify({ channel, from: me, at: new Date().toISOString(), ...message }) }) });
  return (await res.json()).id;
}
// The cursor starts at the newest existing comment, so a fresh join ignores old history.
async function newest(issue) {
  const count = (await (await gh(`/repos/${REPO}/issues/${issue}`)).json()).comments;
  if (!count) return { id: 0, ts: new Date(Date.now() - 5000).toISOString() };
  const [last] = await (await gh(`/repos/${REPO}/issues/${issue}/comments?per_page=1&page=${count}`)).json();
  return { id: last.id, ts: last.created_at };
}

// Poll at 250 ms while a conversation is active, then back off to 1 s.
async function waitFor(issue, accept, timeoutMs) {
  const s = load(); if (!s.cursor) { s.cursor = await newest(issue); save(s); }
  const deadline = Date.now() + timeoutMs; let etag, quietSince = Date.now(); const found = [];
  const url = `/repos/${REPO}/issues/${issue}/comments?per_page=100&since=${encodeURIComponent(s.cursor.ts)}`;
  while (Date.now() < deadline) {
    const res = await gh(url, { headers: etag ? { 'If-None-Match': etag } : {} });
    if (res.status !== 304) {
      etag = res.headers.get('etag') ?? undefined;
      for (const c of (await res.json()).filter((c) => c.id > s.cursor.id)) {
        s.cursor = { id: c.id, ts: c.created_at };
        let m; try { m = JSON.parse(c.body); } catch { continue; }
        if (m.channel === channel && m.from !== me && accept(m)) found.push(m);
      }
      save(s); quietSince = Date.now();
      if (found.length) return found;
    }
    await sleep(Date.now() - quietSince < 30_000 ? 250 : 1000);
  }
  return found;
}
const out = (o) => process.stdout.write(JSON.stringify(o) + '\n');

const issue = await issueNumber();
const timeoutMs = Number(args.timeout ?? 600) * 1000;
if (cmd === 'send') out({ sent: true, id: await post(issue, { type: 'msg', text: args.text ?? '' }) });
else if (cmd === 'watch') { const messages = await waitFor(issue, (m) => m.type === 'msg', timeoutMs); out({ timed_out: !messages.length, messages }); }
else {
  // Both sides exchange random halves; the secret word is derived from both so each side shows the same word.
  // Look back 2 minutes so a peer that said hello first is still seen, whichever side pairs first.
  const s = load(); s.cursor = { id: 0, ts: new Date(Date.now() - 120_000).toISOString() }; save(s);
  const mine = randomBytes(8).toString('hex'); await post(issue, { type: 'hello', half: mine });
  const hellos = await waitFor(issue, (m) => m.type === 'hello', timeoutMs);
  if (!hellos.length) { out({ verified: false, error: 'no peer joined before the timeout' }); process.exit(1); }
  const h = createHash('sha256').update([mine, hellos[0].half].sort().join(':')).digest('hex');
  const words = ['amber', 'birch', 'cedar', 'dawn', 'ember', 'fjord', 'grove', 'harbor', 'iris', 'juniper', 'kelp', 'lilac', 'maple', 'nectar', 'onyx', 'pine'];
  out({ verified: true, peer: hellos[0].from, secret_word: `${words[parseInt(h[0], 16)]}-${words[parseInt(h[1], 16)]}-${h.slice(2, 6)}` });
}
