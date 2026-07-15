import os
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request

from config_schema import ConfigError, load_config as _load_config
from notifier import EmailConfigError, send_notification
from permit_checker import PermitCheckError, check_permit_watch, registration_url

app = Flask(__name__)

# Extend this as new watch types (chore, calendar, ...) get their own checker.
CHECKERS = {
    "permit": check_permit_watch,
}

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")

# Must match the schedule in .github/workflows/hourly-check.yml ("17 * * * *").
# There's no persisted "last checked" time (see PLAN.md Phase 5), so this is
# computed from the known cron schedule rather than tracked state.
CRON_MINUTE_PAST_HOUR = 17

STATUS_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>note-ifs</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f7f8;
      --card-bg: #ffffff;
      --text: #1a1a1a;
      --muted: #6b7280;
      --border: #e5e7eb;
      --accent: #2563eb;
      --ok: #16a34a;
      --off: #9ca3af;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #15161a;
        --card-bg: #1e2027;
        --text: #e8e8ea;
        --muted: #9198a4;
        --border: #2c2f38;
        --accent: #5b8dfc;
        --ok: #4ade80;
        --off: #6b7280;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      max-width: 38rem;
      margin: 0 auto;
      padding: 3rem 1.25rem;
      background: var(--bg);
      color: var(--text);
    }}
    h1 {{
      font-size: 1.375rem;
      font-weight: 650;
      margin: 0 0 0.25rem;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: 0.9rem;
      margin: 0 0 1.75rem;
    }}
    .meta {{
      display: flex;
      gap: 1.5rem;
      flex-wrap: wrap;
      font-size: 0.85rem;
      color: var(--muted);
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
      padding: 0.75rem 0;
      margin-bottom: 1.75rem;
    }}
    .meta strong {{ color: var(--text); font-weight: 600; }}
    h2 {{
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      margin: 0 0 0.75rem;
    }}
    .watch {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.85rem 1rem;
      margin-bottom: 0.6rem;
      display: flex;
      align-items: center;
      gap: 0.7rem;
    }}
    .dot {{
      width: 0.55rem;
      height: 0.55rem;
      border-radius: 50%;
      background: var(--ok);
      flex-shrink: 0;
    }}
    .watch.disabled .dot {{ background: var(--off); }}
    .watch-main {{ min-width: 0; }}
    .watch-label {{
      font-weight: 550;
      font-size: 0.95rem;
      overflow-wrap: anywhere;
    }}
    .watch.disabled .watch-label {{ color: var(--muted); }}
    .watch-id {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.75rem;
      color: var(--muted);
    }}
    .badge {{
      margin-left: auto;
      font-size: 0.7rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      color: var(--muted);
      border: 1px solid var(--border);
      border-radius: 5px;
      padding: 0.15rem 0.4rem;
      flex-shrink: 0;
    }}
    .empty {{ color: var(--muted); font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>note-ifs</h1>
  <p class="subtitle">Notifications server is running.</p>
  <div class="meta">
    <div>Next check: <strong>{next_check}</strong></div>
  </div>
  <h2>Configured watches</h2>
  {watch_list}
</body>
</html>
"""


def load_config():
    return _load_config(CONFIG_PATH)


def next_check_time(now=None):
    now = now or datetime.now(timezone.utc)
    candidate = now.replace(minute=CRON_MINUTE_PAST_HOUR, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(hours=1)
    return candidate


@app.route("/")
def status():
    try:
        config = load_config()
    except ConfigError as e:
        return f"<pre>{e}</pre>", 500
    watches = config.get("watches", [])
    if watches:
        items = "\n".join(
            '<div class="watch{disabled_class}">'
            '<span class="dot"></span>'
            '<div class="watch-main">'
            '<div class="watch-label">{label}</div>'
            '<div class="watch-id">{id}</div>'
            "</div>"
            '<span class="badge">{type}</span>'
            "</div>".format(
                disabled_class="" if w.get("enabled") else " disabled",
                label=w.get("label", w.get("id", "unnamed")),
                id=w.get("id", ""),
                type=w.get("type", "unknown"),
            )
            for w in watches
        )
    else:
        items = '<p class="empty">No watches configured.</p>'
    next_check = next_check_time().strftime("%Y-%m-%d %H:%M UTC")
    return STATUS_HTML.format(watch_list=items, next_check=next_check)


@app.route("/api/cron/check", methods=["GET", "POST"])
def cron_check():
    cron_secret = os.environ.get("CRON_SECRET")
    if cron_secret:
        auth_header = request.headers.get("Authorization")
        if auth_header != f"Bearer {cron_secret}":
            return jsonify({"error": "unauthorized"}), 401

    try:
        config = load_config()
    except ConfigError as e:
        return jsonify({"error": str(e)}), 500

    # No "already notified" state yet (see PLAN.md Phase 5) -- by design,
    # for now this emails every run for as long as availability persists,
    # rather than staying silent when there's nothing to report.
    results = []
    for watch in config.get("watches", []):
        if not watch.get("enabled"):
            continue
        checker = CHECKERS.get(watch["type"])
        if checker is None:
            continue

        try:
            availability = checker(watch)
        except PermitCheckError as e:
            results.append({"id": watch["id"], "error": str(e)})
            continue

        result = {"id": watch["id"], "availability": availability}
        results.append(result)

        if availability:
            lines = [f"{watch['label']} ({watch['id']})", ""]
            for date, by_division in sorted(availability.items()):
                if watch["type"] == "permit":
                    permit_id = watch["params"]["permit_id"]
                    lines.append(f"{date}: {registration_url(permit_id, date)}")
                else:
                    lines.append(f"{date}:")
                for division_id, remaining in sorted(by_division.items()):
                    lines.append(f"  division {division_id} -- {remaining} remaining")
                lines.append("")
            try:
                send_notification(
                    f"note-ifs: availability found -- {watch['label']}",
                    "\n".join(lines),
                )
            except EmailConfigError as e:
                result["email_error"] = str(e)

    return jsonify(
        {
            "ok": True,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "watches_seen": len(config.get("watches", [])),
            "results": results,
        }
    )
