"""PVcomBank — two static PDFs with real text, one per channel (the rate tool itself needs reCAPTCHA).

Counter: GD_Tai_quay_Tien_gui_tiet_kiem_VND.pdf ("BIỂU LÃI SUẤT TIỀN GỬI VND TẠI QUẦY")
Online:  GD_Online_Tien_gui_tiet_kiem_VND.pdf   ("… TRÊN KÊNH ONLINE")
Product: "Đại Chúng", lãi cuối kỳ = the column holding the first rate of the 1-month row.
At the counter, 12 and 13 months have two rows: the plain row is only for new deposits from
2.000 tỷ đồng (10%/năm); "12 tháng(*)" / "13 tháng(*)" is for everyone else, so we take the (*) row.
Effective date: "Áp dụng kể từ ngày DD/MM/YYYY".
"""
import io
import re

import pdfplumber

from ..common import ParseError, Rate, clean, parse_rate, parse_term_months

CODE = "pvcb"
NAME = "PVcomBank"
SOURCE_URL = "https://www.pvcombank.com.vn/bieu-lai-suat"
BASE = "https://www.pvcombank.com.vn/static/BieuPhi/"
FILES = (("counter", "GD_Tai_quay_Tien_gui_tiet_kiem_VND.pdf"), ("online", "GD_Online_Tien_gui_tiet_kiem_VND.pdf"))
SEP = b"\n%%PVCOMBANK-NEXT-FILE%%\n"   # fetch() joins the two PDFs; parse() splits them again
MAX_PLAIN_RATE = 9.0                   # anything higher is a big-deposit special: stop and look


def fetch(session) -> bytes:
    parts = []
    for _, name in FILES:
        r = session.get(BASE + name, headers={"Referer": SOURCE_URL}, timeout=60)
        r.raise_for_status()
        if not r.content.startswith(b"%PDF"):
            raise ParseError(f"PVcomBank: {name} is not a PDF")
        parts.append(r.content)
    return SEP.join(parts)


def _rows(pdf_bytes: bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[0]
        text = clean(page.extract_text() or "")
        table = max(page.extract_tables(), key=len)
    m = re.search(r"Áp dụng kể từ ngày (\d{1,2})/(\d{1,2})/(20\d\d)", text)
    as_of = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None
    return as_of, [[clean(c or "") for c in row] for row in table if row and row[0]]


def parse(raw: bytes):
    docs = raw.split(SEP)
    if len(docs) != 2:
        raise ParseError("PVcomBank: expected two PDFs")
    rates, dates = [], []
    for (ch, _), doc in zip(FILES, docs):
        as_of, rows = _rows(doc)
        dates.append(as_of)
        # The "Đại Chúng" column is where the first rate sits in the 1-month row; later rows (48, 60
        # months) leave it empty and only the instalment products have a rate, so never look further right.
        first = next((r for r in rows if parse_term_months(r[0]) == 1), None)
        col = next((i for i, c in enumerate(first) if i and parse_rate(c)), None) if first else None
        if col is None:
            raise ParseError(f"PVcomBank {ch}: 1-month row not found")
        found = {}
        for row in rows:
            months = parse_term_months(row[0].replace("(*)", "").strip())
            value = parse_rate(row[col]) if len(row) > col else None
            if not months or not value:
                continue
            starred = "(*)" in row[0]
            if starred or months not in found:   # a (*) row replaces the 2.000-tỷ row for the same term
                found[months] = (value, starred)
        for months, (value, _) in sorted(found.items()):
            if value > MAX_PLAIN_RATE:
                raise ParseError(f"PVcomBank {ch} {months}m = {value}% looks like a big-deposit special")
            rates.append(Rate(CODE, ch, months, value, product="Đại Chúng"))
    if len(rates) < 25:
        raise ParseError(f"PVcomBank: only {len(rates)} rates parsed")
    return rates, max(d for d in dates if d) if any(dates) else None
