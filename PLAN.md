# PLAN.md

Living implementation plan for note-ifs. Update this alongside the code —
it's the single place to see what's decided, what's next, and what's still
open.

## Current phase

**Phase 1: Skeleton** — basic Flask app, status page, and cron stub exist
and run locally; not yet deployed to Vercel.

## Decisions log

| Date | Decision | Why |
|------|----------|-----|
| 2026-07-14 | Python + Flask | User preference. |
| 2026-07-14 | Host on Vercel | User wants Vercel; Flask runs there via the Python runtime. |
| 2026-07-14 | Email for delivery | User preference; simplest reliable channel to start. |
| 2026-07-14 | First check: recreation.gov permits | User's starting use case. |
| 2026-07-14 | Config = JSON file committed to repo; runtime state = Vercel Blob/KV | Vercel's filesystem is read-only at runtime, so a repo JSON file can't hold mutable "already notified" state. Splitting static config from mutable state keeps the "JSON database" mental model while actually working on Vercel. |
| 2026-07-14 | Entrypoint is root `app.py` with a top-level `app` Flask instance; no `builds`/`routes` in `vercel.json` | Confirmed against current Vercel docs (fetched during Phase 1): Vercel auto-detects Flask from `requirements.txt` + a supported entrypoint filename (`app.py`, `index.py`, `server.py`, `main.py`, `wsgi.py`, `asgi.py`, or the same under `src/`/`app/`/`api/`). The whole app deploys as one Vercel Function. |
| 2026-07-14 | Cron schedule is daily (`0 13 * * *`), not every 6 hours | Hobby-plan Vercel accounts only allow cron jobs that run once per day — a `0 */6 * * *` schedule made every deploy fail instantly with `deploy_failed`, which is what caused the "error for a second, no deploy visible" symptom the user hit. Revisit if the account moves to Pro and more frequent permit checks are wanted. |

## Phases

### Phase 1: Skeleton
- [x] Flask app scaffolded for Vercel's Python runtime: `app.py` at repo
      root defines the `app` Flask instance (Vercel's supported entrypoint
      convention — confirmed against current Vercel docs, no legacy
      `builds`/`routes` needed).
- [x] `requirements.txt` with Flask pinned.
- [x] One page of light UI at `/`: status page listing configured watches
      from `config/config.json`.
- [x] `/api/cron/check` endpoint, checks `Authorization: Bearer <CRON_SECRET>`
      when `CRON_SECRET` is set, currently just reports it ran (no real
      checks yet — that's Phase 4).
- [x] `vercel.json` `crons` entry wired to `/api/cron/check` every 6 hours.
- [x] Verified locally with Flask's test client (`/` and `/api/cron/check`
      both return 200).
- [x] Deployed to Vercel and confirmed reachable: https://note-ifs.vercel.app
      — both `/` and `/api/cron/check` return 200 in production.
- [ ] Set a `CRON_SECRET` env var in the Vercel project. Right now
      `/api/cron/check` has no secret configured, so the auth check in
      `app.py` is a no-op and the endpoint is open to anyone — fine while it
      only reports "ran", but must be set before Phase 4 makes it do real
      work.
- [ ] Confirm the Vercel GitHub App actually has install access to
      `merswagman/note-ifs` (Vercel dashboard → Settings → Git, or GitHub →
      Settings → Applications → Vercel). The project's Git connection is
      registered, but no deployment was ever auto-triggered by a push in
      this session — deploys so far were all manual (`vercel deploy`).
      Confirm auto-deploy on push works before relying on it.

### Phase 2: Config schema
- [x] Draft shape in place at `config/config.json`: a `watches` array of
      `{id, type, label, enabled, params}`, with one disabled placeholder
      entry (`type: "permit"`, `params.source: "recreation.gov"`). Not yet
      validated against a real permit — placeholder only.
- [ ] Firm up the schema once Phase 4's research spike shows what params a
      real recreation.gov permit watch actually needs.
- [ ] Add schema validation (reject malformed `config.json` at load time
      instead of failing deep in a request) — currently `load_config()` in
      `app.py` does a bare `json.load` with no validation.

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
