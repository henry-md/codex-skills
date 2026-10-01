---
name: compare-commits
description: Resolve commits, branches, PRs, or descriptions of changes into exact Git revisions and open their comparison in a temporary editor project using goto. Use for requests such as comparing two commits, an unmerged PR with main, or before and after a particular fix.
---

# Compare Commits

Turn the user's requested comparison into the correct left and right snapshots,
then open them with the existing `goto` command. Finding hashes is part of the job;
do not ask the user for hashes that repository history or PR evidence can identify.

## Resolve the intended comparison

Use the repository named by the user or established in the conversation. Confirm
its root and remotes; a projectless chat's working directory is not automatically
the target. Keep the source checkout on its current branch, including dirty work.

Resolve conceptual descriptions with focused evidence: commit subjects and
patches, branch history, changed file paths, or the named PR's metadata and commit
list. Useful searches include `git log --all --grep`, `git log -S`, and
`git log -G`; confirm a candidate's patch instead of relying only on its title.

- Two specified endpoints: preserve their order, even across branches, reversed
  chronology, unrelated histories, or identical commits. Use the exact snapshots,
  not a merge base or three-dot PR diff.
- "Before and after this fix": identify the actual change. For one commit, use
  its parent on the left and the change commit on the right. For a multi-commit
  change, identify both boundaries from evidence.
- "Feature/PR versus main": use main as the baseline on the left unless the user
  specifies another direction. Distinguish explicit local `main` from "latest
  main on GitHub"; refresh the appropriate remote ref for a current remote request.
- Unmerged PR commits work normally once their objects exist locally. For a
  GitHub PR, inspect the correct repository's PR metadata and commits (through
  `gh` or an available GitHub connector). Fetch only the needed refs, without
  checking out or merging the PR. A GitHub PR head can be fetched with
  `git fetch REMOTE refs/pull/NUMBER/head`; immediately resolve `FETCH_HEAD`
  to its full commit hash. Use the PR head, not GitHub's synthetic PR merge ref.
- A commit that "landed on main" may differ from its original PR hash after squash
  or rebase. Inspect the merge result and main history to select what the user
  means, and verify ancestry when asserting a commit is on main.

Validate each endpoint with `git rev-parse --verify --end-of-options "REF^{commit}"`
and pin full hashes before opening. Do not silently replace missing historical PR
commits with the current PR head. If fetch/access fails, report the specific
missing revision. When multiple materially different changes or repositories fit
after investigation, ask one focused clarification with the plausible candidates.

State the repository and the chosen left/right hashes with their subjects or
conceptual labels before running `goto`. Proceed without another approval when
the request is clear. For an initial commit with no parent, use `goto SHA` to get
its empty-tree baseline; for a merge's before/after view, use its first parent
unless the user specifies another parent.

## Open with the existing command

Locate the installed `goto.zsh`: on this Mac it is
`$HOME/Developer/.config/zsh/functions/goto.zsh`; the configured
`$HOME/.config/zsh/functions/goto.zsh` may be a symlink to it.
If unavailable, report the missing dependency rather than creating a replacement.

Use `goto` itself; do not duplicate its repository creation, metadata, editor
detection, or cleanup implementation. It is a zsh function, so source its file
in the same shell that invokes it. Pass paths and resolved hashes as positional
arguments rather than interpolating the user's prose into executable shell text:

```zsh
/bin/zsh -f -c '
  source "$1" || exit
  cd -- "$2" || exit
  goto "$3" "$4"
' compare-commits "$goto_file" "$repo_root" "$left_sha" "$right_sha"
```

Run from the source repo. Do not create Git worktrees, switch its branch, stash its
changes, or commit/push as part of a comparison. Necessary fetches may update local
remote refs and Git objects; they do not authorize remote writes. Review creation
does not install project dependencies.

## Verify and hand off

Read the generated review path. Check that the temporary repo's HEAD is the
chosen left commit and its index tree matches the chosen right commit's tree;
the exact comparison appears under **Staged Changes**. The single-root-commit
case has a generated empty baseline. Preserve any existing source edits.

When computer use is available, inspect the opened editor's Source Control view
and a representative changed file. Only claim visual verification when the
requested comparison is visibly present. Otherwise distinguish Git verification
and the editor-launch result from unverified rendering. If the editor fails to
open but the review exists, return its usable path and the specific launch error.

Finish with the two selected commits, why they match the request, and where the
comparison opened. Reviews record their creation time; hourly cleanup, when
installed for their review root, removes them at 24 hours or older (normally
24–25 hours while the Mac is awake). Do not promise scheduled cleanup for an
overridden `GOTO_REVIEW_ROOT` without verifying that cron targets it.
If cleanup is requested, call `clear-goto` with the matching review root,
which uses the same script as cron and prints `X repos cleared`; do not install
or alter scheduled jobs as an incidental part of comparing commits.
