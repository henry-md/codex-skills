---
name: ports
description: Maintain my port registry for development. Also contains best-practice-guidance for agents using ports. Use mainly when creating a new project (and assigning a port), or using a port as an agent. Can also use when documenting localhost ports or miscellaneous port-related tasks.
---

# General

Use this skill as the source of truth for Henry's localhost port assignments.

The main point of this skill is to help avoid port conflicts, so that I can work on any/all combinations of projects at the same time without port conflicts. New ports are created by a random number generator and saved to our durable .md file in this skill for memory, and existing valid ports are saved there as well.

Please be proactive with this skill as well — even if not invoked, you may bring up this skill if (1) you know that the port in this project conflicts with another project, or (2) it is a common default port, like 3000 or 5173.

I also want to use this skill as shorthand for the following reminder: agents should not use the default ports for a project (I'm talking about even the randomly generated ones that are hard-coded in the repo that were created with the guidance of this skill) -- these should be reserved for me, the human user. This way, I can always start the port myself, and have it run indefinitely without it being interrupted by an agent. They can use another randomly generated port on the fly, and check for conflicts with other agents.

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
