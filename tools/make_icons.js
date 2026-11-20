// Logo (ghim bản đồ + dấu %), favicon các cỡ, apple-touch-icon và ảnh chia sẻ og.png.
// Chạy lại khi đổi logo:  node tools/make_icons.js   (cần Node và Playwright: npm i playwright)
// Kết quả ghi vào site/static/; favicon.ico ghép bằng Pillow:  python tools/make_ico.py
const fs = require("fs"), path = require("path");
const { chromium } = require("playwright");
const OUT = path.join(__dirname, "..", "site", "static");
const ORANGE = "#ea580c";
const PIN = "M13 1.2a9.3 9.3 0 0 0-9.3 9.3c0 6.6 9.3 14.3 9.3 14.3s9.3-7.7 9.3-14.3A9.3 9.3 0 0 0 13 1.2z";
const MARK = `<path d="${PIN}" fill="${ORANGE}"/>`
  + `<circle cx="9.9" cy="7.6" r="1.9" fill="none" stroke="#fff" stroke-width="1.7"/>`
  + `<circle cx="16.1" cy="13.4" r="1.9" fill="none" stroke="#fff" stroke-width="1.7"/>`
  + `<path d="M16.6 6.6l-7.2 7.8" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>`;
const SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 26">${MARK}</svg>`;

const og = `<!doctype html><meta charset="utf-8"><style>
*{margin:0;box-sizing:border-box}
body{width:1200px;height:630px;background:#fff;font-family:Inter,"Be Vietnam Pro",Arial,sans-serif;color:#16191d;position:relative}
.bar{height:10px;background:${ORANGE}}
.logo{position:absolute;left:72px;top:72px;display:flex;align-items:center;gap:16px;font-weight:700;font-size:42px;letter-spacing:-.5px}
.logo .vn{color:${ORANGE}}
h1{position:absolute;left:72px;top:218px;width:820px;font-size:72px;line-height:1.12;font-weight:800;letter-spacing:-1.5px}
p{position:absolute;left:72px;top:388px;font-size:30px;color:#6b7280}
.chips{position:absolute;left:72px;top:512px;display:flex;gap:14px}
.chips span{background:#f1f2f4;color:#16191d;font-weight:700;font-size:24px;padding:12px 18px;border-radius:10px}
.live{position:absolute;right:72px;top:508px;background:#f0f9f3;color:#12803f;font-weight:700;font-size:26px;padding:14px 22px;border-radius:30px;display:flex;align-items:center;gap:12px}
.live i{width:12px;height:12px;border-radius:50%;background:#16a34a}
.big{position:absolute;right:70px;top:150px;opacity:.09}
</style>
<div class="bar"></div>
<svg class="big" width="300" height="300" viewBox="0 0 26 26">${MARK}</svg>
<div class="logo"><svg width="58" height="58" viewBox="0 0 26 26">${MARK}</svg><span>tietkiemdau<span class="vn">.vn</span></span></div>
<h1>Gửi tiết kiệm ở đâu lãi cao nhất?</h1>
<p>So sánh lãi suất các ngân hàng, cập nhật mỗi ngày</p>
<div class="chips"><span>VCB</span><span>BID</span><span>AGR</span><span>ACB</span><span>TPB</span><span>STB</span></div>
<div class="live"><i></i>Cập nhật 2 lần/ngày</div>`;

(async () => {
  fs.writeFileSync(path.join(OUT, "favicon.svg"), SVG);
  const b = await chromium.launch(), p = await b.newPage();
  const icon = async (size, file, bg) => {
    await p.setViewportSize({ width: size, height: size });
    const pad = bg ? Math.round(size * 0.12) : 0;      // apple-touch-icon: nền trắng, chừa lề (iOS bo góc)
    await p.setContent(`<body style="margin:0;background:${bg || "transparent"}"><svg width="${size - 2 * pad}" height="${size - 2 * pad}" viewBox="0 0 26 26" style="display:block;margin:${pad}px">${MARK}</svg></body>`);
    await p.screenshot({ path: path.join(OUT, file), omitBackground: !bg });
  };
  for (const s of [32, 48, 96, 192]) await icon(s, `favicon-${s}.png`);
  await icon(256, "favicon-256.tmp.png");
  await icon(180, "apple-touch-icon.png", "#ffffff");
  await p.setViewportSize({ width: 1200, height: 630 });
  await p.setContent(og); await p.waitForTimeout(200);
  await p.screenshot({ path: path.join(OUT, "og.png") });
  await b.close();
  console.log("wrote favicon.svg, favicon-32/48/96/192.png, apple-touch-icon.png, og.png");
})();
