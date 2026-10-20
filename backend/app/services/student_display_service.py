"""Optional synthetic display-name lookup; never used for identity or ML."""

import csv
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)
KEY_COLUMNS = ("id_student", "code_module", "code_presentation")
REQUIRED_COLUMNS = (*KEY_COLUMNS, "student_name")


def _normalize_key(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


@lru_cache(maxsize=8)
def _load_lookup(
    path_string: str, modified_ns: int | None, file_size: int | None
) -> dict[tuple[str, str, str], str]:
    del modified_ns, file_size  # Included in the cache key to notice file updates.
    path = Path(path_string)
    if not path.is_file():
        return {}

    names: dict[tuple[str, str, str], str] = {}
    ambiguous: set[tuple[str, str, str]] = set()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            columns = reader.fieldnames or []
            if len(columns) != len(set(columns)) or not set(REQUIRED_COLUMNS).issubset(columns):
                logger.warning("Optional student display CSV has an invalid header")
                return {}

            invalid_rows = 0
            for row in reader:
                if None in row:
                    invalid_rows += 1
                    continue
                values = tuple(_normalize_key(row.get(column)) for column in KEY_COLUMNS)
                name = _normalize_key(row.get("student_name"))
                if any(value is None for value in values) or name is None:
                    invalid_rows += 1
                    continue
                key = values  # type: ignore[assignment]
                existing = names.get(key)
                if existing is not None and existing != name:
                    ambiguous.add(key)
                else:
                    names[key] = name
            if invalid_rows:
                logger.warning("Optional student display CSV skipped %d invalid rows", invalid_rows)
    except (OSError, UnicodeError, csv.Error):
        logger.warning("Optional student display CSV could not be read")
        return {}

    for key in ambiguous:
        names.pop(key, None)
    if ambiguous:
        logger.warning("Optional student display CSV contains conflicting duplicate keys")
    return names


def get_display_name_lookup() -> dict[tuple[str, str, str], str]:
    path = settings.resolve_backend_path(settings.student_display_csv_path)
    try:
        stat = path.stat()
        modified_ns: int | None = stat.st_mtime_ns
        file_size: int | None = stat.st_size
    except OSError:
        modified_ns = file_size = None
    return _load_lookup(str(path), modified_ns, file_size)


def get_student_name(learner: dict[str, Any]) -> str | None:
    key = tuple(_normalize_key(learner.get(column)) for column in KEY_COLUMNS)
    if any(value is None for value in key):
        return None
    return get_display_name_lookup().get(key)  # type: ignore[arg-type]


def attach_student_names(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = get_display_name_lookup()
    result = []
    for record in records:
        key = tuple(_normalize_key(record.get(column)) for column in KEY_COLUMNS)
        name = None if any(value is None for value in key) else lookup.get(key)  # type: ignore[arg-type]
        result.append({**record, "student_name": name})
    return result
