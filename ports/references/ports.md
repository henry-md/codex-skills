# Localhost Port Registry

This file is the shared source of truth for Henry's local project ports. Update it whenever a project is assigned, moved, or split into additional services.

## Assigned Ports

| App / Project | Repo path | Ports | Config / command | Status | Notes | Updated |
| --- | --- | --- | --- | --- | --- | --- |
| cloud-crash-course | `/Users/Henry/Documents/Codex/2026-09-20/giv` | `5847` preview | `python3 -m http.server 5847 --bind 127.0.0.1 --directory outputs` | temporary | Local illustrated HTML guide for this task. | 2026-09-20 |
| deutsch-law | `/Users/Henry/Developer/deutsch-law` | `4927` default, `4928` agent verification, `4929` main preview, `4931` temporary verification | `npm run dev`; agent previews set `DEUTSCH_LAW_DIST_DIR` and an explicit port | active | Agent previews use a separate Next build directory and stop when verification finishes. The 33-page case-guide check finished and released port 4929. | 2026-10-31 |
| deutsch-law analytics | `/Users/Henry/Developer/deutsch-law-analytics` | `4932` production verification | `./node_modules/.bin/next start -H 127.0.0.1 -p 4932` | retired | Analytics verification finished; its production preview on 4932 and enabled QA preview on the project's port 4928 were stopped. | 2026-10-31 |
| deutsch-law archive | `/Users/Henry/Developer/deutsch-law` | `4930` archive viewer | LaunchAgent `com.henry.deutsch-law-archive`; imports `startArchive({ date: '2026-10-17', port: 4930 })` | active | User-requested persistent viewer on `127.0.0.1`; macOS restarts it after exit and starts it at login. Config: `~/Library/LaunchAgents/com.henry.deutsch-law-archive.plist`. | 2026-11-13 |
| finmark-partners | `/Users/Henry/Developer/finmark-partners` | `3089` frontend | `package.json` scripts: `npm run dev`, `npm run start` | active | Next.js static rebuild of finmarkpartners.com. Repo scripts bind to `127.0.0.1:3089`; dev uses `next dev --webpack` to avoid a Turbopack manifest error in this repo. | 2026-08-19 |
| finmark email review | `/Users/Henry/Developer/finmark-partners/output/emails/nsi-resilient-etfs-v4` | `3090` preview | `python3 -m http.server 3090 --bind 127.0.0.1 --directory output/emails/nsi-resilient-etfs-v4` | retired | HTML email layout checks finished; server stopped and port released. | 2026-11-11 |
| finmark NSIC email review | `/Users/Henry/Developer/finmark-emailers` | `6193` preview | `python3 -m http.server 6193 --bind 127.0.0.1 --directory /Users/Henry/Developer/finmark-emailers` | retired | Desktop and mobile verification completed; temporary server stopped. | 2026-11-23 |
| job-helper | `/Users/Henry/Developer/job-helper` | `1285` web, `4178` extension preview | Root `package.json`: `npm run dev`; extension: `npm run dev -- --host 127.0.0.1 --port 4178` | active | Next.js app plus Chrome extension debug preview. | 2026-07-30 |
| my-site | `/Users/Henry/Developer/my-site` | `5173` frontend | `package.json` script: `npm run dev -- --host 127.0.0.1 --port 5173` | active | Vite portfolio site. | 2026-07-03 |
| number-question | `/Users/Henry/Developer/number-question` | `7462` frontend | `package.json` scripts: `npm run dev`, `npm run start` | active | Next.js number request page. Scripts bind to `127.0.0.1:7462`. | 2026-07-06 |
| steam-engine explainer | `/Users/Henry/Documents/Codex/2026-11-21/inst` | `6152` preview | `python3 -m http.server 6152 --bind 127.0.0.1 --directory outputs` | retired | Browser verification finished; temporary server stopped. | 2026-11-21 |
| vincent-dunn | `/Users/Henry/Developer/vincent-dunn` | `3100` production verification | `npm run start -- --hostname 127.0.0.1 --port 3100` | retired | Umami verification finished; the temporary server was stopped and port 3100 released. | 2026-11-13 |

## Reserved / Avoid

The persistent `deutsch-law` historical archive reserves `127.0.0.1:4930`.
The standalone `npm run archive:serve` command still selects an OS-assigned
port; use its printed URL for those separate, temporary sessions.

| Port | Reason | Updated |
| --- | --- | --- |
| `3000` | Common default for Next.js and many local apps; avoid assigning as a stable project port when possible. | 2026-06-26 |

## Entry Format

- `Ports`: use labels such as `frontend`, `backend`, `api`, `docs`, `webhook`, or `admin`.
- `Status`: use `active`, `assigned`, `temporary`, `retired`, or `unknown`.
- `Config / command`: name the env variable, config file, package script, or command that controls the port.
