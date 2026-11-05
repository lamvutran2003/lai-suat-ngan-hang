"""Parser tests against saved copies of each bank's page (captured 25/10/2026).

When a bank redesigns its site: save the new page over the fixture, run
`pytest`, fix the adapter until the expectations below hold again.
"""
from pathlib import Path

import pytest

from scraper.banks import acb, agri, bab, bidv, lpb, mbv, nab, ocb, stb, tcb, tpb, vcb, vietin, vikki
from scraper.common import parse_amount_range, parse_rate, parse_term_months, soup, table_grid

FX = Path(__file__).parent / "fixtures"
M = 1_000_000


def rates_of(mod, fixture):
    path = FX / fixture
    raw = path.read_bytes() if path.suffix == ".pdf" else path.read_text(encoding="utf-8")
    rates, as_of = mod.parse(raw)
    return {(r.channel, r.term_months, r.min_amount): r.rate for r in rates}, as_of


@pytest.mark.parametrize("label,band", [
    ("Dưới 500 triệu đồng", (0, 500 * M)),
    ("Từ 500 triệu đồng đến\ndưới 2 tỷ đồng", (500 * M, 2000 * M)),
    ("Từ 2 tỷ đồng", (2000 * M, None)),
    ("Từ 100 triệu đồng đến 500 triệu đồng", (100 * M, 500 * M + 1)),
    ("Trên 500 triệu đồng", (500 * M + 1, None)),
])
def test_amount_bands(label, band):
    assert parse_amount_range(label) == band


@pytest.mark.parametrize("label,months", [
    ("12 tháng", 12), ("12T", 12), ("12 THÁNG", 12), ("12-months", 12), ("12 months", 12),
    ("Từ 6 tháng đến dưới 7 tháng", 6), ("Trên 12 tháng đến 13 tháng", 13), ("Từ 1 đến\ndưới 2 tháng", 1),
    ("Không kỳ hạn", None), ("7 ngày", None), ("1 - 3 tuần", None),
    ("Trên 13 tháng đến dưới 18 tháng", None), ("Dưới 1 tháng", None),
])
def test_term_parsing(label, months):
    assert parse_term_months(label) == months


@pytest.mark.parametrize("text,value", [("5,40 %", 5.4), ("4,90*", 4.9), ("2.6%", 2.6), ("", None), ("-", None)])
def test_rate_parsing(text, value):
    assert parse_rate(text) == value


def test_table_grid_expands_spans():
    t = soup("<table><tr><td rowspan=2>A</td><td colspan=2>B</td></tr><tr><td>c</td><td>d</td></tr></table>").table
    assert table_grid(t) == [["A", "B", "B"], ["A", "c", "d"]]


def test_vcb():
    r, as_of = rates_of(vcb, "vcb.json")
    assert as_of == "2026-10-25"
    assert r[("counter", 12, 0)] == 5.4 and r[("counter", 24, 0)] == 5.5
    assert r[("online", 6, 0)] == 3.0


def test_bidv_counter_and_online():
    r, as_of = rates_of(bidv, "bidv.json")
    assert as_of == "2026-10-21"
    assert r[("counter", 1, 0)] == 2.1 and r[("counter", 12, 0)] == 5.4 and r[("counter", 36, 0)] == 5.5
    assert r[("online", 1, 0)] == 4.75 and r[("online", 6, 0)] == 6.6 and r[("online", 12, 0)] == 6.8


def test_vietin():
    r, _ = rates_of(vietin, "vietin.html")
    assert r[("counter", 1, 0)] == 2.1 and r[("counter", 6, 0)] == 3.0 and r[("counter", 12, 0)] == 5.4
    assert r[("counter", 13, 0)] == 5.4 and r[("counter", 24, 0)] == 5.5


def test_agri():
    r, _ = rates_of(agri, "agri.html")
    assert r[("counter", 1, 0)] == 2.6 and r[("counter", 6, 0)] == 3.5 and r[("counter", 12, 0)] == 5.4
    assert 24 in {k[1] for k in r}


def test_acb_counter_and_online_tiers():
    r, _ = rates_of(acb, "acb.html")
    assert r[("counter", 1, 0)] == 4.0 and r[("counter", 12, 0)] == 4.8 and r[("counter", 13, 0)] == 4.9
    assert r[("online", 12, 0)] == 5.2                  # < 200 triệu
    assert r[("online", 12, 200_000_000)] == 5.3        # 200 triệu – < 1 tỷ
    assert r[("online", 12, 5_000_000_000)] == 5.4      # >= 5 tỷ


def test_tpb():
    r, as_of = rates_of(tpb, "tpb.html")
    assert as_of == "2026-10-19"
    assert r[("online", 1, 0)] == 4.75 and r[("online", 12, 0)] == 5.5
    assert r[("counter", 6, 0)] == 5.0 and ("counter", 12, 0) not in r  # blank cell on the bank's table


def test_sacombank_counter_and_online_bands():
    r, as_of = rates_of(stb, "stb.pdf")
    assert as_of == "2026-10-20"
    assert r[("counter", 12, 0)] == 5.4 and r[("counter", 12, 500 * M)] == 5.5 and r[("counter", 12, 2000 * M)] == 5.6
    assert r[("counter", 1, 0)] == 4.5                     # "Từ 1 đến dưới 2 tháng"
    assert r[("online", 12, 0)] == 6.5 and r[("online", 12, 50 * M)] == 6.8 and r[("online", 12, 500 * M)] == 7.0
    assert r[("online", 24, 500 * M)] == 7.3


def test_ocb_counter_and_online_bands():
    r, as_of = rates_of(ocb, "ocb.pdf")
    assert as_of == "2026-10-20"
    assert r[("counter", 6, 0)] == 5.9 and r[("counter", 12, 0)] == 6.2 and r[("counter", 36, 0)] == 6.5
    assert r[("online", 12, 0)] == 6.3 and r[("online", 12, 100 * M)] == 6.4 and r[("online", 12, 500 * M + 1)] == 6.5


def test_techcombank_phat_loc_normal_customer_bands():
    r, as_of = rates_of(tcb, "tcb.pdf")
    assert as_of == "2026-10-24"
    B = 1_000_000_000
    assert r[("counter", 12, 0)] == 5.75 and r[("counter", 12, 3 * B)] == 5.85      # <1 tỷ / ≥3 tỷ
    assert r[("online", 6, 0)] == 6.05 and r[("online", 12, 1 * B)] == 6.25
    assert r[("counter", 1, 0)] == 4.05 and ("counter", 0, 0) not in r


# ---- added 05/11/2026 (pages captured that day)

def test_lpbank_counter_and_online_from_api():
    r, as_of = rates_of(lpb, "lpb.json")
    assert as_of == "2026-10-19"                          # effectiveDate 2026-10-18T17:00Z = 19/10 in Vietnam
    assert r[("counter", 12, 0)] == 6.1 and r[("online", 12, 0)] == 6.7
    assert r[("online", 6, 0)] == 6.5 and r[("counter", 36, 0)] == 5.6
    assert not any(k[1] == 0 for k in r)                   # weeks / no-term rows are skipped


def test_mbv_takes_the_newest_personal_table():
    r, as_of = rates_of(mbv, "mbv.html")
    assert as_of == "2026-10-20"                          # the page also carries older posts (12/11/2025 ...)
    assert r[("counter", 12, 0)] == 7.0 and r[("online", 6, 0)] == 6.5 and r[("counter", 1, 0)] == 4.5


def test_bac_a_vnd_counter_after_postback():
    r, as_of = rates_of(bab, "bab.html")
    assert as_of == "2026-10-19"
    assert r[("counter", 12, 0)] == 6.6 and r[("counter", 6, 0)] == 6.55 and r[("counter", 1, 0)] == 4.75
    assert not any(ch == "online" for ch, _, _ in r)


def test_nam_a_online_and_counter_pages():
    r, as_of = rates_of(nab, "nab.json")
    assert as_of == "2026-10-20"
    assert r[("online", 12, 0)] == 6.1 and r[("online", 24, 0)] == 6.4
    assert r[("counter", 12, 0)] == 5.7 and r[("counter", 1, 0)] == 4.5
    assert ("counter", 24, 0) not in r                    # "24 tháng (**)" has no end-of-term rate


def test_vikki_skips_special_condition_rows():
    r, as_of = rates_of(vikki, "vikki.json")
    assert r[("online", 12, 0)] == 6.1 and r[("counter", 12, 0)] == 6.0   # counter: 365-day column
    assert r[("counter", 13, 0)] == 6.1                   # not the "13 tháng *" special rate (7,4)
    assert as_of == "2026-11-03"
