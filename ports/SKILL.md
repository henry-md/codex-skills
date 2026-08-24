---
name: ports
description: Maintain Henry's local development port registry. Use when assigning, checking, changing, or documenting localhost ports for projects/apps, especially when starting dev servers, avoiding conflicts between multiple local projects, or reconfiguring frontend/backend ports.
---

# Ports

Use this skill as the source of truth for Henry's localhost port assignments.

## Registry

Read [references/ports.md](references/ports.md) before choosing or changing any localhost port.

The registry maps each app/project to one or more ports. Some projects have a single frontend port; others have frontend, backend/API, database UI, worker dashboard, or webhook listener ports.

## Workflow

1. Identify the app/project from the current repo path, package name, or user request.
2. Read `references/ports.md`.
3. If the app already has an assigned port, prefer that port.
4. Before starting a server, check whether the assigned port is currently listening.
   - Use `lsof -nP -iTCP:<port> -sTCP:LISTEN` on macOS.
   - If checking several ports, `lsof -nP -iTCP -sTCP:LISTEN` is fine.
5. If the assigned port conflicts with a different app, choose a free unassigned port and update the registry.
6. If the project config hardcodes a conflicting port, reconfigure the project to use its assigned registry port when that is within the user's request.
7. Start or restart the server on the chosen port and verify with a simple request such as `curl -I http://127.0.0.1:<port>/`.
8. Update `references/ports.md` whenever a new assignment is made, a conflict is resolved, or an app's port changes.

## Assignment Rules

- Prefer four-digit ports for web apps unless the app has a strong convention.
- Do not reuse a port already assigned to another active project.
- Keep frontend and backend ports separate in the registry.
- Record the repo path so future Codex runs can identify the project quickly.
- Record any config/env file that controls the port when known.
- If a port is only temporary for one session, mark it as temporary instead of replacing a stable assignment.

## Updating The Registry

Use `apply_patch` for registry edits.

Keep entries sorted by app/project name. Preserve concise notes that explain why a port exists or what command uses it.
