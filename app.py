import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from config_schema import ConfigError, load_config as _load_config
from notifier import EmailConfigError, send_notification
from permit_checker import PermitCheckError, check_permit_watch

app = Flask(__name__)

# Extend this as new watch types (chore, calendar, ...) get their own checker.
CHECKERS = {
    "permit": check_permit_watch,
}

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")

STATUS_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>note-ifs</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 3rem auto; padding: 0 1rem; }}
    .watch {{ margin: 0.5rem 0; }}
    .disabled {{ color: #888; }}
  </style>
</head>
<body>
  <h1>note-ifs</h1>
  <p>Notifications server is running.</p>
  <h2>Configured watches</h2>
  {watch_list}
</body>
</html>
"""


def load_config():
    return _load_config(CONFIG_PATH)


@app.route("/")
def status():
    try:
        config = load_config()
    except ConfigError as e:
        return f"<pre>{e}</pre>", 500
    watches = config.get("watches", [])
    if watches:
        items = "\n".join(
            '<div class="watch{disabled_class}">{label} ({type})</div>'.format(
                disabled_class="" if w.get("enabled") else " disabled",
                label=w.get("label", w.get("id", "unnamed")),
                type=w.get("type", "unknown"),
            )
            for w in watches
        )
    else:
        items = "<p>No watches configured.</p>"
    return STATUS_HTML.format(watch_list=items)


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
                for division_id, remaining in by_division.items():
                    lines.append(f"  {date}: division {division_id} -- {remaining} remaining")
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
