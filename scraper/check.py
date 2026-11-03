"""Fail the run (so GitHub emails you) only when a bank's or gold shop's numbers are getting old.

A single failed fetch is common: a server hiccups, or briefly blocks GitHub. Those show
as warnings in the run summary. The run fails only when a source has had no fresh data
for longer than its grace period, or has never had any.

    python -m scraper.check              # banks and gold
    python -m scraper.check --gold-only  # the hourly gold runs
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
GRACE_DAYS = 3          # bank rates change rarely
GOLD_GRACE_HOURS = 24   # gold prices change daily


def stale_check(items, now, grace, kind):
    broken = False
    for b in items:
        if b.get("status") == "ok":
            continue
        last_ok = datetime.fromisoformat(b["fetched_at"]) if b.get("fetched_at") else None
        age = (now - last_ok) if last_ok else None
        if age is None or age > grace:
            since = f"last good data {last_ok:%d/%m/%Y %H:%M}" if last_ok else "no data yet"
            print(f"::error title={b['name']} {kind} scraper broken::{since}. {b.get('error')}")
            broken = True
        else:
            print(f"::warning title={b['name']} fetch failed (showing data from {last_ok:%d/%m %H:%M})::{b.get('error')}")
    return broken


def main() -> None:
    gold_only = "--gold-only" in sys.argv
    broken = False
    if not gold_only:
        data = json.loads((DATA / "rates.json").read_text(encoding="utf-8"))
        now = datetime.fromisoformat(data["generated_at"])
        broken |= stale_check(data["banks"], now, timedelta(days=GRACE_DAYS), "bank")
        for b in data["banks"]:
            if b.get("update_needed"):
                print(f"::error title={b['name']}: rates need a manual update::{b.get('update_reason')} "
                      f"Edit data/manual/{b['code']}.json (see README: Hand-entered banks).")
                broken = True
            elif b.get("watch_error"):
                print(f"::warning title={b['name']} watcher failed::{b['watch_error']}")
    gold_path = DATA / "gold.json"
    if gold_path.exists():
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        now = datetime.fromisoformat(gold["generated_at"])
        broken |= stale_check(gold["shops"], now, timedelta(hours=GOLD_GRACE_HOURS), "gold")
        w = gold.get("world", {})
        if w.get("status") != "ok":
            print(f"::warning title=World gold price fetch failed::{w.get('error')}")
    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
