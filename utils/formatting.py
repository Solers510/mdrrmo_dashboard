from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

def format_datetime(value: datetime | None, fallback: str = "Not available", format_str: str = "%d %b %Y, %I:%M %p") -> str:
    """Formats a datetime to a standard Manila time string."""
    if value is None:
        return fallback
    return value.astimezone(MANILA_TIMEZONE).strftime(format_str)

def format_age(value: datetime | None, fallback: str = "No report") -> str:
    """Verbose age formatting (e.g., 'Just now', '5 minutes ago')."""
    if value is None:
        return fallback
    current = datetime.now(MANILA_TIMEZONE)
    localized = value.astimezone(MANILA_TIMEZONE)
    delta = current - localized
    seconds = max(int(delta.total_seconds()), 0)

    if seconds < 60:
        return "Just now"
    minutes = seconds // 60
    if minutes < 60:
        return "1 minute ago" if minutes == 1 else f"{minutes} minutes ago"
    hours = minutes // 60
    if hours < 24:
        return "1 hour ago" if hours == 1 else f"{hours} hours ago"
    days = hours // 24
    return "1 day ago" if days == 1 else f"{days} days ago"

def format_report_age(value: datetime | None, fallback: str = "—") -> str:
    """Compact age formatting for dense tables (e.g., '<1m', '5m', '2h', '1d')."""
    if value is None:
        return fallback
    current = datetime.now(MANILA_TIMEZONE)
    localized = value.astimezone(MANILA_TIMEZONE)
    seconds = max(int((current - localized).total_seconds()), 0)

    if seconds < 60:
        return "<1m"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"

# Alias for backward compatibility with pages using format_table_age
format_table_age = format_report_age

def display_event_name(event: dict[str, Any] | None) -> str:
    """Safely extracts and formats the event name with its classification."""
    if not event:
        return "Unknown Event"
    classification = event.get("classification")
    name = str(event.get("event_name", "Unknown Event"))
    if classification is not None and str(classification).strip():
        return f"{classification} {name}"
    return name

def display_sitrep(event: dict[str, Any] | None, fallback: str = "Not set") -> str:
    """Safely extracts the SitRep number."""
    if not event:
        return fallback
    value = event.get("current_sitrep_number")
    if value in {None, ""}:
        return fallback
    return str(value)

def counted_label(count: int, singular: str, plural: str | None = None) -> str:
    """Returns a singular or plural label based on the count."""
    if count == 1:
        return singular
    return plural if plural is not None else f"{singular}s"
def select_index(options: list[Any], value: Any, fallback: int = 0) -> int:
    """Safely finds the index of a value in a list for Streamlit selectboxes."""
    try:
        return list(options).index(str(value))
    except ValueError:
        return fallback