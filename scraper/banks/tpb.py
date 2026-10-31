"""TPBank — the rate page loads an HTML fragment with the personal-deposit table."""
import re
import time

from ..common import Rate, clean, find_table, parse_rate, parse_term_months, soup, table_grid

CODE = "tpb"
NAME = "TPBank"
SOURCE_URL = "https://tpb.vn/cong-cu-tinh-toan/lai-suat"
FRAGMENT_URL = ("https://tpb.vn/wps/wcm/connect/tpbank_data/sa-website/ty-gia-lai-suat-cong-cu-tinh-toan/"
                "lai-xuat/danh-cho-khach-hang-ca-nhan?source=library&srv=cmpnt"
                "&cmpntid=c3723702-cc5e-43bc-8123-867223571d0a")

# Column header (upper-case) -> (channel, product label)
COLUMNS = {
    "TIẾT KIỆM ĐIỆN TỬ": ("online", "Tiết kiệm điện tử"),
    "TIẾT KIỆM TÍNH LÃI CUỐI KỲ": ("counter", "Tiết kiệm lãi cuối kỳ"),
}


def fetch(session) -> str:
    # TPBank's server answers ~1 in 3 requests with a spurious 400 (measured 25/10/2026).
    # Visiting the page first (cookie + Referer) and retrying a few times is enough.
    session.get(SOURCE_URL, timeout=30)
    r = None
    for attempt in range(6):
        r = session.get(FRAGMENT_URL, headers={"Referer": SOURCE_URL}, timeout=30)
        if r.status_code == 200:
            return r.text
        time.sleep(2 + attempt)
    r.raise_for_status()
    return r.text


def parse(raw: str):
    grid = table_grid(find_table(soup(raw), ["KÌ HẠN", "TIẾT KIỆM ĐIỆN TỬ"]))
    header = [h.upper() for h in grid[0]]
    rates = []
    for col_name, (channel, product) in COLUMNS.items():
        col = header.index(col_name)
        for row in grid[1:]:
            months = parse_term_months(row[0])
            value = parse_rate(row[col])
            if months is None or value is None:
                continue
            rates.append(Rate(CODE, channel, months, value, product=product))
    # "...(hiệu lực từ 14h00 ngày 19/10/2026)..."
    m = re.search(r"hiệu lực từ[^)]*?(\d{1,2})/(\d{1,2})/(20\d\d)", clean(soup(raw).get_text(" ")))
    as_of = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None
    return rates, as_of
