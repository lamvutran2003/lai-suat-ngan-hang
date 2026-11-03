"""Render site/template.html with today's data into dist/.

dist/index.html   full page to deploy (SEO meta + pre-rendered rate table)
dist/rates.json   the raw data, for anyone (or a future app) to reuse
dist/robots.txt, dist/sitemap.xml
preview.html      body-only copy used for the claude.ai preview

Set SITE_URL (e.g. https://tietkiemdau.vn) so canonical links, sharing and the sitemap are right.
"""
from __future__ import annotations

import html
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "site" / "template.html"
DIST = ROOT / "dist"
HISTORY = ROOT / "data" / "history"
SITE_URL = os.environ.get("SITE_URL", "https://tietkiemdau.vn").rstrip("/")

TABLE_TERMS = [1, 3, 6, 12, 24]          # columns of the comparison table
DEFAULT_CHANNEL = "online"
DEFAULT_AMOUNT = 100_000_000
CHANGE_WINDOW_DAYS = 30                  # arrows show changes made within this window
CH = {"online": "Online", "counter": "Tại quầy"}
TICKER = {"vcb": "VCB", "bidv": "BID", "vietin": "CTG", "agri": "AGR", "acb": "ACB",
          "tpb": "TPB", "stb": "STB", "ocb": "OCB"}


# ---------------------------------------------------------------- rate lookup
def rate_for(rates, bank, ch, term, amount):
    cands = [r for r in rates if r["bank"] == bank and r["channel"] == ch and r["term_months"] == term
             and r["min_amount"] <= amount and (r["max_amount"] is None or amount < r["max_amount"])]
    return max(cands, key=lambda r: r["rate"]) if cands else None


def key_of(r) -> str:
    return f"{r['bank']}|{r['channel']}|{r['term_months']}|{r['min_amount']}"


def fmt(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


# ---------------------------------------------------------------- rate changes
def compute_changes(current_rates, history_dir: Path, today: date) -> dict:
    """For each current quote, find when it last changed and from what.

    Returns {key: {"prev": old_rate, "since": "YYYY-MM-DD"}} for quotes whose value
    changed within CHANGE_WINDOW_DAYS. Days where a bank wasn't scraped are skipped,
    so a missing day never looks like a change.
    """
    days = []
    for f in sorted(history_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            days.append((d["date"], {key_of(r): r["rate"] for r in d["rates"]}))
        except (ValueError, KeyError):
            continue
    days.sort()
    out = {}
    for r in current_rates:
        k, now = key_of(r), r["rate"]
        since = None
        for day, quotes in reversed(days):
            if k not in quotes:
                continue
            if quotes[k] == now:
                since = day
                continue
            if since and date.fromisoformat(since) >= today - timedelta(days=CHANGE_WINDOW_DAYS):
                out[k] = {"prev": quotes[k], "since": since}
            break
    return out


# ---------------------------------------------------------------- static table
def table_rows(data, ch, amount):
    """Rows for one channel, sorted by 12-month rate (best first). Same logic as the page's JS."""
    rows = []
    for b in data["banks"]:
        cells = {t: rate_for(data["rates"], b["code"], ch, t, amount) for t in TABLE_TERMS}
        if any(cells.values()):
            rows.append((b, cells))
    rows.sort(key=lambda bc: -(bc[1][12]["rate"] if bc[1].get(12) else 0))
    return rows


def static_table(data, changes, ch=DEFAULT_CHANNEL, amount=DEFAULT_AMOUNT) -> str:
    """Server-rendered copy of the table so search engines see the rates without JavaScript."""
    rows = table_rows(data, ch, amount)
    best = {}
    for t in TABLE_TERMS:  # flag the best only when at most two banks share it (same rule as the page JS)
        top = max((c[t]["rate"] for _, c in rows if c[t]), default=None)
        best[t] = top if sum(1 for _, c in rows if c[t] and c[t]["rate"] == top) <= 2 else None
    head = "".join(f'<th scope="col">{t} tháng</th>' for t in TABLE_TERMS)
    body = []
    for b, cells in rows:
        tds = []
        for t in TABLE_TERMS:
            r = cells[t]
            if not r:
                tds.append('<td class="na">–</td>')
                continue
            cls = " best" if r["rate"] == best[t] else ""
            chg = changes.get(key_of(r))
            arrow = ""
            if chg:
                d = r["rate"] - chg["prev"]
                arrow = (f'<span class="chg {"up" if d > 0 else "down"}" title="Từ {fmt(chg["prev"])}%">'
                         f'{"▲" if d > 0 else "▼"}{fmt(abs(d))}</span>')
            flag = '<span class="flag">Cao nhất</span>' if cls else ""
            tds.append(f'<td class="r{cls}"><span class="v">{fmt(r["rate"])}</span>{arrow}{flag}</td>')
        body.append(f'<tr><th scope="row"><span class="tick">{TICKER.get(b["code"], b["code"].upper())}</span>'
                    f'<span class="bn">{html.escape(b["name"])}</span></th>{"".join(tds)}</tr>')
    return (f'<table class="rates"><thead><tr><th scope="col">Ngân hàng</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def best_sentence(data, term=12) -> str:
    best = None
    for b in data["banks"]:
        for ch in CH:
            r = rate_for(data["rates"], b["code"], ch, term, DEFAULT_AMOUNT)
            if r and (best is None or r["rate"] > best[0]):
                best = (r["rate"], b["name"], ch)
    return f"Kỳ hạn {term} tháng cao nhất: {best[1]} {fmt(best[0])}%/năm ({CH[best[2]].lower()})." if best else ""


# ---------------------------------------------------------------- build
def build() -> None:
    data = json.loads((ROOT / "data" / "rates.json").read_text(encoding="utf-8"))
    aff_path = ROOT / "data" / "affiliates.json"
    affiliates = json.loads(aff_path.read_text(encoding="utf-8")) if aff_path.exists() else {}
    generated = datetime.fromisoformat(data["generated_at"])
    data["changes"] = compute_changes(data["rates"], HISTORY, generated.date())
    data["site_url"] = SITE_URL + "/"

    head, body = TEMPLATE.read_text(encoding="utf-8").split("<!--BODY-->")
    safe_json = lambda obj: json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    body = (body.replace("__RATES_JSON__", safe_json(data))
                .replace("__AFFILIATES_JSON__", safe_json(affiliates))
                .replace("__STATIC_TABLE__", static_table(data, data["changes"]))
                .replace("__UPDATED_TIME__", generated.strftime("%H:%M"))
                .replace("__UPDATED_DATE__", generated.strftime("%d/%m/%Y"))
                .replace("__BANK_COUNT__", str(len(data["banks"])))
                .replace("__SITE_URL__", html.escape(SITE_URL + "/")))

    updated_vn = generated.strftime("%d/%m/%Y")
    desc = (f"So sánh lãi suất tiết kiệm {len(data['banks'])} ngân hàng, cập nhật {updated_vn}. "
            f"{best_sentence(data)} Tính tiền lãi theo số tiền và kỳ hạn.")
    seo = (f'<meta name="description" content="{html.escape(desc)}">\n'
           f'<link rel="canonical" href="{SITE_URL}/">\n'
           f'<meta property="og:title" content="Lãi suất tiết kiệm hôm nay {updated_vn} | Tiết Kiệm Đâu?">\n'
           f'<meta property="og:description" content="{html.escape(desc)}">\n'
           f'<meta property="og:url" content="{SITE_URL}/">\n'
           f'<meta property="og:type" content="website">\n'
           f'<meta property="og:locale" content="vi_VN">\n')
    page = ('<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + seo + head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
            + '</head>\n<body>\n' + body + '\n</body>\n</html>\n')

    DIST.mkdir(exist_ok=True)
    (DIST / "index.html").write_text(page, encoding="utf-8")
    (DIST / "rates.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{SITE_URL}/</loc><lastmod>{generated.date().isoformat()}</lastmod>"
        "<changefreq>daily</changefreq></url></urlset>\n", encoding="utf-8")
    (ROOT / "preview.html").write_text(head + body, encoding="utf-8")
    print(f"built dist/index.html ({len(page)//1024} KB), {len(data['changes'])} recent changes — {desc}")


if __name__ == "__main__":
    build()
