"""Gold price chart for /gia-vang/: SJC bars, plain rings and the world price in đồng, by day.

Data: data/gold-daily.json (scraper/gold_daily.py). The page gets a summary sentence
rendered on the server (search engines and no-JS readers see the trend) and a small
script that draws an SVG line chart with 1/3/6/12-month ranges and a crosshair tooltip.
"""
from __future__ import annotations

import html
import json
from datetime import date, timedelta

GRAMS_PER_LUONG = 37.5
GRAMS_PER_OZ = 31.1034768
E = html.escape


def world_vnd(r) -> float | None:
    if r.get("usd_oz") and r.get("usd_vnd"):
        return r["usd_oz"] * GRAMS_PER_LUONG / GRAMS_PER_OZ * r["usd_vnd"]
    return None


def series(daily: list[dict]) -> dict:
    """Compact arrays in triệu đồng/lượng for the page script."""
    m = lambda v: round(v / 1e6, 2) if v else None
    return {"d": [r["d"] for r in daily],
            "sjc": [m(r.get("sjc", [None, None])[1]) for r in daily],
            "ring": [m(r.get("ring", [None, None])[1]) for r in daily],
            "world": [m(world_vnd(r)) for r in daily]}


def tr(v: float) -> str:
    return f"{v / 1e6:.1f}".replace(".", ",")


def pct(a: float, b: float) -> str:
    x = (a / b - 1) * 100
    return f"{'tăng' if x >= 0 else 'giảm'} {abs(x):.1f}%".replace(".", ",")


def summary(daily: list[dict]) -> str:
    """One-year and one-month change of the SJC selling price, and the premium over the world price."""
    rows = [r for r in daily if r.get("sjc")]
    if len(rows) < 8:
        return ""
    last = rows[-1]
    d_last = date.fromisoformat(last["d"])

    def at(days):
        target = (d_last - timedelta(days=days)).isoformat()
        older = [r for r in rows if r["d"] <= target]
        return older[-1] if older else None

    parts = []
    for days, label in ((365, "một năm"), (30, "một tháng")):
        r = at(days)
        if r and date.fromisoformat(r["d"]) < d_last - timedelta(days=days * 0.8):
            parts.append(f"{pct(last['sjc'][1], r['sjc'][1])} so với {label} trước "
                         f"({tr(r['sjc'][1])} triệu ngày {date.fromisoformat(r['d']):%d/%m/%Y})")
    text = f"Ngày {d_last:%d/%m/%Y}, vàng miếng SJC tại PNJ bán ra {tr(last['sjc'][1])} triệu đồng/lượng"
    text += (", " + " và ".join(parts) + ".") if parts else "."
    w_now, first = world_vnd(last), rows[0]
    w_then = world_vnd(first)
    if w_now and w_then:
        text += (f" Chênh lệch giữa SJC và giá thế giới quy đổi là {tr(last['sjc'][1] - w_now)} triệu đồng/lượng, "
                 f"so với {tr(first['sjc'][1] - w_then)} triệu ngày {date.fromisoformat(first['d']):%d/%m/%Y}.")
    return text


SCRIPT = r"""
(function(){
  const root = document.getElementById('goldChart');
  if (!root) return;
  const D = JSON.parse(document.getElementById('gold-series').textContent);
  const S = [
    {k:'sjc',   name:'Vàng miếng SJC', short:'SJC', cls:'s1'},
    {k:'ring',  name:'Nhẫn trơn 999.9', short:'Nhẫn', cls:'s2'},
    {k:'world', name:'Thế giới quy đổi', short:'TG', cls:'s3'}];
  const svg = root.querySelector('svg'), tip = root.querySelector('.gc-tip');
  const NS = 'http://www.w3.org/2000/svg';
  const el = (n, a, p) => { const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); (p||svg).appendChild(e); return e; };
  const fmt = v => v == null ? '–' : v.toLocaleString('vi-VN', {minimumFractionDigits:1, maximumFractionDigits:1});
  const dt = s => { const [y,m,d] = s.split('-'); return d + '/' + m + '/' + y; };
  let range = 365, idx = [], X, Y, W, H, pad;

  function draw(){
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    W = root.clientWidth; H = W < 520 ? 260 : 320;
    pad = {l: 40, r: 84, t: 12, b: 28};
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('height', H);
    const last = D.d[D.d.length-1];
    const from = new Date(last); from.setDate(from.getDate() - range);
    const f = from.toISOString().slice(0,10);
    idx = D.d.map((d,i) => i).filter(i => D.d[i] >= f);
    if (idx.length < 2) return;
    const vals = idx.flatMap(i => S.map(s => D[s.k][i])).filter(v => v != null);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const step = niceStep((hi - lo) / 4);
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
    const t0 = +new Date(D.d[idx[0]]), t1 = +new Date(D.d[idx[idx.length-1]]);
    X = i => pad.l + (+new Date(D.d[i]) - t0) / (t1 - t0 || 1) * (W - pad.l - pad.r);
    Y = v => pad.t + (hi - v) / (hi - lo || 1) * (H - pad.t - pad.b);
    // grid + y labels
    for (let v = lo; v <= hi + 1e-9; v += step) {
      el('line', {x1: pad.l, x2: W - pad.r, y1: Y(v), y2: Y(v), class: 'gc-grid'});
      el('text', {x: pad.l - 8, y: Y(v) + 4, class: 'gc-ax', 'text-anchor': 'end'}).textContent = Math.round(v);
    }
    // x labels: month starts (or weeks on the 1-month view)
    let lastX = -1e9, prevKey = null;
    const keyOf = d => range <= 31 ? Math.floor((+new Date(d) - 4 * 864e5) / (7 * 864e5)) : d.slice(0, 7);   // week or month
    idx.forEach((i, n) => {
      const d = D.d[i], key = keyOf(d), first = key !== prevKey; prevKey = key;
      if (!first || n === 0) return;   // label the first day with data in each month (week on the 1-month view)
      const x = X(i); if (x - lastX < 46 || x > W - pad.r - 10) return; lastX = x;
      el('line', {x1: x, x2: x, y1: H - pad.b, y2: H - pad.b + 4, class: 'gc-grid'});
      el('text', {x, y: H - 8, class: 'gc-ax', 'text-anchor': 'middle'}).textContent =
        range <= 31 ? d.slice(8) + '/' + d.slice(5,7) : 'T' + (+d.slice(5,7)) + (d.slice(5,7) === '01' ? '/' + d.slice(2,4) : '');
    });
    // lines + end labels
    const ends = [];
    S.forEach(s => {
      let p = '', pen = false;
      idx.forEach(i => { const v = D[s.k][i]; if (v == null) return;   // a missing day joins its neighbours
        p += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1); pen = true; });
      el('path', {d: p, class: 'gc-line ' + s.cls});
      const li = [...idx].reverse().find(i => D[s.k][i] != null);
      if (li != null) { el('circle', {cx: X(li), cy: Y(D[s.k][li]), r: 4, class: 'gc-dot ' + s.cls}); ends.push({s, y: Y(D[s.k][li]), v: D[s.k][li]}); }
    });
    ends.sort((a,b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i-1].y < 15) ends[i].y = ends[i-1].y + 15;
    ends.forEach(e => {
      const t = el('text', {x: W - pad.r + 9, y: e.y + 4, class: 'gc-end'});
      t.textContent = fmt(e.v) + ' ' + e.s.short;
    });
    // crosshair
    const cross = el('line', {y1: pad.t, y2: H - pad.b, class: 'gc-cross', visibility: 'hidden'});
    const hit = el('rect', {x: pad.l, y: pad.t, width: W - pad.l - pad.r, height: H - pad.t - pad.b, fill: 'transparent', tabindex: 0,
      'aria-label': 'Biểu đồ giá vàng; dùng phím mũi tên để xem từng ngày'});
    let cur = idx.length - 1;
    const show = k => {
      cur = Math.max(0, Math.min(idx.length - 1, k)); const i = idx[cur], x = X(i);
      cross.setAttribute('x1', x); cross.setAttribute('x2', x); cross.setAttribute('visibility', 'visible');
      tip.replaceChildren();
      const h = document.createElement('div'); h.className = 'gc-tip-d'; h.textContent = dt(D.d[i]); tip.appendChild(h);
      S.forEach(s => { const r = document.createElement('div'); r.className = 'gc-tip-r';
        const key = document.createElement('i'); key.className = 'gc-key ' + s.cls;
        const b = document.createElement('b'); b.textContent = fmt(D[s.k][i]);
        const n = document.createElement('span'); n.textContent = s.name;
        r.append(key, b, n); tip.appendChild(r); });
      const sj = D.sjc[i], w = D.world[i];
      if (sj != null && w != null) { const r = document.createElement('div'); r.className = 'gc-tip-x';
        r.textContent = 'SJC đắt hơn thế giới ' + fmt(sj - w) + ' triệu'; tip.appendChild(r); }
      tip.hidden = false;
      const tw = tip.offsetWidth; tip.style.left = (x + 12 + tw > W ? x - tw - 12 : x + 12) + 'px';
    };
    const near = ev => { const r = svg.getBoundingClientRect(), px = ev.clientX - r.left;
      let best = 0, bd = 1e9; idx.forEach((i, k) => { const d = Math.abs(X(i) - px); if (d < bd) { bd = d; best = k; } }); return best; };
    hit.addEventListener('pointermove', ev => show(near(ev)));
    hit.addEventListener('pointerdown', ev => show(near(ev)));
    hit.addEventListener('pointerleave', () => { cross.setAttribute('visibility','hidden'); tip.hidden = true; });
    hit.addEventListener('focus', () => show(cur));
    hit.addEventListener('blur', () => { cross.setAttribute('visibility','hidden'); tip.hidden = true; });
    hit.addEventListener('keydown', ev => { if (ev.key === 'ArrowLeft') { show(cur - 1); ev.preventDefault(); }
      if (ev.key === 'ArrowRight') { show(cur + 1); ev.preventDefault(); } });
  }
  function niceStep(raw){ const p = Math.pow(10, Math.floor(Math.log10(raw || 1))), n = raw / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p; }
  document.querySelectorAll('#goldRange .tab').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('#goldRange .tab').forEach(x => x.setAttribute('aria-checked', String(x === b)));
    range = +b.dataset.days; draw(); }));
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(draw, 120); });
  draw();
})();
"""


def chart_block(daily: list[dict]) -> str:
    if len([r for r in daily if r.get("sjc")]) < 8:
        return ""
    data = json.dumps(series(daily), separators=(",", ":")).replace("</", "<\\/")
    span = (date.fromisoformat(daily[-1]["d"]) - date.fromisoformat(daily[0]["d"])).days
    ranges = [(30, "1 tháng"), (90, "3 tháng"), (182, "6 tháng"), (366, "1 năm")]
    ranges = [r for r in ranges if r[0] <= span + 31] or ranges[:1]
    default = ranges[-1][0]
    btns = "".join(f'<button class="tab" type="button" role="radio" aria-checked="{str(d == default).lower()}" data-days="{d}">{l}</button>'
                   for d, l in ranges)
    legend = "".join(f'<span><i class="gc-key {c}"></i>{n}</span>' for c, n in
                     (("s1", "Vàng miếng SJC (PNJ, bán ra)"), ("s2", "Nhẫn trơn 999.9 (PNJ, bán ra)"), ("s3", "Thế giới quy đổi")))
    return f'''<section class="block"><h2>Biểu đồ giá vàng</h2>
<p class="sub">{E(summary(daily))}</p>
<div class="tabs" id="goldRange" role="radiogroup" aria-label="Khoảng thời gian">{btns}</div>
<div class="gc-legend">{legend}</div>
<div class="gc" id="goldChart"><svg role="img" aria-label="Biểu đồ giá vàng SJC, nhẫn trơn và thế giới quy đổi theo ngày" width="100%"></svg>
<div class="gc-tip" role="status" hidden></div></div>
<p class="sub">Triệu đồng/lượng, giá đóng cửa mỗi ngày. Giá trong nước: giá bán ra của PNJ (TP.HCM). Thế giới: giá vàng
COMEX (USD/ounce) quy đổi bằng tỷ giá USD bán ra của Vietcombank, chưa gồm thuế phí.</p>
<noscript><p class="sub">Bật JavaScript để xem biểu đồ.</p></noscript>
<script type="application/json" id="gold-series">{data}</script>
<script>{SCRIPT}</script></section>'''

