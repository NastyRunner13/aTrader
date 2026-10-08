# Contributing to aTrader

Keep changes focused, evidence-linked, and reproducible. Read [README.md](README.md)
for setup and [ROADMAP.md](ROADMAP.md) for current capabilities and planned work.

## Branch structure

`main` is the stable integration branch. Start new work from an up-to-date `main`
and open a pull request back to it. Direct commits to `main` should be limited to
explicitly agreed maintenance or documentation changes.

Use lowercase, hyphen-separated descriptions:

```text
<type>/<short-description>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, and `perf`. Include an
issue number when one exists, for example `feat/123-institutional-context`.
Examples: `fix/announcement-coverage`, `docs/contribution-guide`, and
`feat/investor-research`. Use the same structure for human- and agent-created branches.

```powershell
git switch main
git pull --ff-only origin main
git switch -c feat/investor-research
```

Use one branch per coherent change. Avoid mixing unrelated cleanup into feature
work. Never force-push `main`; coordinate before rewriting a shared feature branch.

## Commit structure

Use Conventional Commits:

```text
<type>(<optional-scope>): <imperative summary>

<optional body: why this change is needed and relevant tradeoffs>

<optional footer: issue references or breaking-change details>
```

Use the branch types above; `build` and `ci` are also valid commit types. Keep the
summary concise (aim for 72 characters), use the imperative mood, and omit the
trailing period. Scopes should name an area such as `data`, `analytics`, `agents`,
`api`, or `web`.

Examples:

```text
feat(data): collect institutional market activity
fix(analytics): remove single-quarter PEG scoring
docs: add contribution and branch conventions
```

For incompatible public contract changes, add `!` after the type/scope and explain
the migration in a `BREAKING CHANGE:` footer. Reference issues with `Refs #123` or
`Closes #123` when applicable. Commit only files relevant to the change; review the
staged diff before committing. Never commit credentials, `.env`, runtime databases,
caches, or generated research reports.

## Implementation expectations

- Keep calculations and scoring deterministic; agents explain cited evidence.
- Preserve source, publication date, period, units, and calculation inputs.
- Treat missing evidence as missing, not as zero or an invented estimate.
- Keep statement bases, data scopes, and provisional/confirmed series distinct.
- Add regression tests for changed behavior and fixtures for provider parsing.
- Document limitations and update the roadmap when a capability changes.
- Prefer small changes that fit existing modules over speculative abstractions.

## Validation

Install dependencies using the README. From the repository root, run the relevant
checks before opening a pull request:

```powershell
uv run pytest -m "not network"
uv run ruff check src tests
uv run mypy src
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

Backend changes need the backend checks; frontend changes need the frontend checks.
Documentation-only changes need a diff and link review. Do not use paid model calls
or live services for routine tests. If API contracts change, regenerate and commit
the schema and frontend types, then run both sets of checks:

```powershell
uv run atrader openapi apps/web/openapi.json
npm --prefix apps/web run types
```

## Pull requests

Use a Conventional Commit-style title. Explain the problem, resulting behavior,
validation performed, and material limitations. Include screenshots for visible UI
changes and migration notes for incompatible contracts. Keep the branch current
with `main`, address review feedback, and ensure required checks pass before merging.
Prefer a squash merge with a meaningful Conventional Commit message; remove merged
feature branches when they are no longer needed.
