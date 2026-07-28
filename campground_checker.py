import time

import requests

# Same WAF workaround as permit_checker.py -- recreation.gov blocks the
# default python-requests User-Agent (403); a browser-like one works.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

RECREATION_GOV_CAMPS_BASE = "https://www.recreation.gov/api/camps"

# Courtesy delay between sequential requests to the same third-party API.
REQUEST_DELAY_SECONDS = 0.3


class CampgroundCheckError(RuntimeError):
    pass


def registration_url(campground_id):
    """The human-facing page to book a site, for a given campground."""
    return f"https://www.recreation.gov/camping/campgrounds/{campground_id}"


def _fetch_month_availability(campground_id, year, month):
    url = f"{RECREATION_GOV_CAMPS_BASE}/availability/campground/{campground_id}/month"
    try:
        response = requests.get(
            url,
            params={"start_date": f"{year}-{month:02d}-01T00:00:00.000Z"},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise CampgroundCheckError(
            f"recreation.gov request failed for campground {campground_id} "
            f"{year}-{month:02d}: {e}"
        ) from e
    return response.json()["campsites"]


def check_campground_watch(watch):
    """
    Checks a config watch of type "campground" (params: campground_ids,
    dates) against recreation.gov's live per-site availability.

    Returns {date: {campground_id: [{"site", "loop", "campsite_id"}, ...]}}
    containing only campground/date combinations with at least one site
    marked "Available". Empty dict means nothing is currently available.
    """
    params = watch["params"]
    campground_ids = params["campground_ids"]
    dates = params["dates"]

    months_needed = sorted({(date[:4], date[5:7]) for date in dates})

    available = {}
    for i, campground_id in enumerate(campground_ids):
        if i > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        month_cache = {
            (year, month): _fetch_month_availability(campground_id, int(year), int(month))
            for year, month in months_needed
        }
        for date in dates:
            year, month = date[:4], date[5:7]
            campsites = month_cache[(year, month)]
            date_key = f"{date}T00:00:00Z"
            open_sites = [
                {
                    "campsite_id": campsite_id,
                    "site": site.get("site"),
                    "loop": site.get("loop"),
                }
                for campsite_id, site in campsites.items()
                if site.get("availabilities", {}).get(date_key) == "Available"
            ]
            if open_sites:
                available.setdefault(date, {})[campground_id] = open_sites

    return available


def format_lines(watch, availability):
    """Email body lines for a campground watch's availability results."""
    lines = []
    for date, by_campground in sorted(availability.items()):
        lines.append(f"{date}:")
        for campground_id, sites in sorted(by_campground.items()):
            lines.append(f"  {registration_url(campground_id)}")
            for site in sites:
                lines.append(f"    site {site['site']} (loop {site['loop']})")
        lines.append("")
    return lines
