"""Guides: every token renders from the data, and the figures follow the amount bands."""
from datetime import date, datetime

from scraper import guides
from tests.test_pages import DATA, M, rate

TODAY = date(2026, 11, 3)
FULL = {**DATA, "rates": DATA["rates"] + [
    rate("vcb", "online", 1, 4.75), rate("stb", "online", 1, 4.75), rate("agri", "counter", 1, 4.75),
    rate("vcb", "online", 3, 4.75), rate("stb", "online", 6, 6.6), rate("vcb", "online", 6, 4.6)]}


def test_where_lists_names_naturally():
    b = lambda n: {"name": n}
    assert guides.where([(b("BIDV"), "online")]) == "BIDV (online)"
    assert guides.where([(b("A"), "online"), (b("B"), "online"), (b("C"), "online")]) == "A, B và C (online)"
    assert guides.where([(b("A"), "online"), (b("B"), "counter")]) == "A (online) và B (tại quầy)"
    assert guides.where([(b(x), "online") for x in "ABCDE"]) == "A, B, C và 2 ngân hàng khác (online)"


def test_best_follows_amount_bands():
    assert guides.best(FULL, 12, 100 * M)[0] == 6.8      # Sacombank 50–500 triệu band
    assert guides.best(FULL, 12, 1000 * M)[0] == 7.0     # ≥500 triệu band
    assert guides.render_tokens("{{best_interest:1000000000:12}}", FULL, TODAY) == "70.000.000 ₫"


def test_days_example_uses_actual_days():
    out = guides.render_tokens("{{days_example:6}}", FULL, TODAY)
    assert "181 ngày" in out and "03/05/2027" in out
    assert "3.272.877 ₫" in out                           # 100 triệu × 6,60% × 181 / 365


def test_every_guide_renders_without_leftover_tokens():
    pages, gs = guides.guide_pages(FULL, datetime(2026, 11, 3, 9, 17), "https://tietkiemdau.vn")
    assert pages[0][0] == "huong-dan" and len(gs) >= 7
    for slug, title, desc, body in pages:
        assert "{{" not in body, slug          # (JSON-LD legitimately ends in "}}")
        assert title and desc


def test_need_monthly_settles_on_band_rate():
    out = guides.render_tokens("{{need_monthly:10000000}}", FULL, TODAY)
    assert out == "1,71 tỷ đồng (lãi 7,00%/năm)"
