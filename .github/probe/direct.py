"""Temporary probe: each rate page via plain HTTP (browser-like headers) and via a real browser."""
import asyncio, re, ssl, urllib.request, gzip
from playwright.async_api import async_playwright
PAGES = {
    "sgb": "https://www.saigonbank.com.vn/vi/truy-cap-nhanh/lai-suat",
    "vab": "https://www.vietabank.com.vn/tien-ich/lai-suat-tien-gui.html",
    "bvbk": "https://www.baovietbank.vn/vn/lai-suat",
    "ncb": "https://www.ncb-bank.vn/vi/lai-suat-tien-gui",
    "abb": "https://www.abbank.vn/thong-tin/lai-suat",
    "vbb": "https://www.vietbank.com.vn/lai-suat",
    "neo": "https://www.vcbneo.com.vn/Pages/InterestRate.aspx",
    "klb": "https://kienlongbank.com.vn/lai-suat",
    "pvcb": "https://www.pvcombank.com.vn/bieu-lai-suat",
    "seab": "https://www.seabank.com.vn/ca-nhan/lai-suat",
    "msb": "https://www.msb.com.vn/vi/bieu-mau-bieu-phi-va-lai-suat.html",
    "shb": "https://www.shb.com.vn/category/lien-ket-nhanh/lai-suat-tien-gui/",
}
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8", "Accept-Encoding": "gzip"}
def plain(url):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30)
        b = r.read(); b = gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
        t = b.decode("utf-8", "replace"); return r.status, len(t), ("12 tháng" in t or "12 Tháng" in t or "12T" in t), t
    except Exception as e:
        return getattr(e, "code", type(e).__name__), 0, False, ""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for code, url in PAGES.items():
            st, n, has, raw = plain(url)
            pdfs = sorted(set(re.findall(r'href="([^"]+\.pdf)"', raw)))[:6]
            print(f"\n##### {code} plain={st} {n}B has12={has} pdfs={pdfs}")
            ctx = await b.new_context(user_agent=H["User-Agent"], locale="vi-VN"); pg = await ctx.new_page()
            calls = []
            async def on(r):
                if r.request.resource_type in ("xhr", "fetch") and not re.search(r"google|facebook|analytics|doubleclick|tiktok|clarity|connect247|zalo", r.url):
                    try: body = (await r.text())[:250]
                    except Exception: body = ""
                    calls.append((r.request.method, r.status, r.url[:170], (r.request.post_data or "")[:120], re.sub(r"\s+", " ", body)))
            pg.on("response", on)
            try: await pg.goto(url, wait_until="networkidle", timeout=40000)
            except Exception as e: print("   goto", str(e).split("\n")[0][:100])
            await pg.wait_for_timeout(2500)
            text = await pg.evaluate("document.body ? document.body.innerText : ''")
            links = await pg.evaluate("""() => [...document.querySelectorAll('a')].map(a => [a.innerText.trim().replace(/\\s+/g,' ').slice(0,60), a.href]).filter(([t,h]) => /\\.pdf|lãi suất tiết kiệm|lai-suat-tiet-kiem|tiền gửi/i.test(t+' '+h)).slice(0,12)""")
            i = max(text.find("12 tháng"), text.find("12 Tháng"))
            print("   browser text", len(text), "| url", pg.url)
            print("   TEXT", re.sub(r"\s+", " | ", text[max(0, i-500):i+600]) if i >= 0 else "(no 12 tháng)")
            for l in links: print("   LINK", l)
            for c in calls[:12]: print("   CALL", c)
            await ctx.close()
        await b.close()
asyncio.run(main())
