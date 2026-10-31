# Sổ Lãi Suất — Vietnamese savings-rate comparison

Scrapes deposit rates from bank websites twice a day, rebuilds a static page,
and deploys it to GitHub Pages for free. No server, no database.

```
scraper/banks/*.py    one adapter per bank: fetch() + parse()
scraper/run.py        fetch all banks, validate, write data/rates.json + data/history/<date>.json
scraper/build_site.py fill site/template.html -> dist/ (index.html, rates.json, sitemap, robots)
scraper/check.py      exit 1 if any bank failed (triggers GitHub's failure email)
tests/                parser tests against saved copies of each bank's page
.github/workflows/    the schedule (09:17 and 16:17 Vietnam time)
```

## Banks covered (25/10/2026)

| Bank | Source type | Counter | Online | Amount tiers |
|---|---|---|---|---|
| Vietcombank | JSON API | ✓ | ✓ | |
| BIDV | 2 JSON endpoints | ✓ | ✓ | |
| VietinBank | HTML table | ✓ | | |
| Agribank | HTML fragment | ✓ | | |
| ACB | HTML tables | ✓ | ✓ | ✓ |
| TPBank | HTML fragment (flaky server, retried) | ✓ | ✓ | |

Checked and **not yet covered**: MB (rates published only as an image),
Techcombank (dated PDF files), VPBank, Sacombank, VIB (rates behind
interactive widgets; would need a headless browser).

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

## Affiliate links

Copy `data/affiliates.example.json` to `data/affiliates.json` and put your
tracking links in it, keyed by bank code (`vcb`, `bidv`, `vietin`, `agri`,
`acb`, `tpb`). A "Mở tài khoản …" link then appears under that bank's rows,
marked `rel="sponsored"` as Google requires for paid links.

## Adding a bank

Write `scraper/banks/<code>.py` with `CODE`, `NAME`, `SOURCE_URL`,
`fetch(session) -> str` and `parse(raw) -> (list[Rate], as_of)`, register it
in `scraper/banks/__init__.py`, add its page to `tests/fixtures/` and a test.
