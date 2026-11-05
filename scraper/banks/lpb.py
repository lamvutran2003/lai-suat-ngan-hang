"""LPBank — the rate page fills its tables from a JSON API, one POST per product category.

  TK_TTQ_KHCN  tiết kiệm tại quầy, khách hàng cá nhân (counter)
  TK_ONLINE    tiết kiệm online
Each DATA row has term ("12 tháng"), startValue (lãi trả trước), monthValue, quarterValue and
endValue (lãi cuối kỳ); groupInterest picks the currency (LSHD_VND). We use endValue.
(Found in the page's own code: getLaiSuat({category: ...}). The site answers GitHub's servers.)
"""
import json
from datetime import datetime, timedelta, timezone

from ..common import ParseError, Rate, parse_term_months

CODE = "lpb"
NAME = "LPBank"
SOURCE_URL = "https://lpbank.com.vn/ca-nhan/lai-suat"
API = "https://lpbank.com.vn/api/content-service/public/interest-rate/findAll"
CATEGORIES = {"counter": "TK_TTQ_KHCN", "online": "TK_ONLINE"}
VN = timezone(timedelta(hours=7))


def fetch(session) -> str:
    out = {}
    for cat in CATEGORIES.values():
        r = session.post(API, json={"category": cat}, timeout=30,
                         headers={"Referer": SOURCE_URL, "Origin": "https://lpbank.com.vn"})
        r.raise_for_status()
        out[cat] = r.json()
    return json.dumps(out, ensure_ascii=False)


def parse(raw: str):
    data = json.loads(raw)
    rates, dates = [], []
    for ch, cat in CATEGORIES.items():
        rows = [x for x in (data.get(cat) or {}).get("data") or [] if x.get("recordType") == "DATA"]
        vnd = [x for x in rows if x.get("groupInterest") == "LSHD_VND"]
        if not vnd:
            raise ParseError(f"LPBank: no VND rows in {cat}")
        for x in vnd:
            months = parse_term_months(x.get("term") or "")
            value = x.get("endValue")
            if months and value:
                rates.append(Rate(CODE, ch, months, float(value)))
            if x.get("effectiveDate"):
                dates.append(datetime.fromisoformat(x["effectiveDate"].replace("Z", "+00:00")).astimezone(VN).date().isoformat())
    return rates, max(dates) if dates else None
