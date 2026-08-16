# Issue tracker: GitHub

Issues and PRDs for this project live as GitHub issues on **TAGOOZ/PharmaTag**, which is also the code repo (the `testTLS/` workspace is its clone). Use the `gh` CLI for all operations; pass `--repo TAGOOZ/PharmaTag` explicitly so commands work regardless of current directory.

## Conventions

- **Create an issue**: `gh issue create --repo TAGOOZ/PharmaTag --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --repo TAGOOZ/PharmaTag --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --repo TAGOOZ/PharmaTag --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --repo TAGOOZ/PharmaTag --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --repo TAGOOZ/PharmaTag --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --repo TAGOOZ/PharmaTag --comment "..."`

## When a skill says "publish to the issue tracker"

Create a GitHub issue with `gh issue create --repo TAGOOZ/PharmaTag`.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --repo TAGOOZ/PharmaTag --comments`.