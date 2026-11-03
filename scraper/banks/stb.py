"""Sacombank — one PDF at a fixed address, replaced whenever rates change.

Page 1: counter savings ("A. ... MỞ TẠI QUẦY"), 3 deposit-size bands.
Page 3: online deposits ("B. ... MỞ TRỰC TUYẾN"), 3 deposit-size bands.
We take the "Lãi cuối kỳ" (interest at maturity) column of each band.
"""
import io
import re

import pdfplumber

from ..common import ParseError, Rate, clean, parse_amount_range, parse_rate, parse_term_months

CODE = "stb"
NAME = "Sacombank"
SOURCE_URL = "https://www.sacombank.com.vn/cong-cu/lai-suat.html"
PDF_URL = ("https://www.sacombank.com.vn/content/dam/sacombank/files/cong-cu/lai-suat/"
           "tien-gui/khcn/SACOMBANK_LAISUATNIEMYETTAIQUAY_KHCN_VIE.pdf")


def fetch(session) -> bytes:
    r = session.get(PDF_URL, timeout=60)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise ParseError("Sacombank rate file is not a PDF any more")
    return r.content


def _band_table(table, channel):
    head, sub = table[0], table[1]
    # Which deposit band each column belongs to: the last band label at or left of it.
    band, bands = None, []
    for cell in head:
        if cell and clean(cell).lower() != "mức tiền":
            band = parse_amount_range(cell)
        bands.append(band)
    rates = []
    for col, label in enumerate(sub):
        if not label or not clean(label).lower().startswith("lãi cuối"):
            continue
        lo, hi = bands[col]
        for row in table[2:]:
            months = parse_term_months(row[0] or "")
            value = parse_rate(row[col] or "")
            if months is None or value is None:
                continue
            rates.append(Rate(CODE, channel, months, value, product="Tiết kiệm có kỳ hạn" if channel == "counter"
                              else "Tiền gửi trực tuyến", min_amount=lo, max_amount=hi))
    return rates


def parse(raw: bytes):
    rates, as_of = [], None
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        first = clean(pdf.pages[0].extract_text() or "")
        m = re.search(r"Hiệu lực từ .*?ngày (\d{1,2})\.(\d{1,2})\.(20\d\d)", first)
        if m:
            as_of = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        for page in pdf.pages:
            text = clean(page.extract_text() or "").upper()
            channel = "online" if "MỞ TRỰC TUYẾN" in text else "counter"
            for table in page.extract_tables():
                if (len(table) > 3 and clean(table[0][0] or "").lower() == "mức tiền"
                        and clean(table[1][0] or "").lower() == "kỳ hạn gửi"):
                    rates += _band_table(table, channel)
    if not any(r.channel == "online" for r in rates):
        raise ParseError("Sacombank online table not found")
    return rates, as_of
