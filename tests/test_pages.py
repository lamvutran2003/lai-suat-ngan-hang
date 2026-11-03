"""Bank and term pages: labels, rankings and worked examples come out right."""
from datetime import datetime

import pytest

from scraper import pages

M = 1_000_000
GEN = datetime(2026, 11, 3, 9, 17)


@pytest.mark.parametrize("lo,hi,label", [
    (0, None, "Mọi mức tiền"), (0, 50 * M, "Dưới 50 triệu"), (50 * M, 500 * M, "50 triệu – dưới 500 triệu"),
    (500 * M, None, "Từ 500 triệu"), (100 * M, 500 * M + 1, "100 triệu – 500 triệu"), (500 * M + 1, None, "Trên 500 triệu"),
    (1000 * M, 5000 * M, "1 tỷ – dưới 5 tỷ"), (0, 100 * M + 1, "Đến 100 triệu"),
])
def test_band_labels(lo, hi, label):
    assert pages.band_label(lo, hi) == label


def rate(bank, ch, term, r, lo=0, hi=None):
    return {"bank": bank, "channel": ch, "term_months": term, "rate": r, "min_amount": lo, "max_amount": hi, "notes": []}


DATA = {
    "banks": [{"code": "stb", "name": "Sacombank", "count": 4, "source_url": "https://x", "as_of": "2026-10-20"},
              {"code": "vcb", "name": "Vietcombank", "count": 3, "source_url": "https://y", "as_of": "2026-11-03"},
              {"code": "agri", "name": "Agribank", "count": 2, "source_url": "https://z", "as_of": None},
              {"code": "ocb", "name": "OCB", "count": 0, "source_url": "https://o"}],
    "rates": [rate("stb", "online", 12, 6.5, 0, 50 * M), rate("stb", "online", 12, 6.8, 50 * M, 500 * M),
              rate("stb", "online", 12, 7.0, 500 * M), rate("stb", "counter", 12, 5.4),
              rate("vcb", "online", 12, 5.4), rate("vcb", "counter", 12, 5.4), rate("vcb", "counter", 6, 3.0),
              rate("agri", "counter", 12, 5.4), rate("agri", "counter", 6, 3.5)],
}


def test_bank_page_uses_band_for_100_million_and_ranks():
    slug, title, desc, body = pages.bank_page(DATA, {}, DATA["banks"][0], GEN)
    assert slug == "ngan-hang/sacombank" and "Sacombank" in title
    assert "6.800.000 ₫" in body          # 100 triệu falls in the 50–500 triệu band at 6,80%
    assert "#1" in body and "trong 3 ngân hàng" in body
    assert "Dưới 50 triệu" in body and "Từ 500 triệu" in body


def test_banks_without_data_get_no_page_and_term_pages_need_three_banks():
    assert [b["code"] for b in pages.banks_with_data(DATA)] == ["stb", "vcb", "agri"]
    assert pages.term_pages(DATA) == [12]   # 6 months has only two banks


def test_term_page_ranks_best_first_with_interest():
    slug, title, desc, body = pages.term_page(DATA, {}, 12, GEN)
    assert slug == "ky-han/12-thang"
    assert body.index("Sacombank") < body.index("Vietcombank")
    assert "6,80%/năm tại Sacombank (online)" in body
    assert "1.400.000 ₫" in body          # (6,80 − 5,40)% of 100 triệu over 12 months
