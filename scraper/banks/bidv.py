"""BIDV — two JSON servlets (POST): counter rates and online rates.

Online is much higher than counter at BIDV (e.g. 12 months: 6.8% vs 5.4% on
25/10/2026), which is exactly the kind of gap the site should surface.
"""
import json
from datetime import datetime

from ..common import Rate, parse_rate, parse_term_months

CODE = "bidv"
NAME = "BIDV"
SOURCE_URL = "https://bidv.com.vn/vn/tra-cuu-lai-suat"
ENDPOINTS = {
    "counter": "https://bidv.com.vn/ServicesBIDV/InterestDetailServlet",
    "online": "https://bidv.com.vn/ServicesLaiSuatOnline/InterestDetailOnlineServlet",
}


def fetch(session) -> str:
    """Returns {"counter": <raw json>, "online": <raw json>} as one string."""
    out = {}
    for channel, url in ENDPOINTS.items():
        r = session.post(url, data={"language": "vn"}, timeout=30)
        r.raise_for_status()
        out[channel] = r.text
    return json.dumps(out, ensure_ascii=False)


def _parse_one(raw: str, channel: str):
    d = json.loads(raw)
    region = d.get("hanoi") or d.get("hcm")  # identical in practice; Hà Nội first
    rates = []
    for row in region["data"]:
        months = parse_term_months(row.get("title_en", "")) or parse_term_months(row.get("title_vi", ""))
        value = parse_rate(row.get("VND", ""))
        if months is None or value is None:
            continue
        rates.append(Rate(CODE, channel, months, value))
    as_of = None
    if region.get("day_vi"):
        as_of = datetime.strptime(region["day_vi"], "%d/%m/%Y").date().isoformat()
    return rates, as_of


def parse(raw: str):
    combined = json.loads(raw)
    rates, dates = [], []
    for channel in ("counter", "online"):
        if channel in combined:
            r, as_of = _parse_one(combined[channel], channel)
            rates += r
            dates.append(as_of)
    dates = [d for d in dates if d]
    return rates, (max(dates) if dates else None)
