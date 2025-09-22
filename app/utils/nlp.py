from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import dateparser

AUS_TZ = ZoneInfo("Australia/Sydney")


def parse_when_range(text: str, now: datetime | None = None) -> tuple[datetime, datetime] | None:
    """
    Parse 'tomorrow', 'next week', etc. Returns (start, end) datetimes in Australia/Sydney.
    """
    if now is None:
        now = datetime.now(AUS_TZ)

    # Common shortcuts
    lower = text.lower()
    if "tomorrow" in lower:
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start, end
    if "next week" in lower:
        # Monday next week to next Monday
        days_ahead = (7 - now.weekday()) % 7  # days until Monday
        start = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        return start, end

    # Fallback: use dateparser with timezone awareness
    settings = {
        "TIMEZONE": "Australia/Sydney",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
    }
    parsed = dateparser.parse(text, settings=settings)
    if parsed:
        # if a single moment, assume 1-hour window
        start = parsed
        end = start + timedelta(hours=1)
        return start, end
    return None


def parse_new_event(text: str, now: datetime | None = None):
    """
    Very rough extraction for "add ... at 3pm tomorrow".
    Returns dict with 'title', 'start', 'end' (1 hour default).
    """
    if now is None:
        now = datetime.now(AUS_TZ)

    # Title after 'called' or quote marks
    title_match = re.search(r"(called|titled)\s+[‘'\"“”]?([^'\"”]+)[’'\"”]?", text, re.IGNORECASE)
    if not title_match:
        title_match = re.search(r"[‘'\"“”]([^'\"”]+)[’'\"”]", text)
    title = title_match.group(2 if title_match and title_match.lastindex == 2 else 1) if title_match else None

    # Time phrase
    time_phrase = None
    time_m = re.search(r"\b(at|for)\s+([0-9]{1,2}(:[0-9]{2})?\s?(am|pm)?)\b", text, re.IGNORECASE)
    if time_m:
        time_phrase = time_m.group(2)

    # Day phrase
    day_phrase = None
    if "tomorrow" in text.lower():
        day_phrase = "tomorrow"
    elif "today" in text.lower():
        day_phrase = "today"
    else:
        # try a fallback parse of the whole string for datetime
        pass

    when_text = f"{day_phrase or ''} {time_phrase or ''}".strip() or text
    settings = {"TIMEZONE": "Australia/Sydney", "RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DATES_FROM": "future"}
    dt = dateparser.parse(when_text, settings=settings)
    if not dt:
        return None

    start = dt
    end = start + timedelta(hours=1)

    return {
        "title": title or "New Event",
        "start": start,
        "end": end,
        "timezone": "Australia/Sydney",
    }
