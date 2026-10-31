"""Parser tests against saved copies of each bank's page (captured 25/10/2026).

When a bank redesigns its site: save the new page over the fixture, run
`pytest`, fix the adapter until the expectations below hold again.
"""
from pathlib import Path

import pytest

from scraper.banks import acb, agri, bidv, tpb, vcb, vietin
from scraper.common import parse_rate, parse_term_months, soup, table_grid

FX = Path(__file__).parent / "fixtures"


def rates_of(mod, fixture):
    rates, as_of = mod.parse((FX / fixture).read_text(encoding="utf-8"))
    return {(r.channel, r.term_months, r.min_amount): r.rate for r in rates}, as_of


@pytest.mark.parametrize("label,months", [
    ("12 tháng", 12), ("12T", 12), ("12 THÁNG", 12), ("12-months", 12), ("12 months", 12),
    ("Từ 6 tháng đến dưới 7 tháng", 6), ("Trên 12 tháng đến 13 tháng", 13),
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
