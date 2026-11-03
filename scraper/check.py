"""Fail the run (so GitHub emails you) only when a bank's numbers are getting old.

A single failed fetch is common: a bank's server hiccups, or briefly blocks
GitHub. Those show as warnings in the run summary. The run fails only when a
bank has had no fresh data for more than GRACE_DAYS, or has never had any.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

GRACE_DAYS = 3

data = json.loads((Path(__file__).resolve().parent.parent / "data" / "rates.json").read_text(encoding="utf-8"))
now = datetime.fromisoformat(data["generated_at"])
broken = False
for b in data["banks"]:
    if b["status"] == "ok":
        continue
    last_ok = datetime.fromisoformat(b["fetched_at"]) if b.get("fetched_at") else None
    age = (now - last_ok) if last_ok else None
    if age is None or age > timedelta(days=GRACE_DAYS):
        since = f"last good data {last_ok:%d/%m/%Y}" if last_ok else "no data yet"
        print(f"::error title={b['name']} scraper broken::{since}. {b.get('error')}")
        broken = True
    else:
        print(f"::warning title={b['name']} fetch failed (showing data from {last_ok:%d/%m %H:%M})::{b.get('error')}")
sys.exit(1 if broken else 0)
