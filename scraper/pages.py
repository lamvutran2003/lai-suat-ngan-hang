"""Per-bank and per-term pages, rendered to static HTML from the day's data.

Everything here is computed from data/rates.json, so the pages update themselves
every run. No JavaScript: search engines read the tables directly.
"""
from __future__ import annotations

import html
from datetime import datetime

from .build_site import CH, SLUG, TICKER, fmt, key_of, rate_for

E = html.escape
EXAMPLE = 100_000_000                 # deposit used for worked examples and rankings
TERM_PAGES = [1, 3, 6, 9, 12, 18, 24, 36]
MIN_BANKS_FOR_TERM_PAGE = 3


def vnd(n: float) -> str:
    return f"{round(n):,}".replace(",", ".")


def interest(amount: int, rate: float, months: int) -> float:
    return amount * rate / 100 * months / 12


def millions(v: int) -> str:
    """500_000_000 -> '500 triệu'; 2_000_000_000 -> '2 tỷ'."""
    if v >= 1_000_000_000:
        x = v / 1_000_000_000
        return f"{x:g}".replace(".", ",") + " tỷ"
    return f"{v // 1_000_000} triệu"


def band_label(lo: int, hi: int | None) -> str:
    """Bands are [lo, hi). A '+1' bound means the bank's wording was inclusive ('đến 500 triệu')."""
    lo_incl = lo % 1_000_000 != 1  # lo = X+1 means "trên X"
    lo_v = lo if lo_incl else lo - 1
    if hi is None:
        return "Mọi mức tiền" if lo == 0 else (f"Từ {millions(lo_v)}" if lo_incl else f"Trên {millions(lo_v)}")
    hi_incl = hi % 1_000_000 == 1
    hi_v = hi - 1 if hi_incl else hi
    if lo == 0:
        return f"Đến {millions(hi_v)}" if hi_incl else f"Dưới {millions(hi_v)}"
    return f"{millions(lo_v)} – {'' if hi_incl else 'dưới '}{millions(hi_v)}"


def banks_with_data(data):
    return [b for b in data["banks"] if b.get("count")]


def best_any(data, code, term, amount=EXAMPLE):
    """Best quote for a bank at a term across both channels -> (rate, channel) or None."""
    best = None
    for ch in CH:
        r = rate_for(data["rates"], code, ch, term, amount)
        if r and (best is None or r["rate"] > best[0]):
            best = (r["rate"], ch)
    return best


def arrow(changes, r) -> str:
    c = changes.get(key_of(r))
    if not c:
        return ""
    d = r["rate"] - c["prev"]
    return (f'<span class="chg {"up" if d > 0 else "down"}" title="Từ {fmt(c["prev"])}%">'
            f'{"▲" if d > 0 else "▼"}{fmt(abs(d))}</span>')


def crumbs(*parts) -> str:
    items = ['<a href="/">Trang chủ</a>'] + [f'<a href="{u}">{E(t)}</a>' if u else f"<span>{E(t)}</span>"
                                             for t, u in parts]
    return f'<nav class="crumbs" aria-label="Đường dẫn">{" › ".join(items)}</nav>'


def browse_links(data, current_bank=None, current_term=None) -> str:
    banks = "".join(
        f'<a class="chip{" on" if b["code"] == current_bank else ""}" href="/ngan-hang/{SLUG[b["code"]]}/">{E(b["name"])}</a>'
        for b in banks_with_data(data))
    terms = "".join(
        f'<a class="chip{" on" if t == current_term else ""}" href="/ky-han/{t}-thang/">{t} tháng</a>'
        for t in term_pages(data))
    return (f'<div class="browse"><h2>Xem theo ngân hàng</h2><div class="chips">{banks}</div>'
            f'<h2>Xem theo kỳ hạn</h2><div class="chips">{terms}</div></div>')


def term_pages(data):
    return [t for t in TERM_PAGES
            if sum(1 for b in banks_with_data(data) if best_any(data, b["code"], t)) >= MIN_BANKS_FOR_TERM_PAGE]


def as_of_line(b, generated: datetime) -> str:
    eff = f"Biểu lãi suất hiệu lực từ {b['as_of'][8:10]}/{b['as_of'][5:7]}/{b['as_of'][:4]}" if b.get("as_of") else \
        "Biểu lãi suất không ghi ngày hiệu lực"
    stale = ' · <span class="stale">Dữ liệu cũ, đang chờ ngân hàng cập nhật</span>' if b.get("stale") else ""
    return (f'{eff} · Kiểm tra lúc {generated:%H:%M %d/%m/%Y} · '
            f'<a href="{E(b["source_url"])}" target="_blank" rel="noopener">Nguồn: website {E(b["name"])}</a>{stale}')


# ---------------------------------------------------------------- bank page
def bank_page(data, changes, b, generated: datetime):
    code, name = b["code"], b["name"]
    rates = [r for r in data["rates"] if r["bank"] == code]
    terms = sorted({r["term_months"] for r in rates})
    others = banks_with_data(data)
    date_vn = f"{generated:%d/%m/%Y}"

    # Headline numbers
    top = max(rates, key=lambda r: (r["rate"], -r["term_months"]))
    r12 = best_any(data, code, 12)
    ranked = sorted((best_any(data, o["code"], 12) or (0, ""))[0] for o in others)[::-1]
    rank12 = ranked.index(r12[0]) + 1 if r12 else None

    tiles = [
        ("Cao nhất", f"{fmt(top['rate'])}%", f"{top['term_months']} tháng · {CH[top['channel']].lower()}"
         + (f" · {band_label(top['min_amount'], top['max_amount']).lower()}" if (top['min_amount'] or top['max_amount']) else "")),
        ("Kỳ hạn 12 tháng", f"{fmt(r12[0])}%" if r12 else "–", f"{CH[r12[1]].lower()}, gửi 100 triệu" if r12 else "chưa niêm yết"),
        ("Xếp hạng 12 tháng", f"#{rank12}" if rank12 else "–", f"trong {len(others)} ngân hàng"),
    ]
    tiles_html = "".join(f'<div class="tile"><span class="k">{k}</span><span class="v">{v}</span><span class="w">{E(w)}</span></div>'
                         for k, v, w in tiles)

    # One table per channel; columns are the bank's deposit bands for that channel
    sections = []
    for ch in ("online", "counter"):
        ch_rates = [r for r in rates if r["channel"] == ch]
        if not ch_rates:
            continue
        bands = sorted({(r["min_amount"], r["max_amount"]) for r in ch_rates}, key=lambda x: x[0])
        best = max(r["rate"] for r in ch_rates)
        head = "".join(f'<th scope="col">{E(band_label(lo, hi)) if len(bands) > 1 else "Lãi suất"}</th>' for lo, hi in bands)
        rows = []
        for t in terms:
            cells = []
            for lo, hi in bands:
                r = next((x for x in ch_rates if x["term_months"] == t and x["min_amount"] == lo and x["max_amount"] == hi), None)
                if not r:
                    cells.append('<td class="na">–</td>')
                    continue
                cls = " best" if r["rate"] == best else ""
                cells.append(f'<td class="r{cls}"><span class="v">{fmt(r["rate"])}</span>{arrow(changes, r)}</td>')
            if any('class="r' in c for c in cells):
                rows.append(f'<tr><th scope="row">{t} tháng</th>{"".join(cells)}</tr>')
        title = "Lãi suất gửi online" if ch == "online" else "Lãi suất gửi tại quầy"
        sub = "Mở sổ trên ứng dụng hoặc ngân hàng điện tử." if ch == "online" else "Gửi trực tiếp tại chi nhánh, phòng giao dịch."
        sections.append(f'<section class="block"><h2>{title}</h2><p class="sub">{sub} Đơn vị %/năm, lãi trả cuối kỳ.'
                        f'{" Mức lãi khác nhau theo số tiền gửi." if len(bands) > 1 else ""}</p>'
                        f'<div class="card"><div class="scroll"><table class="rates term-rows"><thead><tr><th scope="col">Kỳ hạn</th>{head}</tr></thead>'
                        f'<tbody>{"".join(rows)}</tbody></table></div></div></section>')

    # Q&A, every answer computed from the data
    qa = []
    if r12:
        q_int = interest(EXAMPLE, r12[0], 12)
        qa.append((f"Gửi 100 triệu ở {name} kỳ hạn 12 tháng được bao nhiêu tiền lãi?",
                   f"Với mức {fmt(r12[0])}%/năm ({CH[r12[1]].lower()}), 100.000.000 ₫ gửi 12 tháng nhận khoảng "
                   f"<b>{vnd(q_int)} ₫</b> tiền lãi, tổng cộng {vnd(EXAMPLE + q_int)} ₫ khi đáo hạn (lãi trả cuối kỳ, chưa trừ thuế)."))
    on = [r for r in rates if r["channel"] == "online"]
    co = [r for r in rates if r["channel"] == "counter"]
    if on and co:
        diffs = []
        for t in terms:
            a, c = rate_for(rates, code, "online", t, EXAMPLE), rate_for(rates, code, "counter", t, EXAMPLE)
            if a and c:
                diffs.append((a["rate"] - c["rate"], t, a["rate"], c["rate"]))
        if diffs:
            d, t, a, c = max(diffs)
            if d > 0.001:
                qa.append((f"Gửi online hay tại quầy ở {name} lãi cao hơn?",
                           f"Gửi online thường cao hơn. Chênh lệch lớn nhất ở kỳ hạn {t} tháng: online {fmt(a)}%, "
                           f"tại quầy {fmt(c)}%, tức thêm khoảng {vnd(interest(EXAMPLE, d, t))} ₫ trên mỗi 100 triệu."))
            else:
                qa.append((f"Gửi online hay tại quầy ở {name} lãi cao hơn?",
                           "Theo biểu lãi suất hiện tại, lãi gửi online và tại quầy ở các kỳ hạn chính gần như bằng nhau."))
    elif co and not on:
        qa.append((f"{name} có lãi suất gửi online không?",
                   f"Biểu lãi suất {name} công bố trên website hiện chỉ có mức gửi tại quầy."))
    qa.append((f"Kỳ hạn nào ở {name} có lãi suất cao nhất?",
               f"Cao nhất là {fmt(top['rate'])}%/năm ở kỳ hạn {top['term_months']} tháng ({CH[top['channel']].lower()}"
               + (f", {band_label(top['min_amount'], top['max_amount']).lower()}" if (top['min_amount'] or top['max_amount']) else "")
               + ")."))
    if rank12:
        leaders = [o["name"] for o in others if (best_any(data, o["code"], 12) or (0,))[0] == ranked[0]]
        if rank12 == 1:
            tied = [n for n in leaders if n != name]
            verdict = ("Đây là mức cao nhất hiện nay" + (f", ngang với {', '.join(map(E, tied))}" if tied else "") + ". ")
        else:
            verdict = f"Cao nhất hiện là {E(' và '.join(leaders))} với {fmt(ranked[0])}%/năm. "
        qa.append((f"Lãi suất {name} so với các ngân hàng khác thế nào?",
                   f"Ở kỳ hạn 12 tháng, {name} đứng thứ {rank12}/{len(others)} ngân hàng chúng tôi theo dõi. " + verdict
                   + '<a href="/ky-han/12-thang/">Xem bảng so sánh 12 tháng</a>.'))
    qa_html = "".join(f"<details class=\"qa\" open><summary>{E(q)}</summary><p>{a}</p></details>" for q, a in qa)

    top_band = (f", {band_label(top['min_amount'], top['max_amount']).lower()}"
                if (top['min_amount'] or top['max_amount']) else "")
    top_txt = (f"Lãi suất tiết kiệm {name} cao nhất hiện là {fmt(top['rate'])}%/năm, kỳ hạn {top['term_months']} tháng "
               f"({CH[top['channel']].lower()}{top_band}).")
    title = f"Lãi suất {name} hôm nay {date_vn} | Tiết Kiệm Đâu?"
    desc = f"{top_txt} Bảng lãi suất {name} online và tại quầy theo kỳ hạn và số tiền, cập nhật mỗi ngày."
    body = f'''<section class="page gutter"><div class="wrap stack">
{crumbs(("Ngân hàng", None), (name, None))}
<div class="bank-head"><span class="tick big">{TICKER.get(code, code.upper())}</span>
<div><h1>Lãi suất {E(name)} hôm nay</h1><p class="lede">{E(top_txt)} Cập nhật ngày {date_vn}.</p></div></div>
<p class="srcline">{as_of_line(b, generated)}</p>
<div class="tiles">{tiles_html}</div>
{"".join(sections)}
<section class="block"><h2>Câu hỏi thường gặp</h2>{qa_html}</section>
<p class="sub">Lãi suất dành cho khách hàng cá nhân thông thường, chưa gồm ưu đãi riêng. Mũi tên ▲ ▼ cho biết mức lãi đã thay đổi trong 30 ngày gần nhất.
Hãy xác nhận với {E(name)} trước khi gửi tiền. <a href="/#tinh-lai">Tính tiền lãi cho số tiền của bạn</a>.</p>
{browse_links(data, current_bank=code)}
</div></section>'''
    return f"ngan-hang/{SLUG[code]}", title, desc, body


# ---------------------------------------------------------------- term page
def term_page(data, changes, term: int, generated: datetime):
    date_vn = f"{generated:%d/%m/%Y}"
    rows = []
    for b in banks_with_data(data):
        on = rate_for(data["rates"], b["code"], "online", term, EXAMPLE)
        co = rate_for(data["rates"], b["code"], "counter", term, EXAMPLE)
        if not (on or co):
            continue
        best = max((x for x in (on, co) if x), key=lambda x: x["rate"])
        tiered = any(r["bank"] == b["code"] and r["term_months"] == term and (r["min_amount"] or r["max_amount"])
                     for r in data["rates"])
        rows.append({"b": b, "on": on, "co": co, "best": best, "tiered": tiered})
    rows.sort(key=lambda x: -x["best"]["rate"])
    top_rate, low_rate = rows[0]["best"]["rate"], rows[-1]["best"]["rate"]
    leaders = [x for x in rows if x["best"]["rate"] == top_rate]

    def cell(r, is_best):
        if not r:
            return '<td class="na">–</td>'
        return f'<td class="r{" best" if is_best else ""}"><span class="v">{fmt(r["rate"])}</span>{arrow(changes, r)}</td>'

    def col_best(key):  # highlight a column's best only when at most two banks share it
        vals = [x[key]["rate"] for x in rows if x[key]]
        top = max(vals, default=None)
        return top if vals.count(top) <= 2 else None

    best_on, best_co = col_best("on"), col_best("co")
    trs = []
    for i, x in enumerate(rows, 1):
        b = x["b"]
        gain = interest(EXAMPLE, x["best"]["rate"], term)
        note = '<span class="tier" title="Lãi suất thay đổi theo số tiền gửi">theo số tiền</span>' if x["tiered"] else ""
        trs.append(f'<tr><th scope="row"><span class="rk">{i}</span><span class="tick">{TICKER.get(b["code"], "")}</span>'
                   f'<a class="bn" href="/ngan-hang/{SLUG[b["code"]]}/">{E(b["name"])}</a>{note}</th>'
                   f'{cell(x["on"], x["on"] and x["on"]["rate"] == best_on)}{cell(x["co"], x["co"] and x["co"]["rate"] == best_co)}'
                   f'<td class="r"><span class="v">{vnd(gain)} ₫</span><span class="chg muted">{CH[x["best"]["channel"]].lower()}</span></td></tr>')

    names = " và ".join(f'{x["b"]["name"]} ({CH[x["best"]["channel"]].lower()})' for x in leaders[:3])
    spread = interest(EXAMPLE, top_rate - low_rate, term)
    summary = (f"Ngày {date_vn}, lãi suất tiết kiệm kỳ hạn {term} tháng cao nhất là {fmt(top_rate)}%/năm tại {names}. "
               f"Thấp nhất là {fmt(low_rate)}%/năm tại {rows[-1]['b']['name']}. Với 100 triệu đồng, chọn mức cao nhất thay vì thấp nhất giúp bạn nhận thêm "
               f"khoảng {vnd(spread)} ₫ tiền lãi sau {term} tháng.")
    cap = (" Kỳ hạn dưới 6 tháng bị giới hạn tối đa 4,75%/năm theo quy định của Ngân hàng Nhà nước, nên nhiều ngân hàng có cùng mức."
           if term < 6 else "")
    title = f"Lãi suất tiết kiệm {term} tháng ngân hàng nào cao nhất? ({date_vn}) | Tiết Kiệm Đâu?"
    desc = (f"So sánh lãi suất gửi tiết kiệm kỳ hạn {term} tháng của {len(rows)} ngân hàng. Cao nhất {fmt(top_rate)}%/năm "
            f"tại {leaders[0]['b']['name']}. Cập nhật {date_vn}.")
    body = f'''<section class="page gutter"><div class="wrap stack">
{crumbs(("Kỳ hạn", None), (f"{term} tháng", None))}
<div><h1>Lãi suất tiết kiệm {term} tháng: ngân hàng nào cao nhất?</h1>
<p class="lede">{E(summary)}</p></div>
<div class="card"><div class="scroll"><table class="rates rank">
<thead><tr><th scope="col">Ngân hàng</th><th scope="col">Online</th><th scope="col">Tại quầy</th><th scope="col">Lãi trên 100 triệu</th></tr></thead>
<tbody>{"".join(trs)}</tbody></table></div></div>
<p class="sub">Xếp theo mức lãi cao nhất của mỗi ngân hàng cho khoản gửi 100.000.000 ₫, đơn vị %/năm, lãi trả cuối kỳ.{cap}
Ngân hàng ghi "theo số tiền" trả lãi khác nhau tùy số tiền gửi; <a href="/#tinh-lai">nhập số tiền của bạn</a> để xem đúng mức.</p>
{browse_links(data, current_term=term)}
</div></section>'''
    return f"ky-han/{term}-thang", title, desc, body
