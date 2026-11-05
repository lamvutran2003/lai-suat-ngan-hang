"""Daily gold series for the chart: data/gold-daily.json.

One row per day: PNJ's closing price for SJC bars and its plain 999.9 ring (đồng/lượng),
the world price (COMEX gold, USD/ounce, latest close on or before that day) and
Vietcombank's USD selling rate that day.

    python -m scraper.gold_daily --backfill 2025-11-05   # one-off: fill from that date to yesterday
    (gold.py calls update_today() on every run)

Sources: PNJ's price-history feed (keeps about a year), Yahoo Finance GC=F, Vietcombank's
exchange-rate API. All three answer with a date, so the series can be rebuilt any time.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .common import make_session

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "gold-daily.json"
VN_TZ = timezone(timedelta(hours=7))
PNJ_HISTORY = "https://edge-api.pnj.io/ecom-frontend/v1/get-gold-price-history"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF"
VCB_FX = "https://www.vietcombank.com.vn/api/exchangerates"
PNJ_TYPES = {"SJC": "sjc", "PNJ": "ring"}   # "PNJ" in the history feed = Nhẫn trơn PNJ 999.9


def num(s: str) -> int:
    """'144.300' (nghìn đồng/chỉ… shown as thousands with dots) -> đồng/lượng."""
    return int(s.replace(".", "")) * 1000


def pnj_day(session, d: date) -> dict:
    """{'sjc': [buy, sell], 'ring': [buy, sell]} at the day's last update, or {}."""
    r = session.get(PNJ_HISTORY, params={"zone": "00", "date": f"{d:%Y%m%d}"}, timeout=30)
    r.raise_for_status()
    locs = r.json().get("locations") or []
    loc = next((l for l in locs if l["name"] == "TPHCM"), locs[0] if locs else None)
    out = {}
    for g in (loc or {}).get("gold_type", []):
        key = PNJ_TYPES.get(g["name"])
        rows = [x for x in g.get("data", []) if x.get("gia_ban")]
        if key and rows:
            last = max(rows, key=lambda x: datetime.strptime(x["updated_at"], "%d/%m/%Y %H:%M:%S"))
            out[key] = [num(last["gia_mua"]), num(last["gia_ban"])]
    return out


def usd_vnd(session, d: date) -> float | None:
    r = session.get(VCB_FX, params={"date": d.isoformat()}, timeout=30)
    r.raise_for_status()
    usd = next((x for x in r.json().get("Data", []) if x["currencyCode"] == "USD"), None)
    return float(usd["sell"]) if usd else None


def world_closes(session, rng="2y") -> dict[str, float]:
    """{'YYYY-MM-DD': close} for COMEX gold (US trading days)."""
    r = session.get(YAHOO, params={"range": rng, "interval": "1d"}, timeout=30)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    out = {}
    for ts, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]):
        if c:
            out[datetime.fromtimestamp(ts, timezone(timedelta(hours=-5))).date().isoformat()] = round(c, 2)
    return out


def close_on_or_before(closes: dict, d: date):
    keys = [k for k in closes if k <= d.isoformat()]
    return closes[max(keys)] if keys else None


def load() -> list[dict]:
    return json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else []


def save(rows: list[dict]) -> None:
    rows = sorted({r["d"]: r for r in rows}.values(), key=lambda r: r["d"])
    PATH.write_text("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows) + "\n]\n",
                    encoding="utf-8")


def row(d: date, prices: dict, usd_oz, fx) -> dict:
    return {"d": d.isoformat(), **prices, "usd_oz": usd_oz, "usd_vnd": fx}


def backfill(start: date, end: date, pause=0.25) -> None:
    s = make_session()
    closes = world_closes(s)
    have = {r["d"]: r for r in load()}
    d = start
    while d <= end:
        if d.isoformat() not in have:
            try:
                prices = pnj_day(s, d)
                fx = usd_vnd(s, d)
                if prices:
                    have[d.isoformat()] = row(d, prices, close_on_or_before(closes, d), fx)
                print(d, prices.get("sjc"), prices.get("ring"), close_on_or_before(closes, d), fx)
            except Exception as e:  # noqa: BLE001
                print(d, "FAIL", e)
            time.sleep(pause)
        d += timedelta(days=1)
    save(list(have.values()))


def update_today(shops: list[dict], world: dict, session=None) -> None:
    """Today's row from the live PNJ prices; world = COMEX close if Yahoo answers, else the spot price."""
    today = datetime.now(VN_TZ).date()
    pnj = next((s for s in shops if s["code"] == "pnj" and s.get("status") == "ok"), None)
    if not pnj:
        return
    prices = {k: [i["buy"], i["sell"]] for k in ("sjc", "ring")
              for i in pnj["items"] if i["kind"] == k}
    usd_oz = None
    if session is not None:
        try:
            usd_oz = close_on_or_before(world_closes(session, "5d"), today)
        except Exception:  # noqa: BLE001 - fall back to the spot price below
            usd_oz = None
    usd_oz = usd_oz or world.get("usd_oz")
    rows = [r for r in load() if r["d"] != today.isoformat()]
    rows.append(row(today, prices, usd_oz, world.get("usd_vnd")))
    save(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=date.fromisoformat, required=True)
    a = ap.parse_args()
    backfill(a.backfill, datetime.now(VN_TZ).date() - timedelta(days=1))


if __name__ == "__main__":
    main()
