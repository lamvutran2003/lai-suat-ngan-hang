"""OCB — the rate page links a dated PDF; we find the link, then read the PDF's text.

Each term row reads (8 values, '-' = not offered):
  counter: Đầu kỳ, Hàng tháng, Hàng quý, Hàng 6 tháng, Cuối kỳ | online cuối kỳ: band 1, band 2, band 3
"""
import io
import re

import pdfplumber

from ..common import ParseError, Rate, clean, parse_rate, parse_term_months

CODE = "ocb"
NAME = "OCB"
SOURCE_URL = "https://www.ocb.com.vn/vi/cong-cu/lai-suat"
PDF_LINK = re.compile(r"https://webocb-api\.ocb\.com\.vn/Resources/Files/[^\"' <>]*bang-lai-suat-tien-gui-khcn[^\"' <>]*\.pdf")
MILLION = 1_000_000


def fetch(session) -> bytes:
    page = session.get(SOURCE_URL, timeout=30)
    page.raise_for_status()
    links = PDF_LINK.findall(page.text)
    if not links:
        raise ParseError("OCB rate PDF link not found on the rate page")
    # File names start with an upload timestamp, so the highest sorts newest.
    r = session.get(sorted(set(links))[-1], timeout=60)
    r.raise_for_status()
    return r.content


def _online_bands(text: str):
    """Read the three online deposit bands from the header, e.g. <100tr, 100–500tr, >500tr."""
    # The PDF's header cells wrap, so words come out of order ("Dưới 100 Trên 500 ... triệu").
    # Read each band's number from its own keyword; the unit is triệu throughout.
    head = text[: text.find("KKH")] if "KKH" in text else text
    below, frm, above = (re.search(p, head) for p in (r"Dưới (\d+)", r"Từ (\d+) triệu", r"Trên (\d+)"))
    if not (below and frm and above and "triệu" in head):
        raise ParseError("OCB online band header changed")
    a, b, d = (int(x.group(1)) * MILLION for x in (below, frm, above))
    if not a == b < d:
        raise ParseError(f"OCB online bands look wrong: {a}, {b}, {d}")
    return [(0, a), (b, d + 1), (d + 1, None)]


def parse(raw: bytes):
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    flat = clean(text)
    m = re.search(r"Áp dụng cho KHCN từ ngày (\d{1,2})/(\d{1,2})/(20\d\d)", flat)
    as_of = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None
    bands = _online_bands(flat)
    rates = []
    for line in text.split("\n"):
        mm = re.match(r"^\s*(\d+ tháng)\s+(.*)$", clean(line))
        if not mm:
            continue
        months = parse_term_months(mm.group(1))
        vals = mm.group(2).split()
        if months is None or len(vals) != 8:
            continue
        counter = parse_rate(vals[4])
        if counter is not None:
            rates.append(Rate(CODE, "counter", months, counter, product="Tiết kiệm thông thường"))
        for (lo, hi), v in zip(bands, vals[5:]):
            value = parse_rate(v)
            if value is not None:
                rates.append(Rate(CODE, "online", months, value, product="Tiết kiệm trực tuyến",
                                  min_amount=lo, max_amount=hi))
    return rates, as_of
