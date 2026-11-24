# Tiết Kiệm Đâu? (tietkiemdau.vn) — Vietnamese savings-rate comparison

Scrapes deposit rates from bank websites twice a day, rebuilds a static page,
and deploys it to GitHub Pages for free. No server, no database.

```
scraper/banks/*.py    one adapter per bank: fetch() + parse()
scraper/run.py        fetch all banks, validate, write data/rates.json + data/history/<date>.json
scraper/build_site.py assemble site/ -> dist/ (all pages, rates.json, sitemap, robots, icons)
site/home.html        homepage (rate table + calculator)
site/pages/*.html     text pages; each becomes /<file-name>/ (title/description in the top comment)
site/pages/tinh-lai-vay.html  mortgage/loan calculator (promo rate then floating; reducing balance or equal instalments)
site/guides/*.html    guides -> /huong-dan/<file-name>/ ; {{tokens}} in the text are filled with today's
                      figures by scraper/guides.py (token list at the top of that file)
scraper/pages.py      generated pages: /ngan-hang/<bank>/ for each bank with data, /ky-han/<n>-thang/ for
                      terms 1–36 months that at least 3 banks publish; all text computed from the data
site/partials/        shared style.css, header.html, footer.html (incl. sharing script)
site/static/          favicon, share image (og.png), logos/<bank>.png (official icons): copied to the site root
tools/make_icons.js   draws the logo (map pin + %), favicons, apple-touch icon and og.png; then tools/make_ico.py
scraper/gold.py       gold prices (PNJ, Phú Quý, Bảo Tín Mạnh Hải + world price) -> data/gold.json, data/gold-history/
scraper/gold_page.py  /gia-vang/ page from that data; scraper/gold_chart.py draws its price chart
scraper/gold_daily.py daily series for the chart (data/gold-daily.json), with a one-off backfill
scraper/check.py      exit 1 if a bank or gold shop has had no fresh data for too long (GitHub emails you)
tests/                parser tests against saved copies of each bank's page
.github/workflows/    the schedule: banks + gold 09:17 and 16:17; gold only every hour 09:47–21:47 (Vietnam time)
```

## Banks covered (05/11/2026)

| Bank | Source type | Counter | Online | Amount tiers |
|---|---|---|---|---|
| Vietcombank | JSON API | ✓ | ✓ | |
| BIDV | 2 JSON endpoints | ✓ | ✓ | |
| Agribank | HTML fragment | ✓ | | |
| ACB | HTML tables | ✓ | ✓ | ✓ |
| TPBank | HTML fragment (flaky server, retried) | ✓ | ✓ | |
| Sacombank | PDF at a fixed address | ✓ | ✓ | ✓ |
| OCB | PDF linked from the rate page | ✓ | ✓ | ✓ (online) |
| Techcombank | PDF found via its document-list API (Phát Lộc, normal customer) | ✓ | ✓ | ✓ |
| VPBank | **Hand-entered** (`data/manual/vpb.json`); watcher spots new sheets | ✓ | ✓ | ✓ |
| LPBank | JSON API (`TK_TTQ_KHCN` counter, `TK_ONLINE` online) | ✓ | ✓ | |
| MBV | **Hand-entered** (`data/manual/mbv.json`) since its site stopped answering GitHub (18/11/2026); watcher reads the rate post from the site menu, else 14-day re-check | ✓ | ✓ | |
| Bac A Bank | ASP.NET page, VND table after a postback | ✓ | | |
| Nam A Bank | index page → current online and counter pages | ✓ | ✓ | |
| Vikki Bank | two HTML pages (HDBank's digital bank) | ✓ | ✓ | |
| Cake by VPBank | **Hand-entered** (`data/manual/cake.json`), site blocks GitHub; 14-day re-check | | ✓ | |
| HDBank | **Hand-entered** (`data/manual/hdb.json`), PDF list loads encrypted; 14-day re-check | ✓ | ✓ | |
| ABBank | rate index → current dated page (counter + online tables) | ✓ | ✓ | |
| VietBank | one HTML page (standard savings + "Tiền gửi Online") | ✓ | ✓ | |
| Eximbank | **Hand-entered**; watcher reads the PDF name on its rate page | ✓ | ✓ (weekday) | |
| BVBank | **Hand-entered**; site added bot protection (11/2026), so the watcher usually fails and a 14-day re-check reminder takes over | ✓ | ✓ | |
| MB | **Hand-entered** (`data/manual/mb.json`); site blocks all automated access (Akamai), so no watcher, 14-day re-check. Read the sheet in a browser: Hỗ trợ → Biểu lãi suất → Lãi suất huy động (counter = section I, online = section IV "Tiền gửi số truyền thống", Mass) | ✓ | ✓ | |
| VIB | **Hand-entered** (`data/manual/vib.json`); site serves a bot challenge to scripts, so no watcher, 14-day re-check. Rates are on www.vib.com.vn/vn/tiet-kiem: online = "Tiền gửi trực tuyến" table, counter = "Tiền gửi tại quầy → Tiền gửi có kỳ hạn" (3 amount bands each) | ✓ | ✓ | |
| SHB | **Hand-entered** (`data/manual/shb.json`); site serves a security check to scripts, but the PDF itself downloads fine (`pdftotext -layout`). Rate page: shb.com.vn → Liên kết nhanh → Lãi suất → "Lãi suất huy động VND dành cho khách hàng cá nhân". Counter = section 1, online = section 4. No watcher (index page blocked); 14-day re-check | ✓ | ✓ | |
| SeABank (`ssb`) | **Hand-entered** (`data/manual/ssb.json`), counter only: the "Biểu lãi suất" tool at seabank.com.vn/cong-cu-tien-ich/bieu-lai-suat loads rates through Next.js server actions; product "Tiết kiệm Bậc thang", pick each amount band. Online savings rates are not published. No date on the page (as_of empty); 14-day re-check | ✓ | | |
| MSB | **Hand-entered** (`data/manual/msb.json`) from a *scanned* PDF (read the page images; Phụ lục 01 counter, Phụ lục 02 online, column "Lãi suất cao nhất"). Watcher reads the PDF name on the savings-rate page (may be blocked from GitHub; then the 14-day re-check takes over) | ✓ | ✓ | |
| PVcomBank (`pvcb`) | two static PDFs with real text (`GD_Tai_quay_…` counter, `GD_Online_…` online), product "Đại Chúng" lãi cuối kỳ; at the counter the plain 12/13-month rows are for deposits from 2.000 tỷ (10%), so the `(*)` rows are used. The rate tool on the site needs reCAPTCHA, so it's not used | ✓ | ✓ | |
| Saigonbank (`sgb`) | **Hand-entered** (`data/manual/sgb.json`): the page has plain HTML tables, but its filter refuses the scraper's requests, so no adapter; 14-day re-check | ✓ | ✓ | |
| PGBank (`pgb`) | **Hand-entered** (`data/manual/pgb.json`), site serves a bot challenge; table at pgbank.com.vn/lai-suat-tiet-kiem/ca-nhan-vnd ("thông thường" cuối kỳ / "Online" cuối kỳ); 14-day re-check | ✓ | ✓ | |
| BaoViet Bank (`baoviet`) | **Hand-entered** (`data/manual/baoviet.json`), site blocks servers; baovietbank.vn/vn/lai-suat, first VND table (cuối kỳ) and "Tiết kiệm Online - EZ Saving". No date on the page; 14-day re-check | ✓ | ✓ | |
| NCB | **Hand-entered**; watcher reads the PDF list on its rate page (blocked since 11/2026, so the 14-day re-check takes over) | ✓ | ✓ | |

**VietinBank** is hand-entered (`data/manual/vietin.json`): its site refuses GitHub's servers
(HTTP 405), but `scraper/banks/vietin.py` still works from other machines, so refresh the file by
running it locally: `python -c "from scraper.banks import vietin; from scraper.common import make_session as m; print(vietin.parse(vietin.fetch(m())))"`.

Checked and **not covered** (11/2026): VCBNeo (publishes only "maximum" rates and says actual rates vary by region and branch),
Kienlongbank (rate tables live in iframes on laisuat.kienlongbank.com that don't load from servers and stayed blank in a browser too;
the iframe page redirects when opened directly).

Eximbank's PDF server sends an incomplete certificate chain (the DigiCert G5 intermediate is missing),
so scripts can't download the PDF with normal verification. The watcher only reads the main site.
Wallet "savings" (MoMo Túi Thần Tài, Finhay, Tikop…) are left out on purpose: they are fund
investments, not bank deposits, so they are not insured and their return is not fixed.

## Run locally

```bash
pip install -r requirements.txt
python -m pytest -q tests        # parsers against saved pages
python -m scraper.run            # live scrape -> data/rates.json
python -m scraper.build_site     # -> dist/index.html (open it in a browser)
```

## Put it online (one-time, ~15 minutes)

1. Create a GitHub repository and push this folder to it.
2. Repository **Settings → Pages → Source: GitHub Actions**.
3. **Settings → Secrets and variables → Actions → Variables**: add `SITE_URL`
   (e.g. `https://yourname.github.io/repo` or your own domain).
4. **Actions → Update rates → Run workflow** once to test. After that it runs by itself.
5. Optional custom domain: buy it, then add it under Settings → Pages → Custom domain.
6. Submit `SITE_URL/sitemap.xml` in Google Search Console so Google finds the page.

## When you get a "workflow failed" email

The site still deployed; the broken bank just shows its last good numbers
marked "dữ liệu cũ" in the table. After 48 hours without fresh data the bank is left out of every
comparison (table, best-rate boxes, calculator, term pages, guides) and listed under the table as
"tạm không so sánh"; its own page keeps the old numbers. To fix:

1. Open the failed run; the last step names the bank and the error.
2. Save the bank's current page over its file in `tests/fixtures/`.
3. Run `pytest`, adjust that bank's adapter until the test passes, push.

## Optional settings (Settings → Secrets and variables → Actions → Variables)

- `SITE_URL`: the site address, e.g. `https://tietkiemdau.vn`
- `CF_BEACON_TOKEN`: Cloudflare Web Analytics token. When set, visitor stats are switched on and the
  privacy page gains a paragraph saying so.
- `CONTACT_EMAIL`: shown on the About, privacy and footer (default `lienhe@tietkiemdau.vn`)

## Gold prices (`/gia-vang/`)

Sources that answer GitHub's servers (checked 11/2026): PNJ's JSON feed, Phú Quý's price board and
Bảo Tín Mạnh Hải's homepage. SJC, DOJI and Bảo Tín Minh Châu block automated access, so SJC bars are
shown at the prices PNJ and Phú Quý sell them. World price: gold-api.com (USD/ounce) × Vietcombank's
USD selling rate, × 37,5 ÷ 31,1035 for one lượng.

The chart uses `data/gold-daily.json`: one row per day with PNJ's closing SJC and ring prices,
COMEX gold (Yahoo Finance) and Vietcombank's USD rate. Every gold run rewrites today's row, so the
last run of the day is the close. The first year was filled with
`python -m scraper.gold_daily --backfill 2025-11-01` (PNJ's history feed keeps about a year;
running it again only fills missing days).

All prices are stored as đồng per lượng. A shop that fails keeps its last prices marked "dữ liệu cũ";
the run fails (email) only after 24 hours without fresh prices. Fix a broken shop the same way as a
bank: save its page over `tests/fixtures/gold/<file>`, adjust its class in `scraper/gold.py`, run pytest.

## Hand-entered banks (`data/manual/<code>.json`)

For banks whose rate sheet a script can't read (VPBank publishes a scanned PDF).
Each run checks whether the bank has published a new sheet. If it has, the run
**fails and GitHub emails you** "VPBank: rates need a manual update", with the link
to the new sheet. The site keeps showing the old numbers, marked "Đang cập nhật".

To update (about 5 minutes, all on github.com):

1. Open the new sheet from the email link and note the effective date ("Áp dụng từ ngày …").
2. In the repository open `data/manual/vpb.json` → pencil icon (Edit).
3. Change the numbers under `"counter"` and `"online"`. Keys are months (`"12"` = 12 tháng),
   values are %/năm with a dot (`6.40`). Amount bands use the bank's wording
   (`"Dưới 10 tỷ"`, `"Từ 10 tỷ"`); drop `"amount"` if a rate applies to every amount.
4. Update the four header lines:
   - `"document_url"`: the new sheet's link
   - `"watch"`: the last part of that link (the file name), e.g. `2.-20261115-Phu-luc-BLS-niem-yet.pdf`
   - `"as_of"`: the effective date as `YYYY-MM-DD`
   - `"checked_at"`: today, `YYYY-MM-DD`
5. Commit. The commit starts a run by itself (changes under `site/`, `scraper/`, `data/manual/` deploy on push). Green = done.

If a number is mistyped badly (e.g. `67.0` instead of `6.70`), the run rejects the file
and keeps the previous numbers, so a typo can't reach the site.

A bank with no watcher (e.g. MB, whose site blocks scripts) asks for a re-check after
14 days instead: open its rate page, compare, and set `"checked_at"` to today.

## Guides (`site/guides/`)

Each guide is an HTML fragment with a top comment (`title`, `h1`, `description`, `summary`, `order`).
Figures that depend on rates are written as tokens, e.g. `{{best_rate:12}}` or `{{amount_table}}`,
so they stay current without editing. Laws and limits in the text (deposit insurance 350 triệu,
the 4,75% cap, early-withdrawal rules) are written by hand: re-check them when the rules change.

## Affiliate links

Copy `data/affiliates.example.json` to `data/affiliates.json` and put your
tracking links in it, keyed by bank code (`vcb`, `bidv`, `vietin`, `agri`,
`acb`, `tpb`). A "Mở tài khoản …" link then appears under that bank's rows,
marked `rel="sponsored"` as Google requires for paid links.

## Adding a bank

Write `scraper/banks/<code>.py` with `CODE`, `NAME`, `SOURCE_URL`,
`fetch(session) -> str` and `parse(raw) -> (list[Rate], as_of)`, register it
in `scraper/banks/__init__.py`, add its page to `tests/fixtures/` and a test.
