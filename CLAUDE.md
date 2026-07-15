# CLAUDE.md

Guidance for working on this repo. Read [PLAN.md](PLAN.md) too — it tracks
current phase and open decisions and should stay in sync with reality.

## What this is

A notifications server: it watches a configured list of things (starting
with outdoor permit availability, later chores and calendar events) and
emails Christopher when something changes. It has a light web UI for viewing
config/status.

## Stack and architecture

- **Language/framework**: Python + Flask.
- **Hosting**: Vercel, using the Python runtime for serverless functions and
  Vercel Cron (`vercel.json` `crons`) to trigger scheduled checks via HTTP
  endpoints.
- **Delivery**: email.

### Storage is split in two, deliberately

Vercel's function filesystem is ephemeral and read-only at runtime — a
plain JSON file in the repo can be *read* by a deployed function but not
durably *written*. So:

- **Config** (what to watch: permit IDs, chore definitions, thresholds) is a
  JSON file **committed to the repo** and edited via commits/PRs, not through
  the UI at runtime. Treat it as the source of truth for "what should be
  checked."
- **Runtime state** (last-checked timestamps, already-notified flags, so we
  don't email the same thing twice) lives in **Vercel Blob or KV**, not in a
  repo file. Any code that needs to remember something between cron
  invocations must go through that store, never `open(..., "w")` on a repo
  path.

When adding a new kind of check, follow this split: static definition in the
committed config, mutable state in Blob/KV.

## Conventions

- Don't invent or guess third-party API endpoints (e.g. recreation.gov) —
  these are undocumented/reverse-engineered and change. Verify against real
  responses (recorded fixtures or a research spike) before committing to an
  endpoint shape, and note the source/assumptions in PLAN.md.
- Secrets (email credentials, Blob/KV tokens) go in Vercel environment
  variables, never in the committed config JSON or in code.
- Keep the config JSON schema documented in PLAN.md as it evolves — it's the
  main "database" of this app, so changes to its shape are architecturally
  significant, not incidental.
- Cron endpoints should verify the Vercel cron secret header before doing
  work (see Vercel Cron docs) — they're just HTTP endpoints otherwise.

## Working conventions for this repo

- This project is planned incrementally via PLAN.md. When a phase's scope
  changes or a decision gets made/revisited, update PLAN.md's decisions log
  and open-questions section in the same change — don't let it drift out of
  date.
- Prefer small, working vertical slices (e.g. "one permit check + one email")
  over building out abstractions for chores/calendar before the permit path
  works end-to-end.
