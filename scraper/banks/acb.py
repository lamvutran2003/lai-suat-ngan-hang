"""ACB — server-rendered page with two tables we use:

1. Counter rates ("TK Truyền Thống / Tiền Gửi Có Kỳ Hạn", interest paid at maturity).
   Multi-level merged headers, so we read it through table_grid().
2. Online rates by deposit tier ("Tiền gửi Online (LCK)") — feeds the amount filter.
"""
import re

from ..common import (ParseError, Rate, find_table, has_footnote, parse_rate,
                      parse_term_months, soup, table_grid)

CODE = "acb"
NAME = "ACB"
SOURCE_URL = "https://acb.com.vn/lai-suat-tien-gui"
MILLION = 1_000_000


def fetch(session) -> str:
    r = session.get(SOURCE_URL, timeout=30)
    r.raise_for_status()
    return r.text


def _counter(doc):
    grid = table_grid(find_table(doc, ["Kỳ hạn", "TK Truyền Thống", "Lãi cuối kỳ"]))
    # Find the column under "VND" -> "TK Truyền Thống..." -> "Lãi cuối kỳ".
    col = None
    for c in range(len(grid[0])):
        stack = " | ".join(grid[r][c] for r in range(min(3, len(grid)))).lower()
        if "vnd" in stack and "truyền thống" in stack and "cuối kỳ" in stack:
            col = c
            break
    if col is None:
        raise ParseError("ACB counter table: VND / Truyền Thống / Lãi cuối kỳ column not found")
    rates = []
    for row in grid[3:]:
        months = parse_term_months(row[0])
        value = parse_rate(row[col])
        if months is None or value is None:
            continue
        notes = ["Có điều kiện, xem ghi chú của ngân hàng"] if has_footnote(row[col]) else []
        rates.append(Rate(CODE, "counter", months, value, product="Tiền gửi có kỳ hạn", notes=notes))
    return rates


def _tier_bounds(label: str):
    """'< 200' -> (0, 200tr) ; '200 – < 1.000' -> (200tr, 1 tỷ) ; '>= 5.000' -> (5 tỷ, None). Unit: triệu."""
    nums = [int(n.replace(".", "")) for n in re.findall(r"\d[\d.]*", label)]
    if label.strip().startswith("<") and len(nums) == 1:
        return 0, nums[0] * MILLION
    if ">" in label and len(nums) == 1:
        return nums[0] * MILLION, None
    if len(nums) == 2:
        return nums[0] * MILLION, nums[1] * MILLION
    raise ParseError(f"ACB online tier label not understood: {label!r}")


def _online(doc):
    grid = table_grid(find_table(doc, ["Tiền gửi Online (LCK)"], must_not=["tùy chọn"]))
    term_row = grid[1]
    rates = []
    for row in grid[2:]:
        lo, hi = _tier_bounds(row[0])
        for c in range(1, len(row)):
            months = parse_term_months(term_row[c])
            value = parse_rate(row[c])
            if months is None or value is None:
                continue
            rates.append(Rate(CODE, "online", months, value, product="Tiền gửi Online",
                              min_amount=lo, max_amount=hi))
    return rates


def parse(raw: str):
    doc = soup(raw)
    return _counter(doc) + _online(doc), None
