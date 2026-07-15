import json
import re

CONFIG_VERSION = 2

# Extend this set as new watch types (chore, calendar, ...) get implemented.
KNOWN_WATCH_TYPES = {"permit"}
KNOWN_PERMIT_SOURCES = {"recreation.gov"}

_ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ConfigError(ValueError):
    pass


def validate_config(data):
    errors = []

    if not isinstance(data, dict):
        raise ConfigError("config.json must be a JSON object")

    if data.get("version") != CONFIG_VERSION:
        errors.append(
            f'top-level "version" must be {CONFIG_VERSION}, got {data.get("version")!r}'
        )

    watches = data.get("watches")
    if not isinstance(watches, list):
        errors.append('top-level "watches" must be a list')
        watches = []

    seen_ids = set()
    for i, watch in enumerate(watches):
        prefix = f"watches[{i}]"
        if not isinstance(watch, dict):
            errors.append(f"{prefix} must be an object")
            continue

        watch_id = watch.get("id")
        if not isinstance(watch_id, str) or not _ID_PATTERN.match(watch_id):
            errors.append(
                f"{prefix}.id must be a lowercase-hyphenated string, got {watch_id!r}"
            )
        elif watch_id in seen_ids:
            errors.append(f'{prefix}.id "{watch_id}" is not unique')
        else:
            seen_ids.add(watch_id)

        watch_type = watch.get("type")
        if watch_type not in KNOWN_WATCH_TYPES:
            errors.append(
                f"{prefix}.type must be one of {sorted(KNOWN_WATCH_TYPES)}, "
                f"got {watch_type!r}"
            )

        if not isinstance(watch.get("label"), str) or not watch.get("label"):
            errors.append(f"{prefix}.label must be a non-empty string")

        if not isinstance(watch.get("enabled"), bool):
            errors.append(f"{prefix}.enabled must be a boolean")

        params = watch.get("params")
        if not isinstance(params, dict):
            errors.append(f"{prefix}.params must be an object")
        elif watch_type == "permit":
            source = params.get("source")
            if source not in KNOWN_PERMIT_SOURCES:
                errors.append(
                    f"{prefix}.params.source must be one of "
                    f"{sorted(KNOWN_PERMIT_SOURCES)}, got {source!r}"
                )
            permit_id = params.get("permit_id")
            if not isinstance(permit_id, str) or not permit_id:
                errors.append(f"{prefix}.params.permit_id must be a non-empty string")

            division_ids = params.get("division_ids")
            if (
                not isinstance(division_ids, list)
                or not division_ids
                or not all(isinstance(d, str) and d for d in division_ids)
            ):
                errors.append(
                    f"{prefix}.params.division_ids must be a non-empty list of "
                    f"non-empty strings"
                )

            dates = params.get("dates")
            if (
                not isinstance(dates, list)
                or not dates
                or not all(isinstance(d, str) and _DATE_PATTERN.match(d) for d in dates)
            ):
                errors.append(
                    f"{prefix}.params.dates must be a non-empty list of "
                    f'"YYYY-MM-DD" strings'
                )

    if errors:
        raise ConfigError("Invalid config.json:\n  - " + "\n  - ".join(errors))


def load_config(path):
    with open(path) as f:
        data = json.load(f)
    validate_config(data)
    return data
