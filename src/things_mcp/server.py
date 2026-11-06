from typing import List
import hmac
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timedelta
import things
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.dependencies import get_access_token
from fastmcp.tools.tool import ToolResult
from .formatters import format_todo, format_project, format_area, format_tag, format_heading
from . import url_scheme
from .scope import (
    DENY_ALL, SCOPE_CLAIM, SCOPE_ENV, Credential, Scope,
    ScopeError, ScopeView, load_credentials_file, scope_from_env, token_digest,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Transport configuration via environment variables
TRANSPORT = os.environ.get("THINGS_MCP_TRANSPORT", "stdio")  # "stdio" or "http"
HTTP_HOST = os.environ.get("THINGS_MCP_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("THINGS_MCP_PORT", "8000"))
AUTH_TOKEN_ENV = "THINGS_MCP_AUTH_TOKEN"
TOKENS_FILE_ENV = "THINGS_MCP_TOKENS_FILE"
MIN_AUTH_TOKEN_LENGTH = 32

# Applies to stdio, and to THINGS_MCP_AUTH_TOKEN in HTTP mode.
PROCESS_SCOPE = scope_from_env(os.environ)

# Tags that don't exist yet are created only when their name starts with one of
# these prefixes (';'-separated, e.g. "zed:;ai:"). Unset creates none, since
# tag names are global in Things, outside any area.
CREATE_TAG_PREFIXES_ENV = "THINGS_MCP_CREATE_TAG_PREFIXES"
CREATE_TAG_PREFIXES = tuple(
    prefix.strip()
    for prefix in os.environ.get(CREATE_TAG_PREFIXES_ENV, "").split(";")
    if prefix.strip()
)

MISSING_TOKEN_MESSAGE = (
    "THINGS_AUTH_TOKEN not configured. This change requires it. "
    "Enable in Things → Settings → General → Manage."
)

# Initialize FastMCP server
mcp = FastMCP("Things")


class BearerTokenVerifier(TokenVerifier):
    """Accept HTTP requests whose bearer token matches a configured credential.

    Each credential carries its own scope, attached to the access token as a
    claim. Only SHA-256 digests are kept, compared in constant time. FastMCP's
    StaticTokenVerifier is documented as development-only.
    """

    def __init__(self, credentials: list[Credential]):
        super().__init__()
        self._credentials = list(credentials)

    async def verify_token(self, token: str) -> AccessToken | None:
        digest = token_digest(token)
        match = None
        for credential in self._credentials:
            if hmac.compare_digest(digest, credential.digest):
                match = credential
        if match is None:
            return None
        return AccessToken(
            token=token, client_id=match.name, scopes=[],
            claims={SCOPE_CLAIM: match.scope.to_claim()},
        )


def _http_auth_from_env(environ=os.environ) -> BearerTokenVerifier:
    """Build the HTTP auth provider, refusing to start without a strong token.

    HTTP mode exposes read and write access to the Things database, so it
    fails closed: any process or host that can reach the port would otherwise
    have full access.
    """
    credentials = []

    token = environ.get(AUTH_TOKEN_ENV, "").strip()
    tokens_file = environ.get(TOKENS_FILE_ENV, "").strip()
    if not token and not tokens_file:
        raise SystemExit(
            f"HTTP transport requires {AUTH_TOKEN_ENV} or {TOKENS_FILE_ENV}. Generate a "
            f"token with `openssl rand -hex 32` and send it as 'Authorization: Bearer <token>'."
        )

    if token:
        if len(token) < MIN_AUTH_TOKEN_LENGTH:
            raise SystemExit(
                f"{AUTH_TOKEN_ENV} must be at least {MIN_AUTH_TOKEN_LENGTH} characters. "
                f"Generate one with `openssl rand -hex 32`."
            )
        credentials.append(Credential(
            name=AUTH_TOKEN_ENV, digest=token_digest(token), scope=scope_from_env(environ),
        ))
    elif SCOPE_ENV in environ:
        # It only applies to THINGS_MCP_AUTH_TOKEN; ignoring it silently would
        # leave someone believing access is narrower than it is.
        raise SystemExit(
            f"{SCOPE_ENV} only applies to {AUTH_TOKEN_ENV}. "
            f"Set a \"scope\" per token in {TOKENS_FILE_ENV} instead."
        )

    if tokens_file:
        try:
            credentials.extend(load_credentials_file(tokens_file))
        except (OSError, ValueError) as error:
            raise SystemExit(f"Invalid {TOKENS_FILE_ENV} ({tokens_file}): {error}")

    names = [c.name for c in credentials]
    digests = [c.digest for c in credentials]
    if len(set(names)) != len(names):
        raise SystemExit("Every token needs a unique name.")
    if len(set(digests)) != len(digests):
        raise SystemExit("The same token is configured more than once.")

    for credential in credentials:
        logger.info("HTTP token %r: %s", credential.name, credential.scope.describe())
    return BearerTokenVerifier(credentials)


def _current_scope() -> Scope:
    if mcp.auth is None:
        return PROCESS_SCOPE
    access_token = get_access_token()
    if access_token is None:
        return DENY_ALL
    return Scope.from_claim((access_token.claims or {}).get(SCOPE_CLAIM))


def _scope_view() -> ScopeView:
    return ScopeView(_current_scope())


def _require_unrestricted(view: ScopeView, action: str) -> None:
    if not view.unrestricted:
        raise ScopeError(
            f"{action} isn't available because this server is limited to specific areas and projects."
        )


# Build a set of Someday project UUIDs and a mapping of heading UUID -> project UUID
# for headings that belong to Someday projects.
def _get_someday_context():
    """Return (someday_project_ids, heading_to_project) for Someday filtering.

    Returns:
        Tuple of (set of Someday project UUIDs, dict mapping heading UUID to project UUID)
    """
    try:
        someday_project_ids = {p['uuid'] for p in (things.projects(start='Someday') or [])}
    except Exception:
        return set(), {}
    if not someday_project_ids:
        return set(), {}
    # Build heading -> project mapping for headings inside Someday projects
    heading_to_project = {}
    for proj_id in someday_project_ids:
        try:
            headings = things.tasks(type='heading', project=proj_id)
            for h in (headings or []):
                heading_to_project[h['uuid']] = proj_id
        except Exception:
            pass
    return someday_project_ids, heading_to_project


def _is_in_someday_project(todo, someday_project_ids, heading_to_project):
    """Check if a todo belongs to a Someday project, directly or via heading."""
    if todo.get('project') in someday_project_ids:
        return True
    if not todo.get('project') and todo.get('heading'):
        return todo['heading'] in heading_to_project
    return False


def _today_fallback():
    """Re-implementation of ``things.today()`` with a None-safe sort key.

    Workaround for an upstream things-py bug (see things-mcp #43): the
    library's ``today()`` aggregates three task sets and sorts the union
    on ``(today_index, start_date)``. The "unconfirmed overdue" branch
    selects tasks via ``start_date=False`` — i.e. tasks with a deadline
    today but no start date — so ``start_date`` is None for those rows.
    Mixed with the other two branches (which have string start_dates),
    the tuple comparison crashes with
    ``'<' not supported between instances of 'NoneType' and 'str'``.

    We push None start_dates to the end with a sentinel string.
    """
    regular = things.tasks(
        start_date=True, start="Anytime", index="todayIndex", include_items=True
    ) or []
    unconfirmed_scheduled = things.tasks(
        start_date="past", start="Someday", index="todayIndex", include_items=True
    ) or []
    unconfirmed_overdue = things.tasks(
        start_date=False, deadline="past", deadline_suppressed=False, include_items=True
    ) or []
    result = [*regular, *unconfirmed_scheduled, *unconfirmed_overdue]
    result.sort(key=lambda t: (
        t["today_index"] if t.get("today_index") is not None else 0,
        t["start_date"] if t.get("start_date") is not None else "9999-99-99",
    ))
    return result


# Helper function to filter out tasks from Someday projects
def filter_someday_project_tasks(todos):
    """Filter out tasks that belong to Someday projects.

    This matches Things UI behavior where tasks from Someday projects
    don't appear in Today, Upcoming, or Anytime views. Handles both
    direct project membership and tasks under headings in Someday projects.

    Args:
        todos: List of todo dictionaries

    Returns:
        Filtered list excluding tasks from Someday projects
    """
    someday_project_ids, heading_to_project = _get_someday_context()
    if not someday_project_ids:
        return todos
    return [todo for todo in todos if not _is_in_someday_project(todo, someday_project_ids, heading_to_project)]


# Pagination helpers
def _validate_pagination(limit, offset):
    """Return an error string if limit/offset are invalid, else None."""
    if limit is not None and limit <= 0:
        return "Error: limit must be a positive integer"
    if offset < 0:
        return "Error: offset must be zero or a positive integer"
    return None


def _paginate_format(items, formatter, limit, offset, empty_msg, separator="\n\n---\n\n"):
    """Format a list with optional limit/offset pagination.

    When limit is None and offset is 0, output is byte-identical to the
    pre-pagination behavior (no header). Otherwise a "Showing X-Y of Z
    items" header is prepended so the caller knows there is more to fetch.
    """
    items = items or []
    total = len(items)

    # Fast path: preserve exact legacy output when no pagination requested.
    if limit is None and offset == 0:
        if not items:
            return empty_msg
        return separator.join(formatter(i) for i in items)

    if total == 0:
        return empty_msg
    if offset >= total:
        return f"Showing 0 of {total} items (offset {offset} is past the end)"

    end = total if limit is None else offset + limit
    page = items[offset:end]
    header = f"Showing {offset + 1}-{offset + len(page)} of {total} items\n\n"
    return header + separator.join(formatter(i) for i in page)


def _paginate_result(items, formatter, limit, offset, empty_msg, separator="\n\n---\n\n",
                     *, view=None):
    """Like _paginate_format, but returns a FastMCP ToolResult that carries
    BOTH the human-readable text (channel 1) AND JSON-safe structured data
    (channel 2) under structured_content.

    Items are first narrowed to the caller's scope. Doing it here covers every
    list/search tool, including ones added later.

    This is the pattern for opting a tool into structured output on FastMCP
    3.x while preserving the nicely formatted text. The text is identical to
    what _paginate_format produces; structured_content adds the raw item
    dicts plus pagination metadata so programmatic clients don't have to
    scrape the prose.
    """
    items = (view or _scope_view()).filter(items or [])
    text = _paginate_format(items, formatter, limit, offset, empty_msg, separator)
    total = len(items)
    end = total if limit is None else offset + limit
    page = [] if offset >= total else items[offset:end]
    # structured_content carries the same data the text renders — the full
    # item dicts (including nested checklist / sub-items). things.py dicts
    # contain datetime.date objects, which aren't JSON serializable, so coerce
    # the payload to JSON-safe primitives. Use `limit` to bound large lists;
    # it shrinks both channels together.
    safe_items = json.loads(json.dumps(page, default=str))
    structured = {
        "items": safe_items,
        "count": len(safe_items),
        "total": total,
        "offset": offset,
        "limit": limit,
    }
    return ToolResult(content=text, structured_content=structured)


def _error_result(msg):
    """ToolResult for an error / early-return path: human-readable text plus a
    structured {"error": msg} so structured-output clients see it too."""
    return ToolResult(content=msg, structured_content={"error": msg})


def _prepare_tags(names):
    """Make sure tags exist before Things is asked to apply them.

    The URL scheme silently drops unknown tags, so missing ones are created
    when they carry a configured prefix (CREATE_TAG_PREFIXES) and reported
    otherwise. Returns (tags to apply, created, not applied).

    Reporting a missing tag reveals no more than applying it would: the caller
    could read the tag back from its own to-do.
    """
    if not names:
        return names, [], []
    existing = {tag["title"] for tag in (things.tags() or [])}
    missing = [name for name in dict.fromkeys(names) if name not in existing]
    created = [name for name in missing if name.startswith(CREATE_TAG_PREFIXES)] if CREATE_TAG_PREFIXES else []
    url_scheme.create_tags(created)
    not_applied = [name for name in missing if name not in created]
    return [name for name in names if name not in not_applied], created, not_applied


def _tag_note(created, not_applied):
    notes = []
    if created:
        notes.append(f"created tags: {', '.join(created)}")
    if not_applied:
        notes.append(f"not applied, no such tag in Things: {', '.join(not_applied)}")
    return f" ({'; '.join(notes)})" if notes else ""


# List view tools
@mcp.tool
async def get_inbox(limit: int = None, offset: int = 0) -> ToolResult:
    """Get todos from Inbox

    Args:
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    todos = things.inbox(include_items=True)
    return _paginate_result(todos, format_todo, limit, offset, "No items found")

@mcp.tool
async def get_today(limit: int = None, offset: int = 0) -> ToolResult:
    """Get todos due today

    Args:
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    try:
        todos = things.today(include_items=True)
    except TypeError:
        todos = _today_fallback()
    # Filter out tasks from Someday projects, then paginate
    todos = filter_someday_project_tasks(todos or [])
    return _paginate_result(todos, format_todo, limit, offset, "No items found")

@mcp.tool
async def get_upcoming(limit: int = None, offset: int = 0) -> ToolResult:
    """Get upcoming todos

    Args:
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    todos = things.upcoming(include_items=True)
    # Filter out tasks from Someday projects, then paginate
    todos = filter_someday_project_tasks(todos or [])
    return _paginate_result(todos, format_todo, limit, offset, "No items found")

@mcp.tool
async def get_anytime(limit: int = None, offset: int = 0) -> ToolResult:
    """Get todos from Anytime list

    Args:
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    todos = things.anytime(include_items=True)
    # Filter out tasks from Someday projects, then paginate
    todos = filter_someday_project_tasks(todos or [])
    return _paginate_result(todos, format_todo, limit, offset, "No items found")

@mcp.tool
async def get_someday(limit: int = None, offset: int = 0) -> ToolResult:
    """Get todos from Someday list, including tasks in Someday projects

    Args:
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    todos = things.someday(include_items=True)
    if todos is None:
        todos = []
    # Also include tasks that have start="Anytime" but belong to a Someday project
    # (directly or via a heading), since Things.py doesn't inherit project Someday status
    someday_project_ids, heading_to_project = _get_someday_context()
    if someday_project_ids:
        anytime_todos = things.anytime(include_items=True) or []
        existing_uuids = {t['uuid'] for t in todos}
        for todo in anytime_todos:
            if _is_in_someday_project(todo, someday_project_ids, heading_to_project) and todo['uuid'] not in existing_uuids:
                todos.append(todo)
    return _paginate_result(todos, format_todo, limit, offset, "No items found")

_LOGBOOK_PERIOD_RE = re.compile(r'(\d+)([dwmy])')
_LOGBOOK_PERIOD_DAYS = {'d': 1, 'w': 7, 'm': 30, 'y': 365}


def _parse_logbook_period(period: str):
    """Return a timedelta for strings like '7d', '2w', '3m', '1y', or None."""
    match = _LOGBOOK_PERIOD_RE.fullmatch(period.strip().lower())
    if not match:
        return None
    return timedelta(days=int(match.group(1)) * _LOGBOOK_PERIOD_DAYS[match.group(2)])


def _item_datetime(todo, key):
    """Parse a todo's local-time date field (e.g. 'stop_date', 'created') into a
    naive datetime, or None if absent/unparseable."""
    value = todo.get(key)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace(' ', 'T'))
    except ValueError:
        return None


def _stop_datetime(todo):
    """Parse a todo's stop_date into a naive datetime, or None if absent/unparseable."""
    return _item_datetime(todo, 'stop_date')


@mcp.tool
async def get_logbook(period: str = "7d", limit: int = 50, offset: int = 0,
                      project_uuid: str = None) -> ToolResult:
    """Get completed and canceled todos from Logbook, defaults to last 7 days, optionally filtered by project

    Args:
        period: Time period to look back (e.g., '3d', '1w', '2m', '1y'). Defaults to '7d'
        limit: Maximum number of entries to return. Defaults to 50
        offset: Number of entries to skip from the start (default: 0)
        project_uuid: Optional UUID of a project to filter by; includes items
            under the project's headings
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    # things.last(period, status='completed') filters on creationDate, not
    # stopDate — so tasks created before the window but completed inside it
    # are invisible (which is most tasks in real use). Fetch all logged
    # tasks and filter on stop_date in Python. The Logbook holds both
    # completed and canceled tasks, so query both statuses.
    delta = _parse_logbook_period(period)
    if delta is None:
        return _error_result(
            f"Invalid period {period!r}. Use a number followed by d/w/m/y, "
            "e.g. '7d', '2w', '3m', '1y'."
        )

    cutoff = datetime.now() - delta
    logged = []
    for status in ('completed', 'canceled'):
        logged.extend(things.tasks(status=status, include_items=True, project=project_uuid) or [])
    in_window = []
    for todo in logged:
        stopped = _stop_datetime(todo)
        if stopped is not None and stopped >= cutoff:
            in_window.append((stopped, todo))
    in_window.sort(key=lambda pair: pair[0], reverse=True)
    todos = [t for _, t in in_window]

    return _paginate_result(todos, format_todo, limit, offset, "No items found")

@mcp.tool
async def get_trash(limit: int = None, offset: int = 0) -> ToolResult:
    """Get trashed todos

    Args:
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    todos = things.trash(include_items=True)
    return _paginate_result(todos, format_todo, limit, offset, "No items found")

# Basic operations
@mcp.tool
async def get_todos(project_uuid: str = None, include_items: bool = True,
                    limit: int = None, offset: int = 0) -> ToolResult:
    """Get todos from Things, optionally filtered by project

    Returns both human-readable text and structured JSON (the raw todo dicts
    plus pagination metadata) so MCP clients can consume either form.

    Args:
        project_uuid: Optional UUID of a specific project to get todos from
        include_items: Include checklist items
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    view = _scope_view()
    if project_uuid:
        project = things.get(project_uuid)
        # Out-of-scope projects get the same error as missing ones.
        if not project or project.get('type') != 'project' or not view.allows(project):
            return _error_result(f"Error: Invalid project UUID '{project_uuid}'")

    todos = things.todos(project=project_uuid, start=None, include_items=include_items)
    return _paginate_result(todos, format_todo, limit, offset, "No todos found", view=view)

@mcp.tool
async def get_todos_by_ids(ids: List[str]) -> ToolResult:
    """Get specific to-dos by UUID in one call, with checklist items and modification times

    Meant for cheap refreshes of to-dos a client already tracks. Works for
    open, completed and canceled to-dos. IDs that are missing, trashed, not
    to-dos, or outside this server's scope are all listed as not found.

    Args:
        ids: UUIDs of the to-dos to fetch
    """
    if not ids:
        return _error_result("Error: pass at least one ID")
    view = _scope_view()
    found, missing = [], []
    for uid in dict.fromkeys(ids):
        item = things.get(uid)
        if item and item.get("type") == "to-do" and not item.get("trashed") and view.allows(item):
            found.append(item)
        else:
            missing.append(uid)
    found = view.filter(found)
    text = "\n\n---\n\n".join(format_todo(todo) for todo in found) or "No todos found"
    if missing:
        text += f"\n\nNot found: {', '.join(missing)}"
    structured = {
        "items": json.loads(json.dumps(found, default=str)),
        "count": len(found),
        "missing": missing,
    }
    return ToolResult(content=text, structured_content=structured)

@mcp.tool
async def get_projects(include_items: bool = False, limit: int = None, offset: int = 0) -> ToolResult:
    """Get all projects from Things

    Args:
        include_items: Include tasks within projects
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    projects = things.projects()
    return _paginate_result(
        projects, lambda p: format_project(p, include_items),
        limit, offset, "No projects found"
    )

@mcp.tool
async def get_areas(include_items: bool = False, limit: int = None, offset: int = 0) -> ToolResult:
    """Get all areas from Things

    Args:
        include_items: Include projects and tasks within areas
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    areas = things.areas()
    return _paginate_result(
        areas, lambda a: format_area(a, include_items),
        limit, offset, "No areas found"
    )

# Tag operations
@mcp.tool
async def get_tags(include_items: bool = False, limit: int = None, offset: int = 0) -> ToolResult:
    """Get all tags

    Args:
        include_items: Include items tagged with each tag
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    view = _scope_view()
    tags = things.tags()
    item_filter = None if view.unrestricted else view.filter
    return _paginate_result(
        tags, lambda t: format_tag(t, include_items, item_filter=item_filter),
        limit, offset, "No tags found", view=view
    )

@mcp.tool
async def get_tagged_items(tag: str, limit: int = None, offset: int = 0) -> ToolResult:
    """Get items with a specific tag

    Args:
        tag: Tag title to filter by
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    view = _scope_view()
    empty_msg = f"No items found with tag '{tag}'"
    # things.py raises for unknown tags; answer the same way for tags outside
    # the scope so their existence isn't revealed.
    if not view.unrestricted and tag not in view.visible_tags():
        return _paginate_result([], format_todo, limit, offset, empty_msg, view=view)
    todos = things.todos(tag=tag, include_items=True)
    return _paginate_result(todos, format_todo, limit, offset, empty_msg, view=view)

@mcp.tool
async def get_tag_usage(only_unused: bool = False) -> str:
    """Report how many items use each tag, sorted by usage (highest first).

    Useful for cleaning up tags that accumulate over time. Identify
    rarely-used or unused tags first; then either remove them from any
    remaining items (via update_todo's tags parameter) or delete the
    tag manually in Things — the URL scheme does not support tag
    deletion or renaming.

    Args:
        only_unused: If true, return only tags with zero items.
    """
    view = _scope_view()
    tags = view.filter(things.tags())
    if not tags:
        return "No tags found"

    rows = []
    for tag in tags:
        title = tag['title']
        open_count = len(view.filter(things.todos(tag=title)))
        all_count = len(view.filter(things.tasks(tag=title, status=None)))
        rows.append((title, open_count, all_count))

    if only_unused:
        rows = [r for r in rows if r[2] == 0]
        if not rows:
            return "No unused tags"
        rows.sort(key=lambda r: r[0].lower())
    else:
        rows.sort(key=lambda r: (-r[2], r[0].lower()))

    return "\n".join(f"{name}: {open_c} open, {all_c} total" for name, open_c, all_c in rows)

@mcp.tool
async def get_headings(project_uuid: str = None, limit: int = None, offset: int = 0) -> ToolResult:
    """Get headings from Things

    Args:
        project_uuid: Optional UUID of a specific project to get headings from
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    view = _scope_view()
    if project_uuid:
        project = things.get(project_uuid)
        if not project or project.get('type') != 'project' or not view.allows(project):
            return _error_result(f"Error: Invalid project UUID '{project_uuid}'")
        headings = things.tasks(type='heading', project=project_uuid)
    else:
        headings = things.tasks(type='heading')

    return _paginate_result(headings, format_heading, limit, offset, "No headings found", view=view)

# Search operations
@mcp.tool
async def search_todos(query: str, limit: int = None, offset: int = 0) -> ToolResult:
    """Search todos by title or notes

    Args:
        query: Search term to look for in todo titles and notes
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    todos = things.search(query, include_items=True)
    return _paginate_result(todos, format_todo, limit, offset, f"No todos found matching '{query}'")

@mcp.tool
async def search_advanced(
    status: str = None,
    start_date: str = None,
    stop_date: str = None,
    deadline: str = None,
    tag: str = None,
    area: str = None,
    project: str = None,
    type: str = None,
    last: str = None,
    limit: int = None,
    offset: int = 0
) -> ToolResult:
    """Advanced todo search with multiple filters

    Args:
        status: Filter by todo status (incomplete, completed, canceled)
        start_date: Filter by start date (YYYY-MM-DD)
        stop_date: Filter by completion/cancellation date (YYYY-MM-DD with optional
            operator, e.g. '>=2024-01-01', or 'past'/'future')
        deadline: Filter by deadline (YYYY-MM-DD)
        tag: Filter by tag
        area: Filter by area UUID
        project: Filter by project UUID (includes items under the project's headings)
        type: Filter by item type (to-do, project, heading)
        last: Filter by creation date (e.g., '3d' for last 3 days, '1w' for last week, '1y' for last year)
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    search_params = {}
    if status:
        search_params["status"] = status
    if start_date:
        search_params["start_date"] = start_date
    if stop_date:
        search_params["stop_date"] = stop_date
    if deadline:
        search_params["deadline"] = deadline
    if tag:
        search_params["tag"] = tag
    if area:
        search_params["area"] = area
    if project:
        search_params["project"] = project
    if last:
        search_params["last"] = last

    view = _scope_view()
    if tag and not view.unrestricted and tag not in view.visible_tags():
        return _paginate_result([], format_todo, limit, offset, "No matching todos found", view=view)

    if type:
        # Use things.tasks() when type is specified since things.todos()
        # hardcodes type="to-do"
        todos = things.tasks(type=type, include_items=True, **search_params)
    else:
        todos = things.todos(include_items=True, **search_params)
    return _paginate_result(todos, format_todo, limit, offset, "No matching todos found", view=view)

# Recent items
@mcp.tool
async def get_recent(period: str, limit: int = None, offset: int = 0) -> ToolResult:
    """Get open (incomplete) items created within a rolling time window, newest first

    Args:
        period: How far back from now to look (e.g., '1d' = the last 24 hours, '1w', '2m', '1y')
        limit: Maximum number of items to return (default: all)
        offset: Number of items to skip from the start (default: 0)
    """
    err = _validate_pagination(limit, offset)
    if err:
        return _error_result(err)
    delta = _parse_logbook_period(period)
    if delta is None:
        return _error_result(
            f"Invalid period {period!r}. Use a number followed by d/w/m/y, "
            "e.g. '1d', '2w', '3m', '1y'."
        )
    # things.last() compares the local-time creation date against SQLite's
    # UTC 'now', so its window is skewed by the UTC offset (west of UTC, '1d'
    # misses items from earlier in the day). It also rejects months. Over-fetch
    # by a day and filter on 'created' (local time) in Python.
    todos = things.last(f"{delta.days + 1}d", include_items=True) or []
    cutoff = datetime.now() - delta
    todos = [t for t in todos
             if (created := _item_datetime(t, 'created')) is not None and created >= cutoff]
    return _paginate_result(todos, format_todo, limit, offset, f"No items found in the last {period}")

# Things URL Scheme tools
@mcp.tool
async def add_todo(
    title: str,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: List[str] = None,
    checklist_items: List[str] = None,
    list_id: str = None,
    list_title: str = None,
    heading: str = None,
    heading_id: str = None
) -> str:
    """Create a new todo in Things and return its ID

    Args:
        title: Title of the todo
        notes: Notes for the todo
        when: When to schedule the todo (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD).
            Use YYYY-MM-DD@HH:MM format to add a reminder (e.g., 2024-01-15@14:30)
        deadline: Deadline for the todo (YYYY-MM-DD)
        tags: Tags to apply to the todo
        checklist_items: Checklist items to add
        list_id: ID of project/area to add to
        list_title: Title of project/area to add to
        heading: Heading title to add under
        heading_id: Heading ID to add under (takes precedence over heading)
    """
    view = _scope_view()
    if not view.unrestricted:
        list_id = view.resolve_destination(list_id, list_title, heading_id)
        list_title = None
    tags, created_tags, dropped_tags = _prepare_tags(tags)
    tag_note = _tag_note(created_tags, dropped_tags)

    token = things.token()
    if not token:
        # Without the token the follow-up update can't run, so fall back to a
        # single URL-scheme add, which can't report the new ID.
        url = url_scheme.add_todo(
            title=title, notes=notes, when=when, deadline=deadline,
            tags=tags or None, checklist_items=checklist_items,
            list_id=list_id, list_title=list_title,
            heading=heading, heading_id=heading_id,
        )
        url_scheme.execute_url(url)
        return (
            f"Created new todo: {title} (ID unknown: enable the Things auth token to get it)"
            f"{tag_note}"
        )

    if list_id is None and heading_id is not None:
        # Place it in the heading's project first, so the heading applies.
        heading_item = things.get(heading_id)
        list_id = heading_item.get("project") if heading_item else None
    list_type = None
    if list_id is not None:
        container = things.get(list_id)
        list_type = container.get("type") if container else None
        if list_type not in ("project", "area"):
            return f"Error: No project or area with ID {list_id!r}"

    todo_id = url_scheme.create_todo(title=title, notes=notes, list_id=list_id, list_type=list_type)
    result = f"Created new todo: {title} (id: {todo_id}){tag_note}"

    follow_up = dict(
        when=when, deadline=deadline, tags=tags or None,
        checklist_items=checklist_items or None,
        list=list_title, heading=heading, heading_id=heading_id,
    )
    if any(value is not None for value in follow_up.values()):
        try:
            url_scheme.execute_url(url_scheme.update_todo(id=todo_id, **follow_up))
        except subprocess.CalledProcessError as error:
            return f"{result}, but setting its other fields failed: {error}"
    return result

@mcp.tool
async def add_area(title: str) -> str:
    """Create a new Area in Things 3

    Areas are top-level containers in Things 3 (e.g. "Work", "Personal", "Backlog").
    The Things URL scheme cannot create Areas, so this uses AppleScript.

    Args:
        title: Title of the area
    """
    _require_unrestricted(_scope_view(), "Creating areas")
    area_id = url_scheme.add_area(title=title)
    return f"Created new area: {title} (id: {area_id})"

@mcp.tool
async def update_area(id: str, title: str = None, tags: List[str] = None) -> str:
    """Update an existing Area in Things 3 (rename and/or set tags)

    The Things URL scheme has no area operations, so this uses AppleScript.
    Only the fields you provide are changed.

    Note: there is no delete_area tool by design — deleting an Area in Things
    also deletes every project it contains, which is destructive and cannot be
    undone. Areas can be created, read, and updated here, but not deleted.

    Args:
        id: UUID of the area to update
        title: New name for the area
        tags: Tags to set on the area (replaces existing tags; only tags that
            already exist in Things are applied)
    """
    if title is None and tags is None:
        return "No changes specified — pass title and/or tags."
    view = _scope_view()
    if not view.unrestricted:
        view.require(id, ("area",))
    url_scheme.update_area(area_id=id, title=title, tags=tags)
    changed = []
    if title is not None:
        changed.append(f"title={title!r}")
    if tags is not None:
        changed.append(f"tags={tags}")
    return f"Updated area {id}: {', '.join(changed)}"

@mcp.tool
async def add_project(
    title: str,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: List[str] = None,
    area_id: str = None,
    area_title: str = None,
    todos: List[str] = None
) -> str:
    """Create a new project in Things

    Args:
        title: Title of the project
        notes: Notes for the project
        when: When to schedule the project (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD).
            Use YYYY-MM-DD@HH:MM format to add a reminder (e.g., 2024-01-15@14:30)
        deadline: Deadline for the project (YYYY-MM-DD)
        tags: Tags to apply to the project
        area_id: ID of area to add to
        area_title: Title of area to add to
        todos: Initial todos to create in the project
    """
    view = _scope_view()
    if not view.unrestricted:
        area_id = view.resolve_destination(area_id, area_title, kinds=("area",))
        area_title = None
    url = url_scheme.add_project(
        title=title,
        notes=notes,
        when=when,
        deadline=deadline,
        tags=tags,
        area_id=area_id,
        area_title=area_title,
        todos=todos
    )
    url_scheme.execute_url(url)
    return f"Created new project: {title}"

@mcp.tool
async def update_todo(
    id: str,
    title: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: List[str] = None,
    add_tags: List[str] = None,
    remove_tags: List[str] = None,
    completed: bool = None,
    canceled: bool = None,
    list: str = None,
    list_id: str = None,
    heading: str = None,
    heading_id: str = None,
    checklist_items: List[str] = None,
    prepend_checklist_items: List[str] = None,
    append_checklist_items: List[str] = None,
) -> str:
    """Update an existing todo in Things

    Args:
        id: ID of the todo to update
        title: New title
        notes: New notes
        when: New schedule (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD).
            Use YYYY-MM-DD@HH:MM format to add a reminder (e.g., 2024-01-15@14:30)
        deadline: New deadline (YYYY-MM-DD)
        tags: New tags (replaces all existing tags)
        add_tags: Tags to append without removing existing tags
        remove_tags: Tags to remove, keeping the others (can be combined with add_tags, not with tags)
        completed: Mark as completed
        canceled: Mark as canceled
        list: The title of a project or area to move the to-do into
        list_id: The ID of a project or area to move the to-do into (takes precedence over list)
        heading: The heading title to move the to-do under
        heading_id: The heading ID to move the to-do under (takes precedence over heading)
        checklist_items: Replace the entire checklist with these items. Pass an
            empty list to clear the checklist.
        prepend_checklist_items: Add these items to the start of the existing checklist
        append_checklist_items: Add these items to the end of the existing checklist
    """
    view = _scope_view()
    if not view.unrestricted:
        view.require(id, ("to-do",))
        list_id = view.resolve_destination(list_id, list, heading_id, required=False)
        list = None
    if remove_tags:
        if tags is not None:
            return "Error: pass either tags or remove_tags, not both."
        overlap = set(remove_tags) & set(add_tags or [])
        if overlap:
            return f"Error: {', '.join(sorted(overlap))} is in both add_tags and remove_tags."
        # The URL scheme can only replace the whole list, so rebuild it.
        current = (things.get(id) or {}).get("tags") or []
        tags = [tag for tag in current if tag not in remove_tags]
        tags += [tag for tag in (add_tags or []) if tag not in current]
        add_tags = None
    if tags:
        tags, created_tags, dropped_tags = _prepare_tags(tags)
    else:
        add_tags, created_tags, dropped_tags = _prepare_tags(add_tags)
        add_tags = add_tags or None
    url = url_scheme.update_todo(
        id=id,
        title=title,
        notes=notes,
        when=when,
        deadline=deadline,
        tags=tags,
        add_tags=add_tags,
        completed=completed,
        canceled=canceled,
        list=list,
        list_id=list_id,
        heading=heading,
        heading_id=heading_id,
        checklist_items=checklist_items,
        prepend_checklist_items=prepend_checklist_items,
        append_checklist_items=append_checklist_items,
    )
    url_scheme.execute_url(url)
    return f"Updated todo with ID: {id}{_tag_note(created_tags, dropped_tags)}"

@mcp.tool
async def bulk_update_todos(
    ids: List[str],
    list: str = None,
    list_id: str = None,
    tags: List[str] = None,
    add_tags: List[str] = None,
    when: str = None,
    deadline: str = None,
    heading: str = None,
    heading_id: str = None,
    completed: bool = None,
    canceled: bool = None,
) -> str:
    """Apply the same change to many to-dos in a single Things round-trip.

    Use for weekly-review style operations — e.g. "move every grocery item
    in my inbox to Shopping List", "tag this batch with 'next-quarter'",
    "complete all of these". One URL invocation replaces N sequential
    update_todo calls, which makes 20-task moves feel instant instead of
    taking minutes.

    All non-None parameters apply to every id in 'ids'. For per-item
    changes use update_todo individually.

    Args:
        ids: UUIDs of todos to update
        list: Project/area title to move all into
        list_id: Project/area UUID to move all into (takes precedence over list)
        tags: Replace tags on all (existing tags removed)
        add_tags: Append tags to all (existing tags preserved)
        when: Reschedule all (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD)
        deadline: Set deadline on all (YYYY-MM-DD)
        heading: Move all under this heading title
        heading_id: Move all under this heading UUID (takes precedence over heading)
        completed: Mark all completed
        canceled: Mark all canceled
    """
    if not ids:
        return "No items to update"

    view = _scope_view()
    if not view.unrestricted:
        for uid in ids:
            view.require(uid, ("to-do",))
        list_id = view.resolve_destination(list_id, list, heading_id, required=False)
        list = None

    tags, created_tags, dropped_tags = _prepare_tags(tags)
    add_tags, added_created, added_dropped = _prepare_tags(add_tags)
    created_tags += [tag for tag in added_created if tag not in created_tags]
    dropped_tags += [tag for tag in added_dropped if tag not in dropped_tags]

    attributes: dict = {}
    if list_id is not None:
        attributes['list-id'] = list_id
    elif list is not None:
        attributes['list'] = list
    if tags is not None:
        attributes['tags'] = tags
    if add_tags is not None:
        attributes['add-tags'] = add_tags
    if when is not None:
        attributes['when'] = when
    if deadline is not None:
        attributes['deadline'] = deadline
    if heading_id is not None:
        attributes['heading-id'] = heading_id
    elif heading is not None:
        attributes['heading'] = heading
    if completed is not None:
        attributes['completed'] = completed
    if canceled is not None:
        attributes['canceled'] = canceled

    if not attributes:
        return "No changes specified — pass at least one attribute (list, tags, when, …)."

    token = things.token()
    if not token:
        return (
            "THINGS_AUTH_TOKEN not configured. Bulk updates require it. "
            "Enable in Things → Settings → General → Manage."
        )

    payload = [
        {"type": "to-do", "operation": "update", "id": uid, "attributes": attributes}
        for uid in ids
    ]
    url = url_scheme.json_command(payload, auth_token=token)
    url_scheme.execute_url(url)
    return f"Submitted bulk update for {len(ids)} todos{_tag_note(created_tags, dropped_tags)}"

@mcp.tool
async def set_checklist_items(id: str, check: List[str] = None, uncheck: List[str] = None) -> str:
    """Tick or untick checklist items of a to-do by title, keeping all other items as they are

    Items are matched by title: Things gives every checklist item a new ID
    whenever a checklist is rewritten, which is the only way to change one.
    If a title matches no item, or more than one, nothing is changed.

    Args:
        id: UUID of the to-do
        check: Titles of items to mark completed
        uncheck: Titles of items to mark not completed
    """
    check, uncheck = check or [], uncheck or []
    if not check and not uncheck:
        return "No changes specified — pass check and/or uncheck."
    overlap = set(check) & set(uncheck)
    if overlap:
        return f"Error: {', '.join(sorted(overlap))} is in both check and uncheck. Nothing changed."

    view = _scope_view()
    if view.unrestricted:
        todo = things.get(id)
        if not todo or todo.get("type") != "to-do":
            return f"Error: No to-do with ID {id!r}"
    else:
        todo = view.require(id, ("to-do",))

    items = todo.get("checklist") if isinstance(todo.get("checklist"), list) else []
    titles = [item.get("title") for item in items]
    problems = []
    for title in [*check, *uncheck]:
        count = titles.count(title)
        if count == 0:
            problems.append(f"no item titled {title!r}")
        elif count > 1:
            problems.append(f"{count} items titled {title!r}")
    if problems:
        return f"Error: {'; '.join(problems)}. Nothing changed."

    states = []
    for item in items:
        status = item.get("status")
        if item["title"] in check:
            status = "completed"
        elif item["title"] in uncheck:
            status = "incomplete"
        states.append((item["title"], status))
    summary = ", ".join(
        f"{'✓' if status == 'completed' else '✕' if status == 'canceled' else '☐'} {title}"
        for title, status in states
    )
    done = sum(status == "completed" for _, status in states)
    progress = f"{done}/{len(states)} done: {summary}"
    if states == [(item["title"], item.get("status")) for item in items]:
        # A rewrite would still give every item a new ID, so skip it.
        return f"Checklist of {todo['title']!r} already up to date ({progress})"

    token = things.token()
    if not token:
        return MISSING_TOKEN_MESSAGE
    checklist = []
    for title, status in states:
        attributes = {"title": title}
        if status == "completed":
            attributes["completed"] = True
        elif status == "canceled":
            attributes["canceled"] = True
        checklist.append({"type": "checklist-item", "attributes": attributes})
    payload = [{
        "type": "to-do", "operation": "update", "id": id,
        "attributes": {"checklist-items": checklist},
    }]
    url_scheme.execute_url(url_scheme.json_command(payload, auth_token=token))
    return f"Updated checklist of {todo['title']!r} ({progress})"

@mcp.tool
async def update_project(
    id: str,
    title: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: List[str] = None,
    completed: bool = None,
    canceled: bool = None
) -> str:
    """Update an existing project in Things

    Args:
        id: ID of the project to update
        title: New title
        notes: New notes
        when: New schedule (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD).
            Use YYYY-MM-DD@HH:MM format to add a reminder (e.g., 2024-01-15@14:30)
        deadline: New deadline (YYYY-MM-DD)
        tags: New tags
        completed: Mark as completed
        canceled: Mark as canceled
    """
    view = _scope_view()
    if not view.unrestricted:
        view.require(id, ("project",))
    url = url_scheme.update_project(
        id=id,
        title=title,
        notes=notes,
        when=when,
        deadline=deadline,
        tags=tags,
        completed=completed,
        canceled=canceled
    )
    url_scheme.execute_url(url)
    return f"Updated project with ID: {id}"

@mcp.tool
async def show_item(
    id: str,
    query: str = None,
    filter_tags: List[str] = None
) -> str:
    """Show a specific item or list in Things

    Args:
        id: ID of item to show, or one of: inbox, today, upcoming, anytime, someday, logbook
        query: Optional query to filter by
        filter_tags: Optional tags to filter by
    """
    view = _scope_view()
    if not view.unrestricted:
        # Built-in lists like 'today' span every area, so only scoped items qualify.
        view.require(id, ("to-do", "project", "area", "heading"))
    url = url_scheme.show(
        id=id,
        query=query,
        filter_tags=filter_tags
    )
    url_scheme.execute_url(url)
    return f"Showing item: {id}"

@mcp.tool
async def search_items(query: str) -> str:
    """Search for items in Things

    Args:
        query: Search query
    """
    _require_unrestricted(_scope_view(), "Searching in the Things app")
    url = url_scheme.search(query)
    url_scheme.execute_url(url)
    return f"Searching for '{query}'"


def main():
    """Main entry point for the Things MCP server."""
    if TRANSPORT == "http":
        mcp.auth = _http_auth_from_env()
        mcp.run(transport="http", host=HTTP_HOST, port=HTTP_PORT)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
