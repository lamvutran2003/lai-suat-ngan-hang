"""Nam A Bank — the rate index lists dated pages; we follow the current online and counter VND pages.

Index: /lai-suat has a hidden <select class="news-list" id="259"> (personal customers) whose options
name the current pages, e.g. "Lãi suất Tiết kiệm Trực tuyến (Online) (%/năm) (Hiệu lực ngày 20/10/2026)".
"""
import json
import re
from urllib.parse import urljoin

from ..common import ParseError, Rate, clean, parse_rate, parse_term_months, soup

CODE = "nab"
NAME = "Nam A Bank"
SOURCE_URL = "https://www.namabank.com.vn/lai-suat"
PAGES = {"online": "lãi suất tiết kiệm trực tuyến", "counter": "lãi suất tiền gửi vnd"}


def pages(index_html: str) -> dict:
    doc = soup(index_html)
    sel = doc.find("select", {"class": "news-list", "id": "259"})
    if not sel:
        raise ParseError("Nam A Bank: personal rate list not found")
    out = {}
    for opt in sel.find_all("option"):
        label = clean(opt.get_text(" "))
        for ch, start in PAGES.items():
            if label.lower().startswith(start) and ch not in out:
                out[ch] = (label, opt.get("data-news-href"))
    if set(out) != set(PAGES):
        raise ParseError(f"Nam A Bank: expected online and counter pages, found {sorted(out)}")
    return out


def fetch(session) -> str:
    r = session.get(SOURCE_URL, timeout=30)
    r.raise_for_status()
    out = {}
    for ch, (label, href) in pages(r.text).items():
        p = session.get(urljoin(SOURCE_URL, href), timeout=30)
        p.raise_for_status()
        out[ch] = {"label": label, "html": p.text}
    return json.dumps(out, ensure_ascii=False)


def term(label: str):
    return parse_term_months(re.split(r"[,(]", label)[0])


def parse(raw: str):
    data = json.loads(raw)
    rates, dates = [], []
    for ch, page in data.items():
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", page["label"])
        if m:
            dates.append(f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}")
        table = next((t for t in soup(page["html"]).find_all("table") if "cuối kỳ" in t.get_text().lower()), None)
        if table is None:
            raise ParseError(f"Nam A Bank: {ch} table not found")
        rows = [[clean(c.get_text(" ")) for c in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]
        col = next(i for i, h in enumerate(rows[0]) if "cuối kỳ" in h.lower())
        for row in rows[1:]:
            if "*" in row[0]:                # footnoted terms carry conditions
                continue
            if len(row) > col and (months := term(row[0])) and (value := parse_rate(row[col])):
                rates.append(Rate(CODE, ch, months, value))
    return rates, max(dates) if dates else None
