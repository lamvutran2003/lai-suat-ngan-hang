"""Gold: each shop parser against a saved copy, unit conversion to đồng/lượng, and the page."""
from datetime import datetime
from pathlib import Path

import pytest

from scraper import gold, gold_page
from scraper.common import ParseError

F = Path(__file__).parent / "fixtures" / "gold"


def parsed(mod):
    items, updated = mod.parse((F / mod.FIXTURE).read_text(encoding="utf-8"))
    gold.validate(mod.CODE, items)
    return {i["kind"]: i for i in items if i["kind"]}, items, updated


def test_pnj_thousands_per_chi_become_dong_per_luong():
    kinds, items, updated = parsed(gold.PNJ)
    assert kinds["sjc"]["sell"] == 140_600_000 and kinds["sjc"]["buy"] == 137_600_000
    assert kinds["ring"]["sell"] == 138_900_000
    assert updated == "2026-11-03T14:12+07:00"
    assert not any("nguyên liệu" in i["name"] for i in items)


def test_phu_quy_board():
    kinds, items, updated = parsed(gold.PhuQuy)
    assert kinds["sjc"]["buy"] == 136_000_000 and kinds["ring"]["sell"] == 139_000_000
    assert kinds["jewelry"]["sell"] == 138_000_000
    assert not any("phi sjc" in i["name"].lower() or "bạc" in i["name"].lower() for i in items)
    assert updated == "2026-11-03T18:22+07:00"


def test_bao_tin_manh_hai_skips_silver_and_per_piece_products():
    kinds, items, updated = parsed(gold.BTMH)
    assert kinds["ring"]["name"] == "Kim Gia Bảo 24K" and kinds["ring"]["sell"] == 140_300_000
    assert not any("Tiểu Kim Cát" in i["name"] or "Ngân" in i["name"] for i in items)
    assert updated == "2026-11-03T20:41+07:00"


def test_world_price_in_dong_per_luong():
    w = gold.world(None, F)
    assert w["usd_vnd"] == 25960.0
    assert abs(w["vnd_luong"] - w["usd_oz"] * 37.5 / 31.1034768 * 25960) < 1000


def test_validate_rejects_buy_above_sell_and_wrong_units():
    with pytest.raises(ParseError):
        gold.validate("x", [gold.item("Vàng miếng SJC", 150_000_000, 140_000_000, "sjc")])
    with pytest.raises(ParseError):
        gold.validate("x", [gold.item("Vàng miếng SJC", 13_760_000, 14_060_000, "sjc")])   # per chỉ, not per lượng


def test_page_picks_cheapest_and_compares_with_world(tmp_path, monkeypatch):
    monkeypatch.setattr(gold_page, "HISTORY", tmp_path)
    shops = []
    for mod in gold.SHOPS:
        items, updated = mod.parse((F / mod.FIXTURE).read_text(encoding="utf-8"))
        shops.append({"code": mod.CODE, "name": mod.NAME, "source_url": mod.SOURCE_URL, "status": "ok",
                      "updated": updated, "items": items})
    g = {"generated_at": "2026-11-04T09:47+07:00", "shops": shops, "world": gold.world(None, F)}
    slug, title, desc, body = gold_page.gold_page(g, datetime.fromisoformat(g["generated_at"]))
    assert slug == "gia-vang" and "04/11/2026" in title
    assert "Nhẫn trơn 999.9 bán ra thấp nhất 138,9 triệu đồng/lượng tại PNJ" in desc
    assert "thấp hơn vàng miếng SJC 17,6 triệu" in desc
    assert "Giá vàng những ngày gần đây" not in body     # needs at least two days of history
