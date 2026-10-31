"""Vietcombank — JSON API behind the public rate page."""
import json

from ..common import Rate, parse_term_months

CODE = "vcb"
NAME = "Vietcombank"
SOURCE_URL = "https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/KHCN---Lai-suat"
API_URL = "https://www.vietcombank.com.vn/vi-VN/api/interestrates?accountType=Personal"

# tenorType -> our channel. "FixedDeposit" duplicates "Savings" at VCB, so it is skipped.
CHANNELS = {"Savings": "counter", "Online": "online"}


def fetch(session) -> str:
    r = session.get(API_URL, headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.text


def parse(raw: str):
    d = json.loads(raw)
    rates = []
    for x in d["Data"]:
        channel = CHANNELS.get(x.get("tenorType"))
        if channel is None or x.get("currencyCode") != "VND":
            continue
        months = parse_term_months(x.get("tenor", ""))
        if months is None or x.get("rates") is None:
            continue
        rates.append(Rate(CODE, channel, months, round(float(x["rates"]) * 100, 2)))
    as_of = (d.get("UpdatedDate") or "")[:10] or None
    return rates, as_of
