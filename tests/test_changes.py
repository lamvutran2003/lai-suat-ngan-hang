"""The ▲/▼ arrows: a quote's last change within the window, ignoring days it wasn't scraped."""
import json
from datetime import date

from scraper.build_site import compute_changes


def write(tmp, day, rate, bank="stb"):
    (tmp / f"{day}.json").write_text(json.dumps({"date": day, "rates": [
        {"bank": bank, "channel": "online", "term_months": 12, "min_amount": 0, "rate": rate}]}))


CUR = [{"bank": "stb", "channel": "online", "term_months": 12, "min_amount": 0, "rate": 6.8}]
KEY = "stb|online|12|0"


def test_recent_increase(tmp_path):
    write(tmp_path, "2026-10-20", 6.5); write(tmp_path, "2026-10-28", 6.8); write(tmp_path, "2026-11-03", 6.8)
    assert compute_changes(CUR, tmp_path, date(2026, 11, 3)) == {KEY: {"prev": 6.5, "since": "2026-10-28"}}


def test_old_change_hidden(tmp_path):
    write(tmp_path, "2026-08-01", 6.5); write(tmp_path, "2026-09-01", 6.8); write(tmp_path, "2026-11-03", 6.8)
    assert compute_changes(CUR, tmp_path, date(2026, 11, 3)) == {}


def test_missing_days_are_not_changes(tmp_path):
    write(tmp_path, "2026-10-30", 6.8); write(tmp_path, "2026-11-01", 9.9, bank="vcb"); write(tmp_path, "2026-11-03", 6.8)
    assert compute_changes(CUR, tmp_path, date(2026, 11, 3)) == {}
