"""Guides: hand-written articles in site/guides/*.html with live numbers filled in at build time.

Each guide starts with a front-matter comment (title, description, summary, order). In the
body, {{token}} or {{token:arg:arg}} is replaced with a figure or table computed from
today's rates, so "the best 12-month rate is ..." is never out of date.

Tokens (amounts in đồng, terms in months):
  {{updated}}                     date of the data, dd/mm/yyyy
  {{bank_count}}                  banks with data
  {{best_rate:12}}                highest rate for 12 months on a 100 triệu deposit: "6,80%"
  {{best_where:12}}               "BIDV (online)"; ties list up to 3 banks
  {{best_interest:100000000:12}}  interest at the best rate for that amount and term: "6.800.000 ₫"
  {{amount_table}}                amounts × terms, best rate and interest
  {{term_table}}                  per term: highest rate, where, and the middle rate across banks
  {{channel_table:12}}            per bank: online vs counter at that term
  {{online_higher:12}}            "6 trên 8"
  {{days_example:6}}              worked example, actual days / 365 vs months / 12
  {{early_example:12:6}}          100 triệu for 12 months, withdrawn after 6
  {{rollover_table}}              1 năm theo cách: 12 lần 1 tháng / 2 lần 6 tháng / 1 lần 12 tháng
  {{need_monthly:10000000}}       deposit needed for that much interest per month at the best 12-month rate
  {{gold_compare}}                100 triệu: savings vs buying gold and selling back (data/gold.json)
  {{gold_spread:sjc}}             cheapest buy-in vs best sell-back gap for SJC bars or rings (ring)
"""
from __future__ import annotations

import calendar
import html
import json
import re
from datetime import date, datetime
from pathlib import Path
from statistics import median

from .build_site import CH, SLUG, fmt, front_matter, logo_img, rate_for
from .pages import EXAMPLE, banks_with_data, crumbs, millions, vnd

E = html.escape
GUIDES_DIR = Path(__file__).resolve().parent.parent / "site" / "guides"
NON_TERM_RATE = 0.1   # illustrative non-term rate (%/năm) for early-withdrawal examples; stated in the text
AMOUNTS = [50_000_000, 100_000_000, 200_000_000, 500_000_000, 1_000_000_000]
TERMS = [1, 3, 6, 9, 12, 18, 24, 36]


# ---------------------------------------------------------------- data helpers
def best(data, term, amount=EXAMPLE):
    """(rate, [(bank, channel), ...]) for the highest quote at this term/amount across all banks."""
    quotes = []
    for b in banks_with_data(data):
        for ch in CH:
            r = rate_for(data["rates"], b["code"], ch, term, amount)
            if r:
                quotes.append((r["rate"], b, ch))
    if not quotes:
        return None, []
    top = max(q[0] for q in quotes)
    who, seen = [], set()
    for rate, b, ch in quotes:
        if rate == top and b["code"] not in seen:
            seen.add(b["code"])
            who.append((b, ch))
    return top, who


def bank_best(data, code, term, amount=EXAMPLE):
    vals = [r["rate"] for ch in CH if (r := rate_for(data["rates"], code, ch, term, amount))]
    return max(vals) if vals else None


def join_vi(items) -> str:
    """['A'] -> 'A'; ['A','B'] -> 'A và B'; ['A','B','C'] -> 'A, B và C'."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " và " + items[-1]


def where(who) -> str:
    """'BIDV, Sacombank và VPBank (online)'; mixed channels name each one; more than 3 banks are counted."""
    if not who:
        return "–"
    shown = who[:3]
    same = len({ch for _, ch in shown}) == 1
    names = [b["name"] if same else f'{b["name"]} ({CH[ch].lower()})' for b, ch in shown]
    if len(who) > 3:
        names.append(f"{len(who) - 3} ngân hàng khác")
    return join_vi(names) + (f" ({CH[shown[0][1]].lower()})" if same else "")


def interest(amount, rate, months):
    return amount * rate / 100 * months / 12


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


# ---------------------------------------------------------------- tokens
def t_amount_table(data, today):
    terms = [t for t in (1, 6, 12) if best(data, t)[0]]
    head = "".join(f'<th scope="col">{t} tháng</th>' for t in terms)
    rows = []
    for a in AMOUNTS:
        cells = []
        for t in terms:
            rate, who = best(data, t, a)
            cells.append(f'<td class="r"><span class="v">{vnd(interest(a, rate, t))} ₫</span>'
                         f'<span class="chg muted">{fmt(rate)}%</span></td>')
        monthly = interest(a, best(data, 12, a)[0], 1)
        rows.append(f'<tr><th scope="row">{millions(a)}</th>{"".join(cells)}'
                    f'<td class="r"><span class="v">{vnd(monthly)} ₫</span></td></tr>')
    return (f'<div class="card"><div class="scroll"><table class="rates term-rows"><thead><tr><th scope="col">Số tiền gửi</th>'
            f'{head}<th scope="col">Bình quân mỗi tháng (gửi 12 tháng)</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>')


def t_term_table(data, today):
    rows = []
    for t in TERMS:
        rate, who = best(data, t)
        if rate is None:
            continue
        vals = [v for b in banks_with_data(data) if (v := bank_best(data, b["code"], t)) is not None]
        rows.append(f'<tr><th scope="row"><a href="/ky-han/{t}-thang/">{t} tháng</a></th>'
                    f'<td class="r"><span class="v">{fmt(rate)}</span></td><td>{E(where(who))}</td>'
                    f'<td class="r"><span class="v">{fmt(median(vals))}</span></td></tr>')
    return ('<div class="card"><div class="scroll"><table class="rates guide-tbl"><thead><tr><th scope="col">Kỳ hạn</th>'
            '<th scope="col">Cao nhất</th><th scope="col">Tại</th><th scope="col">Mức giữa</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></div>')


def channel_pairs(data, term):
    out = []
    for b in banks_with_data(data):
        on = rate_for(data["rates"], b["code"], "online", term, EXAMPLE)
        co = rate_for(data["rates"], b["code"], "counter", term, EXAMPLE)
        if on and co:
            out.append((b, on["rate"], co["rate"]))
    return out


def t_channel_table(data, today, term="12"):
    term = int(term)
    rows = []
    for b, on, co in sorted(channel_pairs(data, term), key=lambda x: -(x[1] - x[2])):
        d = on - co
        diff = f'+{fmt(d)}' if d > 0.001 else ("0" if abs(d) <= 0.001 else f'−{fmt(-d)}')
        rows.append(f'<tr><th scope="row">{logo_img(b["code"])}<a class="bn" href="/ngan-hang/{SLUG[b["code"]]}/">{E(b["name"])}</a></th>'
                    f'<td class="r"><span class="v">{fmt(on)}</span></td><td class="r"><span class="v">{fmt(co)}</span></td>'
                    f'<td class="r"><span class="v">{diff}</span></td><td class="r"><span class="v">{vnd(interest(EXAMPLE, d, term))} ₫</span></td></tr>')
    return ('<div class="card"><div class="scroll"><table class="rates rank"><thead><tr><th scope="col">Ngân hàng</th>'
            '<th scope="col">Online</th><th scope="col">Tại quầy</th><th scope="col">Chênh lệch</th>'
            f'<th scope="col">Thêm trên 100 triệu</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>')


def t_online_higher(data, today, term="12"):
    pairs = channel_pairs(data, int(term))
    return f"{sum(1 for _, on, co in pairs if on > co + 0.001)} trên {len(pairs)}"


def t_days_example(data, today, term="6"):
    term = int(term)
    rate, who = best(data, term)
    end = add_months(today, term)
    days = (end - today).days
    by_days = EXAMPLE * rate / 100 * days / 365
    by_months = interest(EXAMPLE, rate, term)
    return (f'<div class="example"><p><b>Ví dụ:</b> gửi 100.000.000 ₫ kỳ hạn {term} tháng với lãi suất {fmt(rate)}%/năm, '
            f'mức cao nhất hôm nay của {E(where(who))}. Thời gian gửi từ {today:%d/%m/%Y} đến {end:%d/%m/%Y}, tức {days} ngày.</p>'
            f'<ul><li>Theo số ngày thực tế: 100.000.000 × {fmt(rate)}% × {days} ÷ 365 = <b>{vnd(by_days)} ₫</b></li>'
            f'<li>Tính nhanh theo tháng: 100.000.000 × {fmt(rate)}% × {term} ÷ 12 = <b>{vnd(by_months)} ₫</b></li></ul>'
            f'<p>Hai cách lệch nhau {vnd(abs(by_days - by_months))} ₫. Ngân hàng trả theo cách thứ nhất.</p></div>')


def t_early_example(data, today, term="12", after="6"):
    term, after = int(term), int(after)
    rate, who = best(data, term)
    days = (add_months(today, after) - today).days
    full = interest(EXAMPLE, rate, term)
    early = EXAMPLE * NON_TERM_RATE / 100 * days / 365
    kept = EXAMPLE * rate / 100 * days / 365
    return (f'<div class="example"><p><b>Ví dụ:</b> gửi 100.000.000 ₫ kỳ hạn {term} tháng, lãi {fmt(rate)}%/năm, '
            f'mức cao nhất hôm nay của {E(where(who))}. Giữ đủ {term} tháng, bạn nhận khoảng <b>{vnd(full)} ₫</b> tiền lãi.</p>'
            f'<p>Nếu rút toàn bộ sau {after} tháng ({days} ngày) và lãi không kỳ hạn của ngân hàng là {fmt(NON_TERM_RATE)}%/năm:</p>'
            f'<ul><li>Tiền lãi nhận được: 100.000.000 × {fmt(NON_TERM_RATE)}% × {days} ÷ 365 ≈ <b>{vnd(early)} ₫</b></li>'
            f'<li>Nếu được giữ mức {fmt(rate)}% cho {days} ngày đó, bạn đã có khoảng {vnd(kept)} ₫</li></ul>'
            f'<p>Rút trước hạn làm mất khoảng <b>{vnd(kept - early)} ₫</b>, gần như toàn bộ tiền lãi của {after} tháng.</p></div>')


def t_rollover_table(data, today):
    plans = []
    for t, n in ((1, 12), (3, 4), (6, 2), (12, 1)):
        rate, who = best(data, t)
        if rate is None:
            continue
        total = EXAMPLE * ((1 + rate / 100 * t / 12) ** n) - EXAMPLE
        label = f"Kỳ hạn {t} tháng, quay vòng {n} lần (lãi nhập gốc)" if n > 1 else "Gửi một lần kỳ hạn 12 tháng"
        plans.append((label, rate, total, where(who)))
    rows = "".join(f'<tr><th scope="row">{E(l)}</th><td class="r"><span class="v">{fmt(r)}</span></td>'
                   f'<td class="r"><span class="v">{vnd(tot)} ₫</span></td></tr>' for l, r, tot, w in plans)
    return ('<div class="card"><div class="scroll"><table class="rates guide-tbl"><thead><tr><th scope="col">Cách gửi 100 triệu trong 1 năm</th>'
            '<th scope="col">Lãi suất cao nhất</th><th scope="col">Tiền lãi sau 1 năm</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></div>')


def t_need_monthly(data, today, monthly="10000000"):
    """Deposit needed for this much interest a month (12-month term, best rate for that amount)."""
    monthly = int(monthly)
    amount = EXAMPLE
    for _ in range(4):   # the best rate depends on the amount (bands), so settle it
        rate = best(data, 12, amount)[0]
        amount = monthly * 12 / (rate / 100)
    return f"{millions(int(round(amount, -7)))} đồng (lãi {fmt(rate)}%/năm)"


def _gold():
    path = GUIDES_DIR.parent.parent / "data" / "gold.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def gold_best(kind):
    """(lowest sell, its shop, highest buy, its shop) for SJC bars / rings across shops."""
    g = _gold()
    if not g:
        return None
    qs = [(s["name"], i) for s in g["shops"] for i in s.get("items", []) if i["kind"] == kind and i["buy"]]
    if not qs:
        return None
    sell = min(qs, key=lambda x: x[1]["sell"])
    buy = max(qs, key=lambda x: x[1]["buy"])
    return sell[1]["sell"], sell[0], buy[1]["buy"], buy[0]


def t_gold_compare(data, today):
    """100 triệu for a year: savings at the best 12-month rate vs gold that must rise enough to match it."""
    rate, who = best(data, 12)
    gain = interest(EXAMPLE, rate, 12)
    rows = [f'<tr><th scope="row">Gửi tiết kiệm 12 tháng ({fmt(rate)}%/năm)</th><td class="r"><span class="v">+{vnd(gain)} ₫</span></td>'
            f'<td>Biết trước, không phụ thuộc giá cả</td></tr>']
    for kind, label in (("sjc", "Vàng miếng SJC"), ("ring", "Nhẫn trơn 999.9")):
        g = gold_best(kind)
        if not g:
            continue
        sell, shop_s, buy, shop_b = g
        loss = EXAMPLE * (1 - buy / sell)                       # buy at the lowest sell, sell back at the best buy
        need = (sell * (1 + rate / 100) / buy - 1) * 100        # rise in the shop's buying price to match savings
        rows.append(f'<tr><th scope="row">{label}: mua rồi bán lại ngay</th><td class="r"><span class="v">−{vnd(loss)} ₫</span></td>'
                    f'<td>Giá vàng phải tăng khoảng {fmt(need)}% trong 1 năm mới bằng lãi tiết kiệm</td></tr>')
    return ('<div class="card"><div class="scroll"><table class="rates guide-tbl"><thead><tr><th scope="col">Với 100 triệu đồng</th>'
            '<th scope="col">Lời/lỗ</th><th scope="col">Ghi chú</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></div>')


def t_gold_spread(data, today, kind="sjc"):
    g = gold_best(kind)
    if not g:
        return "vài triệu đồng/lượng"
    sell, _, buy, _ = g
    return f"{fmt((sell - buy) / 1e6).rstrip('0').rstrip(',')} triệu đồng/lượng (khoảng {fmt((1 - buy / sell) * 100)}% số tiền bỏ ra)"


def render_tokens(src: str, data, today: date) -> str:
    def simple(name, *args):
        if name == "updated":
            return f"{today:%d/%m/%Y}"
        if name == "bank_count":
            return str(len(banks_with_data(data)))
        if name == "best_rate":
            return f"{fmt(best(data, int(args[0]))[0])}%"
        if name == "best_where":
            return E(where(best(data, int(args[0]))[1]))
        if name == "best_interest":
            a, t = int(args[0]), int(args[1])
            return f"{vnd(interest(a, best(data, t, a)[0], t))} ₫"
        fn = TOKENS.get(name)
        if fn is None:
            raise KeyError(f"unknown guide token {{{{{name}}}}}")
        return fn(data, today, *args)

    return re.sub(r"\{\{(\w+)((?::[^}:]+)*)\}\}", lambda m: simple(m.group(1), *[a for a in m.group(2).split(":") if a]), src)


TOKENS = {"amount_table": t_amount_table, "term_table": t_term_table, "channel_table": t_channel_table,
          "online_higher": t_online_higher, "days_example": t_days_example, "early_example": t_early_example,
          "rollover_table": t_rollover_table, "need_monthly": t_need_monthly,
          "gold_compare": t_gold_compare, "gold_spread": t_gold_spread}


# ---------------------------------------------------------------- pages
def load_guides():
    out = []
    for p in sorted(GUIDES_DIR.glob("*.html")):
        meta, src = front_matter(p.read_text(encoding="utf-8"))
        out.append({"slug": p.stem, "title": meta["title"], "h1": meta.get("h1", meta["title"]),
                    "description": meta["description"], "summary": meta.get("summary", meta["description"]),
                    "order": int(meta.get("order", 99)), "src": src})
    return sorted(out, key=lambda g: (g["order"], g["slug"]))


def guide_links(guides, current=None, limit=None) -> str:
    items = [g for g in guides if g["slug"] != current][:limit]
    return "".join(f'<li><a href="/huong-dan/{g["slug"]}/">{E(g["h1"])}</a><span>{E(g["summary"])}</span></li>' for g in items)


def article_ld(g, url, site_url, today):
    return json.dumps({
        "@context": "https://schema.org", "@type": "Article", "headline": g["h1"], "description": g["description"],
        "dateModified": today.isoformat(), "inLanguage": "vi", "mainEntityOfPage": url,
        "publisher": {"@type": "Organization", "name": "Tiết Kiệm Đâu?", "url": site_url},
    }, ensure_ascii=False).replace("</", "<\\/")


def guide_pages(data, generated: datetime, site_url: str):
    """-> list of (slug, title, desc, body) for /huong-dan/ and each guide."""
    today = generated.date()
    guides = load_guides()
    pages = []
    for g in guides:
        url = f"{site_url}/huong-dan/{g['slug']}/"
        body = f'''<section class="page gutter"><div class="wrap stack">
{crumbs(("Hướng dẫn", "/huong-dan/"), (g["h1"], None))}
<article class="article guide">
<h1>{E(g["h1"])}</h1>
<p class="muted">Số liệu lãi suất trong bài cập nhật tự động ngày {today:%d/%m/%Y} từ {len(banks_with_data(data))} ngân hàng.</p>
{render_tokens(g["src"], data, today)}
</article>
<section class="block"><h2>Bài viết khác</h2><ul class="guide-list">{guide_links(guides, g["slug"])}</ul></section>
</div></section>
<script type="application/ld+json">{article_ld(g, url, site_url, today)}</script>'''
        pages.append((f"huong-dan/{g['slug']}", f"{g['title']} | Tiết Kiệm Đâu?", g["description"], body))
    index = f'''<section class="page gutter"><div class="wrap stack">
{crumbs(("Hướng dẫn", None))}
<div><h1>Hướng dẫn gửi tiết kiệm</h1>
<p class="lede">Những điều nên biết trước khi gửi tiền: cách tính lãi, chọn kỳ hạn, rút trước hạn, bảo hiểm tiền gửi. Số liệu trong bài cập nhật mỗi ngày.</p></div>
<ul class="guide-list">{guide_links(guides)}</ul>
</div></section>'''
    pages.insert(0, ("huong-dan", "Hướng dẫn gửi tiết kiệm ngân hàng | Tiết Kiệm Đâu?",
                     "Cách tính lãi tiết kiệm, nên gửi kỳ hạn nào, gửi online hay tại quầy, rút trước hạn mất bao nhiêu lãi, "
                     "bảo hiểm tiền gửi tối đa bao nhiêu. Số liệu cập nhật mỗi ngày.", index))
    return pages, guides
