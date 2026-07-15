# note-ifs

A small notifications server for Christopher, with a light web UI.

It periodically checks external sources for things worth knowing about and
emails a notification when something changes. The first check is for outdoor
permit availability (recreation.gov); chores and calendar events are planned
next.

## Stack

- **App**: Python + Flask
- **Hosting**: Vercel (Python serverless functions, Vercel Cron for scheduled checks)
- **Config**: a JSON file committed to the repo, defining what to watch (permits, later chores/calendar)
- **Runtime state** (last-checked time, already-notified flags): Vercel Blob/KV, since Vercel's filesystem is read-only at runtime
- **Delivery**: email

## Status

This project is in early planning/scaffolding. See [PLAN.md](PLAN.md) for the
phased implementation plan and current progress, and [CLAUDE.md](CLAUDE.md)
for architecture and working conventions.

## Quick start

Not yet runnable — see PLAN.md Phase 1 for the first working skeleton.
