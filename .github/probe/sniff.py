"""Temporary probe: for each bank, open the homepage, follow the best 'lãi suất' link, log data requests."""
import asyncio, json, re, sys
from playwright.async_api import async_playwright

BANKS = {
    "vib": "https://www.vib.com.vn/vn/tiet-kiem/bieu-lai-suat-tiet-kiem-tai-quay",
    "msb": "https://www.msb.com.vn/",
    "shb": "https://www.shb.com.vn/",
    "seab": "https://www.seabank.com.vn/",
    "pvcb": "https://www.pvcombank.com.vn/",
    "abb": "https://www.abbank.vn/",
    "ncb": "https://www.ncb-bank.vn/",
    "bvb": "https://bvbank.net.vn/",
    "klb": "https://kienlongbank.com/",
    "vbb": "https://www.vietbank.com.vn/",
    "sgb": "https://www.saigonbank.com.vn/vi/truy-cap-nhanh/lai-suat",
    "pgb": "https://www.pgbank.com.vn/",
    "neo": "https://www.vcbneo.com.vn/",
    "bvbk": "https://www.baovietbank.vn/",
    "vab": "https://www.vietabank.com.vn/",
}
SKIP = ("google", "facebook", "doubleclick", "analytics", "tiktok", "clarity", "hotjar", "zalo", "gtm", "pixel", "adtima")

async def visit(b, url, follow=True):
    ctx = await b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", locale="vi-VN", ignore_https_errors=False)
    pg = await ctx.new_page()
    calls = []
    async def on(r):
        if r.request.resource_type in ("xhr", "fetch") and not any(s in r.url for s in SKIP):
            try: body = (await r.text())[:300]
            except Exception: body = ""
            calls.append((r.request.method, r.status, r.url[:180], (r.request.post_data or "")[:150], re.sub(r"\s+", " ", body)))
    pg.on("response", on)
    status = "ok"
    try:
        await pg.goto(url, wait_until="networkidle", timeout=45000)
    except Exception as e:
        status = "ERR " + str(e).split("\n")[0][:120]
    await pg.wait_for_timeout(2000)
    try: text = await pg.evaluate("document.body.innerText")
    except Exception: text = ""
    links = []
    try:
        links = await pg.evaluate("""() => [...document.querySelectorAll('a')].map(a => [a.innerText.trim().replace(/\\s+/g,' ').slice(0,70), a.href]).filter(([t,h]) => /lãi suất|lai-suat|laisuat|interest|bieu-lai/i.test(t+' '+h))""")
    except Exception: pass
    final = pg.url
    await ctx.close()
    return status, final, text, links, calls

def pick(links):
    score = lambda t, h: (("tiết kiệm" in t.lower() or "tiet-kiem" in h) * 3 + ("huy động" in t.lower() or "huy-dong" in h or "tien-gui" in h) * 2
                          + ("cá nhân" in t.lower() or "ca-nhan" in h or "khcn" in h.lower()) + ("vay" in t.lower() or "cho-vay" in h) * -5 + h.endswith(".pdf") * 1)
    best = sorted(((score(t, h), t, h) for t, h in links if h.startswith("http")), reverse=True)
    return best[0] if best else None

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for code, url in BANKS.items():
            st, final, text, links, calls = await visit(b, url)
            print(f"\n##### {code} {st} {final} text={len(text)} links={len(links)}")
            for l in links[:10]: print("   LINK", l)
            target = None
            if "12 tháng" not in text:
                best = pick(links)
                if best:
                    target = best[2]; print("   FOLLOW", best)
                    if not target.endswith(".pdf"):
                        st, final, text, links2, calls2 = await visit(b, target)
                        calls += calls2; print(f"   -> {st} {final} text={len(text)}")
                        for l in links2[:8]: print("   LINK2", l)
            i = text.find("12 tháng"); 
            if i < 0: i = text.find("12T")
            print("   TEXT", re.sub(r"\s+", " | ", text[max(0, i-600):i+700]) if i >= 0 else "(no '12 tháng')")
            for c in calls[:25]:
                if re.search(r"lai|rate|interest|saving|tiet|deposit|json|api", c[2], re.I): print("   CALL", c)
        await b.close()
asyncio.run(main())
