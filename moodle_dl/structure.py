"""The authoritative map of a course.

Moodle's own web UI asks the server for the course structure as JSON. Using
the same call gives an exact list of every section and every activity -
including their parent/child nesting - instead of inferring it from the page
markup. Nothing can hide from the crawl because the list is the server's own.

Monash has the mobile web service disabled, so this session-based endpoint is
the only structured route available.
"""
from __future__ import annotations

import dataclasses
import json

from .session import MoodleSession

STATE_METHOD = "core_courseformat_get_state"


@dataclasses.dataclass
class Module:
    """One activity: a file, a page, a link, an external tool..."""
    id: str
    name: str
    modname: str
    url: str | None
    section_id: str
    visible: bool
    # False when the activity exists but is not open to this student yet -
    # a restricted release date, for example. The page renders it as plain
    # text with no link, which is why the markup alone never reveals it.
    user_visible: bool = True


@dataclasses.dataclass
class Section:
    id: str
    number: int
    title: str
    parent_id: str | None
    module_ids: list[str]
    visible: bool


@dataclasses.dataclass
class CourseMap:
    sections: dict[str, Section]           # by section id
    modules: dict[str, Module]             # by module id
    by_number: dict[int, Section]

    def parent_of(self, section: Section) -> Section | None:
        if not section.parent_id:
            return None
        return self.sections.get(section.parent_id)

    def modules_in(self, section: Section) -> list[Module]:
        return [self.modules[mid] for mid in section.module_ids
                if mid in self.modules]


def fetch_course_map(sess: MoodleSession, base_url: str, sesskey: str,
                     course_id: int) -> CourseMap | None:
    """Ask Moodle for the course structure. None if the call is unavailable."""
    payload = [{"index": 0, "methodname": STATE_METHOD,
                "args": {"courseid": course_id}}]
    resp = sess.ctx.request.post(
        f"{base_url}/lib/ajax/service.php?sesskey={sesskey}&info={STATE_METHOD}",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"})
    if not resp.ok:
        return None
    try:
        first = json.loads(resp.body().decode("utf-8", "replace"))[0]
        if first.get("error"):
            return None
        data = first["data"]
        if isinstance(data, str):      # the payload arrives JSON-encoded
            data = json.loads(data)
    except Exception:
        return None

    sections: dict[str, Section] = {}
    by_number: dict[int, Section] = {}
    for s in data.get("section", []):
        try:
            number = int(s.get("number", s.get("section", -1)))
        except (TypeError, ValueError):
            number = -1
        sec = Section(
            id=str(s["id"]),
            number=number,
            title=(s.get("rawtitle") or s.get("title") or "").strip(),
            parent_id=(str(s["parentsectionid"])
                       if s.get("parentsectionid") else None),
            module_ids=[str(c) for c in (s.get("cmlist") or [])],
            visible=bool(s.get("visible", True)),
        )
        sections[sec.id] = sec
        if number >= 0:
            by_number[number] = sec

    modules: dict[str, Module] = {}
    for c in data.get("cm", []):
        mod = Module(
            id=str(c["id"]),
            name=(c.get("name") or "").strip(),
            # "module" is the plugin name (resource, page, lti); "modname"
            # is the label a human sees ("File", "External tool").
            modname=(c.get("module") or c.get("plugin") or "").strip(),
            url=c.get("url"),
            section_id=str(c.get("sectionid") or ""),
            visible=bool(c.get("visible", True)),
            user_visible=bool(c.get("uservisible", True)),
        )
        modules[mod.id] = mod

    if not sections:
        return None
    return CourseMap(sections=sections, modules=modules, by_number=by_number)


def week_titles(cmap: CourseMap, section: Section) -> list[str]:
    """A section's title plus its ancestors', so a child can inherit a week."""
    titles, seen = [], set()
    cur: Section | None = section
    while cur and cur.id not in seen:
        seen.add(cur.id)
        if cur.title:
            titles.append(cur.title)
        cur = cmap.parent_of(cur)
    return titles
