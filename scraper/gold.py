"""Gold prices: Vietnamese shops (buy/sell per lượng) plus the world price converted to đồng.

Writes data/gold.json and data/gold-history/<date>.json (the day's latest snapshot).
Like the bank scraper, a source that fails keeps its last good prices, marked stale.

Sources (checked 11/2026 from GitHub's servers; SJC, DOJI and Bảo Tín Minh Châu block them):
  pnj   PNJ JSON feed                 nghìn đồng / chỉ
  pq    Phú Quý price board (HTML)    đồng / chỉ
  btmh  Bảo Tín Mạnh Hải homepage     đồng / chỉ
  world gold-api.com XAU (USD/oz) × Vietcombank USD selling rate

Every shop price is stored as đồng per lượng (1 lượng = 10 chỉ = 37,5 g).

Usage:
    python -m scraper.gold                  # live
    python -m scraper.gold --fixtures DIR   # saved copies (tests/fixtures/gold)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import ParseError, clean, make_session, soup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VN_TZ = timezone(timedelta(hours=7))
GRAMS_PER_LUONG = 37.5
GRAMS_PER_OZ = 31.1034768
PRICE_RANGE = (30_000_000, 600_000_000)   # đồng/lượng for 24K gold; outside = parsing error

# Categories compared across shops
KINDS = {"sjc": "Vàng miếng SJC", "ring": "Nhẫn trơn 999.9", "jewelry": "Vàng trang sức 999.9"}


def item(name, buy, sell, kind=None):
    return {"name": clean(name), "buy": int(buy) if buy else None, "sell": int(sell) if sell else None, "kind": kind}


def digits(s: str) -> int | None:
    d = re.sub(r"\D", "", s or "")
    return int(d) if d else None


def vn_time(s: str, fmt: str) -> str | None:
    try:
        return datetime.strptime(s, fmt).replace(tzinfo=VN_TZ).isoformat(timespec="minutes")
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- PNJ
class PNJ:
    CODE, NAME = "pnj", "PNJ"
    SOURCE_URL = "https://www.pnj.com.vn/site/gia-vang"
    API = "https://edge-api.pnj.io/ecom-frontend/v1/get-gold-price?zone=00"
    FIXTURE = "pnj.json"
    KIND = {"SJC": "sjc", "N24K": "ring", "24K": "jewelry"}

    @staticmethod
    def fetch(session):
        r = session.get(PNJ.API, timeout=30)
        r.raise_for_status()
        return r.text

    @staticmethod
    def parse(raw):
        d = json.loads(raw)
        items = [item(x["tensp"], x.get("giamua") and x["giamua"] * 10_000, x.get("giaban") and x["giaban"] * 10_000,
                      PNJ.KIND.get(x["masp"])) for x in d["data"] if not x["masp"].startswith("RAW")]
        return items, vn_time(d.get("updateDate"), "%d/%m/%Y %H:%M:%S")


# ---------------------------------------------------------------- Phú Quý
class PhuQuy:
    CODE, NAME = "pq", "Phú Quý"
    SOURCE_URL = "https://phuquygroup.vn/"
    FIXTURE = "pq.html"
    KIND = {"vàng miếng sjc": "sjc", "nhẫn tròn phú quý 999.9": "ring", "vàng trang sức 999.9": "jewelry"}

    @staticmethod
    def fetch(session):
        r = session.get(PhuQuy.SOURCE_URL, timeout=30)
        r.raise_for_status()
        return r.text

    @staticmethod
    def parse(raw):
        s = soup(raw)
        items = []
        for tr in s.select("tr"):
            cells = [clean(td.get_text(" ")) for td in tr.find_all("td")]
            if len(cells) < 3 or "bạc" in cells[0].lower():
                continue
            buy, sell = digits(cells[1]), digits(cells[2])
            if not sell or "phi sjc" in cells[0].lower():   # "phi SJC" rows are buy-only raw gold
                continue
            items.append(item(cells[0], buy * 10 if buy else None, sell * 10, PhuQuy.KIND.get(cells[0].lower())))
        m = re.search(r"lúc (\d{1,2}:\d{2}) (\d{2}/\d{2}/\d{4})", s.get_text(" "))
        return items, vn_time(f"{m.group(2)} {m.group(1)}", "%d/%m/%Y %H:%M") if m else None


# ---------------------------------------------------------------- Bảo Tín Mạnh Hải
class BTMH:
    CODE, NAME = "btmh", "Bảo Tín Mạnh Hải"
    SOURCE_URL = "https://baotinmanhhai.vn/"
    FIXTURE = "btmh.html"
    KIND = {"kim gia bảo 24k": "ring", "vàng trang sức 24k (999.9)": "jewelry"}
    SKIP = ("ngân", "bạc", "tiểu kim cát")   # silver, and the 0,1-chỉ product priced per piece

    @staticmethod
    def fetch(session):
        r = session.get(BTMH.SOURCE_URL, timeout=30)
        r.raise_for_status()
        return r.text

    @staticmethod
    def parse(raw):
        s = soup(raw)
        items, seen = [], set()
        for h in s.find_all("h3"):
            name = clean(h.get_text(" "))
            if not name or name.lower().startswith(BTMH.SKIP) or name in seen:
                continue
            box = h.find_parent("div")
            prices = {}
            for p in box.find_all("p"):
                label = clean(p.get_text(" ")).lower()
                span = p.find_next("span")
                if label in ("bán ra", "mua vào") and span:
                    prices.setdefault(label, digits(span.get_text()))
            if prices.get("bán ra"):
                seen.add(name)
                items.append(item(name, (prices.get("mua vào") or 0) * 10 or None, prices["bán ra"] * 10,
                                  BTMH.KIND.get(name.lower())))
        m = re.search(r"Cập nhật lúc (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", s.get_text(" "))
        return items, vn_time(m.group(1), "%Y-%m-%d %H:%M") if m else None


SHOPS = [PNJ, PhuQuy, BTMH]


# ---------------------------------------------------------------- world price
def world(session=None, fixtures: Path | None = None) -> dict:
    if fixtures:
        xau = json.loads((fixtures / "xau.json").read_text())
        fx = json.loads((fixtures / "vcbfx.json").read_text())
    else:
        xau = session.get("https://api.gold-api.com/price/XAU", timeout=30).json()
        today = datetime.now(VN_TZ).date().isoformat()
        fx = session.get(f"https://www.vietcombank.com.vn/api/exchangerates?date={today}", timeout=30).json()
    usd_oz = float(xau["price"])
    usd = next(x for x in fx["Data"] if x["currencyCode"] == "USD")
    usd_vnd = float(usd["sell"])
    if not (500 < usd_oz < 20_000) or not (15_000 < usd_vnd < 60_000):
        raise ParseError(f"world price looks wrong: {usd_oz} USD/oz, {usd_vnd} VND/USD")
    return {"usd_oz": round(usd_oz, 2), "usd_vnd": usd_vnd,
            "vnd_luong": round(usd_oz * GRAMS_PER_LUONG / GRAMS_PER_OZ * usd_vnd),
            "updated": xau.get("updatedAt"), "fx_updated": fx.get("UpdatedDate"),
            "source": "gold-api.com, tỷ giá USD bán ra Vietcombank"}


def validate(code, items):
    kinds = {i["kind"] for i in items if i["kind"]}
    if not kinds:
        raise ParseError("none of the compared products (SJC, nhẫn 999.9, trang sức 999.9) found")
    for i in items:
        for v in (i["buy"], i["sell"]):
            if v is not None and i["kind"] and not (PRICE_RANGE[0] <= v <= PRICE_RANGE[1]):
                raise ParseError(f"{i['name']}: {v} đồng/lượng looks wrong")
        if i["buy"] and i["sell"] and i["buy"] > i["sell"]:
            raise ParseError(f"{i['name']}: buy {i['buy']} above sell {i['sell']}")


# ---------------------------------------------------------------- run
def run(fixtures: Path | None = None) -> dict:
    now = datetime.now(VN_TZ)
    path = DATA / "gold.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"shops": []}
    prev = {s["code"]: s for s in previous.get("shops", [])}
    session = None if fixtures else make_session()

    shops = []
    for mod in SHOPS:
        entry = {"code": mod.CODE, "name": mod.NAME, "source_url": mod.SOURCE_URL}
        try:
            raw = (fixtures / mod.FIXTURE).read_text(encoding="utf-8") if fixtures else mod.fetch(session)
            items, updated = mod.parse(raw)
            validate(mod.CODE, items)
            entry.update(status="ok", stale=False, updated=updated, fetched_at=now.isoformat(timespec="minutes"), items=items)
            print(f"  ok    {mod.NAME:<17} {len(items):>2} products  (updated {updated or 'n/a'})")
        except Exception as e:  # noqa: BLE001
            old = prev.get(mod.CODE, {})
            entry.update(status="error", error=f"{type(e).__name__}: {e}"[:300], stale=bool(old.get("items")),
                         updated=old.get("updated"), fetched_at=old.get("fetched_at"), items=old.get("items", []))
            print(f"  FAIL  {mod.NAME:<17} {entry['error']}  -> kept old prices", file=sys.stderr)
        shops.append(entry)

    try:
        w = world(session, fixtures)
        w.update(status="ok", stale=False)
        print(f"  ok    world             {w['usd_oz']} USD/oz × {w['usd_vnd']:,.0f} = {w['vnd_luong']:,} đ/lượng")
    except Exception as e:  # noqa: BLE001
        w = {**previous.get("world", {}), "status": "error", "stale": True, "error": f"{type(e).__name__}: {e}"[:300]}
        print(f"  FAIL  world             {w['error']}", file=sys.stderr)

    out = {"generated_at": now.isoformat(timespec="minutes"), "shops": shops, "world": w}
    if not fixtures:
        from .gold_daily import update_today
        try:
            update_today(shops, w, session)
        except Exception as e:  # noqa: BLE001 - the chart can miss a point; the prices must still publish
            print(f"  WARN  daily series not updated: {e}", file=sys.stderr)
    DATA.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    hist = DATA / "gold-history"
    hist.mkdir(exist_ok=True)
    fresh = {**out, "shops": [s for s in shops if s["status"] == "ok"]}
    (hist / f"{now.date().isoformat()}.json").write_text(json.dumps(fresh, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", type=Path)
    out = run(ap.parse_args().fixtures)
    ok = sum(s["status"] == "ok" for s in out["shops"])
    print(f"{ok}/{len(out['shops'])} gold shops updated")
    if ok == 0 and out["world"].get("status") != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
