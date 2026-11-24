"""Hand-entered banks: validation, the 'new sheet published' flag and the re-check reminder."""
import json
from datetime import date

import pytest

from scraper.common import ParseError
from scraper.manual import ManualBank

B = 1_000_000_000


def bank(tmp_path, code="vpb", **over):
    d = {"name": "VPBank", "source_url": "https://x", "watch": "sheet-0211.pdf", "as_of": "2026-11-02",
         "checked_at": "2026-11-03",
         "counter": [{"amount": "Dưới 10 tỷ", "rates": {"12": 6.40}}, {"amount": "Từ 10 tỷ", "rates": {"12": 6.90}}],
         "online": [{"rates": {"12": 6.70, "15": 7.40}}]}
    d.update(over)
    p = tmp_path / f"{code}.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return ManualBank(p), d


def raw(d, latest=None):
    return json.dumps({**d, "_latest": latest}, ensure_ascii=False)


def test_bands_and_rates(tmp_path):
    m, d = bank(tmp_path)
    rates, as_of = m.parse(raw(d, ("sheet-0211.pdf", "https://x/sheet-0211.pdf")), today=date(2026, 11, 4))
    got = {(r.channel, r.term_months, r.min_amount, r.max_amount): r.rate for r in rates}
    assert got[("counter", 12, 0, 10 * B)] == 6.40 and got[("counter", 12, 10 * B, None)] == 6.90
    assert got[("online", 15, 0, None)] == 7.40 and as_of == "2026-11-02"
    assert m.meta()["manual"] and not m.meta().get("update_needed")


def test_new_sheet_published_flags_update(tmp_path):
    m, d = bank(tmp_path)
    m.parse(raw(d, ("sheet-1511.pdf", "https://x/sheet-1511.pdf")), today=date(2026, 11, 15))
    assert m.meta()["update_needed"] and m.meta()["latest_document"] == "https://x/sheet-1511.pdf"


def test_bank_without_watcher_asks_for_recheck_after_14_days(tmp_path):
    m, d = bank(tmp_path, code="mb", name="MB")
    m.parse(raw(d), today=date(2026, 11, 17))
    assert not m.meta().get("update_needed")
    m.parse(raw(d), today=date(2026, 11, 18))
    assert m.meta()["update_needed"]


def test_typo_in_rate_is_rejected(tmp_path):
    m, d = bank(tmp_path, online=[{"rates": {"12": 67.0}}])
    with pytest.raises(ParseError):
        m.parse(raw(d))


class FakeSession:
    def __init__(self, html): self.html = html
    def get(self, url, timeout=None):
        return type("R", (), {"text": self.html})()


def test_pdf_watchers_read_the_file_name():
    from scraper import manual
    eib = 'x <a href="https://media.eximbank.com.vn/exim/files/TB%20LSHD%20VND%20KHBL%20hieu%20luc%20tu%20ngay%2031102026.pdf">'
    assert manual.watch_eib(FakeSession(eib)) == (
        "TB LSHD VND KHBL hieu luc tu ngay 31102026.pdf",
        "https://media.eximbank.com.vn/exim/files/TB%20LSHD%20VND%20KHBL%20hieu%20luc%20tu%20ngay%2031102026.pdf")
    ncb = '<a href="/InterestRates/2026/10/Bieu lai suat niem yet - hieu luc 19.10.2026 update.pdf">'
    name, url = manual.watch_ncb(FakeSession(ncb))
    assert name == "Bieu lai suat niem yet - hieu luc 19.10.2026 update.pdf" and url.startswith("https://www.ncb-bank.vn/InterestRates/2026/10/Bieu%20lai")
    bvb = '<a href="https://bvbank.net.vn/wp-content/uploads/2026/10/Bieu-LSNY_Web_19.10.2026.pdf">Lãi suất</a>'
    assert manual.watch_bvb(FakeSession(bvb))[0] == "Bieu-LSNY_Web_19.10.2026.pdf"


def test_blocked_watcher_falls_back_to_recheck_reminder(tmp_path):
    # BVBank's site added bot protection (11/2026): the watcher fails, so after 14 days ask for a manual check
    m, d = bank(tmp_path, code="bvb", name="BVBank")
    blocked = {**d, "_latest": None, "_watch_error": "ParseError: no rate-sheet PDF"}
    m.parse(json.dumps(blocked, ensure_ascii=False), today=date(2026, 11, 10))
    assert not m.meta().get("update_needed")                      # within 14 days of checked_at: quiet
    m.parse(json.dumps(blocked, ensure_ascii=False), today=date(2026, 11, 20))
    assert m.meta()["update_needed"] and "re-check" in m.meta()["update_reason"]
    assert "watch_error" in m.meta()
    # a working watcher with an unchanged sheet never nags, however old checked_at is
    m.parse(raw(d, ("sheet-0211.pdf", "https://x/sheet-0211.pdf")), today=date(2027, 1, 1))
    assert not m.meta().get("update_needed")


def test_mbv_watcher_reads_the_rate_post_from_the_site_menu():
    from scraper import manual
    menu = {"data": {"items": [{"page_translation": {"slug": "gioi-thieu"}},
                               {"page_translation": {"slug": "tin-tuc/bieu-lai-suat-20102026"}}]}}

    class Menu:
        def get(self, url, timeout=None):
            return type("R", (), {"json": lambda self: menu, "raise_for_status": lambda self: None})()
    assert manual.watch_mbv(Menu()) == ("tin-tuc/bieu-lai-suat-20102026",
                                       "https://www.mbv.com.vn/tin-tuc/bieu-lai-suat-20102026")


def test_mbv_hand_entered_file_is_valid():
    # MBV's site stopped answering GitHub (18/11/2026); its numbers live in data/manual/mbv.json
    from pathlib import Path
    from scraper.banks import ADAPTERS
    m = ManualBank(Path(__file__).resolve().parents[1] / "data" / "manual" / "mbv.json")
    rates, as_of = m.parse(m.fetch(None), today=date(2026, 11, 20))
    assert as_of == "2026-10-20" and len(rates) == 14
    assert {r.channel for r in rates} == {"counter", "online"}
    assert not m.meta().get("update_needed")          # re-check due 14 days after 18/11
    assert all(a.CODE != "mbv" for a in ADAPTERS)     # not scraped and hand-entered at the same time


def test_mb_hand_entered_file_is_valid():
    # MB's site blocks all automated access; numbers typed from its 21/10/2026 sheet (sections I and IV)
    from pathlib import Path
    from scraper.banks import ADAPTERS
    m = ManualBank(Path(__file__).resolve().parents[1] / "data" / "manual" / "mb.json")
    rates, as_of = m.parse(m.fetch(None), today=date(2026, 11, 24))
    assert as_of == "2026-10-21" and len(rates) == 76 and m.NAME == "MB"
    q = {(r.channel, r.term_months, r.min_amount): r.rate for r in rates}
    assert q[("counter", 12, 0)] == 5.7 and q[("online", 6, 0)] == 5.2 and q[("online", 12, 1_000_000_000)] == 5.85
    assert not m.meta().get("update_needed")
    from scraper.manual import WATCHERS
    assert "mb" not in WATCHERS                 # site blocks scripts: 14-day re-check instead
    assert m.parse(m.fetch(None), today=date(2026, 12, 9))[0] and m.meta().get("update_needed")
    assert all(a.CODE != "mb" for a in ADAPTERS)


def test_vib_hand_entered_file_is_valid():
    # VIB's site serves a bot challenge to scripts; numbers typed from www.vib.com.vn/vn/tiet-kiem (24/11/2026)
    from pathlib import Path
    from scraper.banks import ADAPTERS
    from scraper.manual import WATCHERS
    m = ManualBank(Path(__file__).resolve().parents[1] / "data" / "manual" / "vib.json")
    rates, as_of = m.parse(m.fetch(None), today=date(2026, 11, 24))
    assert as_of == "2026-10-20" and len(rates) == 96 and m.NAME == "VIB"
    q = {(r.channel, r.term_months, r.min_amount): r.rate for r in rates}
    assert q[("online", 12, 0)] == 7.0 and q[("online", 1, 300 * 10**6)] == 4.4 and q[("counter", 3, 3 * B)] == 4.45
    assert "vib" not in WATCHERS and not m.meta().get("update_needed")
    assert all(a.CODE != "vib" for a in ADAPTERS)
