"""ABBank — /thong-tin/lai-suat links the current dated page, e.g.
"Lãi suất tiết kiệm VND (Ngày hiệu lực 21/10/2026)". That page has two tables:
"Tại Quầy giao dịch" (counter) and "kênh Online – Esaving / Msaving" (online).
Term cells are split: a merged unit cell ("Tuần"/"Tháng") next to the number.
"""
import json
import re
from urllib.parse import urljoin

from ..common import ParseError, Rate, clean, parse_rate, soup, table_grid

CODE = "abb"
NAME = "ABBank"
SOURCE_URL = "https://www.abbank.vn/thong-tin/lai-suat"


def current_page(index_html: str):
    for a in soup(index_html).find_all("a"):
        label, href = clean(a.get_text(" ")), a.get("href") or ""
        if "lai-suat-tiet-kiem-vnd-ngay-hieu-luc" in href and label.lower().startswith("lãi suất tiết kiệm vnd"):
            return label, urljoin(SOURCE_URL, href)
    raise ParseError("ABBank: current VND savings page not linked from the rate index")


def fetch(session) -> str:
    r = session.get(SOURCE_URL, timeout=30)
    r.raise_for_status()
    label, url = current_page(r.text)
    p = session.get(url, timeout=30)
    p.raise_for_status()
    return json.dumps({"label": label, "url": url, "html": p.text}, ensure_ascii=False)


def parse(raw: str):
    data = json.loads(raw)
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", data["label"])
    as_of = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None
    rates = []
    for table in soup(data["html"]).find_all("table"):
        before = clean(table.find_previous(string=re.compile(r"Tại Quầy|Online", re.I)) or "").lower()
        ch = "online" if "online" in before else "counter" if "quầy" in before else None
        if ch is None:
            continue
        grid = table_grid(table)
        if "cuối kỳ" not in grid[0][2].lower():
            raise ParseError("ABBank: third column is no longer 'Lĩnh lãi cuối kỳ'")
        for row in grid[1:]:
            if len(row) > 2 and row[0].lower() == "tháng" and row[1].isdigit() and (value := parse_rate(row[2])):
                rates.append(Rate(CODE, ch, int(row[1]), value))
    if {r.channel for r in rates} != {"counter", "online"}:
        raise ParseError("ABBank: expected both counter and online tables")
    return rates, as_of
