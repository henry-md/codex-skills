# Localhost Port Registry

This file is the shared source of truth for Henry's local project ports. Update it whenever a project is assigned, moved, or split into additional services.

## Assigned Ports

| App / Project | Repo path | Ports | Config / command | Status | Notes | Updated |
| --- | --- | --- | --- | --- | --- | --- |
| deutsch-law | `/Users/Henry/Developer/deutsch-law` | `4927` default, `4929` main preview, `4931` temporary verification | `npm run dev`; verification: `DEUTSCH_LAW_DIST_DIR=.next-main-preview-4931 ./node_modules/.bin/next dev -H 127.0.0.1 -p 4931` | active | Port 4929 was already in use during a 2026-08-21 visual check, so the isolated verification server uses 4931 and its own Next build directory. Port 4928 is held by an unresponsive stale process. | 2026-08-21 |
| finmark-partners | `/Users/Henry/Developer/finmark-partners` | `3089` frontend | `package.json` scripts: `npm run dev`, `npm run start` | active | Next.js static rebuild of finmarkpartners.com. Repo scripts bind to `127.0.0.1:3089`; dev uses `next dev --webpack` to avoid a Turbopack manifest error in this repo. | 2026-08-19 |
| job-helper | `/Users/Henry/Developer/job-helper` | `1285` web, `4178` extension preview | Root `package.json`: `npm run dev`; extension: `npm run dev -- --host 127.0.0.1 --port 4178` | active | Next.js app plus Chrome extension debug preview. | 2026-07-30 |
| my-site | `/Users/Henry/Developer/my-site` | `5173` frontend | `package.json` script: `npm run dev -- --host 127.0.0.1 --port 5173` | active | Vite portfolio site. | 2026-07-03 |
| number-question | `/Users/Henry/Developer/number-question` | `7462` frontend | `package.json` scripts: `npm run dev`, `npm run start` | active | Next.js number request page. Scripts bind to `127.0.0.1:7462`. | 2026-07-06 |
| vincent-dunn | `/Users/Henry/Developer/vincent-dunn` | `3100` frontend | Temporary verification: `npm run start -- -p 3100` | temporary | Clean production render used while the existing user-owned dev server remains on 3000. | 2026-07-28 |

## Reserved / Avoid

| Port | Reason | Updated |
| --- | --- | --- |
| `3000` | Common default for Next.js and many local apps; avoid assigning as a stable project port when possible. | 2026-06-26 |

## Entry Format

- `Ports`: use labels such as `frontend`, `backend`, `api`, `docs`, `webhook`, or `admin`.
- `Status`: use `active`, `assigned`, `temporary`, `retired`, or `unknown`.
- `Config / command`: name the env variable, config file, package script, or command that controls the port.
