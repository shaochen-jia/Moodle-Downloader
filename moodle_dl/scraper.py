from __future__ import annotations

import dataclasses
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# Activity types whose links point at downloadable content
FILE_MODS = ("resource", "folder")

# Assessment activity types (collected for the Assignments folder / index)
ASSESS_MODS = ("assign", "quiz", "workshop", "lti")

# pluginfile.php components that are site chrome, not course content
_SKIP_COMPONENTS = re.compile(r"pluginfile\.php/\d+/(theme_|msttools_)")


@dataclasses.dataclass
class Activity:
    name: str
    url: str
    mod: str  # "resource" | "folder" | "pluginfile"


@dataclasses.dataclass
class SectionInfo:
    number: int
    titles: set[str] = dataclasses.field(default_factory=set)
    parent: int | None = None
    activities: list[Activity] = dataclasses.field(default_factory=list)

    @property
    def title(self) -> str:
        return " / ".join(sorted(self.titles))


def match_week(title: str, patterns: list[str], weeks: range) -> int | None:
    for week in weeks:
        for pat in patterns:
            if re.search(pat.replace("{week}", str(week)), title, re.IGNORECASE):
                return week
    return None


def find_section_links(html: str, course_id: int) -> set[int]:
    """Section numbers linked from a page (view.php?id=<course>&section=N)."""
    pat = re.compile(rf"view\.php\?id={course_id}(?:&amp;|&)section=(\d+)")
    return {int(m.group(1)) for m in pat.finditer(html)}


def _own_copy(li) -> BeautifulSoup:
    """Copy of a section <li> with nested section <li>s removed."""
    copy = BeautifulSoup(str(li), "html.parser")
    root = copy.find("li")
    for nested in root.select("li.section"):
        if nested is not root:
            nested.decompose()
    return root


def _titles_of(li) -> set[str]:
    out = set()
    for el in li.select(".sectionname"):
        for hidden in el.select(".accesshide"):
            hidden.extract()
        text = el.get_text(" ", strip=True)
        if text:
            out.add(text)
    return out


def _activities_in(li, base_url: str) -> list[Activity]:
    out: list[Activity] = []
    seen: set[str] = set()

    for act_li in li.select("li.activity"):
        classes = act_li.get("class") or []
        mod = next((m for m in FILE_MODS + ASSESS_MODS
                    if m in classes or f"modtype_{m}" in classes), None)
        if mod is None:
            continue
        a = act_li.select_one(f'a[href*="/mod/{mod}/view.php"]')
        if not a or not a.get("href"):
            continue
        url = urljoin(base_url, a["href"])
        if url in seen:
            continue
        seen.add(url)
        name_el = a.select_one(".instancename") or a
        for hidden in name_el.select(".accesshide"):
            hidden.extract()
        name = name_el.get_text(" ", strip=True)
        out.append(Activity(name=name, url=url, mod=mod))

    # Files linked or embedded directly in the section content (labels,
    # Monash "cms" content modules, ...)
    for name, url in extract_pluginfile_links(str(li), base_url):
        if url.split("?")[0] in {u.split("?")[0] for u in seen}:
            continue
        seen.add(url)
        out.append(Activity(name=name, url=url, mod="pluginfile"))
    return out


def parse_section_page(html: str, base_url: str) -> list[SectionInfo]:
    """All sections present on one page, with parent links from the nesting.

    The first entry (if any) is the page's main section; listings of nested
    subsections only contribute titles/parents, not activities, unless their
    content is rendered inline (then activities are picked up from their own
    <li> copy, which is safe because downloads are de-duplicated).
    """
    soup = BeautifulSoup(html, "html.parser")
    infos: dict[int, SectionInfo] = {}

    for li in soup.select("li.section[data-sectionnum]"):
        try:
            num = int(li["data-sectionnum"])
        except (ValueError, KeyError):
            continue
        info = infos.setdefault(num, SectionInfo(number=num))
        info.titles |= _titles_of(_own_copy(li))
        parent_li = li.find_parent("li", class_="section")
        if parent_li and parent_li.get("data-sectionnum"):
            try:
                info.parent = int(parent_li["data-sectionnum"])
            except ValueError:
                pass
        acts = _activities_in(_own_copy(li), base_url)
        if acts and not info.activities:
            info.activities = acts
    return infos and list(infos.values()) or []


def extract_pluginfile_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """(name, url) pairs for course-content pluginfile links in a page."""
    soup = BeautifulSoup(html, "html.parser") if not hasattr(html, "select") else html
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.select('a[href*="pluginfile.php"]'):
        url = urljoin(base_url, a["href"])
        if _SKIP_COMPONENTS.search(url):
            continue
        key = url.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        name = a.get_text(" ", strip=True) or key.rsplit("/", 1)[-1]
        out.append((name, url))
    return out
