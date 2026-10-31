"""Exit 1 if any bank failed its latest scrape, so the scheduled job emails you.

Runs after the site is deployed, so a broken bank never blocks the update —
it just tells you which adapter needs a look.
"""
import json
import sys
from pathlib import Path

data = json.loads((Path(__file__).resolve().parent.parent / "data" / "rates.json").read_text(encoding="utf-8"))
failed = [b for b in data["banks"] if b["status"] != "ok"]
for b in failed:
    print(f"::error title={b['name']} scraper broken::{b.get('error')}")
sys.exit(1 if failed else 0)
