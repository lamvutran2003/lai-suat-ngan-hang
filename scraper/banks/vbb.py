"""VietBank — one HTML page with all personal rates (F5-protected, but plain requests pass).

Counter: "I. Sản phẩm tiết kiệm thông thường – 1. Tiết kiệm có kỳ hạn …", VND "Lãi cuối kỳ" (2nd column).
Online:  "6. Tiền gửi Online", column "Tiền gửi Online có kỳ hạn".
Effective date: "Lãi suất huy động dành cho Khách hàng cá nhân (Hiệu lực ngày 19/10/2026)".
"""
import re

from ..common import ParseError, Rate, clean, parse_rate, parse_term_months, soup, table_grid

CODE = "vbb"
NAME = "VietBank"
SOURCE_URL = "https://www.vietbank.com.vn/lai-suat"


def fetch(session) -> str:
    r = session.get(SOURCE_URL, timeout=30)
    r.raise_for_status()
    return r.text


def heading(table) -> str:
    s = table.find_previous(string=re.compile(r"^\s*\d+\.\s"))
    return clean(s).lower() if s else ""


def parse(raw: str):
    doc = soup(raw)
    m = re.search(r"Khách hàng cá nhân \(Hiệu lực ngày (\d{1,2})/(\d{1,2})/(\d{4})\)", clean(doc.get_text(" ")))
    as_of = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None
    tables = doc.find_all("table")
    counter = next((t for t in tables if heading(t).startswith("1. tiết kiệm có kỳ hạn")), None)
    online = next((t for t in tables if heading(t).startswith("6. tiền gửi online")), None)
    if counter is None or online is None:
        raise ParseError("VietBank: counter or online table not found")
    rates = []
    for ch, table in (("counter", counter), ("online", online)):
        for row in table_grid(table):
            if not row or "*" in row[0]:
                continue
            months = parse_term_months(row[0])
            value = parse_rate(row[1]) if len(row) > 1 else None
            if months and value:
                rates.append(Rate(CODE, ch, months, value))
    return rates, as_of
