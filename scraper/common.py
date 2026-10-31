"""Shared helpers: HTTP session, rate/term parsing, and HTML table flattening."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
TIMEOUT = 30


@dataclass
class Rate:
    """One savings rate quote, normalised across banks."""

    bank: str                      # short code, e.g. "vcb"
    channel: str                   # "counter" (tại quầy) or "online"
    term_months: int               # 1, 3, 6, 12 ...
    rate: float                    # % per year, e.g. 5.4
    product: str = ""              # bank's own product name, if any
    min_amount: int = 0            # VND, inclusive
    max_amount: Optional[int] = None  # VND, exclusive; None = no cap
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*",
                      "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"})
    retry = Retry(total=3, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET", "POST"))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def clean(text: str) -> str:
    """Collapse whitespace and normalise Vietnamese accents to NFC.

    Some banks (e.g. VietinBank) publish decomposed characters ("u" + combining
    hook) that look identical on screen but don't match normal strings.
    """
    text = unicodedata.normalize("NFC", (text or "").replace("\xa0", " "))
    return re.sub(r"\s+", " ", text).strip()


def parse_rate(text: str) -> Optional[float]:
    """'5,40 %' -> 5.4 ; '4,90*' -> 4.9 ; '' / '-' -> None."""
    t = clean(text).replace("%", "").replace("*", "").strip()
    if not t or t in {"-", "–"}:
        return None
    t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def has_footnote(text: str) -> bool:
    return "*" in (text or "")


_TERM_PATTERNS = [
    (re.compile(r"(\d+)\s*-?\s*(?:t|tháng|month|months)"), lambda m: int(m.group(1))),
    (re.compile(r"từ (\d+) tháng đến dưới \d+ tháng"), lambda m: int(m.group(1))),
    (re.compile(r"trên \d+ tháng đến (\d+) tháng"), lambda m: int(m.group(1))),
]


def parse_term_months(label: str) -> Optional[int]:
    """Map a bank's term label to whole months, or None for terms we don't compare.

    '12 tháng' / '12T' / '12 THÁNG' / '12-months' / '12 months' -> 12
    'Từ 6 tháng đến dưới 7 tháng' -> 6
    'Trên 12 tháng đến 13 tháng'  -> 13
    'Không kỳ hạn', '7 ngày', '1 - 3 tuần', 'Trên 13 tháng đến dưới 18 tháng' -> None
    """
    t = clean(label).lower()
    if not t or any(x in t for x in ("không kỳ hạn", "ngày", "tuần", "days", "demand")):
        return None
    for pattern, fn in _TERM_PATTERNS:
        m = pattern.fullmatch(t)
        if m:
            months = fn(m)
            return months if 1 <= months <= 60 else None
    return None


def table_grid(table: Tag) -> list[list[str]]:
    """Flatten an HTML table into a rectangular grid, expanding rowspan/colspan.

    Merged cells are copied into every slot they cover, so column positions
    line up across rows (needed for ACB's multi-level headers).
    """
    grid: list[list[Optional[str]]] = []
    for r, tr in enumerate(table.find_all("tr")):
        while len(grid) <= r:
            grid.append([])
        row = grid[r]
        c = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while c < len(row) and row[c] is not None:
                c += 1
            text = clean(cell.get_text(" ", strip=True))
            rs = int(cell.get("rowspan", 1) or 1)
            cs = int(cell.get("colspan", 1) or 1)
            for dr in range(rs):
                while len(grid) <= r + dr:
                    grid.append([])
                target = grid[r + dr]
                while len(target) < c + cs:
                    target.append(None)
                for dc in range(cs):
                    if target[c + dc] is None:
                        target[c + dc] = text
            c += cs
    width = max((len(r) for r in grid), default=0)
    return [[(x if x is not None else "") for x in row] + [""] * (width - len(row)) for row in grid]


def find_table(doc: BeautifulSoup, must_contain: list[str], must_not: list[str] = ()) -> Tag:
    """First table whose text contains all `must_contain` strings (case-insensitive)."""
    for t in doc.find_all("table"):
        text = clean(t.get_text(" ", strip=True)).lower()
        if (all(clean(s).lower() in text for s in must_contain)
                and not any(clean(s).lower() in text for s in must_not)):
            return t
    raise ValueError(f"No table containing {must_contain!r}")


class ParseError(Exception):
    """Raised when a bank's page no longer looks the way the parser expects."""
