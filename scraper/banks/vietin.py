"""VietinBank — server-rendered HTML table (rows appear twice: desktop + mobile)."""
from ..common import Rate, find_table, parse_rate, parse_term_months, soup, table_grid

CODE = "vietin"
NAME = "VietinBank"
SOURCE_URL = "https://www.vietinbank.vn/ca-nhan/cong-cu-tien-ich/lai-suat-khcn?type=bang-lai-suat"


def fetch(session) -> str:
    r = session.get(SOURCE_URL, timeout=30)
    r.raise_for_status()
    return r.text


def parse(raw: str):
    grid = table_grid(find_table(soup(raw), ["Kỳ hạn", "VND", "USD"]))
    header = [h.lower() for h in grid[0]]
    vnd_col = next(i for i, h in enumerate(header) if h.startswith("vnd"))
    seen = {}
    for row in grid[1:]:
        months = parse_term_months(row[0])
        value = parse_rate(row[vnd_col])
        if months is None or value is None:
            continue
        seen.setdefault(months, value)  # first occurrence wins; duplicates are identical
    rates = [Rate(CODE, "counter", m, v) for m, v in sorted(seen.items())]
    return rates, None
