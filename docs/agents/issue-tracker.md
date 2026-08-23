# Issue tracker: GitHub

Issues and PRDs for this project live as GitHub issues on **TAGOOZ/PharmaTag**, which is also the code repo (the `testTLS/` workspace is its clone). Use the `gh` CLI for all operations; pass `--repo TAGOOZ/PharmaTag` explicitly so commands work regardless of current directory.

## Conventions

- **Create an issue**: `gh issue create --repo TAGOOZ/PharmaTag --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: use the **REST API, not `gh issue view`** — the GraphQL path breaks on this repo ("Projects (classic) is being deprecated"):
  `gh api repos/TAGOOZ/PharmaTag/issues/<number> --jq '{title, state, labels: [.labels[].name], body}'`.
  Comments: `gh api repos/TAGOOZ/PharmaTag/issues/<number>/comments --jq '.[] | .body'`. Post via `gh api .../comments -f body="..."`.
- **List issues**: `gh api "repos/TAGOOZ/PharmaTag/issues?state=open&per_page=100" --jq '.[] | select(.pull_request == null) | "#\(.number) \(.title) [\([.labels[].name] | join(","))]"'` (add `&labels=` to filter; REST returns PRs too, hence the select).
- **Comment on an issue**: `gh issue comment <number> --repo TAGOOZ/PharmaTag --body "..."`, or the REST form above for full control.
- **Apply / remove labels**: `gh api repos/TAGOOZ/PharmaTag/issues/<number> -X PATCH -f 'labels[]=...'` or `gh issue edit <number> --repo TAGOOZ/PharmaTag --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --repo TAGOOZ/PharmaTag --comment "..."`, or REST: `gh api repos/TAGOOZ/PharmaTag/issues/<number> -X PATCH -f state=closed` after posting the close comment — close the ticket when its acceptance criteria are implemented AND verified (both twins green where relevant), with a comment summarizing what was done and referencing the commit. Also remove the `ready-for-agent` label so it isn't re-grabbed. Don't close on "written but not verified".
- **Edge-case pass (required before close)**: after the ACs are green, run an explicit edge-case pass on the ticket's deliverable before closing. Enumerate the slice's edge cases and cover the important ones with tests; fix whatever the tests expose:
  - data: empty result set, missing/null fields, duplicates, boundary values, deleted/inactive rows;
  - auth/permission: unauthenticated, wrong/expired token, insufficient `permission_level` / granular permission, cross-branch access;
  - connectivity: offline/disconnected (desktop SQLite must still work), API down, CORS origin, timeouts;
  - money/stock (when the slice touches them): exact-decimal rounding, zero/negative qty, insufficient stock, concurrent updates (`FOR UPDATE`), audit + outbox rows written atomically, idempotent replay (LWW), day-close reversal;
  - UI: empty states, RTL, light/dark theme, keyboard focus, a11y basics.
  For pure-shell / UI-only / no-logic tickets the pass is lighter but still covers empty states, RTL, theme, and a11y. List the edge cases covered in the close comment.

## When a skill says "publish to the issue tracker"

Create a GitHub issue with `gh issue create --repo TAGOOZ/PharmaTag`.

## When a skill says "fetch the relevant ticket"

Use the REST API (NOT `gh issue view` — GraphQL breaks on this repo):
`gh api repos/TAGOOZ/PharmaTag/issues/<number> --jq '{title, state, labels: [.labels[].name], body}'`
and `gh api repos/TAGOOZ/PharmaTag/issues/<number>/comments` for the discussion.