"""Agribank — the page loads its table from a plain HTML fragment URL."""
from ..common import Rate, find_table, parse_rate, parse_term_months, soup, table_grid

CODE = "agri"
NAME = "Agribank"
SOURCE_URL = "https://www.agribank.com.vn/vn/lai-suat-tien-gui"
FRAGMENT_URL = ("https://www.agribank.com.vn/wcm/connect/ttkhac/lai-suat/lai-suat-cn"
                "?source=library&srv=cmpnt&cmpntid=c1687c7c-142f-4616-a8b0-02f09a14f844")


def fetch(session) -> str:
    r = session.get(FRAGMENT_URL, timeout=30)
    r.raise_for_status()
    return r.text


def parse(raw: str):
    # The fragment also holds a "maximum rate" regulatory table; that one has no VND column header.
    grid = table_grid(find_table(soup(raw), ["Kì hạn", "VND", "USD"]))
    vnd_col = [h.upper() for h in grid[0]].index("VND")
    rates = []
    for row in grid[1:]:
        months = parse_term_months(row[0])
        value = parse_rate(row[vnd_col])
        if months is None or value is None:
            continue
        rates.append(Rate(CODE, "counter", months, value))
    return rates, None
