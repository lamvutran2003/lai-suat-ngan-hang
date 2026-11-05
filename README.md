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
scraper/gold.py       gold prices (PNJ, Phú Quý, Bảo Tín Mạnh Hải + world price) -> data/gold.json, data/gold-history/
scraper/gold_page.py  /gia-vang/ page from that data; scraper/gold_chart.py draws its price chart
scraper/gold_daily.py daily series for the chart (data/gold-daily.json), with a one-off backfill
scraper/check.py      exit 1 if a bank or gold shop has had no fresh data for too long (GitHub emails you)
tests/                parser tests against saved copies of each bank's page
.github/workflows/    the schedule: banks + gold 09:17 and 16:17; gold only every hour 09:47–21:47 (Vietnam time)
```

## Banks covered (03/11/2026)

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

Switched off: **VietinBank** (`scraper/banks/vietin.py`) — its site refuses
GitHub's servers (HTTP 405). Its rates matched Vietcombank and BIDV anyway.

Checked and **not covered**: MB (site blocks all automated access; can be hand-entered
with a 14-day re-check reminder), LPBank, MSB, MBV, BVBank (rates load in ways not yet
worked out).

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
marked "Dữ liệu cũ". To fix:

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
5. Commit, then Actions → Update rates → Run workflow. Green = done.

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
