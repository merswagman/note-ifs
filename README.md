# note-ifs

A small notifications server for Christopher, with a light web UI.

It periodically checks external sources for things worth knowing about and
emails a notification when something changes. The first check is for outdoor
permit availability (recreation.gov); chores and calendar events are planned
next.

## Stack

- **App**: Python + Flask
- **Hosting**: Vercel (Python serverless functions)
- **Scheduling**: a GitHub Actions workflow (`.github/workflows/hourly-check.yml`)
  calls the app hourly — Vercel's own Cron is Hobby-plan-limited to once/day,
  so it isn't used
- **Config**: a JSON file committed to the repo, defining what to watch (permits, later chores/calendar)
- **Runtime state** (last-checked time, already-notified flags): Vercel Blob/KV (not yet built), since Vercel's filesystem is read-only at runtime
- **Delivery**: email (not yet built)

## Status

Live at https://notifs.mersman.dev. Phases 1 (skeleton) and 2 (config schema)
are done; see [PLAN.md](PLAN.md) for the phased implementation plan and
current progress, and [CLAUDE.md](CLAUDE.md) for architecture and working
conventions.

## Quick start

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c "from app import app; app.run(debug=True)"
```

Deploying: `vercel deploy` (preview) or `vercel deploy --prod` (production),
via `npx vercel@latest` if the CLI isn't installed globally.
