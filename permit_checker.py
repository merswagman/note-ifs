import time

import requests

# recreation.gov blocks requests carrying the default python-requests
# User-Agent (403); a browser-like one works. Confirmed by hand against
# the live API during the Phase 4 research spike (see PLAN.md).
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

RECREATION_GOV_BASE = "https://www.recreation.gov/api/permititinerary"

# Courtesy delay between sequential requests to the same third-party API.
REQUEST_DELAY_SECONDS = 0.3


class PermitCheckError(RuntimeError):
    pass


def registration_url(permit_id, date):
    """The human-facing page to book a permit, for a given date."""
    return f"https://www.recreation.gov/permits/{permit_id}/registration/detailed-availability?date={date}"


def _fetch_month_availability(permit_id, division_id, year, month):
    url = f"{RECREATION_GOV_BASE}/{permit_id}/division/{division_id}/availability/month"
    try:
        response = requests.get(
            url,
            params={"month": month, "year": year, "commercial": "false"},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise PermitCheckError(
            f"recreation.gov request failed for permit {permit_id} "
            f"division {division_id} {year}-{month:02d}: {e}"
        ) from e
    return response.json()["payload"]


def check_permit_watch(watch):
    """
    Checks a config watch of type "permit" (params: permit_id, division_ids,
    dates) against recreation.gov's live availability.

    Returns {date: {division_id: remaining_count, ...}, ...} containing only
    date/division combinations where remaining > 0. Empty dict means nothing
    is currently available.
    """
    params = watch["params"]
    permit_id = params["permit_id"]
    division_ids = params["division_ids"]
    dates = params["dates"]

    months_needed = sorted({(date[:4], date[5:7]) for date in dates})

    available = {}
    for i, division_id in enumerate(division_ids):
        if i > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        month_cache = {
            (year, month): _fetch_month_availability(permit_id, division_id, year, int(month))
            for year, month in months_needed
        }
        for date in dates:
            year, month = date[:4], date[5:7]
            quota_maps = month_cache[(year, month)].get("quota_type_maps", {})
            remaining = max(
                (by_date.get(date, {}).get("remaining", 0) for by_date in quota_maps.values()),
                default=0,
            )
            if remaining > 0:
                available.setdefault(date, {})[division_id] = remaining

    return available
