"""Tests for visibility of repeating (recurring) to-dos.

Things 3 stores a repeating to-do as one template row carrying a recurrence
rule, and materializes at most one real instance ahead of today. things.py
additionally filters every template row out of its queries. Together that made
repeating to-dos invisible in Today / Upcoming / search (things-mcp #67).

These tests exercise the projection that fills that gap.
"""

import plistlib
import sqlite3
from datetime import date, timedelta

import pytest

from things_mcp import recurrence


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def make_rule(unit, interval=1, constraints=None, repeat_type=0, anchor=None,
              lead_days=0, end_date=None, count_limit=0):
    """Build a recurrence-rule plist blob the way Things stores one."""
    anchor = anchor or date(2026, 1, 1)
    rule = {
        "rrv": 4,
        "tp": repeat_type,
        "fu": unit,
        "fa": interval,
        "of": constraints if constraints is not None else [],
        "ia": float(
            (anchor - date(1970, 1, 1)).days * 86400
        ),
        "sr": 0.0,
        # Far-future sentinel = "never ends", matching real data.
        "ed": 64092211200.0 if end_date is None else float(
            (end_date - date(1970, 1, 1)).days * 86400
        ),
        "rc": count_limit,
        "ts": lead_days,
    }
    return plistlib.dumps(rule)


def to_thingsdate(value):
    """Encode a date the way Things packs startDate/deadline integers."""
    if value is None:
        return None
    return (value.year << 16) | (value.month << 12) | (value.day << 7)


SCHEMA = """
CREATE TABLE TMTask (
    uuid TEXT PRIMARY KEY,
    title TEXT,
    notes TEXT,
    type INTEGER DEFAULT 0,
    status INTEGER DEFAULT 0,
    trashed INTEGER DEFAULT 0,
    project TEXT,
    area TEXT,
    heading TEXT,
    startDate INTEGER,
    deadline INTEGER,
    rt1_repeatingTemplate TEXT,
    rt1_recurrenceRule BLOB,
    rt1_nextInstanceStartDate INTEGER,
    rt1_instanceCreationPaused INTEGER
);
"""


@pytest.fixture(autouse=True)
def no_real_recurrence_templates():
    """Override the global guard from conftest.

    These tests drive the projection deliberately, against purpose-built
    temporary databases, so the real ``fetch_templates`` must stay live.
    """
    yield


@pytest.fixture
def things_db(tmp_path):
    """A minimal Things-shaped SQLite database with helpers to populate it."""
    path = tmp_path / "main.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.commit()

    class DB:
        filepath = str(path)

        @staticmethod
        def add_template(uuid, title, rule, status=0, trashed=0, project=None,
                         next_instance=None, paused=0, notes=None):
            connection.execute(
                "INSERT INTO TMTask (uuid, title, notes, status, trashed, project,"
                " rt1_recurrenceRule, rt1_nextInstanceStartDate,"
                " rt1_instanceCreationPaused)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (uuid, title, notes, status, trashed, project, rule,
                 to_thingsdate(next_instance), paused),
            )
            connection.commit()

        @staticmethod
        def add_instance(uuid, template_uuid, start, trashed=0, status=0):
            connection.execute(
                "INSERT INTO TMTask (uuid, title, status, trashed,"
                " rt1_repeatingTemplate, startDate) VALUES (?,?,?,?,?,?)",
                (uuid, "instance", status, trashed, template_uuid,
                 to_thingsdate(start)),
            )
            connection.commit()

        @staticmethod
        def add_project(uuid, title, status=0, trashed=0):
            connection.execute(
                "INSERT INTO TMTask (uuid, title, type, status, trashed)"
                " VALUES (?,?,1,?,?)",
                (uuid, title, status, trashed),
            )
            connection.commit()

    yield DB
    connection.close()


# --------------------------------------------------------------------------
# Rule decoding
# --------------------------------------------------------------------------

class TestRuleParsing:
    """The recurrence rule is an XML plist with abbreviated keys."""

    def test_parses_weekly_rule(self):
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_WEEK, interval=2,
                      constraints=[{"wd": 1}], anchor=date(2026, 1, 5))
        )
        assert rule["unit"] == recurrence.UNIT_WEEK
        assert rule["interval"] == 2
        assert rule["type"] == recurrence.TYPE_FIXED_SCHEDULE
        assert rule["anchor"] == date(2026, 1, 5)
        assert rule["constraints"] == [
            {"day": None, "month": None, "weekday": 1, "weekday_ordinal": None}
        ]

    def test_parses_yearly_rule_with_month_and_day(self):
        # dy/mo are 0-indexed: dy=13, mo=1 means February 14th.
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_YEAR, constraints=[{"dy": 13, "mo": 1}],
                      anchor=date(2026, 2, 14))
        )
        assert recurrence.occurrences(
            rule, date(2026, 1, 1), date(2026, 12, 31)
        ) == [date(2026, 2, 14)]

    def test_returns_none_for_unparseable_rule(self):
        assert recurrence.parse_recurrence_rule(b"not a plist") is None
        assert recurrence.parse_recurrence_rule(None) is None


# --------------------------------------------------------------------------
# Occurrence projection
# --------------------------------------------------------------------------

class TestOccurrenceProjection:
    """Projecting a rule onto a date window."""

    def test_weekly_template_appears_once_per_week_over_four_weeks(self):
        # Every Thursday (wd=4, 0-indexed from Sunday).
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_WEEK, constraints=[{"wd": 4}],
                      anchor=date(2026, 9, 3))
        )
        found = recurrence.occurrences(
            rule, date(2026, 9, 1), date(2026, 9, 28), max_occurrences=8
        )
        assert found == [
            date(2026, 9, 3), date(2026, 9, 10),
            date(2026, 9, 17), date(2026, 9, 24),
        ]
        assert all(d.weekday() == 3 for d in found)  # Thursday

    def test_daily_template_appears_every_day(self):
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_DAY, constraints=[{"dy": 0}],
                      anchor=date(2026, 9, 1))
        )
        found = recurrence.occurrences(
            rule, date(2026, 9, 1), date(2026, 9, 30), max_occurrences=5
        )
        assert found == [date(2026, 9, d) for d in range(1, 6)]

    def test_interval_greater_than_one_keeps_phase(self):
        # Every 2 weeks on Tuesday (wd=2), anchored on a real occurrence.
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_WEEK, interval=2,
                      constraints=[{"wd": 2}], anchor=date(2026, 9, 1))
        )
        found = recurrence.occurrences(
            rule, date(2026, 9, 1), date(2026, 10, 31), max_occurrences=4
        )
        assert found == [
            date(2026, 9, 1), date(2026, 9, 15),
            date(2026, 9, 29), date(2026, 10, 13),
        ]

    def test_monthly_day_of_month_is_zero_indexed(self):
        # dy=0 is the 1st of the month.
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_MONTH, constraints=[{"dy": 0}],
                      anchor=date(2026, 9, 1))
        )
        found = recurrence.occurrences(
            rule, date(2026, 9, 1), date(2026, 12, 31), max_occurrences=8
        )
        assert found == [date(2026, m, 1) for m in (9, 10, 11, 12)]

    def test_monthly_last_day_of_month(self):
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_MONTH, constraints=[{"dy": -1}],
                      anchor=date(2026, 1, 31))
        )
        found = recurrence.occurrences(
            rule, date(2026, 1, 1), date(2026, 4, 30), max_occurrences=8
        )
        assert found == [
            date(2026, 1, 31), date(2026, 2, 28),
            date(2026, 3, 31), date(2026, 4, 30),
        ]

    def test_monthly_nth_weekday(self):
        # First Tuesday of each month: wd=2, wdo=1.
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_MONTH, constraints=[{"wd": 2, "wdo": 1}],
                      anchor=date(2026, 9, 1))
        )
        found = recurrence.occurrences(
            rule, date(2026, 9, 1), date(2026, 11, 30), max_occurrences=8
        )
        assert found == [date(2026, 9, 1), date(2026, 10, 6), date(2026, 11, 3)]

    def test_multiple_weekdays_in_one_week(self):
        # Mon (1), Wed (3), Fri (5).
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_WEEK,
                      constraints=[{"wd": 1}, {"wd": 3}, {"wd": 5}],
                      anchor=date(2026, 9, 7))
        )
        found = recurrence.occurrences(
            rule, date(2026, 9, 7), date(2026, 9, 13), max_occurrences=8
        )
        assert found == [date(2026, 9, 7), date(2026, 9, 9), date(2026, 9, 11)]

    def test_lead_time_shifts_start_date_earlier(self):
        # Due Feb 14 every year, surfacing 14 days earlier (ts=-14).
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_YEAR, constraints=[{"dy": 13, "mo": 1}],
                      anchor=date(2026, 2, 14), lead_days=-14)
        )
        assert recurrence.occurrences(
            rule, date(2027, 1, 1), date(2027, 12, 31)
        ) == [date(2027, 1, 31)]

    def test_max_occurrences_is_respected(self):
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_DAY, anchor=date(2026, 9, 1))
        )
        found = recurrence.occurrences(
            rule, date(2026, 9, 1), date(2027, 9, 1), max_occurrences=3
        )
        assert len(found) == 3

    def test_rule_end_date_stops_the_series(self):
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_DAY, anchor=date(2026, 9, 1),
                      end_date=date(2026, 9, 3))
        )
        found = recurrence.occurrences(
            rule, date(2026, 9, 1), date(2026, 9, 30), max_occurrences=10
        )
        assert found == [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]

    def test_after_completion_rules_are_not_projected(self):
        """tp=1 dates depend on when each instance is completed, so a series
        cannot be derived from the rule — nothing is invented."""
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_DAY, interval=2,
                      repeat_type=recurrence.TYPE_AFTER_COMPLETION,
                      anchor=date(2026, 9, 1))
        )
        assert recurrence.occurrences(
            rule, date(2026, 9, 1), date(2026, 9, 30)
        ) == []

    def test_empty_window_returns_nothing(self):
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_DAY, anchor=date(2026, 9, 1))
        )
        assert recurrence.occurrences(
            rule, date(2026, 9, 10), date(2026, 9, 1)
        ) == []


# --------------------------------------------------------------------------
# Template loading and status filtering
# --------------------------------------------------------------------------

class TestTemplateLoading:
    """Only live templates should ever produce occurrences."""

    def test_active_template_is_loaded(self, things_db):
        things_db.add_template("tpl-1", "Water plants",
                               make_rule(recurrence.UNIT_DAY))
        templates = recurrence.fetch_templates(things_db.filepath)
        assert [t["title"] for t in templates] == ["Water plants"]

    @pytest.mark.parametrize("status,label", [(2, "canceled"), (3, "completed")])
    def test_canceled_and_completed_templates_leak_nothing(self, things_db, status, label):
        things_db.add_template(f"tpl-{label}", f"{label} template",
                               make_rule(recurrence.UNIT_DAY,
                                         anchor=date(2026, 9, 1)),
                               status=status)
        assert recurrence.fetch_templates(things_db.filepath) == []
        assert recurrence.recurring_occurrences(
            date(2026, 9, 1), date(2026, 9, 30),
            templates=recurrence.fetch_templates(things_db.filepath),
        ) == []

    def test_trashed_template_leaks_nothing(self, things_db):
        things_db.add_template("tpl-trash", "Trashed",
                               make_rule(recurrence.UNIT_DAY), trashed=1)
        assert recurrence.fetch_templates(things_db.filepath) == []

    def test_paused_template_leaks_nothing(self, things_db):
        things_db.add_template("tpl-paused", "Paused",
                               make_rule(recurrence.UNIT_DAY), paused=1)
        assert recurrence.fetch_templates(things_db.filepath) == []

    def test_template_in_canceled_project_leaks_nothing(self, things_db):
        """Guards the mismatch where a canceled project is hidden but its
        children still surface."""
        things_db.add_project("proj-dead", "Canceled project", status=2)
        things_db.add_template("tpl-child", "Child of canceled project",
                               make_rule(recurrence.UNIT_DAY),
                               project="proj-dead")
        assert recurrence.fetch_templates(things_db.filepath) == []

    def test_template_in_active_project_is_loaded(self, things_db):
        things_db.add_project("proj-live", "Active project", status=0)
        things_db.add_template("tpl-child", "Child of active project",
                               make_rule(recurrence.UNIT_DAY),
                               project="proj-live")
        assert len(recurrence.fetch_templates(things_db.filepath)) == 1

    def test_missing_database_is_survivable(self, tmp_path):
        assert recurrence.fetch_templates(str(tmp_path / "nope.sqlite")) == []


# --------------------------------------------------------------------------
# Merging into real results
# --------------------------------------------------------------------------

class TestMerging:
    """Projected occurrences must not duplicate rows Things already has."""

    def test_materialized_instance_is_not_double_counted(self, things_db):
        things_db.add_template("tpl-1", "Daily task",
                               make_rule(recurrence.UNIT_DAY,
                                         anchor=date(2026, 9, 1)))
        # Things already created a real row for Sept 2nd.
        things_db.add_instance("inst-1", "tpl-1", date(2026, 9, 2))

        templates = recurrence.fetch_templates(things_db.filepath)
        projected = recurrence.recurring_occurrences(
            date(2026, 9, 1), date(2026, 9, 4), templates=templates
        )
        dates = [t["start_date"] for t in projected]
        assert dates == ["2026-09-01", "2026-09-03", "2026-09-04"]
        assert "2026-09-02" not in dates

    def test_trashed_instance_does_not_suppress_an_occurrence(self, things_db):
        things_db.add_template("tpl-1", "Daily task",
                               make_rule(recurrence.UNIT_DAY,
                                         anchor=date(2026, 9, 1)))
        things_db.add_instance("inst-1", "tpl-1", date(2026, 9, 2), trashed=1)
        templates = recurrence.fetch_templates(things_db.filepath)
        projected = recurrence.recurring_occurrences(
            date(2026, 9, 1), date(2026, 9, 2), templates=templates
        )
        assert [t["start_date"] for t in projected] == ["2026-09-01", "2026-09-02"]

    def test_projected_items_are_tagged(self, things_db):
        things_db.add_template("tpl-1", "Weekly review",
                               make_rule(recurrence.UNIT_WEEK,
                                         constraints=[{"wd": 0}],
                                         anchor=date(2026, 9, 6)))
        templates = recurrence.fetch_templates(things_db.filepath)
        item = recurrence.recurring_occurrences(
            date(2026, 9, 6), date(2026, 9, 6), templates=templates
        )[0]
        assert item["is_recurring"] is True
        assert item["template_id"] == "tpl-1"
        assert item["uuid"] == "tpl-1:2026-09-06"
        assert item["recurrence_unit"] == "week"
        assert item["title"] == "Weekly review"

    def test_after_completion_template_uses_things_own_next_date(self, things_db):
        """Only the one date Things has computed, never a projected series."""
        things_db.add_template(
            "tpl-1", "Shave",
            make_rule(recurrence.UNIT_DAY, interval=4,
                      repeat_type=recurrence.TYPE_AFTER_COMPLETION,
                      anchor=date(2026, 9, 1)),
            next_instance=date(2026, 9, 5),
        )
        templates = recurrence.fetch_templates(things_db.filepath)
        projected = recurrence.recurring_occurrences(
            date(2026, 9, 1), date(2026, 9, 30), templates=templates
        )
        assert [t["start_date"] for t in projected] == ["2026-09-05"]
        assert projected[0]["repeats_after_completion"] is True

    def test_merge_preserves_existing_todos_and_sorts(self, things_db):
        things_db.add_template("tpl-1", "Daily task",
                               make_rule(recurrence.UNIT_DAY,
                                         anchor=date(2026, 9, 1)))
        real = [{"uuid": "real-1", "title": "Real", "start_date": "2026-09-02"}]
        templates = recurrence.fetch_templates(things_db.filepath)
        merged = recurrence.merge_recurring(
            real, date(2026, 9, 1), date(2026, 9, 3), templates=templates
        )
        # Sorted by (start_date, title); "Daily task" sorts before "Real"
        # on the shared 2026-09-02 date.
        assert [t["uuid"] for t in merged] == [
            "tpl-1:2026-09-01", "tpl-1:2026-09-02", "real-1", "tpl-1:2026-09-03",
        ]

    def test_merge_returns_input_unchanged_when_nothing_projects(self, things_db):
        real = [{"uuid": "real-1", "title": "Real", "start_date": "2026-09-02"}]
        assert recurrence.merge_recurring(
            real, date(2026, 9, 1), date(2026, 9, 3), templates=[]
        ) is real


# --------------------------------------------------------------------------
# Server tool integration
# --------------------------------------------------------------------------

class TestServerIntegration:
    """The list/search tools surface projected occurrences."""

    @staticmethod
    def _template(title="Daily standup", anchor=None, notes=None):
        rule = recurrence.parse_recurrence_rule(
            make_rule(recurrence.UNIT_DAY, anchor=anchor or date(2020, 1, 1))
        )
        return {
            "uuid": "tpl-1", "title": title, "notes": notes, "project": None,
            "area": None, "heading": None, "rule": rule,
            "next_instance": None, "existing_dates": set(),
        }

    @pytest.mark.asyncio
    async def test_get_today_includes_todays_occurrence(self, mocker):
        from things_mcp.server import get_today

        mocker.patch("things.today", return_value=[])
        mocker.patch("things_mcp.server.filter_someday_project_tasks",
                     side_effect=lambda todos: todos)
        mocker.patch("things_mcp.recurrence.fetch_templates",
                     return_value=[self._template()])

        result = await get_today()
        items = result.structured_content["items"]
        assert len(items) == 1
        assert items[0]["title"] == "Daily standup"
        assert items[0]["is_recurring"] is True
        assert items[0]["start_date"] == date.today().isoformat()

    @pytest.mark.asyncio
    async def test_get_today_can_opt_out(self, mocker):
        from things_mcp.server import get_today

        mocker.patch("things.today", return_value=[])
        mocker.patch("things_mcp.server.filter_someday_project_tasks",
                     side_effect=lambda todos: todos)
        mocker.patch("things_mcp.recurrence.fetch_templates",
                     return_value=[self._template()])

        result = await get_today(include_recurring=False)
        assert result.structured_content["items"] == []

    @pytest.mark.asyncio
    async def test_get_upcoming_projects_future_occurrences(self, mocker):
        from things_mcp.server import get_upcoming

        mocker.patch("things.upcoming", return_value=[])
        mocker.patch("things_mcp.server.filter_someday_project_tasks",
                     side_effect=lambda todos: todos)
        mocker.patch("things_mcp.recurrence.fetch_templates",
                     return_value=[self._template()])
        mocker.patch("things_mcp.server.RECURRING_OCCURRENCES", 8)

        result = await get_upcoming()
        items = result.structured_content["items"]
        # A daily repeat yields one occurrence per day, starting tomorrow.
        assert len(items) == 8
        assert items[0]["start_date"] == (
            date.today() + timedelta(days=1)
        ).isoformat()
        assert all(i["is_recurring"] for i in items)

    @pytest.mark.asyncio
    async def test_search_todos_matches_template_title(self, mocker):
        from things_mcp.server import search_todos

        mocker.patch("things.search", return_value=[])
        mocker.patch("things_mcp.recurrence.fetch_templates",
                     return_value=[self._template(title="Water the plants")])
        mocker.patch("things_mcp.server.RECURRING_OCCURRENCES", 2)

        result = await search_todos("water")
        items = result.structured_content["items"]
        assert items and all(i["title"] == "Water the plants" for i in items)

    @pytest.mark.asyncio
    async def test_search_todos_ignores_non_matching_templates(self, mocker):
        from things_mcp.server import search_todos

        mocker.patch("things.search", return_value=[])
        mocker.patch("things_mcp.recurrence.fetch_templates",
                     return_value=[self._template(title="Water the plants")])

        result = await search_todos("mortgage")
        assert result.structured_content["items"] == []

    @pytest.mark.asyncio
    async def test_projection_failure_leaves_view_intact(self, mocker):
        """A broken projection must never break an existing list view."""
        from things_mcp.server import get_today

        real = [{"uuid": "real-1", "title": "Real", "type": "to-do"}]
        mocker.patch("things.today", return_value=real)
        mocker.patch("things_mcp.server.filter_someday_project_tasks",
                     side_effect=lambda todos: todos)
        mocker.patch("things_mcp.recurrence.fetch_templates",
                     side_effect=RuntimeError("database exploded"))

        result = await get_today()
        assert [i["uuid"] for i in result.structured_content["items"]] == ["real-1"]
