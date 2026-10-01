---
name: today
description: Review my unfinished Linear assignments and recent Slack directives, group remaining work for every project in my editable roster, and suggest three next steps per project. Use when I invoke /today or ask what to work on today.
---

# Today

Read [projects.md](projects.md) on every run. It records the projects Henry currently belongs to. Use it to guide Slack searches and organize the brief, but inspect **all** unfinished Linear issues assigned to him. Put assignments outside the roster under `Other assigned work`; do not infer project membership from a ticket or mention. Edit the roster when Henry explicitly adds, leaves, or renames a project.

Use live Linear and Slack data and the current date in Henry's timezone. Query the selected connectors headlessly when authenticated. A configured CLI is also suitable if it covers the same workspace and its data is current. If a required connection needs reauthentication, tell Henry to sign in and defer the full brief. Do not use a desktop app or browser UI as an authentication fallback.

1. Identify the connected Linear user and page through their assigned issues. Exclude completed, canceled, and duplicate issues. Account for the entire unfinished set by grouping issues within each roster project into a few meaningful workstream or outcome buckets. Give each bucket a count and issue links or compact IDs; distinguish work in progress or review from ready, blocked, and backlog work. Inspect due dates, issue priority, dependencies, and recent updates where they affect the grouping or next steps. Do not describe every assigned issue as active work.
2. Search at least the past 14 days of Slack DMs, mentions, participating threads, and channels relevant to the roster and candidate issues. Follow promising threads through later replies. Add concrete requests or commitments directed at Henry that still appear open to the relevant buckets; call out requests without a matching ticket separately. Distinguish them from ideas, general announcements, and requests later completed, withdrawn, or corrected. Extend the lookback when an older unresolved request is relevant. Do not reproduce credentials or unrelated private messages in the brief.
3. For **each project in the roster**, suggest the next three specific things Henry should work on, using deadlines, commitments, blockers, dependencies, issue priority, and current momentum to order actions *within that project*. Give a concrete next move and brief reason for each. If fewer than three actions are supported, list only those and say why. Do not select a main project, merge projects into a global top three, or rank one project against another.

Respond in chat with each project's remaining-work buckets and three next steps, followed by any untracked Slack directives or out-of-roster assignments. Keep the coverage check visible so no unfinished assignment silently disappears. Link the supporting Linear issues and Slack messages; give the Slack lookback and source freshness. Name unavailable or partial sources rather than interpreting missing results as no work. This briefing is read-only in Linear and Slack.
