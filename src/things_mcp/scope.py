"""Limit what an MCP client can read and change to configured Areas and Projects.

A scope is a list of names:

    Work            the area "Work"
    Work->Launch    the project "Launch" in the area "Work"
    ->Launch        the project "Launch" that isn't in any area

An Area includes its to-dos, its projects, and everything inside those
projects. A Project includes its headings and to-dos. Everything else (Inbox,
other areas and projects) is hidden from reads and rejected by writes.

Names are resolved against the database on every request. Because Things
doesn't keep names unique, an entry that matches more than one item grants
nothing, so a duplicate can never widen access.

Scopes come from environment variables for a whole process (stdio), or from a
tokens file that maps each HTTP bearer token to its own scope.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Iterable, Optional

import things
from fastmcp.exceptions import ToolError

logger = logging.getLogger(__name__)

SCOPE_ENV = "THINGS_MCP_SCOPE"
SCOPE_CLAIM = "things_scope"
ENTRY_SEPARATOR = ";"
PROJECT_SEPARATOR = "->"

_TOKEN_FILE_KEYS = {"name", "sha256", "scope", "unrestricted"}
_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")


class ScopeError(ToolError):
    """A request touches something outside the caller's scope.

    A ToolError, so FastMCP reports the message to the client as a failed call.
    """


@dataclass(frozen=True)
class Scope:
    entries: frozenset = frozenset()
    unrestricted: bool = False

    def describe(self) -> str:
        if self.unrestricted:
            return "unrestricted"
        return f"{len(self.entries)} area/project name(s)"

    def to_claim(self) -> dict:
        # Plain JSON types, so the scope survives any serialization of the
        # access token.
        return {"unrestricted": self.unrestricted, "entries": sorted(self.entries)}

    @classmethod
    def from_claim(cls, claim) -> "Scope":
        """Parse a token claim. Anything malformed denies everything."""
        if not isinstance(claim, dict):
            return DENY_ALL
        if claim.get("unrestricted") is True:
            return UNRESTRICTED
        entries = claim.get("entries")
        if not _is_entry_list(entries):
            return DENY_ALL
        return cls(entries=frozenset(entries))


UNRESTRICTED = Scope(unrestricted=True)
DENY_ALL = Scope()


def _is_entry_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _clean_entries(entries) -> frozenset:
    return frozenset(entry.strip() for entry in entries if entry.strip())


def scope_from_env(environ) -> Scope:
    """Read the process-wide scope from THINGS_MCP_SCOPE.

    Entries are separated by ';', since names often contain commas and spaces.
    Unset means unrestricted (the historical behavior). Once set, only the
    listed names are in scope, so an empty value denies everything rather than
    silently granting full access.
    """
    if SCOPE_ENV not in environ:
        return UNRESTRICTED
    return Scope(entries=_clean_entries(environ[SCOPE_ENV].split(ENTRY_SEPARATOR)))


def _same_name(title, name: str) -> bool:
    return isinstance(title, str) and title.strip() == name.strip()


def _project_readings(entry: str):
    """Yield every (area, project) split of an entry at a '->'.

    Trying every split means names that themselves contain '->' still work;
    an entry that ends up matching more than one item grants nothing.
    """
    start = 0
    while (index := entry.find(PROJECT_SEPARATOR, start)) != -1:
        yield entry[:index].strip(), entry[index + len(PROJECT_SEPARATOR):].strip()
        start = index + 1


def _entry_matches(entry: str, areas: list, projects: list, area_titles: dict) -> set:
    matches = {("area", a["uuid"]) for a in areas if _same_name(a.get("title"), entry)}
    for area_name, project_name in _project_readings(entry):
        for project in projects:
            if not _same_name(project.get("title"), project_name):
                continue
            area = project.get("area")
            in_area = area is None if not area_name else (
                area is not None and _same_name(area_titles.get(area), area_name)
            )
            if in_area:
                matches.add(("project", project["uuid"]))
    return matches


_reported_entries: set = set()


def _report_unresolved(entry: str, count: int) -> None:
    # Once per entry and outcome, so the log isn't flooded on every request.
    if (entry, count) in _reported_entries:
        return
    _reported_entries.add((entry, count))
    if count == 0:
        logger.warning("Scope entry %r matches no area or project; it grants nothing.", entry)
    else:
        logger.warning(
            "Scope entry %r matches %d areas/projects; it grants nothing until the names are unique.",
            entry, count,
        )


@dataclass(frozen=True)
class Credential:
    name: str
    digest: bytes
    scope: Scope


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def load_credentials_file(path: str) -> list:
    """Load bearer-token credentials from a JSON file.

    The file stores only SHA-256 hashes of the tokens, never the tokens:

        {"tokens": [
            {"name": "work-laptop", "sha256": "<hex>", "scope": ["Work", "Clients->Acme"]},
            {"name": "admin", "sha256": "<hex>", "unrestricted": true}
        ]}

    Raises ValueError for anything malformed, so a typo can't widen access.
    """
    with open(path, encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict) or set(data) != {"tokens"}:
        raise ValueError('expected an object with a single "tokens" list')
    entries = data["tokens"]
    if not isinstance(entries, list) or not entries:
        raise ValueError('"tokens" must be a non-empty list')

    credentials = []
    for index, entry in enumerate(entries):
        where = f"tokens[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{where} must be an object")
        unknown = set(entry) - _TOKEN_FILE_KEYS
        if unknown:
            raise ValueError(f"{where} has unknown keys: {', '.join(sorted(unknown))}")

        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f'{where} needs a non-empty "name"')
        where = f"{where} ({name})"

        sha256 = entry.get("sha256")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            raise ValueError(f'{where}: "sha256" must be 64 hex characters')

        unrestricted = entry.get("unrestricted", False)
        if not isinstance(unrestricted, bool):
            raise ValueError(f'{where}: "unrestricted" must be true or false')
        entries = entry.get("scope", [])
        if not _is_entry_list(entries):
            raise ValueError(f'{where}: "scope" must be a list of non-empty area/project names')
        if unrestricted and entries:
            raise ValueError(f'{where}: use either "unrestricted": true or "scope", not both')
        if not unrestricted and not entries:
            raise ValueError(f'{where}: list at least one area or project in "scope", or set "unrestricted": true')

        scope = UNRESTRICTED if unrestricted else Scope(entries=_clean_entries(entries))
        credentials.append(Credential(name=name, digest=bytes.fromhex(sha256), scope=scope))

    return credentials


_KIND_LABELS = {"to-do": "to-do", "project": "project", "area": "area", "heading": "heading"}


def _label(kinds: Iterable[str]) -> str:
    return " or ".join(_KIND_LABELS.get(kind, kind) for kind in kinds)


class ScopeView:
    """A scope resolved against the current Things database.

    Build one per request: projects added to a scoped area since the last
    request are picked up automatically.
    """

    def __init__(self, scope: Scope):
        self.scope = scope
        self.unrestricted = scope.unrestricted
        self._visible_tags: Optional[set] = None
        if self.unrestricted:
            return
        areas = things.areas() or []
        area_titles = {a["uuid"]: a.get("title") for a in areas}
        # Include completed and trashed projects so their logbook and trash
        # entries stay visible inside a scoped area.
        all_projects = things.projects(status=None, trashed=None) or []
        # Names only match open projects, so an old completed project with the
        # same name doesn't make an entry ambiguous.
        open_projects = [
            p for p in all_projects
            if p.get("status") == "incomplete" and not p.get("trashed")
        ]

        self.area_ids = set()
        named_projects = set()
        for entry in scope.entries:
            matches = _entry_matches(entry, areas, open_projects, area_titles)
            if len(matches) != 1:
                _report_unresolved(entry, len(matches))
                continue
            [(kind, uuid)] = matches
            (self.area_ids if kind == "area" else named_projects).add(uuid)

        self.project_ids = named_projects | {
            p["uuid"] for p in all_projects if p.get("area") in self.area_ids
        }
        # To-dos under a heading carry the heading, not the project.
        headings = things.tasks(
            type="heading", status=None, trashed=None, context_trashed=None
        ) or []
        self._heading_project = {h["uuid"]: h.get("project") for h in headings}

    def allows(self, item: dict) -> bool:
        if self.unrestricted:
            return True
        kind = item.get("type")
        if kind == "area":
            return item.get("uuid") in self.area_ids
        if kind == "project":
            return item.get("uuid") in self.project_ids
        if kind == "heading":
            return item.get("project") in self.project_ids
        if kind == "to-do":
            return (
                item.get("area") in self.area_ids
                or item.get("project") in self.project_ids
                or self._heading_project.get(item.get("heading")) in self.project_ids
            )
        if kind == "tag":
            return item.get("title") in self.visible_tags()
        return False

    def visible_tags(self) -> set:
        """Tags used by at least one in-scope item.

        Tag names are global in Things, but names alone can be sensitive, so a
        scoped client only sees tags it would find on its own items.
        """
        if self._visible_tags is None:
            visible = set()
            for tag in things.tags() or []:
                title = tag["title"]
                tagged = [
                    *(things.tasks(tag=title, status=None) or []),
                    *(things.areas(tag=title) or []),
                ]
                if any(self.allows(item) for item in tagged):
                    visible.add(title)
            self._visible_tags = visible
        return self._visible_tags

    def filter(self, items):
        """Drop out-of-scope items and redact out-of-scope container names."""
        if self.unrestricted:
            return items or []
        return [self._redact(item) for item in (items or []) if self.allows(item)]

    def _redact(self, item: dict) -> dict:
        # A project scoped on its own may sit in an area that isn't in scope;
        # don't reveal that area's name.
        item = dict(item)
        if item.get("area") and item["area"] not in self.area_ids:
            item.pop("area", None)
            item.pop("area_title", None)
        if isinstance(item.get("items"), list):
            item["items"] = [self._redact(child) for child in item["items"] if self.allows(child)]
        return item

    def require(self, uuid: str, kinds: Iterable[str]) -> dict:
        """Return the item, or raise if it is missing, the wrong kind, or out of scope.

        Missing and out-of-scope items get the same message, so a client can't
        probe for items outside its scope.
        """
        kinds = tuple(kinds)
        item = things.get(uuid) if uuid else None
        if not item or item.get("type") not in kinds or not self.allows(item):
            raise ScopeError(f"No {_label(kinds)} with ID {uuid!r} in this server's scope.")
        return item

    def resolve_destination(self, list_id=None, list_title=None, heading_id=None,
                            kinds=("project", "area"), required=True) -> Optional[str]:
        """Check where an item will be created or moved, and return its list ID.

        A title is resolved to a UUID among in-scope containers, so Things can
        never pick a same-named container outside the scope.
        """
        kinds = tuple(kinds)
        if heading_id is not None:
            self.require(heading_id, ("heading",))
        if list_id is not None:
            self.require(list_id, kinds)
            return list_id
        if list_title is not None:
            matches = [c for c in self._containers(kinds) if c.get("title") == list_title]
            if len(matches) == 1:
                return matches[0]["uuid"]
            if not matches:
                raise ScopeError(f"No {_label(kinds)} titled {list_title!r} in this server's scope.")
            raise ScopeError(
                f"{len(matches)} items titled {list_title!r} are in scope; pass the UUID instead."
            )
        if heading_id is None and required:
            raise ScopeError(
                "This server is limited to specific areas and projects, so new items "
                f"need a destination: pass the UUID or title of a {_label(kinds)} in scope."
            )
        return None

    def _containers(self, kinds) -> list:
        containers = []
        if "area" in kinds:
            containers += [a for a in (things.areas() or []) if self.allows(a)]
        if "project" in kinds:
            containers += [p for p in (things.projects() or []) if self.allows(p)]
        return containers
