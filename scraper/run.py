"""Fetch every bank, validate, and write data/rates.json + data/history/<date>.json.

Usage:
    python -m scraper.run                 # live fetch
    python -m scraper.run --fixtures DIR  # parse saved pages instead (offline / tests)

If a bank fails (site down, layout changed, numbers look wrong), its last good
data from the previous rates.json is kept and flagged "stale", so the site never
shows an empty row. `python -m scraper.check` exits non-zero when that happens,
which makes GitHub Actions email you.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .banks import ADAPTERS
from .manual import manual_banks
from .common import ParseError, make_session

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VN_TZ = timezone(timedelta(hours=7))

MIN_RECORDS = 4          # fewer than this = the parser probably broke
RATE_RANGE = (0.1, 15.0)  # % per year; anything outside is a parsing error
FIXTURE_NAMES = {"vcb": "vcb.json", "bidv": "bidv.json", "vietin": "vietin.html",
                 "agri": "agri.html", "acb": "acb.html", "tpb": "tpb.html",
                 "stb": "stb.pdf", "ocb": "ocb.pdf", "tcb": "tcb.pdf",
                 "lpb": "lpb.json", "mbv": "mbv.html", "bab": "bab.html", "nab": "nab.json", "vikki": "vikki.json"}


def read_fixture(folder: Path, code: str):
    path = folder / FIXTURE_NAMES[code]
    return path.read_bytes() if path.suffix == ".pdf" else path.read_text(encoding="utf-8")


def validate(code: str, rates) -> None:
    if len(rates) < MIN_RECORDS:
        raise ParseError(f"only {len(rates)} rates parsed (expected >= {MIN_RECORDS})")
    bad = [r for r in rates if not (RATE_RANGE[0] <= r.rate <= RATE_RANGE[1])]
    if bad:
        raise ParseError(f"rate out of range: {bad[0].term_months}m = {bad[0].rate}%")
    if not any(r.term_months == 12 for r in rates):
        raise ParseError("no 12-month rate found")


def load_previous() -> dict:
    path = DATA / "rates.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"banks": [], "rates": []}


def run(fixtures: Path | None = None) -> dict:
    now = datetime.now(VN_TZ)
    previous = load_previous()
    prev_banks = {b["code"]: b for b in previous.get("banks", [])}
    session = None if fixtures else make_session()

    banks, rates = [], []
    for mod in list(ADAPTERS) + manual_banks():
        entry = {"code": mod.CODE, "name": mod.NAME, "source_url": mod.SOURCE_URL}
        try:
            manual = hasattr(mod, "meta")
            raw = (mod.fetch(session) if manual else
                   read_fixture(fixtures, mod.CODE) if fixtures else mod.fetch(session))
            parsed, as_of = mod.parse(raw)
            validate(mod.CODE, parsed)
            entry.update(status="ok", stale=False, as_of=as_of,
                         fetched_at=now.isoformat(timespec="minutes"), count=len(parsed))
            if manual:
                entry.update(mod.meta())
            rates.extend(r.to_dict() for r in parsed)
            flag = "  [manual" + (", NEEDS UPDATE]" if entry.get("update_needed") else "]") if manual else ""
            print(f"  ok    {mod.NAME:<12} {len(parsed):>3} rates  (as of {as_of or 'n/a'}){flag}")
        except Exception as e:  # noqa: BLE001 - one bank must never take down the rest
            old = [r for r in previous.get("rates", []) if r["bank"] == mod.CODE]
            prev = prev_banks.get(mod.CODE, {})
            entry.update(status="error", error=f"{type(e).__name__}: {e}"[:300], stale=bool(old),
                         as_of=prev.get("as_of"), fetched_at=prev.get("fetched_at"), count=len(old))
            rates.extend(old)
            print(f"  FAIL  {mod.NAME:<12} {entry['error']}  -> kept {len(old)} old rates", file=sys.stderr)
        banks.append(entry)

    out = {"generated_at": now.isoformat(timespec="minutes"), "banks": banks, "rates": rates}
    DATA.mkdir(exist_ok=True)
    (DATA / "rates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    hist = DATA / "history"
    hist.mkdir(exist_ok=True)
    fresh = [r for r in rates if any(b["code"] == r["bank"] and b["status"] == "ok" for b in banks)]
    (hist / f"{now.date().isoformat()}.json").write_text(
        json.dumps({"date": now.date().isoformat(), "rates": fresh}, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", type=Path, help="parse saved pages from this folder instead of fetching")
    args = ap.parse_args()
    out = run(args.fixtures)
    ok = sum(b["status"] == "ok" for b in out["banks"])
    print(f"{ok}/{len(out['banks'])} banks updated, {len(out['rates'])} rates written")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
