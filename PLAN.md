# PLAN.md

Living implementation plan for note-ifs. Update this alongside the code —
it's the single place to see what's decided, what's next, and what's still
open.

## Current phase

**Phase 3: Email delivery** — in progress. `notifier.py`'s
`send_notification()` (Gmail SMTP) and `send_test_email.py` are written and
the missing-credentials error path is verified. Blocked on Christopher
generating a Gmail app password and setting `SMTP_USERNAME`/`SMTP_PASSWORD`
(locally + in Vercel) — see Phase 3 checklist for exact steps. Not yet
deployed (no app.py changes this phase, so no redeploy needed yet).

Phase 1 remaining loose end: confirm Vercel's GitHub App has
deploy-on-push access (not yet needed, since deploys so far are manual
`vercel deploy`).

## Decisions log

| Date | Decision | Why |
|------|----------|-----|
| 2026-07-14 | Python + Flask | User preference. |
| 2026-07-14 | Host on Vercel | User wants Vercel; Flask runs there via the Python runtime. |
| 2026-07-14 | Email for delivery | User preference; simplest reliable channel to start. |
| 2026-07-14 | First check: recreation.gov permits | User's starting use case. |
| 2026-07-14 | Config = JSON file committed to repo; runtime state = Vercel Blob/KV | Vercel's filesystem is read-only at runtime, so a repo JSON file can't hold mutable "already notified" state. Splitting static config from mutable state keeps the "JSON database" mental model while actually working on Vercel. |
| 2026-07-14 | Entrypoint is root `app.py` with a top-level `app` Flask instance; no `builds`/`routes` in `vercel.json` | Confirmed against current Vercel docs (fetched during Phase 1): Vercel auto-detects Flask from `requirements.txt` + a supported entrypoint filename (`app.py`, `index.py`, `server.py`, `main.py`, `wsgi.py`, `asgi.py`, or the same under `src/`/`app/`/`api/`). The whole app deploys as one Vercel Function. |
| 2026-07-14 | Cron schedule is daily (`0 13 * * *`), not every 6 hours | Hobby-plan Vercel accounts only allow cron jobs that run once per day — a `0 */6 * * *` schedule made every deploy fail instantly with `deploy_failed`, which is what caused the "error for a second, no deploy visible" symptom the user hit. Superseded same day — see next entry. |
| 2026-07-14 | Scheduling moved entirely to a GitHub Actions workflow (`.github/workflows/hourly-check.yml`, hourly), `vercel.json`'s `crons` block removed | User wants hourly checks; Hobby-plan Vercel Cron can't go below daily and Vercel's Workflow DevKit (which could durably `sleep()` around the limit) is TypeScript/Node-only, not usable from this Flask/Python app. GitHub Actions is free, needs no new language/service, and avoids two schedulers hitting the same endpoint. Tradeoff: GitHub disables scheduled workflows after 60 days of repo inactivity, and timing can drift a few minutes under GitHub's load — acceptable for a permit check. |
| 2026-07-15 | Config schema versioned (`version: 1`), validated by hand-rolled `config_schema.py` instead of pydantic/jsonschema | The shape is simple (one envelope + one known type so far), so a dependency wasn't justified. A `version` field is cheap now and avoids a painful migration later once chores/calendar (Phase 7) add real fields. Validation raises with *all* problems found, since this file is meant to be hand-edited by Christopher, not just machine-generated. |
| 2026-07-15 | Canonical URL is `https://notifs.mersman.dev`, not `note-ifs.vercel.app` | Christopher added a custom domain in the Vercel dashboard (matching his other projects' `*.mersman.dev` pattern) between deploys. It became the primary alias and `note-ifs.vercel.app` stopped resolving (404) — caught because the GitHub Actions workflow was still hardcoded to the old URL and would have started failing hourly. Updated `.github/workflows/hourly-check.yml` and this doc; if the domain changes again, grep the repo for the old one before assuming it still works. |
| 2026-07-15 | Email via Gmail SMTP (app password), not a transactional API | User preference — reuses an existing Gmail account, no new service signup. Uses stdlib `smtplib`, so no new dependency. Tradeoff accepted: Gmail SMTP is slightly more failure-prone for automated senders than a dedicated transactional API (occasional login flags), acceptable for low-volume personal notifications. |

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
- [x] ~~`vercel.json` `crons` entry wired to `/api/cron/check` every 6
      hours~~ — superseded: Hobby-plan Vercel Cron can't run more than
      once/day, so scheduling moved entirely to GitHub Actions instead (see
      decisions log).
- [x] Verified locally with Flask's test client (`/` and `/api/cron/check`
      both return 200).
- [x] Deployed to Vercel and confirmed reachable: https://notifs.mersman.dev
      (custom domain; the default `note-ifs.vercel.app` stopped resolving
      once this was set up as the primary alias — see 2026-07-15 decisions
      log entry)
      — both `/` and `/api/cron/check` return 200 in production.
- [x] `CRON_SECRET` set by Christopher in both Vercel (Production env var)
      and GitHub Actions repo secrets — confirmed enforced: unauthenticated
      requests to `/api/cron/check` now 401, and a manual
      `workflow_dispatch` run of the Actions workflow got back
      `{"ok":true,...}` using the real secret, end-to-end.
- [x] Hourly scheduling confirmed live: `.github/workflows/hourly-check.yml`
      is registered and active on GitHub (`17 * * * *` + manual
      `workflow_dispatch`), verified via a real triggered run.
- [ ] Confirm the Vercel GitHub App actually has install access to
      `merswagman/note-ifs` (Vercel dashboard → Settings → Git, or GitHub →
      Settings → Applications → Vercel). The project's Git connection is
      registered, but no deployment was ever auto-triggered by a push in
      this session — deploys so far were all manual (`vercel deploy`).
      Confirm auto-deploy on push works before relying on it.

### Phase 2: Config schema — complete
- [x] Schema settled (v1), documented here:
  ```json
  {
    "version": 1,
    "watches": [
      {
        "id": "lowercase-hyphenated-slug",
        "type": "permit",
        "label": "human-readable name",
        "enabled": true,
        "params": { "source": "recreation.gov", "permit_id": "..." }
      }
    ]
  }
  ```
  Every watch needs `id` (unique, `^[a-z0-9]+(-[a-z0-9]+)*$`), `type` (must
  be in `config_schema.KNOWN_WATCH_TYPES` — currently only `"permit"`;
  extend that set, not this doc, when chores/calendar land in Phase 7),
  `label`, `enabled` (bool), and a type-specific `params` object. For
  `type: "permit"`, `params.source` must be in
  `config_schema.KNOWN_PERMIT_SOURCES` (currently only `"recreation.gov"`)
  and `params.permit_id` must be a non-empty string — exact meaning of
  "permit_id" (facility ID vs. permit ID vs. something else) is still TBD
  pending Phase 4's research spike; the field exists as a placeholder slot.
- [x] Validation lives in `config_schema.py` (`validate_config`,
      `load_config`) — hand-rolled rather than a dependency like pydantic,
      since the shape is simple. Raises `ConfigError` with every problem
      found (not just the first), so a hand-edited config shows all issues
      at once. Verified against 6 malformed-config cases (missing version,
      wrong type for `watches`, bad id format, duplicate id, unknown watch
      type, unknown permit source/empty permit_id) — all rejected with
      correct, specific messages.
- [x] `app.py` now catches `ConfigError` at both routes (`/` renders a 500
      with the error text; `/api/cron/check` returns
      `{"error": ...}, 500`) instead of an unhandled exception — config
      loading is a system boundary per CLAUDE.md conventions.

### Phase 3: Email delivery
- [x] Email path: Gmail SMTP with an app password, not a transactional API.
      User preference — no new service signup, reuses an existing Gmail
      account. Uses Python's stdlib `smtplib`/`ssl`/`email.message`, so no
      new dependency in `requirements.txt`.
- [x] `send_notification(subject, body)` helper in `notifier.py`. Reads
      `SMTP_HOST` (default `smtp.gmail.com`), `SMTP_PORT` (default `465`,
      SSL), `SMTP_USERNAME`/`SMTP_PASSWORD` (required, no defaults —
      raises `EmailConfigError` if unset), and `NOTIFY_EMAIL_TO` (optional,
      defaults to sending to `SMTP_USERNAME` itself). Verified the
      missing-credentials path fails cleanly (`EmailConfigError`, not a
      raw exception) via `send_test_email.py` with no env vars set.
- [ ] **User action needed to finish this phase**: generate a Gmail app
      password (Google Account → Security → 2-Step Verification → App
      passwords; requires 2FA enabled) and set `SMTP_USERNAME` (the Gmail
      address) + `SMTP_PASSWORD` (the app password) — locally (for testing)
      and in Vercel's Production env vars (for real use). Same convention as
      `CRON_SECRET`: Christopher sets credentials himself, Claude only
      references them by name.
- [ ] Manual test send with real credentials, once set — not done yet.
- [ ] Not wired into `/api/cron/check` yet — that's Phase 4's job (checker →
      state store → email → cron endpoint).

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
