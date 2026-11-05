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
DIST = ROOT / "dist"
HISTORY = ROOT / "data" / "history"
SITE_URL = (os.environ.get("SITE_URL") or "https://tietkiemdau.vn").rstrip("/")

TABLE_TERMS = [1, 3, 6, 9, 12, 18, 24, 36]  # columns of the comparison table
DEFAULT_CHANNEL = "online"
DEFAULT_AMOUNT = 100_000_000
CHANGE_WINDOW_DAYS = 30                  # arrows show changes made within this window
CH = {"online": "Online", "counter": "Tại quầy"}
SLUG = {"vcb": "vietcombank", "bidv": "bidv", "vietin": "vietinbank", "agri": "agribank",
        "acb": "acb", "tpb": "tpbank", "stb": "sacombank", "ocb": "ocb", "tcb": "techcombank",
        "vpb": "vpbank", "mb": "mbbank", "lpb": "lpbank", "mbv": "mbv", "bab": "bac-a-bank", "nab": "nam-a-bank",
        "vikki": "vikki-bank", "cake": "cake", "hdb": "hdbank", "abb": "abbank", "vbb": "vietbank", "eib": "eximbank",
        "bvb": "bvbank", "ncb": "ncb"}
TICKER = {"vcb": "VCB", "bidv": "BID", "vietin": "CTG", "agri": "AGR", "acb": "ACB",
          "tpb": "TPB", "stb": "STB", "ocb": "OCB", "tcb": "TCB", "vpb": "VPB", "mb": "MBB", "lpb": "LPB",
          "mbv": "MBV", "bab": "BAB", "nab": "NAB", "vikki": "VKB", "cake": "CAKE", "hdb": "HDB", "abb": "ABB",
          "vbb": "VBB", "eib": "EIB", "bvb": "BVB", "ncb": "NVB"}


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
def logo_img(code: str, size: int = 22) -> str:
    return (f'<img class="bl" src="/logos/{code}.png" alt="" width="{size}" height="{size}" loading="lazy" '
            "onerror=\"this.style.visibility='hidden'\">")


def table_rows(data, ch, amount):
    """Rows for one channel, sorted by 12-month rate (best first). Same logic as the page's JS."""
    rows = []
    for b in data["banks"]:
        cells = {t: rate_for(data["rates"], b["code"], ch, t, amount) for t in TABLE_TERMS}
        if any(cells.values()):
            rows.append((b, cells))
    rows.sort(key=lambda bc: (bc[1][12] is None, -(bc[1][12]["rate"] if bc[1].get(12) else 0), bc[0]["name"]))
    return rows


def static_table(data, changes, ch=DEFAULT_CHANNEL, amount=DEFAULT_AMOUNT) -> str:
    """Server-rendered copy of the table so search engines see the rates without JavaScript."""
    rows = table_rows(data, ch, amount)
    best = {}
    for t in TABLE_TERMS:  # flag the best only when at most two banks share it (same rule as the page JS)
        top = max((c[t]["rate"] for _, c in rows if c[t]), default=None)
        best[t] = top if sum(1 for _, c in rows if c[t] and c[t]["rate"] == top) <= 2 else None
    head = "".join(
        (f'<th scope="col" aria-sort="descending" class="sorted">' if t == 12 else '<th scope="col">')
        + f'<button class="sort" type="button" data-t="{t}" aria-label="Sắp xếp theo kỳ hạn {t} tháng">{t} tháng'
        + f'<span class="ar" aria-hidden="true">{"↓" if t == 12 else "↕"}</span></button></th>'
        for t in TABLE_TERMS)
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
            tds.append(f'<td class="r{cls}"><span class="v">{fmt(r["rate"])}</span>{arrow}</td>')
        body.append(f'<tr><th scope="row">{logo_img(b["code"])}'
                    f'<a class="bn" href="/ngan-hang/{SLUG[b["code"]]}/">{html.escape(b["name"])}</a></th>{"".join(tds)}</tr>')
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
SITE = ROOT / "site"
FONT_LINK = ""  # system fonts (SF Pro / Segoe UI / Roboto): fast, no third-party request
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL") or "lienhe@tietkiemdau.vn"
CF_BEACON_TOKEN = os.environ.get("CF_BEACON_TOKEN", "").strip()   # Cloudflare Web Analytics, optional


def read(rel: str) -> str:
    return (SITE / rel).read_text(encoding="utf-8")


def front_matter(src: str) -> tuple[dict, str]:
    """Pages start with an HTML comment of 'key: value' lines (title, description)."""
    meta = {}
    if src.startswith("<!--"):
        end = src.index("-->")
        for line in src[4:end].strip().splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
        src = src[end + 3:].lstrip("\n")
    return meta, src


def analytics_blocks(src: str) -> str:
    """Keep <!--IF_ANALYTICS--> ... <!--/IF_ANALYTICS--> only when analytics is switched on."""
    import re
    if CF_BEACON_TOKEN:
        return src.replace("<!--IF_ANALYTICS-->\n", "").replace("<!--/IF_ANALYTICS-->\n", "")
    return re.sub(r"<!--IF_ANALYTICS-->.*?<!--/IF_ANALYTICS-->\n", "", src, flags=re.S)


def head_tags(title: str, desc: str, url: str) -> str:
    e = html.escape
    tags = (f"<title>{e(title)}</title>\n"
            f'<meta name="description" content="{e(desc)}">\n'
            f'<link rel="canonical" href="{url}">\n'
            '<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
            '<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">\n'
            '<link rel="icon" href="/favicon-48.png" sizes="48x48" type="image/png">\n'
            '<link rel="icon" href="/favicon-96.png" sizes="96x96" type="image/png">\n'
            '<link rel="icon" href="/favicon-192.png" sizes="192x192" type="image/png">\n'
            '<link rel="apple-touch-icon" href="/apple-touch-icon.png">\n'
            '<meta name="theme-color" content="#0f4c81">\n'
            f'<meta property="og:title" content="{e(title)}">\n'
            f'<meta property="og:description" content="{e(desc)}">\n'
            f'<meta property="og:url" content="{url}">\n'
            f'<meta property="og:image" content="{SITE_URL}/og.png">\n'
            '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
            '<meta property="og:type" content="website">\n<meta property="og:locale" content="vi_VN">\n'
            '<meta property="og:site_name" content="Tiết Kiệm Đâu?">\n'
            '<meta name="twitter:card" content="summary_large_image">\n')
    if CF_BEACON_TOKEN:
        tags += ('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                 f"data-cf-beacon='{{\"token\": \"{e(CF_BEACON_TOKEN)}\"}}'></script>\n")
    return tags


def fill(src: str, values: dict) -> str:
    for k, v in values.items():
        src = src.replace(k, v)
    return src


def full_page(title, desc, url, body, css) -> str:
    return ('<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + head_tags(title, desc, url) + FONT_LINK + f"<style>\n{css}</style>\n</head>\n<body>\n"
            + body + "\n</body>\n</html>\n")


def build() -> None:
    import shutil
    data = json.loads((ROOT / "data" / "rates.json").read_text(encoding="utf-8"))
    aff_path = ROOT / "data" / "affiliates.json"
    affiliates = json.loads(aff_path.read_text(encoding="utf-8")) if aff_path.exists() else {}
    # Accept the old form {"tpb": "https://..."} as well as full objects.
    affiliates = {k: ({"url": v, "label": "Mở tài khoản online"} if isinstance(v, str) else v)
                  for k, v in affiliates.items() if v}
    generated = datetime.fromisoformat(data["generated_at"])
    data["changes"] = compute_changes(data["rates"], HISTORY, generated.date())
    data["site_url"] = SITE_URL + "/"

    css, header, footer = read("partials/style.css"), read("partials/header.html"), read("partials/footer.html")
    safe_json = lambda obj: json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    banks_with_data = [b["name"] for b in data["banks"] if b.get("count")]
    common = {
        "__BANK_COUNT__": str(len(banks_with_data)),
        "__BANK_LIST__": ", ".join(banks_with_data),
        "__CONTACT_EMAIL__": html.escape(CONTACT_EMAIL),
        "__UPDATED_TIME__": generated.strftime("%H:%M"),
        "__UPDATED_DATE__": generated.strftime("%d/%m/%Y"),
        "__SITE_URL__": html.escape(SITE_URL + "/"),
    }
    DIST.mkdir(exist_ok=True)
    pages = []  # (path, lastmod)
    from . import guides as gd, pages as gp
    guide_pages, guides = gd.guide_pages(data, generated, SITE_URL)
    gp.GUIDE_LINKS[:] = [(g["slug"], g["h1"]) for g in guides]
    gold_path = ROOT / "data" / "gold.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8")) if gold_path.exists() else None
    if gold:
        from .gold_page import gold_summary
        gp.GOLD_LINE[:] = [html.escape(gold_summary(gold))]

    # Homepage
    updated_vn = generated.strftime("%d/%m/%Y")
    home_desc = (f"So sánh lãi suất tiết kiệm {len(banks_with_data)} ngân hàng, cập nhật {updated_vn}. "
                 f"{best_sentence(data)} Tính tiền lãi theo số tiền và kỳ hạn.")
    home_body = fill(header + read("home.html") + "\n" + footer, {
        **common, "__PAGE_URL__": SITE_URL + "/",
        "__RATES_JSON__": safe_json(data), "__AFFILIATES_JSON__": safe_json(affiliates), "__SLUG_JSON__": safe_json(SLUG),
        "__STATIC_TABLE__": static_table(data, data["changes"]),
        "__BROWSE__": __import__("scraper.pages", fromlist=["x"]).browse_links(data),
    })
    home_title = f"Lãi suất tiết kiệm hôm nay {updated_vn} | Tiết Kiệm Đâu?"
    (DIST / "index.html").write_text(full_page(home_title, home_desc, SITE_URL + "/", home_body, css), encoding="utf-8")
    pages.append(("/", generated.date().isoformat()))
    # Body-only copy for the claude.ai preview (it adds its own <html>/<head>)
    (ROOT / "preview.html").write_text(
        '<title>Tiết Kiệm Đâu?</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
        + FONT_LINK + f"<style>\n{css}</style>\n" + home_body, encoding="utf-8")

    # Text pages: site/pages/<slug>.html -> /<slug>/
    for src_path in sorted((SITE / "pages").glob("*.html")):
        meta, src = front_matter(src_path.read_text(encoding="utf-8"))
        slug = src_path.stem
        url = f"{SITE_URL}/{slug}/"
        body = fill(header + analytics_blocks(src) + "\n" + footer, {**common, "__PAGE_URL__": url})
        out = DIST / slug
        out.mkdir(exist_ok=True)
        (out / "index.html").write_text(full_page(meta.get("title", slug), meta.get("description", ""), url, body, css),
                                        encoding="utf-8")
        pages.append((f"/{slug}/", None))

    # Generated pages: one per bank with data, one per common term, the guides
    browse = gp.browse_links(data)
    generated_pages = [gp.bank_page(data, data["changes"], b, generated, affiliates.get(b["code"]))
                       for b in gp.banks_with_data(data)]
    generated_pages += [gp.term_page(data, data["changes"], t, generated) for t in gp.term_pages(data)]
    generated_pages += guide_pages
    if gold:
        from .gold_page import gold_page
        generated_pages.append(gold_page(gold, datetime.fromisoformat(gold["generated_at"])))
        shutil.copyfile(gold_path, DIST / "gold.json")
    for slug, title, desc, gbody in generated_pages:
        url = f"{SITE_URL}/{slug}/"
        out = DIST / slug
        out.mkdir(parents=True, exist_ok=True)
        page_html = full_page(title, desc, url, fill(header + gbody + "\n" + footer, {**common, "__PAGE_URL__": url}), css)
        (out / "index.html").write_text(page_html, encoding="utf-8")
        pages.append((f"/{slug}/", generated.date().isoformat()))

    # Static files (icons, share image) go to the site root
    shutil.copytree(SITE / "static", DIST, dirs_exist_ok=True)  # includes logos/

    (DIST / "rates.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    urls = "".join(f"<url><loc>{SITE_URL}{path}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</url>"
                   for path, lm in pages)
    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                      f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n',
                                      encoding="utf-8")
    print(f"built {len(pages)} pages, {len(data['changes'])} recent changes — {home_desc}")


if __name__ == "__main__":
    build()
