# PLAN.md

Living implementation plan for note-ifs. Update this alongside the code —
it's the single place to see what's decided, what's next, and what's still
open.

## Current phase

**Phase 0: Docs/scaffolding** — in progress. README/CLAUDE.md/PLAN.md written;
no application code yet.

## Decisions log

| Date | Decision | Why |
|------|----------|-----|
| 2026-07-14 | Python + Flask | User preference. |
| 2026-07-14 | Host on Vercel | User wants Vercel; Flask runs there via the Python runtime. |
| 2026-07-14 | Email for delivery | User preference; simplest reliable channel to start. |
| 2026-07-14 | First check: recreation.gov permits | User's starting use case. |
| 2026-07-14 | Config = JSON file committed to repo; runtime state = Vercel Blob/KV | Vercel's filesystem is read-only at runtime, so a repo JSON file can't hold mutable "already notified" state. Splitting static config from mutable state keeps the "JSON database" mental model while actually working on Vercel. |

## Phases

### Phase 1: Skeleton
- [ ] Flask app scaffolded for Vercel's Python runtime (`api/index.py` or
      equivalent entrypoint + `vercel.json`).
- [ ] `requirements.txt` with Flask pinned.
- [ ] One page of light UI: static status page (even just "it's alive" +
      current config summary).
- [ ] One HTTP endpoint intended for Vercel Cron to hit, protected by the
      cron secret header, that currently no-ops.
- [ ] `vercel.json` `crons` entry wired to that endpoint on a sane interval
      (e.g. every few hours — permit availability doesn't need minute-level
      polling).
- [ ] Deployed to Vercel and confirmed reachable.

### Phase 2: Config schema
- [ ] Define `config.json` shape for a "watch" — at minimum: id, type
      (`permit` initially), human label, source-specific params, enabled
      flag.
- [ ] Document the schema here once it's settled (replace this bullet with
      the actual schema/example).
- [ ] Loader that reads and validates `config.json` at request/cron time.

### Phase 3: Email delivery
- [ ] Choose email path: SMTP with env-var credentials vs. a transactional
      API (e.g. Resend/SendGrid). **Open question — see below.**
- [ ] `send_notification(subject, body)` helper, reads credentials from
      Vercel env vars.
- [ ] Manual test send before wiring to real checks.

### Phase 4: recreation.gov permit checker
- [ ] Research spike: confirm the actual recreation.gov endpoint(s)/response
      shape for permit availability (undocumented API — verify against real
      traffic, don't assume). Record findings here.
- [ ] Implement a checker for one configured permit: fetch availability,
      compare against last-known state, return "changed: yes/no" + details.
- [ ] Wire checker → state store (Phase 5) → email (Phase 3) → cron endpoint
      (Phase 1).
- [ ] Confirm end-to-end with a real permit ID that has some availability
      signal to test against.

### Phase 5: Runtime state persistence
- [ ] Pick primitive: Vercel Blob (simple JSON blob mirroring config shape)
      vs. Vercel KV/Upstash Redis (better for per-watch key lookups). Default
      assumption: start with Blob for simplicity, revisit if per-key access
      patterns get awkward.
- [ ] Read/write helpers for "last checked" + "last notified state" per
      watch id.

### Phase 6: Light UI, read side
- [ ] Show configured watches and their last-checked/last-notified state.
- [ ] No editing through the UI yet (config stays git-committed per the
      storage split above).
- [ ] Decide whether the UI needs auth (it'll be a public Vercel URL by
      default). **Open question — see below.**

### Phase 7: Extend beyond permits
- [ ] Chores: define what a "chore" watch looks like (recurring reminder on
      a schedule vs. state-based like permits). Likely a different `type` in
      the same config schema.
- [ ] Calendar events: source TBD (Google Calendar API? ICS feed?). Decide
      auth model for pulling calendar data.
- [ ] Generalize the checker interface if the permit-specific one doesn't
      already fit (only do this once there are 2+ real check types, not
      preemptively).

## Open questions

- **Email provider**: SMTP + env-var creds, or a transactional email API?
  Affects Phase 3 implementation and required env vars.
- **UI auth**: does the light UI need a login/shared secret, or is it fine
  as an unauthenticated Vercel URL (security through obscurity)? Matters
  once it shows real config/state.
- **recreation.gov specifics**: which permit(s)/park(s) to watch first, and
  the exact endpoint shape — needs a research spike in Phase 4, not a guess.
- **Chores model**: are chores time-based reminders (e.g. "every Tuesday")
  or state-based (e.g. "bin day, check if already marked done")? Affects
  whether the Phase 2 schema needs a `schedule` field now or later.
- **Calendar source**: which calendar (Google, iCloud, other) and how it
  authenticates.
