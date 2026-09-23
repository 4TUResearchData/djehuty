#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pyyaml",
#     "tzdata; sys_platform == 'win32'",
# ]
# ///
"""
Generate .ics files for the djehuty Community Hour calendar from calendar/events.yaml.

For each event in events.yaml this writes an individual file at
  assets/ics/<filename>
(the same path already referenced by events.yaml's `filename` field and used
by the "Add to calendar" button and the Calendar page).

It also writes one combined, subscribable feed containing every event:
  assets/ics/community-hour.ics

Run manually with:
  python3 scripts/generate_ics.py

Wired up as a Quarto pre-render script (see _quarto.yml), so it runs
automatically before every `quarto render` / `quarto preview`.

Requires: PyYAML (pip install pyyaml)
"""

import datetime
import pathlib
import re
import sys
import zoneinfo

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVENTS_FILE = ROOT / "calendar" / "events.yaml"
OUTPUT_DIR = ROOT / "assets" / "ics"
FEED_FILENAME = "community-hour.ics"
FEED_PATH = OUTPUT_DIR / FEED_FILENAME

# Default meeting length when an event doesn't specify one.
DEFAULT_DURATION_MINUTES = 60

# Standing links included in every event's description below the
# event-specific blurb. Edit here to update them everywhere at once.
DJEHUTY_REPO_URL = "https://github.com/4TUResearchData/djehuty"
ROLLING_NOTES_URL = "https://hackmd.io/@6bIO96d8RkOmyO6gPwZYAA/S1Zrdz3OGx"
COMMUNITY_SITE_URL = "https://djehuty.4tu.nl/community/"

# Events are given in Europe/Amsterdam local time in events.yaml; this
# converts them to UTC when writing the .ics files (see build_vevent).
# UTC timestamps ("...Z") need no VTIMEZONE block and are the most widely
# and reliably supported format — some clients (Outlook in particular) are
# unreliable with a hand-written VTIMEZONE that doesn't match their own.
EVENT_TZ = zoneinfo.ZoneInfo("Europe/Amsterdam")


def load_events():
    if not EVENTS_FILE.exists():
        sys.exit(f"error: {EVENTS_FILE} not found")
    with EVENTS_FILE.open(encoding="utf-8") as fh:
        events = yaml.safe_load(fh) or []
    if not isinstance(events, list):
        sys.exit(f"error: {EVENTS_FILE} must contain a list of events")
    return events


def parse_time(time_str):
    """Parse a 'HH:MM' or 'HH:MM CEST'/'HH:MM CET' string into (hour, minute).
    The timezone abbreviation, if present, is informational only: every event
    is treated as Europe/Amsterdam local time via TZID, so DST is handled by
    the VTIMEZONE block above rather than by this suffix."""
    match = re.match(r"^\s*(\d{1,2}):(\d{2})", str(time_str))
    if not match:
        sys.exit(f"error: could not parse time '{time_str}'")
    return int(match.group(1)), int(match.group(2))


def escape_text(value):
    """Escape text per RFC 5545 (comma, semicolon, backslash, newline)."""
    value = str(value)
    value = value.replace("\\", "\\\\")
    value = value.replace(",", "\\,")
    value = value.replace(";", "\\;")
    value = value.replace("\n", "\\n")
    return value


def fold_line(line, limit=75):
    """Fold a line to <=75 octets per RFC 5545, continuation lines start with a space."""
    if len(line.encode("utf-8")) <= limit:
        return line
    out = []
    current = line
    first = True
    while len(current.encode("utf-8")) > limit:
        # Fold on a byte boundary; content here is ASCII-safe (escaped already).
        cut = limit if first else limit - 1
        out.append((current[:cut]) if first else " " + current[:cut])
        current = current[cut:]
        first = False
    out.append(current if first else " " + current)
    return "\r\n".join(out)


def build_description(event, path):
    """Combine the event's own one-line blurb (from events.yaml) with the
    standing Community Hour boilerplate: how to join, what the meeting is,
    and links to the rolling notes doc and the community site. Blank lines
    become paragraph breaks once escaped into the .ics DESCRIPTION field."""
    parts = []

    blurb = event.get("description", "").strip()
    if blurb:
        parts.append(blurb)

    if path:
        parts.append(f"Join with Google Meet: {path}")

    parts.append(
        f"Join Community Hour of djehuty: {DJEHUTY_REPO_URL}.\n"
        "We meet monthly to discuss recent developments, upcoming work, "
        "community contributions, feature requests, and other topics "
        "relevant to the djehuty project."
    )

    parts.append(
        f"Rolling Notes: {ROLLING_NOTES_URL}\n"
        f"Community website: {COMMUNITY_SITE_URL}"
    )

    return "\n\n".join(parts)


def build_vevent(event, dtstamp):
    date_str = event.get("date")
    time_str = event.get("time")
    title = event.get("title", "djehuty Community Hour")
    location = event.get("location", "")
    path = event.get("path", "")
    duration = int(event.get("duration_minutes", DEFAULT_DURATION_MINUTES))

    if not date_str or not time_str:
        sys.exit(f"error: event '{title}' is missing 'date' or 'time'")

    hour, minute = parse_time(time_str)
    local_start = datetime.datetime.combine(
        date_str if isinstance(date_str, datetime.date) else
        datetime.date.fromisoformat(str(date_str)),
        datetime.time(hour, minute),
        tzinfo=EVENT_TZ,
    )
    local_end = local_start + datetime.timedelta(minutes=duration)
    start = local_start.astimezone(datetime.timezone.utc)
    end = local_end.astimezone(datetime.timezone.utc)

    uid_date = start.strftime("%Y%m%dT%H%M%S")
    # The domain is a uniqueness namespace, not a link. Keep it stable: a UID
    # identifies an event for that event's lifetime (RFC 5545), so changing it
    # later would make subscribed calendars treat every event as a new one.
    uid = f"djehuty-community-hour-{uid_date}@djehuty.4tu.nl"

    full_description = build_description(event, path)

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{escape_text(title)}",
    ]
    if location:
        lines.append(f"LOCATION:{escape_text(location)}")
    if full_description:
        lines.append(f"DESCRIPTION:{escape_text(full_description)}")
    if path:
        lines.append(f"URL:{path}")
    lines.append("END:VEVENT")
    return [fold_line(line) for line in lines]


def build_calendar(vevent_blocks, calendar_name=None):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//djehuty community//Community Hour//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    if calendar_name:
        lines.append(f"X-WR-CALNAME:{escape_text(calendar_name)}")
        lines.append("REFRESH-INTERVAL;VALUE=DURATION:P1D")
        lines.append("X-PUBLISHED-TTL:P1D")
    for block in vevent_blocks:
        lines.extend(block)
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    events = load_events()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dtstamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    all_blocks = []
    seen_filenames = set()

    for event in events:
        filename = event.get("filename")
        if not filename:
            sys.exit(f"error: event '{event.get('title')}' is missing 'filename'")
        if filename in seen_filenames:
            sys.exit(
                f"error: filename '{filename}' is used by more than one event — "
                "each event needs its own .ics filename"
            )
        seen_filenames.add(filename)

        block = build_vevent(event, dtstamp)
        all_blocks.append(block)

        single_ics = build_calendar([block])
        (OUTPUT_DIR / filename).write_text(single_ics, encoding="utf-8", newline="")
        print(f"wrote {OUTPUT_DIR / filename}")

    feed = build_calendar(all_blocks, calendar_name="djehuty Community Hour")
    FEED_PATH.write_text(feed, encoding="utf-8", newline="")
    print(f"wrote {FEED_PATH} ({len(all_blocks)} event(s))")


if __name__ == "__main__":
    main()
