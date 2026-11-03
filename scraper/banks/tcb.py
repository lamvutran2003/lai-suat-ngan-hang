"""Techcombank — the rate page lists its PDFs through a JSON API; the deposit PDF has real text.

We use "Tiết kiệm Phát Lộc" (Techcombank's main term deposit) at the counter and
"Tiền gửi Phát Lộc Online", normal-customer columns ("KH THƯỜNG"), which come in
three deposit bands: ≥3 tỷ, 1–3 tỷ, <1 tỷ. Each term row lists 12 rates:
PRIVATE, PRIORITY, INSPIRE, KH THƯỜNG × (≥3B, 1-3B, <1B); we take the last three.
"""
import io
import re

import pdfplumber

from ..common import ParseError, Rate, clean, parse_rate

CODE = "tcb"
NAME = "Techcombank"
SOURCE_URL = "https://techcombank.com/cong-cu-tien-ich/bieu-phi-lai-suat"
LIST_URL = ("https://techcombank.com/graphql/execute.json/techcombank/viewDocumentList%3BcfPath%3D/content/dam/"
            "techcombank/master-data/vi/list-view-document/cong-cu-tien-ich/bieu-phi-lai-suat/khcn/")
DOC_CATEGORY = "lãi suất tiền gửi tiết kiệm/tiền gửi có kỳ hạn"
BILLION = 1_000_000_000
BANDS = [(3 * BILLION, None), (1 * BILLION, 3 * BILLION), (0, 1 * BILLION)]   # order of the last 3 columns
SECTIONS = {"TIẾT KIỆM PHÁT LỘC TẠI QUẦY": ("counter", "Tiết kiệm Phát Lộc"),
            "TIỀN GỬI PHÁT LỘC ONLINE": ("online", "Tiền gửi Phát Lộc Online")}


def latest_document(session) -> str:
    """URL of the newest personal deposit-rate PDF in Techcombank's document list."""
    session.get(SOURCE_URL, timeout=30)  # sets cookies the API expects
    r = session.get(LIST_URL, headers={"Referer": SOURCE_URL, "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    items = r.json()["data"]["listViewDocumentFragmentList"]["items"]
    docs = [x for x in items
            if clean((x.get("categoryTitle") or {}).get("plaintext") or "").lower().startswith(DOC_CATEGORY)
            and (x.get("documentPath") or {}).get("_path")]
    if not docs:
        raise ParseError("Techcombank deposit-rate document not found in the document list")
    newest = max(docs, key=lambda x: x.get("date") or "")
    return "https://techcombank.com" + newest["documentPath"]["_path"]


def fetch(session) -> bytes:
    r = session.get(latest_document(session), timeout=60)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise ParseError("Techcombank rate file is not a PDF")
    return r.content


def parse(raw: bytes):
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    m = re.search(r"Áp dụng từ ngày (\d{1,2}) tháng (\d{1,2}) năm (20\d\d)", clean(text))
    as_of = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None

    rates, section = [], None
    for line in text.split("\n"):
        line = clean(line)
        upper = line.upper()
        hit = next((v for k, v in SECTIONS.items() if upper.startswith(k)), None)
        if hit:
            section = hit
            continue
        if section is None:
            continue
        if upper.startswith("(*)") or upper.startswith("TCB PUBLIC"):
            section = None
            continue
        mm = re.match(r"^(\d+)M\s+((?:\d+\.\d+\s*){12})$", line)
        if not mm:
            continue
        months = int(mm.group(1))
        values = mm.group(2).split()[-3:]          # KH THƯỜNG: ≥3B, 1-3B, <1B
        channel, product = section
        for (lo, hi), v in zip(BANDS, values):
            rate = parse_rate(v)
            if rate is not None:
                rates.append(Rate(CODE, channel, months, rate, product=product, min_amount=lo, max_amount=hi))
    if not {r.channel for r in rates} >= {"counter", "online"}:
        raise ParseError("Techcombank: Phát Lộc counter/online tables not found")
    return rates, as_of
