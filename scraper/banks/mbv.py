"""MBV (Ngân hàng Việt Nam Hiện Đại) — rates are published as a news post per change.

The site menu (client-api/primary_menu) links "LÃI SUẤT" to the current post, e.g.
tin-tuc/bieu-lai-suat-20102026. The post page is a Next.js app: its HTML arrives inside
self.__next_f.push([...]) strings. We decode those, then take the personal-customer table
("Trả lãi cuối kỳ tại quầy" / "Trả lãi cuối kỳ Online") with the newest "Áp dụng từ ngày".
"""
import json
import re

from ..common import ParseError, Rate, clean, parse_rate, parse_term_months, soup

CODE = "mbv"
NAME = "MBV"
SOURCE_URL = "https://www.mbv.com.vn/"
MENU_URL = "https://www.mbv.com.vn/client-api/primary_menu?language_code=vi"


def current_slug(menu: dict) -> str:
    for item in menu.get("data", {}).get("items", []):
        slug = (item.get("page_translation") or {}).get("slug") or ""
        if re.fullmatch(r"tin-tuc/bieu-lai-suat-\d{8}", slug):
            return slug
    raise ParseError("MBV: rate post not found in the site menu")


def fetch(session) -> str:
    menu = session.get(MENU_URL, timeout=30)
    menu.raise_for_status()
    r = session.get(SOURCE_URL + current_slug(menu.json()), timeout=30)
    r.raise_for_status()
    return r.text


def decode(page: str) -> str:
    parts = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', page)
    return "".join(json.loads('"' + p + '"') for p in parts) or page


def parse(raw: str):
    doc = soup(decode(raw))
    best = None
    for table in doc.find_all("table"):
        rows = [[clean(c.get_text(" ")) for c in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]
        head = " ".join(rows[0]).lower() if rows else ""
        if not ("tại quầy" in head and "online" in head):
            continue
        note = table.find_previous(string=re.compile("Áp dụng từ ngày"))
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", clean(note.parent.get_text(" ")) if note else "")
        as_of = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""
        if best is None or as_of > best[0]:
            best = (as_of, rows)
    if best is None:
        raise ParseError("MBV: personal VND rate table not found")
    as_of, rows = best
    rates = []
    for row in rows[1:]:
        months = parse_term_months(row[0]) if row and "*" not in row[0] else None
        for ch, i in (("counter", 1), ("online", 2)):
            if months and len(row) > i and (value := parse_rate(row[i])):
                rates.append(Rate(CODE, ch, months, value))
    return rates, as_of or None
