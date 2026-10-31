"""Render site/template.html with today's data into dist/.

dist/index.html   full page to deploy (SEO meta + pre-rendered rate table)
dist/rates.json   the raw data, for anyone (or a future app) to reuse
dist/robots.txt, dist/sitemap.xml
preview.html      body-only copy used for the claude.ai preview

Set SITE_URL (e.g. https://solaisuat.vn) so canonical links and the sitemap are right.
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "site" / "template.html"
DIST = ROOT / "dist"
SITE_URL = os.environ.get("SITE_URL", "https://example.com").rstrip("/")
TERMS = [1, 3, 6, 9, 12, 13, 18, 24, 36]
CH = {"online": "Online", "counter": "Tại quầy"}


def rate_for(rates, bank, ch, term, amount):
    cands = [r for r in rates if r["bank"] == bank and r["channel"] == ch and r["term_months"] == term
             and r["min_amount"] <= amount and (r["max_amount"] is None or amount < r["max_amount"])]
    return max(cands, key=lambda r: r["rate"]) if cands else None


def cell(rates, bank, term, amount=100_000_000):
    on, co = rate_for(rates, bank, "online", term, amount), rate_for(rates, bank, "counter", term, amount)
    if not on and not co:
        return None
    return (on["rate"], "online") if (not co or (on and on["rate"] >= co["rate"])) else (co["rate"], "counter")


def fmt(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def static_matrix(data) -> str:
    rates = data["rates"]
    terms = [t for t in TERMS if any(r["term_months"] == t for r in rates)]
    best = {t: max((c[0] for b in data["banks"] if (c := cell(rates, b["code"], t))), default=0) for t in terms}
    head = "".join(f'<th scope="col">{t} th</th>' for t in terms)
    rows = []
    for b in data["banks"]:
        tds = []
        for t in terms:
            c = cell(rates, b["code"], t)
            if c:
                hi = " hi" if c[0] == best[t] else ""
                tds.append(f'<td class="r{hi}">{fmt(c[0])}<span class="ch">{CH[c[1]]}</span></td>')
            else:
                tds.append('<td class="r na">–</td>')
        rows.append(f"<tr><td>{html.escape(b['name'])}</td>{''.join(tds)}</tr>")
    return (f'<table><thead><tr><th scope="col">Ngân hàng</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def best_12m_sentence(data) -> str:
    rates = data["rates"]
    cells = [(c[0], b["name"], c[1]) for b in data["banks"] if (c := cell(rates, b["code"], 12))]
    if not cells:
        return ""
    r, name, ch = max(cells)
    return f"Kỳ hạn 12 tháng cao nhất: {name} {fmt(r)}%/năm ({CH[ch].lower()})."


def build() -> None:
    data = json.loads((ROOT / "data" / "rates.json").read_text(encoding="utf-8"))
    aff_path = ROOT / "data" / "affiliates.json"
    affiliates = json.loads(aff_path.read_text(encoding="utf-8")) if aff_path.exists() else {}
    generated = datetime.fromisoformat(data["generated_at"])
    updated_vn = generated.strftime("%d/%m/%Y")

    head, body = TEMPLATE.read_text(encoding="utf-8").split("<!--BODY-->")
    safe_json = lambda obj: json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    body = (body.replace("__RATES_JSON__", safe_json(data))
                .replace("__AFFILIATES_JSON__", safe_json(affiliates))
                .replace("__STATIC_MATRIX__", static_matrix(data))
                .replace("__UPDATED_VN__", updated_vn)
                .replace("__BANK_COUNT__", str(len(data["banks"]))))

    desc = (f"So sánh lãi suất tiết kiệm {len(data['banks'])} ngân hàng, cập nhật {updated_vn}. "
            f"{best_12m_sentence(data)} Tính tiền lãi theo số tiền và kỳ hạn.")
    seo = (f'<meta name="description" content="{html.escape(desc)}">\n'
           f'<link rel="canonical" href="{SITE_URL}/">\n'
           f'<meta property="og:title" content="So sánh lãi suất tiết kiệm hôm nay {updated_vn}">\n'
           f'<meta property="og:description" content="{html.escape(desc)}">\n'
           f'<meta property="og:type" content="website">\n')
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
    print(f"built dist/index.html ({len(page)//1024} KB) — {desc}")


if __name__ == "__main__":
    build()
