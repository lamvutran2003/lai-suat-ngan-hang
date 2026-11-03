"""Hand-entered banks: rates typed from the bank's own rate sheet into data/manual/<code>.json.

For banks whose sheet can't be read automatically (a scanned PDF, an image, or a
site that blocks scripts). Each run:
  1. loads and validates the file,
  2. asks the bank's "watcher" (if it has one) for the newest rate sheet; if it
     differs from the sheet the numbers were typed from, the bank is flagged
     update_needed and the run fails, so GitHub emails you the link,
  3. for banks without a watcher, flags the bank after REVIEW_DAYS so you check it.

File format (amount bands are optional; leave "amount" out for "every amount"):
{
  "name": "VPBank",
  "source_url": "https://...",            page where the bank lists its rate sheets
  "document_url": "https://...pdf",       the sheet these numbers were typed from
  "watch": "2.-20261102-Phu-luc-BLS-niem-yet.pdf",   what the watcher compares against
  "as_of": "2026-11-02",                  effective date printed on the sheet
  "checked_at": "2026-11-03",             the day you checked/typed the numbers
  "product": "Tiết kiệm thường, lĩnh lãi cuối kỳ",
  "counter": [{"amount": "Dưới 10 tỷ", "rates": {"1": 4.45, "12": 6.40}}, ...],
  "online":  [{"amount": "Từ 10 tỷ",  "rates": {"1": 4.65, "12": 7.10}}, ...]
}
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from .common import ParseError, Rate, parse_amount_range

ROOT = Path(__file__).resolve().parent.parent
MANUAL_DIR = ROOT / "data" / "manual"
REVIEW_DAYS = 14          # banks without a watcher: ask for a re-check after this many days
RATE_RANGE = (0.1, 15.0)


# ---------------------------------------------------------------- watchers
def watch_vpb(session) -> tuple[str, str]:
    """VPBank: newest personal deposit-rate document -> (fingerprint, document URL)."""
    base = "https://www.vpbank.com.vn"
    cat = "/tai-lieu-bieu-mau/lai-suat-huy-dong/khach-hang-ca-nhan"
    years = session.get(f"{base}/uiux-api/api/category/children", params={"path": cat, "lang": "vi"}, timeout=30).json()
    newest_year = max(years, key=lambda y: y.get("orderIndex", 0))["path"]
    docs = session.get(f"{base}/uiux-api/api/document", timeout=30, params={
        "categoryPath": newest_year, "pageIndex": 1, "pageSize": 1, "sort": "publishTime,DESC", "lang": "vi"}).json()["data"]
    if not docs or not docs[0].get("itemList"):
        raise ParseError("VPBank document list is empty")
    url = docs[0]["itemList"][0]["url"]
    return url.rsplit("/", 1)[-1], base + url


WATCHERS = {"vpb": watch_vpb}


# ---------------------------------------------------------------- loading
def _bands(code, channel, blocks):
    rates = []
    for block in blocks or []:
        label = block.get("amount")
        lo, hi = parse_amount_range(label) if label else (0, None)
        for term, value in block["rates"].items():
            months, rate = int(term), float(value)
            if not (1 <= months <= 60) or not (RATE_RANGE[0] <= rate <= RATE_RANGE[1]):
                raise ParseError(f"{code} {channel} {label or ''} {term}: {value} looks wrong")
            rates.append(Rate(code, channel, months, rate, min_amount=lo, max_amount=hi))
    return rates


class ManualBank:
    """Looks like a scraper adapter to run.py: CODE, NAME, SOURCE_URL, fetch(), parse(), meta()."""

    def __init__(self, path: Path):
        self.path = path
        self.CODE = path.stem
        d = json.loads(path.read_text(encoding="utf-8"))
        self.NAME = d["name"]
        self.SOURCE_URL = d.get("source_url") or d.get("document_url")
        self._meta = {}

    def fetch(self, session) -> str:
        d = json.loads(self.path.read_text(encoding="utf-8"))
        latest = None
        watcher = WATCHERS.get(self.CODE)
        if watcher and session is not None:
            try:
                latest = watcher(session)
            except Exception as e:  # noqa: BLE001 - a broken watcher shouldn't hide typed rates
                d["_watch_error"] = f"{type(e).__name__}: {e}"[:200]
        d["_latest"] = latest
        return json.dumps(d, ensure_ascii=False)

    def parse(self, raw: str, today: date | None = None):
        d = json.loads(raw)
        today = today or date.today()
        rates = _bands(self.CODE, "counter", d.get("counter")) + _bands(self.CODE, "online", d.get("online"))
        checked = date.fromisoformat(d["checked_at"])
        meta = {"manual": True, "checked_at": d["checked_at"], "document_url": d.get("document_url"),
                "product": d.get("product")}
        latest = d.get("_latest")
        if latest and latest[0] != d.get("watch"):
            meta.update(update_needed=True, latest_document=latest[1],
                        update_reason=f"{self.NAME} published a new rate sheet: {latest[1]}")
        elif self.CODE not in WATCHERS and (today - checked).days > REVIEW_DAYS:
            meta.update(update_needed=True, latest_document=d.get("source_url"),
                        update_reason=f"{self.NAME} was last checked {checked:%d/%m/%Y}; please re-check its rate sheet")
        if d.get("_watch_error"):
            meta["watch_error"] = d["_watch_error"]
        self._meta = meta
        return rates, d.get("as_of")

    def meta(self) -> dict:
        return self._meta


def manual_banks() -> list[ManualBank]:
    if not MANUAL_DIR.exists():
        return []
    return [ManualBank(p) for p in sorted(MANUAL_DIR.glob("*.json")) if re.fullmatch(r"[a-z]+", p.stem)]
