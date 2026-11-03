"""/gia-vang/: today's gold prices by shop, the world price in đồng, and recent days.

Rendered from data/gold.json and data/gold-history/. No JavaScript.
"""
from __future__ import annotations

import html
import json
from datetime import date, datetime
from pathlib import Path

from .gold import KINDS
from .pages import crumbs

E = html.escape
HISTORY = Path(__file__).resolve().parent.parent / "data" / "gold-history"
HISTORY_DAYS = 10


def k(v) -> str:
    """đồng/lượng -> nghìn đồng/lượng, '140.600'."""
    return "–" if v is None else f"{round(v / 1000):,}".replace(",", ".")


def tr(v, nd: int = 1) -> str:
    """đồng -> triệu, trailing zeros dropped: 140.600.000 -> '140,6'; 122.994.703 -> '123'."""
    s = f"{round(v / 1_000_000, nd):.{nd}f}"
    return (s.rstrip("0").rstrip(".") if "." in s else s).replace(".", ",")


def when(iso: str | None) -> str:
    if not iso:
        return "không ghi giờ"
    t = datetime.fromisoformat(iso)
    return f"{t:%H:%M %d/%m}"


def ok_shops(gold):
    return [s for s in gold["shops"] if s.get("items")]


def quotes(gold, kind):
    """[(shop, item)] for the compared product of this kind at each shop."""
    out = []
    for s in ok_shops(gold):
        it = next((i for i in s["items"] if i["kind"] == kind), None)
        if it:
            out.append((s, it))
    return out


def load_history(today: date):
    """[(date, snapshot)] for earlier days, newest first."""
    out = []
    for f in sorted(HISTORY.glob("*.json"), reverse=True):
        d = date.fromisoformat(f.stem)
        if d < today:
            out.append((d, json.loads(f.read_text(encoding="utf-8"))))
    return out


def prev_price(history, shop_code, kind):
    for d, snap in history:
        for s in snap.get("shops", []):
            if s["code"] == shop_code:
                it = next((i for i in s["items"] if i["kind"] == kind), None)
                if it:
                    return it["sell"], d
    return None, None


def change(now, before) -> str:
    if before is None or now is None:
        return ""
    d = now - before
    if abs(d) < 1000:
        return '<span class="chg muted">0</span>'
    return f'<span class="chg {"up" if d > 0 else "down"}">{"▲" if d > 0 else "▼"}{k(abs(d))}</span>'


def kind_table(gold, kind, history):
    qs = quotes(gold, kind)
    if not qs:
        return ""
    low_sell = min(i["sell"] for _, i in qs)
    high_buy = max((i["buy"] for _, i in qs if i["buy"]), default=None)
    rows = []
    for s, i in sorted(qs, key=lambda x: x[1]["sell"]):
        before, _ = prev_price(history, s["code"], kind)
        spread = i["sell"] - i["buy"] if i["buy"] else None
        stale = ' <span class="tier">dữ liệu cũ</span>' if s.get("stale") else ""
        rows.append(
            f'<tr><th scope="row"><b>{E(s["name"])}</b>{stale}<span class="pn">{E(i["name"])} · {when(s.get("updated"))}</span></th>'
            f'<td class="r{" best" if i["buy"] == high_buy and len(qs) > 1 else ""}"><span class="v">{k(i["buy"])}</span></td>'
            f'<td class="r{" best" if i["sell"] == low_sell and len(qs) > 1 else ""}"><span class="v">{k(i["sell"])}</span>{change(i["sell"], before)}</td>'
            f'<td class="r"><span class="v">{k(spread)}</span></td></tr>')
    return (f'<section class="block"><h2>{KINDS[kind]}</h2>'
            '<div class="card"><div class="scroll"><table class="rates gold">'
            '<thead><tr><th scope="col">Cửa hàng</th><th scope="col">Mua vào</th><th scope="col">Bán ra</th>'
            '<th scope="col">Chênh lệch</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></div></section>')


def world_block(gold, sjc_low, ring_low):
    w = gold.get("world") or {}
    if not w.get("vnd_luong"):
        return ""
    v = w["vnd_luong"]
    rows = [("Giá vàng thế giới", f'{w["usd_oz"]:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".") + " USD/ounce"),
            ("Tỷ giá USD bán ra (Vietcombank)", f'{w["usd_vnd"]:,.0f}'.replace(",", ".") + " đồng"),
            ("Quy đổi ra đồng", f"{k(v)} nghìn đồng/lượng")]
    if sjc_low:
        rows.append(("Vàng miếng SJC đắt hơn thế giới", f"{tr(sjc_low - v)} triệu đồng/lượng ({(sjc_low / v - 1) * 100:.1f}%)".replace(".", ",")))
    if ring_low:
        rows.append(("Nhẫn trơn 999.9 đắt hơn thế giới", f"{tr(ring_low - v)} triệu đồng/lượng ({(ring_low / v - 1) * 100:.1f}%)".replace(".", ",")))
    body = "".join(f'<tr><th scope="row">{E(a)}</th><td class="r"><span class="v">{E(b)}</span></td></tr>' for a, b in rows)
    stale = ' Giá thế giới chưa cập nhật được ở lần kiểm tra gần nhất.' if w.get("stale") else ""
    return ('<section class="block"><h2>Giá vàng thế giới quy đổi</h2>'
            f'<div class="card"><div class="scroll"><table class="rates guide-tbl kv"><tbody>{body}</tbody></table></div></div>'
            f'<p class="sub">Quy đổi = giá USD/ounce × 37,5 ÷ 31,1035 × tỷ giá, chưa gồm thuế, phí vận chuyển và gia công, '
            f'nên chỉ dùng để so sánh. Giá thế giới cập nhật {when(_iso_vn(w.get("updated")))}.{stale}</p></section>')


def _iso_vn(utc_iso):
    if not utc_iso:
        return None
    from datetime import timedelta, timezone
    return datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=7))).isoformat()


def history_block(gold, history, today):
    """Last few days: lowest SJC and ring selling price, and the world price in đồng."""
    days = [(today, gold)] + history[:HISTORY_DAYS - 1]
    if len(days) < 2:
        return ""
    rows = []
    for d, snap in days:
        sjc = [i["sell"] for _, i in quotes(snap, "sjc")]
        ring = [i["sell"] for _, i in quotes(snap, "ring")]
        w = (snap.get("world") or {}).get("vnd_luong")
        rows.append(f'<tr><th scope="row">{d:%d/%m}</th><td class="r"><span class="v">{k(min(sjc)) if sjc else "–"}</span></td>'
                    f'<td class="r"><span class="v">{k(min(ring)) if ring else "–"}</span></td>'
                    f'<td class="r"><span class="v">{k(w)}</span></td></tr>')
    return ('<section class="block"><h2>Giá vàng những ngày gần đây</h2>'
            '<div class="card"><div class="scroll"><table class="rates guide-tbl"><thead><tr><th scope="col">Ngày</th>'
            '<th scope="col">SJC bán ra</th><th scope="col">Nhẫn 999.9 bán ra</th><th scope="col">Thế giới quy đổi</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></div>'
            '<p class="sub">Giá bán ra thấp nhất trong các cửa hàng, lần kiểm tra cuối mỗi ngày, nghìn đồng/lượng.</p></section>')


def boards(gold):
    out = []
    for s in ok_shops(gold):
        rows = "".join(f'<tr><th scope="row">{E(i["name"])}</th><td class="r"><span class="v">{k(i["buy"])}</span></td>'
                       f'<td class="r"><span class="v">{k(i["sell"])}</span></td></tr>' for i in s["items"])
        out.append(f'<details class="qa"><summary>Bảng giá đầy đủ {E(s["name"])}</summary>'
                   f'<div class="scroll"><table class="rates guide-tbl"><thead><tr><th scope="col">Loại vàng</th>'
                   f'<th scope="col">Mua vào</th><th scope="col">Bán ra</th></tr></thead><tbody>{rows}</tbody></table></div>'
                   f'<p class="sub">Cập nhật {when(s.get("updated"))} · <a href="{E(s["source_url"])}" target="_blank" rel="noopener">'
                   f'Nguồn: website {E(s["name"])}</a></p></details>')
    return "".join(out)


def gold_summary(gold) -> str:
    sjc = [i["sell"] for _, i in quotes(gold, "sjc")]
    ring = [i["sell"] for _, i in quotes(gold, "ring")]
    bits = []
    if sjc:
        bits.append(f"vàng miếng SJC bán ra {tr(min(sjc))} triệu đồng/lượng")
    if ring:
        bits.append(f"nhẫn trơn 999.9 từ {tr(min(ring))} triệu")
    t = datetime.fromisoformat(gold["generated_at"])
    return (f"Lúc {t:%H:%M %d/%m}: " + ", ".join(bits) + ".") if bits else ""


def gold_page(gold: dict, generated: datetime):
    today = generated.date()
    history = load_history(today)
    sjc, ring = quotes(gold, "sjc"), quotes(gold, "ring")
    sjc_low = min((i["sell"] for _, i in sjc), default=None)
    ring_low = min((i["sell"] for _, i in ring), default=None)
    ring_who = [s["name"] for s, i in ring if i["sell"] == ring_low]
    w = (gold.get("world") or {}).get("vnd_luong")
    date_vn = f"{today:%d/%m/%Y}"

    parts = []
    if sjc:
        sells = sorted({i["sell"] for _, i in sjc})
        buys = sorted({i["buy"] for _, i in sjc if i["buy"]})
        rng = f"{tr(sells[0])}" + (f" – {tr(sells[-1])}" if len(sells) > 1 else "")
        parts.append(f"Vàng miếng SJC bán ra {rng} triệu đồng/lượng"
                     + (f", mua vào {tr(buys[0])}" + (f" – {tr(buys[-1])}" if len(buys) > 1 else "") + " triệu" if buys else "") + ".")
    if ring:
        parts.append(f"Nhẫn trơn 999.9 bán ra thấp nhất {tr(ring_low)} triệu đồng/lượng tại {' và '.join(ring_who)}.")
    if w:
        wtxt = f"Giá thế giới quy đổi khoảng {tr(w)} triệu đồng/lượng"
        parts.append(wtxt + (f", thấp hơn vàng miếng SJC {tr(sjc_low - w)} triệu." if sjc_low else "."))
    summary = " ".join(parts)

    tiles = []
    if sjc_low:
        tiles.append(("SJC bán ra", tr(sjc_low), "triệu đồng/lượng, thấp nhất"))
    if ring_low:
        tiles.append(("Nhẫn 999.9 bán ra", tr(ring_low), f"triệu/lượng · {tr(ring_low / 10, 2)} triệu/chỉ"))
    if w:
        tiles.append(("Thế giới quy đổi", tr(w), f"triệu/lượng · {gold['world']['usd_oz']:,.0f} USD/oz".replace(",", ".")))
    tiles_html = "".join(f'<div class="tile"><span class="k">{a}</span><span class="v">{b}</span><span class="w">{E(c)}</span></div>'
                         for a, b, c in tiles)

    tables = "".join(kind_table(gold, kd, history) for kd in KINDS)
    sources = " · ".join(f'<a href="{E(s["source_url"])}" target="_blank" rel="noopener">{E(s["name"])}</a>' for s in gold["shops"])
    qa = [
        ("Giá mua vào và bán ra khác nhau thế nào?",
         "Giá <b>bán ra</b> là giá cửa hàng bán cho bạn, tức giá bạn trả khi mua vàng. Giá <b>mua vào</b> là giá cửa hàng mua lại "
         "từ bạn khi bạn bán vàng. Khoảng chênh giữa hai giá là chi phí bạn chịu ngay khi mua: mua xong bán lại ngay, bạn mất đúng "
         "khoản chênh lệch đó."),
        ("1 lượng vàng bằng bao nhiêu chỉ?",
         "1 lượng (1 cây) = 10 chỉ = 37,5 gam. Giá trên trang tính theo lượng; muốn biết giá một chỉ, chia cho 10."),
        ("Vì sao giá vàng trong nước cao hơn giá thế giới?",
         "Giá trong nước do cung cầu trong nước quyết định, cộng thêm thuế, phí nhập khẩu, vận chuyển và gia công, nên thường khác "
         "giá thế giới quy đổi. Chênh lệch này thay đổi theo thời gian và có thể thu hẹp hoặc nới rộng nhanh."),
        ("Nhẫn trơn 999.9 và vàng miếng SJC khác nhau thế nào?",
         "Cả hai đều là vàng 99,99%. Vàng miếng SJC là thương hiệu vàng miếng quốc gia, giá thường cao hơn. Nhẫn trơn mang thương hiệu "
         "của từng cửa hàng; khi bán lại, nhiều cửa hàng mua giá tốt nhất với nhẫn do chính họ sản xuất."),
    ]
    qa_html = "".join(f'<details class="qa" open><summary>{E(q)}</summary><p>{a}</p></details>' for q, a in qa)

    title = f"Giá vàng hôm nay {date_vn}: SJC, nhẫn trơn 999.9 | Tiết Kiệm Đâu?"
    desc = (summary or "Giá vàng SJC, nhẫn trơn 999.9 và vàng trang sức tại các cửa hàng, giá thế giới quy đổi.")[:300]
    body = f'''<section class="page gutter"><div class="wrap stack">
{crumbs(("Giá vàng", None))}
<div><h1>Giá vàng hôm nay {date_vn}</h1><p class="lede">{E(summary)}</p></div>
<p class="srcline">Kiểm tra lúc {generated:%H:%M %d/%m/%Y}, khoảng mỗi giờ từ 9 giờ sáng đến 10 giờ tối · Nguồn: website {sources}</p>
<div class="tiles">{tiles_html}</div>
{tables}
<p class="sub">Đơn vị nghìn đồng/lượng (1 lượng = 10 chỉ). Chữ xanh: giá bán ra thấp nhất và giá mua vào cao nhất. Mũi tên so với giá bán ra
ngày hôm trước. Giá có thể khác theo chi nhánh và thay đổi nhiều lần trong ngày; hãy xác nhận với cửa hàng trước khi giao dịch.</p>
{world_block(gold, sjc_low, ring_low)}
{history_block(gold, history, today)}
<section class="block"><h2>Bảng giá từng cửa hàng</h2>{boards(gold)}</section>
<section class="block"><h2>Câu hỏi thường gặp</h2>{qa_html}</section>
<p class="sub">Đang cân nhắc giữa vàng và tiết kiệm? Xem <a href="/huong-dan/gui-tiet-kiem-hay-mua-vang/">gửi tiết kiệm hay mua vàng</a>
và <a href="/">lãi suất tiết kiệm hôm nay</a>.</p>
</div></section>'''
    return "gia-vang", title, desc, body
