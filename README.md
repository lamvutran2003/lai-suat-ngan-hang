# Tiết Kiệm Đâu? (tietkiemdau.vn) — Vietnamese savings-rate comparison

Scrapes deposit rates from bank websites twice a day, rebuilds a static page,
and deploys it to GitHub Pages for free. No server, no database.

```
scraper/banks/*.py    one adapter per bank: fetch() + parse()
scraper/run.py        fetch all banks, validate, write data/rates.json + data/history/<date>.json
scraper/build_site.py assemble site/ -> dist/ (all pages, rates.json, sitemap, robots, icons)
site/home.html        homepage (rate table + calculator)
site/pages/*.html     text pages; each becomes /<file-name>/ (title/description in the top comment)
scraper/pages.py      generated pages: /ngan-hang/<bank>/ for each bank with data, /ky-han/<n>-thang/ for
                      terms 1–36 months that at least 3 banks publish; all text computed from the data
site/partials/        shared style.css, header.html, footer.html (incl. sharing script)
site/static/          favicon, share image (og.png): copied to the site root
scraper/check.py      exit 1 if any bank failed (triggers GitHub's failure email)
tests/                parser tests against saved copies of each bank's page
.github/workflows/    the schedule (09:17 and 16:17 Vietnam time)
```

## Banks covered (01/11/2026)

| Bank | Source type | Counter | Online | Amount tiers |
|---|---|---|---|---|
| Vietcombank | JSON API | ✓ | ✓ | |
| BIDV | 2 JSON endpoints | ✓ | ✓ | |
| Agribank | HTML fragment | ✓ | | |
| ACB | HTML tables | ✓ | ✓ | ✓ |
| TPBank | HTML fragment (flaky server, retried) | ✓ | ✓ | |
| Sacombank | PDF at a fixed address | ✓ | ✓ | ✓ |
| OCB | PDF linked from the rate page | ✓ | ✓ | ✓ (online) |

Switched off: **VietinBank** (`scraper/banks/vietin.py`) — its site refuses
GitHub's servers (HTTP 405). Its rates matched Vietcombank and BIDV anyway.

Known issue (03/11/2026): **OCB** relaunched its website and its rate page
(`/vi/cong-cu/lai-suat`, still linked from OCB's own menu) returns 404, and the
old rate PDF was removed. OCB is left off the page until it comes back; if the
new page uses a different format, `scraper/banks/ocb.py` needs updating.

Checked and **not covered**: VPBank (rate sheet is a scanned PDF with no
text; would need OCR), MB (rates published only as an image), Techcombank,
LPBank, MSB, MBV, BVBank (rates load in ways not yet worked out).

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

## Affiliate links

Copy `data/affiliates.example.json` to `data/affiliates.json` and put your
tracking links in it, keyed by bank code (`vcb`, `bidv`, `vietin`, `agri`,
`acb`, `tpb`). A "Mở tài khoản …" link then appears under that bank's rows,
marked `rel="sponsored"` as Google requires for paid links.

## Adding a bank

Write `scraper/banks/<code>.py` with `CODE`, `NAME`, `SOURCE_URL`,
`fetch(session) -> str` and `parse(raw) -> (list[Rate], as_of)`, register it
in `scraper/banks/__init__.py`, add its page to `tests/fixtures/` and a test.
