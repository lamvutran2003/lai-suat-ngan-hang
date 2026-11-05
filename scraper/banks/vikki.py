"""Vikki Bank (ngân hàng số của HDBank, trước là DongA Bank) — two plain HTML pages.

Online:  "Tiết Kiệm Phú Quý – Nhận Lãi Cuối Kỳ" column.
Counter: "Tiết kiệm bằng VND", columns for a 360- and a 365-day year; we take 365-day "Cuối kỳ"
(the last column), which is how every other bank on the site is quoted.
"""
import json
import re

from ..common import ParseError, Rate, clean, parse_rate, parse_term_months, soup

CODE = "vikki"
NAME = "Vikki Bank"
SOURCE_URL = "https://vikkibank.vn/lai-suat-tien-gui/"
URLS = {"online": "https://vikkibank.vn/lai-suat-huy-dong-tiet-kiem-bang-vnd-online/",
        "counter": "https://vikkibank.vn/lai-suat-tiet-kiem-bang-vnd/"}


def fetch(session) -> str:
    out = {}
    for ch, url in URLS.items():
        r = session.get(url, timeout=30)
        r.raise_for_status()
        out[ch] = r.text
    return json.dumps(out, ensure_ascii=False)


def since(text: str):
    m = re.search(r"kể từ ngày (\d{1,2})/(\d{1,2})/(\d{4})", text)
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None


def parse(raw: str):
    pages = json.loads(raw)
    rates, dates = [], []
    for ch, page in pages.items():
        doc = soup(page)
        dates.append(since(clean(doc.get_text(" "))))
        table = doc.find("table")
        if table is None:
            raise ParseError(f"Vikki: {ch} table not found")
        rows = [[clean(c.get_text(" ")) for c in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]
        if ch == "online" and "cuối kỳ" not in rows[0][-1].lower():
            raise ParseError("Vikki: online table's last column is no longer 'Nhận lãi cuối kỳ'")
        if ch == "counter" and not any("365" in " ".join(r) for r in rows[:3]):
            raise ParseError("Vikki: counter table no longer shows the 365-day columns")
        for row in rows:
            if not row or "*" in row[0]:      # "13 tháng *": a special-condition product, not the listed rate
                continue
            months = parse_term_months(row[0])
            value = parse_rate(row[-1]) if row else None
            if months and value:
                rates.append(Rate(CODE, ch, months, value))
    dates = [d for d in dates if d]
    return rates, max(dates) if dates else None
