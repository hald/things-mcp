"""Materialize occurrences of repeating (recurring) to-dos.

Background
----------
Things 3 stores a repeating to-do as a single *template* row in ``TMTask``
carrying a recurrence rule in the ``rt1_recurrenceRule`` BLOB column. Things
itself materializes only ONE real instance ahead of "now"; the rest of the
series exists purely as the rule.

On top of that, things.py hard-codes ``TASK.rt1_recurrenceRule IS NULL`` into
the WHERE clause of *every* task query (see ``things/database.py``), so
templates are invisible to the entire things.py API — there is no parameter
that opts back in. That is why repeating to-dos never showed up in
``get_today`` / ``get_upcoming`` / ``search_todos`` (things-mcp #67).

This module therefore reads the template rows directly from the same SQLite
file things.py uses (read-only), decodes the rule, and projects occurrences
onto a requested date window.

Rule encoding
-------------
``rt1_recurrenceRule`` is an XML property list. Keys (reverse-engineered and
validated against real materialized instances):

==========  ====================================================================
``rrv``     Rule format version (4 in all observed data).
``tp``      Repeat type. ``0`` = fixed calendar schedule, ``1`` = repeat a
            fixed span *after completion*.
``fu``      Frequency unit, using legacy ``NSCalendarUnit`` constants:
            ``4`` = year, ``8`` = month, ``16`` = day, ``256`` = week.
``fa``      Frequency amount — the "every N units" interval.
``of``      List of constraint dicts narrowing which dates in a period match:
            ``dy``  day of month, 0-indexed (``0`` = the 1st); ``-1`` = last day
            ``mo``  month, 0-indexed (``0`` = January)
            ``wd``  weekday, 0-indexed from Sunday (``0`` = Sun ... ``6`` = Sat)
            ``wdo`` weekday ordinal — the nth ``wd`` of the period (1 = first)
``ia``      Anchor date (Unix seconds, UTC). Always falls on a valid
            occurrence, so it is used as the phase anchor for ``fa`` > 1.
``sr``      Series start. Rewritten when the user edits the rule, and observed
            to post-date existing instances, so it is NOT used for phasing.
``ed``      End date (Unix seconds). A far-future sentinel means "never".
``rc``      Occurrence limit; ``0`` means unlimited.
``ts``      Lead time in days (<= 0). The ``of`` constraints resolve to the
            occurrence's *due* date; the to-do becomes visible ``ts`` days
            earlier. Verified against ``rt1_nextInstanceStartDate``, which
            equals ``due date + ts`` (e.g. a Feb 14 yearly rule with
            ``ts = -14`` reports a next start of Jan 31).
==========  ====================================================================

Scope
-----
This module deliberately does not reimplement Things' full recurrence engine.
For ``tp=1`` ("after completion") rules the future schedule genuinely cannot be
derived from the rule — each date depends on when the user completes the
previous instance — so only the single next date Things has already computed
(``rt1_nextInstanceStartDate``) is surfaced. Nothing is invented.
"""

import calendar
import logging
import os
import plistlib
import sqlite3
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Frequency units (legacy NSCalendarUnit values).
UNIT_YEAR = 4
UNIT_MONTH = 8
UNIT_DAY = 16
UNIT_WEEK = 256

UNIT_NAMES = {
    UNIT_YEAR: "year",
    UNIT_MONTH: "month",
    UNIT_DAY: "day",
    UNIT_WEEK: "week",
}

# Repeat types.
TYPE_FIXED_SCHEDULE = 0
TYPE_AFTER_COMPLETION = 1

# Default number of occurrences materialized per template.
DEFAULT_MAX_OCCURRENCES = 8

# Safety valve: never step more than this many periods looking for matches.
_MAX_PERIOD_STEPS = 2000

# Things encodes some dates as YYYYYYYYYYYMMMMDDDDD0000000 in a single integer.
_YEAR_MASK = 134152192
_MONTH_MASK = 61440
_DAY_MASK = 3968


def _thingsdate_to_date(value):
    """Decode Things' packed integer date format into a ``datetime.date``."""
    if not value:
        return None
    year = (value & _YEAR_MASK) >> 16
    month = (value & _MONTH_MASK) >> 12
    day = (value & _DAY_MASK) >> 7
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _unixtime_to_date(value):
    """Decode a Unix timestamp into a UTC ``datetime.date``."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).date()
    except (ValueError, OverflowError, OSError):
        return None


def database_path():
    """Resolve the same Things SQLite path things.py uses."""
    env_path = os.getenv("THINGSDB")
    if env_path:
        return env_path
    from things.database import DEFAULT_FILEPATH

    return DEFAULT_FILEPATH


def parse_recurrence_rule(blob):
    """Decode an ``rt1_recurrenceRule`` BLOB into a plain dict.

    Returns None when the blob is missing or cannot be decoded, so a single
    malformed rule can never take down a whole list view.
    """
    if not blob:
        return None
    try:
        plist = plistlib.loads(blob)
    except Exception:
        logger.debug("Could not decode recurrence rule plist", exc_info=True)
        return None
    if not isinstance(plist, dict):
        return None

    constraints = []
    for entry in plist.get("of") or []:
        if isinstance(entry, dict):
            constraints.append(
                {
                    "day": entry.get("dy"),
                    "month": entry.get("mo"),
                    "weekday": entry.get("wd"),
                    "weekday_ordinal": entry.get("wdo"),
                }
            )

    return {
        "type": plist.get("tp", TYPE_FIXED_SCHEDULE),
        "unit": plist.get("fu"),
        "interval": max(1, int(plist.get("fa") or 1)),
        "constraints": constraints,
        "anchor": _unixtime_to_date(plist.get("ia")),
        # Lead time in days (<= 0): start date = due date + lead_days.
        "lead_days": int(plist.get("ts") or 0),
        "end_date": _unixtime_to_date(plist.get("ed")),
        "count_limit": plist.get("rc") or 0,
    }


def _rule_weekday_to_python(weekday):
    """Convert rule weekday (0=Sunday) to ``date.weekday()`` (0=Monday)."""
    return (int(weekday) - 1) % 7


def _month_day(year, month, day_index):
    """Resolve a 0-indexed day-of-month (``-1`` = last day) to a real date."""
    last = calendar.monthrange(year, month)[1]
    day = last if day_index == -1 else int(day_index) + 1
    if day < 1 or day > last:
        return None
    return date(year, month, day)


def _nth_weekday(year, month, weekday, ordinal):
    """Resolve the nth (``ordinal``) ``weekday`` of a month.

    ``ordinal`` is 1-based; negative values count back from the end.
    """
    py_weekday = _rule_weekday_to_python(weekday)
    days = [
        date(year, month, d)
        for d in range(1, calendar.monthrange(year, month)[1] + 1)
        if date(year, month, d).weekday() == py_weekday
    ]
    if not days:
        return None
    index = int(ordinal)
    try:
        return days[index - 1] if index > 0 else days[index]
    except IndexError:
        return None


def _add_months(anchor, months):
    """Shift a date by whole months, clamping the day to the target month."""
    total = anchor.year * 12 + (anchor.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _period_index_for(rule, target):
    """Period index (relative to the anchor) whose period contains ``target``.

    Computed arithmetically rather than by stepping, so a rule anchored years
    away from the requested window costs the same as a nearby one.
    """
    anchor = rule["anchor"]
    unit = rule["unit"]
    interval = rule["interval"]

    if unit == UNIT_DAY:
        delta = (target - anchor).days
    elif unit == UNIT_WEEK:
        anchor_week = anchor - timedelta(days=(anchor.weekday() + 1) % 7)
        target_week = target - timedelta(days=(target.weekday() + 1) % 7)
        delta = (target_week - anchor_week).days // 7
    elif unit == UNIT_MONTH:
        delta = (target.year - anchor.year) * 12 + (target.month - anchor.month)
    elif unit == UNIT_YEAR:
        delta = target.year - anchor.year
    else:
        return 0

    return delta // interval


def _period_dates(rule, period_index):
    """Return the candidate dates produced by one period of the rule."""
    anchor = rule["anchor"]
    unit = rule["unit"]
    interval = rule["interval"]
    step = period_index * interval
    constraints = rule["constraints"]
    results = []

    if unit == UNIT_DAY:
        # Daily rules carry no meaningful constraints.
        results.append(anchor + timedelta(days=step))

    elif unit == UNIT_WEEK:
        # Anchor the week on its Sunday so rule weekdays map cleanly.
        week_start = anchor - timedelta(days=(anchor.weekday() + 1) % 7)
        week_start += timedelta(weeks=step)
        weekdays = [c["weekday"] for c in constraints if c.get("weekday") is not None]
        if not weekdays:
            results.append(anchor + timedelta(weeks=step))
        for weekday in weekdays:
            results.append(week_start + timedelta(days=int(weekday)))

    elif unit == UNIT_MONTH:
        base = _add_months(anchor.replace(day=1), step)
        if not constraints:
            results.append(_add_months(anchor, step))
        for c in constraints:
            if c.get("weekday") is not None and c.get("weekday_ordinal") is not None:
                found = _nth_weekday(
                    base.year, base.month, c["weekday"], c["weekday_ordinal"]
                )
            elif c.get("day") is not None:
                found = _month_day(base.year, base.month, c["day"])
            else:
                found = None
            if found:
                results.append(found)

    elif unit == UNIT_YEAR:
        year = anchor.year + step
        if not constraints:
            try:
                results.append(anchor.replace(year=year))
            except ValueError:
                pass
        for c in constraints:
            month = int(c["month"]) + 1 if c.get("month") is not None else anchor.month
            if not 1 <= month <= 12:
                continue
            if c.get("weekday") is not None and c.get("weekday_ordinal") is not None:
                found = _nth_weekday(year, month, c["weekday"], c["weekday_ordinal"])
            elif c.get("day") is not None:
                found = _month_day(year, month, c["day"])
            else:
                found = None
            if found:
                results.append(found)

    return sorted(set(results))


def occurrences(rule, window_start, window_end, max_occurrences=DEFAULT_MAX_OCCURRENCES):
    """Project a parsed rule onto ``[window_start, window_end]``.

    The window is interpreted in *scheduled start date* space — the date the
    to-do actually surfaces in Today/Upcoming. Internally the rule resolves to
    due dates, which are then shifted by the rule's lead time.

    Only fixed-schedule (``tp=0``) rules are projected. "After completion"
    rules are not predictable from the rule alone and are handled by the
    caller using the single next date Things has already computed.
    """
    if not rule or rule.get("anchor") is None:
        return []
    if rule.get("type") != TYPE_FIXED_SCHEDULE:
        return []
    if rule.get("unit") not in UNIT_NAMES:
        return []
    if window_end < window_start:
        return []

    # Translate the requested window from start-date space into due-date space.
    lead = timedelta(days=rule.get("lead_days") or 0)
    window_start -= lead
    window_end -= lead

    end_date = rule.get("end_date")
    if end_date and end_date < window_start:
        return []

    # Jump straight to the period containing the start of the window, backing
    # off one period so a match that lands early in the window is not missed.
    index = _period_index_for(rule, window_start) - 1

    found = []
    steps = 0
    while steps < _MAX_PERIOD_STEPS and len(found) < max_occurrences:
        dates = _period_dates(rule, index)
        if dates and min(dates) > window_end:
            break
        for occurrence in dates:
            if occurrence < window_start or occurrence > window_end:
                continue
            if end_date and occurrence > end_date:
                return found
            found.append(occurrence)
            if len(found) >= max_occurrences:
                break
        index += 1
        steps += 1

    limit = rule.get("count_limit") or 0
    if limit:
        found = found[:limit]
    # Back into scheduled-start-date space.
    return [d + lead for d in found]


def _connect(db_path):
    """Open the Things database read-only."""
    uri = "file:{}?mode=ro".format(db_path.replace("?", "%3f").replace("#", "%23"))
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def fetch_templates(db_path=None):
    """Read active repeating templates and their materialized instance dates.

    Returns a list of dicts. Canceled, completed and trashed templates are
    excluded, as are templates whose parent project is canceled/trashed, so
    they never leak occurrences.
    """
    db_path = db_path or database_path()
    try:
        connection = _connect(db_path)
    except sqlite3.Error:
        logger.debug("Could not open Things database for recurrence", exc_info=True)
        return []

    templates = []
    try:
        with connection:
            rows = connection.execute(
                """
                SELECT TASK.uuid, TASK.title, TASK.notes, TASK.type,
                       TASK.project, TASK.area, TASK.heading,
                       TASK.rt1_recurrenceRule, TASK.rt1_nextInstanceStartDate,
                       TASK.rt1_instanceCreationPaused, TASK.deadline
                FROM TMTask AS TASK
                LEFT JOIN TMTask AS PROJECT ON TASK.project = PROJECT.uuid
                WHERE TASK.rt1_recurrenceRule IS NOT NULL
                  AND TASK.status = 0
                  AND TASK.trashed = 0
                  AND (TASK.rt1_instanceCreationPaused IS NULL
                       OR TASK.rt1_instanceCreationPaused = 0)
                  AND (PROJECT.uuid IS NULL
                       OR (PROJECT.status = 0 AND PROJECT.trashed = 0))
                """
            ).fetchall()

            for row in rows:
                rule = parse_recurrence_rule(row["rt1_recurrenceRule"])
                if not rule:
                    continue
                instances = connection.execute(
                    """
                    SELECT startDate FROM TMTask
                    WHERE rt1_repeatingTemplate = ? AND trashed = 0
                      AND startDate IS NOT NULL
                    """,
                    (row["uuid"],),
                ).fetchall()
                existing = {
                    d
                    for d in (_thingsdate_to_date(i["startDate"]) for i in instances)
                    if d is not None
                }
                templates.append(
                    {
                        "uuid": row["uuid"],
                        "title": row["title"],
                        "notes": row["notes"],
                        "project": row["project"],
                        "area": row["area"],
                        "heading": row["heading"],
                        "rule": rule,
                        "next_instance": _thingsdate_to_date(
                            row["rt1_nextInstanceStartDate"]
                        ),
                        "existing_dates": existing,
                    }
                )
    except sqlite3.Error:
        logger.debug("Could not read repeating templates", exc_info=True)
        return []
    finally:
        connection.close()

    return templates


def _synthesize(template, occurrence_date):
    """Build a todo-shaped dict for one projected occurrence.

    ``occurrence_date`` is the scheduled start date. When the rule carries a
    lead time the underlying due date is reported as the deadline, matching
    how Things presents the real instance.
    """
    rule = template["rule"]
    lead = rule.get("lead_days") or 0
    deadline = (occurrence_date - timedelta(days=lead)).isoformat() if lead else None
    return {
        # Synthetic, stable and clearly derived — never a real Things uuid.
        "uuid": "{}:{}".format(template["uuid"], occurrence_date.isoformat()),
        "title": template["title"],
        "type": "to-do",
        "status": "incomplete",
        "notes": template.get("notes"),
        "project": template.get("project"),
        "area": template.get("area"),
        "heading": template.get("heading"),
        "start_date": occurrence_date.isoformat(),
        "start": "Anytime",
        "deadline": deadline,
        "is_recurring": True,
        "template_id": template["uuid"],
        "recurrence_unit": UNIT_NAMES.get(rule.get("unit")),
        "recurrence_interval": rule.get("interval"),
        "repeats_after_completion": rule.get("type") == TYPE_AFTER_COMPLETION,
    }


def recurring_occurrences(
    window_start,
    window_end,
    max_occurrences=DEFAULT_MAX_OCCURRENCES,
    templates=None,
):
    """Return synthetic todos for every repeating template in the window.

    Dates Things has already materialized as real rows are skipped, so
    occurrences are never double-counted against the normal things.py results.
    """
    if window_end < window_start:
        return []
    if templates is None:
        templates = fetch_templates()

    results = []
    for template in templates or []:
        rule = template.get("rule") or {}
        existing = template.get("existing_dates") or set()

        if rule.get("type") == TYPE_AFTER_COMPLETION:
            # Not derivable from the rule — trust only Things' own next date.
            next_date = template.get("next_instance")
            dates = (
                [next_date]
                if next_date and window_start <= next_date <= window_end
                else []
            )
        else:
            dates = occurrences(rule, window_start, window_end, max_occurrences)

        for occurrence_date in dates:
            if occurrence_date in existing:
                continue  # Things already has a real row for this date.
            results.append(_synthesize(template, occurrence_date))

    results.sort(key=lambda t: (t["start_date"], t["title"] or ""))
    return results


def merge_recurring(todos, window_start, window_end, max_occurrences=DEFAULT_MAX_OCCURRENCES, templates=None):
    """Merge projected occurrences into a list of real todos.

    Any failure is swallowed and the original list returned unchanged, so
    enabling this can only ever add results — never break an existing view.
    """
    todos = todos or []
    try:
        extra = recurring_occurrences(
            window_start, window_end, max_occurrences, templates=templates
        )
    except Exception:
        logger.debug("Recurring occurrence projection failed", exc_info=True)
        return todos
    if not extra:
        return todos

    seen = {t.get("uuid") for t in todos if isinstance(t, dict)}
    merged = list(todos) + [t for t in extra if t["uuid"] not in seen]
    merged.sort(key=lambda t: (str(t.get("start_date") or "9999-99-99"), t.get("title") or ""))
    return merged
