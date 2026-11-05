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
