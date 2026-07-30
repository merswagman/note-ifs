# PLAN.md

Living implementation plan for note-ifs. Update this alongside the code —
it's the single place to see what's decided, what's next, and what's still
open.

## Current phase

**Phase 4 (checker) and Phase 6 (UI, visual pass)** — both in good shape.
Phase 4 is complete and deployed: emails include a direct recreation.gov
booking link per available date, verified in a real received email. Phase
6 got a restyled status page (cards, light/dark, next-check time) verified
by screenshotting the Flask dev server with headless Chromium — not yet
redeployed to Vercel. Do that next. Phase 5 (state persistence) remains on
hold by explicit user choice.

**Phase 8 (multi-recipient / second user)** deployed 2026-07-27, bug fixed
2026-07-30. A friend gets his own watch emailed to his own address
(`notify_to`), covering 4 campgrounds via a new `campground` watch type +
`campground_checker.py`. Found and fixed a real correctness bug the day
after go-live: the checker treated each requested date as an independent
"is anything open anywhere" check, so it flagged campgrounds as available
based on scattered single-night openings (mostly Sunday checkout gaps)
that never actually covered his full requested stay — no site was ever
open for *both* nights he needed. Rewritten to require every date in a
watch's `dates` list to be free on the *same* site before it counts as a
hit (a real "book a trip" semantics, not "any night, any site"). Verified
against live data both ways (correctly empty for the actually-booked-out
8/7–8/8, correctly non-empty for a known-open multi-night stretch). See
Phase 8 section and its 2026-07-30 decisions log entry for detail.

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
| 2026-07-15 | recreation.gov availability endpoint confirmed as `/api/permititinerary/{permit_id}/division/{division_id}/availability/month` | Found via Phase 4's research spike (grepping the permit page's JS bundle), not assumed — see Phase 4 section for the full contract, User-Agent gotcha, and the Capitol Lake multi-division finding. |
| 2026-07-15 | Config schema bumped v1 → v2: `permit` params gained required `division_ids` and `dates` | The v1 shape (just `permit_id`) couldn't express which zone/date to check — discovered once the research spike showed a permit has multiple independently-quota'd divisions. Real breaking change to the only existing config entry, which was rewritten (not migrated) since there's a single user and no back-compat need. |
| 2026-07-15 | Added `requests` as a dependency | `permit_checker.py` needs custom headers (User-Agent workaround) and clean error handling against recreation.gov; stdlib `urllib` would work but be noticeably more verbose for this. First non-Flask dependency in the project. |
| 2026-07-15 | Phase 5 (dedup/state persistence) deliberately skipped for now; checker wired straight to email | User's explicit call: "we can hold off on the persistence... I think I want to be spammed by it for now. (but only email me when there's availability and not when there's not)." So `/api/cron/check` re-checks and re-emails every hour availability persists, with no memory of previous runs. Revisit Phase 5 only if this becomes annoying in practice. |
| 2026-07-15 | Status page shows a computed "next check" time, not a tracked "last checked" time | A real last-checked timestamp needs persisted state (same blocker as Phase 5, still on hold); the next scheduled run is fully derivable from the known GitHub Actions cron schedule (`17 * * * *`) with no storage needed. Must be kept in sync by hand with the workflow file if the schedule changes — there's a pointer comment in `app.py` at `CRON_MINUTE_PAST_HOUR`. |
| 2026-07-27 | Multi-recipient routing is a per-watch optional `notify_to` field, not a top-level "users" concept, and not a bump to `CONFIG_VERSION` | A friend now wants his own permit/campground watches emailed to his own address. Per-watch is the smallest change that fits the existing flat `watches` list — no new top-level structure needed, and every existing watch still validates unchanged (field is optional, falls back to `NOTIFY_EMAIL_TO`/`SMTP_USERNAME` exactly as before), so per CLAUDE.md's own rule this is additive, not a breaking schema change. Revisit if a real multi-user concept (per-user watch grouping, per-user status page filtering) becomes worth it — not needed yet for one friend and a handful of watches. |
| 2026-07-30 | `campground` watch `dates` means "must all be free on the same site" (a contiguous stay), not "any one of these dates on any site" | The friend was getting hourly emails claiming availability that was never actually bookable. Confirmed against live recreation.gov data this wasn't a data/parsing bug — the checker was correctly reporting real single-night openings (mostly Sunday-checkout gaps at Front Range campgrounds), but those never covered the full 2-night weekend stay he actually needs, so the emails were technically accurate per-night but practically useless. Changed `check_campground_watch`'s matching logic and return shape (`{campground_id: [sites]}` instead of `{date: {campground_id: [sites]}}`) so a hit means "this site works for your whole trip." Raised, but didn't act on, whether `permit_checker.py` has the same independent-dates issue for multi-night permits (e.g. Snowmass Lake) — needs Christopher's input before touching permit semantics. |

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

### Phase 2: Config schema — complete (updated to v2 during Phase 4)
- [x] Schema (v2), documented here:
  ```json
  {
    "version": 2,
    "watches": [
      {
        "id": "lowercase-hyphenated-slug",
        "type": "permit",
        "label": "human-readable name",
        "enabled": true,
        "notify_to": "optional-override@example.com",
        "params": {
          "source": "recreation.gov",
          "permit_id": "4675333",
          "division_ids": ["4675333030", "..."],
          "dates": ["2026-07-18"]
        }
      }
    ]
  }
  ```
  Every watch needs `id` (unique, `^[a-z0-9]+(-[a-z0-9]+)*$`), `type` (must
  be in `config_schema.KNOWN_WATCH_TYPES` — currently only `"permit"`;
  extend that set, not this doc, when chores/calendar land in Phase 7),
  `label`, `enabled` (bool), and a type-specific `params` object.
  `notify_to` is optional (added Phase 8, 2026-07-27) — a valid-looking
  email string that overrides where *this watch's* availability emails go;
  omitted means fall back to `NOTIFY_EMAIL_TO`/`SMTP_USERNAME` as before,
  so every pre-existing watch is unaffected. For
  `type: "permit"`, `params.source` must be in
  `config_schema.KNOWN_PERMIT_SOURCES` (currently only `"recreation.gov"`),
  `params.permit_id` is recreation.gov's permit ID (from the permit's URL,
  e.g. `/permits/4675333/...`), `params.division_ids` is a non-empty list of
  that permit's division/zone/site IDs to check (a "zone" can be several
  numbered divisions — see Phase 4's research spike), and `params.dates` is
  a non-empty list of `"YYYY-MM-DD"` strings. Bumped from v1 → v2 because
  the old `permit_id`-only shape couldn't express *which* division/date to
  actually check — a real breaking change, not an additive one.
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
- [x] `SMTP_USERNAME`/`SMTP_PASSWORD` set by Christopher (Gmail app
      password) — both locally (fish config) and in Vercel (Preview +
      Production env vars), confirmed via `vercel env ls`.
- [x] Manual test send with real credentials: `send_test_email.py` run
      locally (via `fish -c` so the env vars were inherited) sent
      successfully, and Christopher confirmed the email actually arrived.
- [ ] Not wired into `/api/cron/check` yet — that's Phase 4's job (checker →
      state store → email → cron endpoint).

**Phase 3 complete** except for the Phase-4 wiring, which is out of scope
here by design.

### Phase 4: recreation.gov permit checker
- [x] Research spike (2026-07-15), confirmed against live traffic, not
      assumed:
  - The permit detail page (`/permits/{permit_id}/registration/detailed-availability`)
    is a client-rendered SPA with no useful server HTML — the real data comes
    from `GET https://www.recreation.gov/api/permititinerary/{permit_id}/division/{division_id}/availability/month?month={M}&year={YYYY}&commercial=false`,
    found by pulling the page's JS bundle and grepping for the `On(...)` URL
    builder around `division/${a}/availability/month`.
  - Response shape: `{"payload": {"bools": {"YYYY-MM-DD": bool, ...}, "quota_type_maps": {"ConstantQuotaUsageDaily": {"YYYY-MM-DD": {"total": int, "remaining": int, "show_walkup": bool, "is_hidden": bool, "season_type": str}, ...}}}}`.
    Confirmed `bools[date] == (remaining > 0)` exactly, by cross-checking a
    date with `remaining: 1` against a batch of `remaining: 0` dates.
  - **The default `python-requests` User-Agent gets a 403** (recreation.gov's
    WAF blocks known bot signatures); an empty UA or a browser-like UA both
    get 200. `permit_checker.py` sends a browser-like UA to be safe against
    future tightening.
  - A permit has multiple "divisions" (zones/campsites) under
    `/api/permitcontent/{permit_id}`'s `divisions` map. For permit `4675333`
    (Maroon Bells-Snowmass Wilderness), the "Capitol Lake" zone is actually
    9 separate divisions (`4675333030`–`4675333038`, "Capitol Lake Site
    1"–"9"), each with its own independent quota. A "Capitol Lake" watch
    needs to check all 9 and report if *any* has `remaining > 0` — assumed
    that's what "Capitol Lake permits" means (any site in the zone), not one
    specific numbered site. **Flag to Christopher if that assumption is
    wrong.**
- [x] `permit_checker.py`'s `check_permit_watch(watch)` fetches all
      `division_ids` × `dates` from a watch's params and returns
      `{date: {division_id: remaining_count}}` for only the combinations
      currently available. Verified against live data both ways: the
      current real target (Capitol Lake, 2026-07-18) correctly returns `{}`
      (all 9 sites show `remaining: 0` right now), and a synthetic check
      against known-open September 2026 dates correctly returned the
      available date/division/count.
- [x] Wired into `/api/cron/check` → `notifier.send_notification` — **without**
      Phase 5 state, on explicit user instruction: "hold off on the
      persistence... I think I want to be spammed by it for now." Every
      hourly run re-checks and re-emails for as long as availability
      persists; nothing is sent when there's none. `CHECKERS = {"permit":
      check_permit_watch}` dict dispatch added in `app.py` so future watch
      types (chore, calendar) plug in the same way. Per-watch errors
      (`PermitCheckError`, `EmailConfigError`) are caught and reported in
      the JSON response rather than crashing the whole cron run.
- [x] Verified end-to-end twice: (1) real run against the live Capitol Lake
      target correctly found nothing and sent no email; (2) a mocked
      `CHECKERS["permit"]` returning a fake available slot correctly
      triggered a real send, and Christopher confirmed the email arrived.
- [x] Email body now includes a direct `registration_url(permit_id, date)`
      link per available date (same URL pattern Christopher originally
      gave: `/permits/{permit_id}/registration/detailed-availability?date={date}`)
      so he can jump straight to booking instead of just getting a bare
      notification. Verified in a real received email.
- [x] Bumped `vercel.json`'s `maxDuration` 30s → 60s (9 sequential
      recreation.gov requests per run) and added a 0.3s courtesy delay
      between requests in `permit_checker.py`.
- Phase 5 (state persistence / dedup) is intentionally **not** being built
  right now — revisit only if the hourly-spam behavior becomes annoying in
  practice.

### Phase 5: Runtime state persistence — on hold, deliberately
User explicitly chose repeat/duplicate emails over building this now (see
2026-07-15 decisions log entry). Nothing below is started.
- [ ] Pick primitive: Vercel Blob (simple JSON blob mirroring config shape)
      vs. Vercel KV/Upstash Redis (better for per-watch key lookups). Default
      assumption: start with Blob for simplicity, revisit if per-key access
      patterns get awkward.
- [ ] Read/write helpers for "last checked" + "last notified state" per
      watch id.

### Phase 6: Light UI, read side — visual pass done, state display still open
- [x] Restyled the status page (`STATUS_HTML` in `app.py`): card-based watch
      list, enabled/disabled shown as a colored dot + muted label rather
      than a CSS class no one could see, a type badge, light/dark support
      via `prefers-color-scheme` (verified both render correctly by
      screenshotting the Flask dev server with headless Chromium, including
      the disabled-watch state).
- [x] Shows **next** scheduled check time (`next_check_time()`), computed
      from the known GitHub Actions cron schedule (`17 * * * *`) rather than
      tracked — no state store exists (Phase 5 is on hold), so this is
      derived, not measured. Must be kept in sync by hand with
      `.github/workflows/hourly-check.yml` if that schedule ever changes;
      there's a comment at `CRON_MINUTE_PAST_HOUR` in `app.py` pointing back
      at the workflow file.
- [ ] A true **last**-checked timestamp (vs. computed next-check) would
      need real persisted state — same blocker as Phase 5, intentionally
      not built.
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

### Phase 8: Multi-recipient (second user) — in progress
- [x] `notify_to` optional per-watch field: schema validation
      (`config_schema.py`, simple email-shape regex), `notifier.py`'s
      `send_notification` takes an optional `to_addr` override, `app.py`'s
      cron loop passes `watch.get("notify_to")` through. No `CONFIG_VERSION`
      bump (additive/backward-compatible, see 2026-07-27 decisions log).
      Verified end-to-end via `app.test_client()` against the real
      `/api/cron/check` path (real SMTP creds, real CRON_SECRET, live
      recreation.gov data) — 200 OK, both existing permit watches checked
      correctly, no regression.
- [x] Research spike (2026-07-27), confirmed against live traffic via
      `curl` with the same browser-like User-Agent workaround as Phase 4,
      not assumed:
  - Per-site month availability: `GET https://www.recreation.gov/api/camps/availability/campground/{facility_id}/month?start_date={YYYY-MM}-01T00:00:00.000Z`.
    Response: `{"campsites": {"{campsite_id}": {"site": str, "loop": str, "campsite_reserve_type": str, "availabilities": {"YYYY-MM-DDT00:00:00Z": "Available"|"Reserved"|..., ...}, "quantities": {...}, ...}, ...}, "count": int}`.
    A date/site is open when `availabilities[date] == "Available"` (cross-checked against `quantities` being `1` for the same key).
  - Facility metadata (name etc.): `GET https://www.recreation.gov/api/camps/campgrounds/{facility_id}` →
    `{"campground": {"facility_name": str, "parent_asset_id": str, ...}}`.
    Not currently used by the checker (label comes from config), but useful
    for building config entries by hand.
  - This is a genuinely different API from the permit itinerary one (Phase
    4) — different base path (`/api/camps/...` vs `/api/permititinerary/...`),
    different auth-window behavior, and per-site rather than per-division
    results. Confirmed the four campgrounds Christopher's friend asked
    about are real, live facility IDs: `233720` (Riverside), `233722`
    (Cove Campground), `233721` (Spillway Campground), `233718` (Springer
    Gulch) — all share `parent_asset_id: "1053"` (same park/area).
- [x] `campground_checker.py` added, mirroring `permit_checker.py`'s shape:
      `check_campground_watch(watch)` takes `params.campground_ids` +
      `params.dates`. **Original return shape**
      `{date: {campground_id: [{"campsite_id", "site", "loop"}, ...]}}`
      (independent per-date) **was changed 2026-07-30** to
      `{campground_id: [sites]}` (site must be open for *all* requested
      dates) — see the bug-fix entry below for why. `format_lines(watch,
      availability)` builds the email body section for this type.
- [x] `type: "campground"` added to `KNOWN_WATCH_TYPES` in
      `config_schema.py`, with `params.source` (must be
      `KNOWN_CAMPGROUND_SOURCES`, currently just `"recreation.gov"`),
      `params.campground_ids` (non-empty list of non-empty strings), and
      `params.dates` (same `"YYYY-MM-DD"` list shape as permit). No
      `CONFIG_VERSION` bump — a new watch `type` is additive, existing
      watches unaffected, same reasoning as the `notify_to` field above.
- [x] `app.py` generalized: `CHECKERS`/`EMAIL_FORMATTERS` are now
      per-type dicts (`{"permit": ..., "campground": ...}`) instead of the
      old permit-shaped-only email-building code — done in the same change
      since the old code only knew how to format permit results. Verified
      no regression via the same `/api/cron/check` real-data test above.
- [x] Friend's email (matthewhale1090@gmail.com) added as `notify_to` on a
      new `friend-campgrounds-2026-08-07` watch in `config/config.json`
      (campground_ids `233720`/`233722`/`233721`/`233718`). Dates were
      briefly `2026-08-07`/`08`/`09` (extended to 3 dates 2026-07-28 at his
      request) but reverted to just `08-07`/`08-08` on 2026-07-30 once the
      "must be both nights" bug below was understood — see that entry.
- [x] **Bug found and fixed (2026-07-30)**: the friend reported every
      hourly email "showing availability" that was never actually
      bookable. Investigated by pulling the exact same raw recreation.gov
      data the checker used at send time and diffing it against the sent
      email — the email matched the raw API exactly, so this wasn't a
      parsing bug. The real problem was semantic: `check_campground_watch`
      treated `dates` as independent alternatives ("is any site open on
      any one of these dates"), so it flagged campgrounds where, e.g.,
      site 014 at Riverside was open 8/9 only (Reserved both 8/7 and
      8/8) — a real single-night opening, but useless for a trip that
      needs both 8/7 and 8/8. Confirmed directly against live data that
      **no site across any of the 4 campgrounds had all of 8/7+8/8+8/9
      open together** at the time the false-positive email went out. Root
      cause: recreation.gov's own weekend booking pattern (Fri/Sat nights
      booked solid, scattered Sunday-checkout gaps reopening on random
      sites) looks exactly like sporadic "availability" if you check each
      night in isolation.
  - Fix: `check_campground_watch` now only counts a site as a hit if it's
    `"Available"` for *every* date in the watch's `dates` list (merging
    availability across month boundaries first, since a stay can span
    two calendar months) — i.e. `dates` means "this contiguous stay",
    not "any of these nights". Return shape simplified from
    `{date: {campground_id: [sites]}}` to `{campground_id: [sites]}`
    since a qualifying site is now good for the whole requested stay by
    definition. `format_lines` updated to match ("Available for all of:
    <dates>" instead of a per-date breakdown).
  - Verified against live data both ways: the actual friend watch
    (8/7+8/8, both weekend nights) now correctly returns `{}` — nothing
    is open for both nights right now, matching manual/live confirmation
    that the campgrounds are fully booked those two nights. A synthetic
    watch against a known multi-night-open stretch (Riverside, 8/4+8/5)
    correctly returned real qualifying sites. Full `/api/cron/check` run
    (all 3 watches, real creds) still 200 OK, no regression to the permit
    watches.
  - **Open question this raised, not yet acted on**: the existing
    Snowmass Lake permit watch (`dates: ["2026-08-21", "2026-08-22"]`,
    also a 2-night backpacking trip) has the *same* independent-dates
    semantics in `permit_checker.py` — it reports each date/division
    independently rather than requiring the same division to be open
    both nights. Unknown whether that's actually wrong for permits (wilderness
    permits may not require a fixed campsite per night the way a
    reservable campground site does) or the same class of bug. Flag to
    Christopher; don't change `permit_checker.py` without confirming
    intent first.
- [ ] Confirm with Christopher whether the friend should also be able to
      see the status page (`/`) — currently unauthenticated, shows all
      watches from everyone, no per-user filtering.

## Open questions

- **UI auth**: does the light UI need a login/shared secret, or is it fine
  as an unauthenticated Vercel URL (security through obscurity)? Matters
  once it shows real config/state.
- **recreation.gov specifics**: which permit(s)/park(s) to watch first, and
  the exact endpoint shape — needs a research spike in Phase 4, not a guess.
- ~~**recreation.gov campground specifics**~~ — resolved 2026-07-27, see
  Phase 8's research spike entry.
- **Chores model**: are chores time-based reminders (e.g. "every Tuesday")
  or state-based (e.g. "bin day, check if already marked done")? Affects
  whether the Phase 2 schema needs a `schedule` field now or later.
- **Calendar source**: which calendar (Google, iCloud, other) and how it
  authenticates.
