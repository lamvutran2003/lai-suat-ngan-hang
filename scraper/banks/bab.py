"""Bac A Bank — ASP.NET page; the VND table appears after a postback that picks 'VNĐ' in a dropdown.

Only counter rates are published there (no online table). We read the 'Lĩnh lãi cuối kỳ' column.
The 'VNĐ50ty' option (deposits of 50 tỷ and more) is not compared.
"""
import re
from urllib.parse import urljoin

from ..common import ParseError, Rate, clean, parse_rate, parse_term_months, soup

CODE = "bab"
NAME = "Bac A Bank"
SOURCE_URL = "https://www.baca-bank.vn/SitePages/website/lai-xuat.aspx?ac=L%25u00e3i%252520su%25u1ea5t&s=LX"
OPTION = "VND|VNĐ"


def fetch(session) -> str:
    r = session.get(SOURCE_URL, timeout=30)
    r.raise_for_status()
    doc = soup(r.text)
    form = doc.find("form")
    sel = doc.find("select", id=lambda x: x and x.endswith("DDL_LS"))
    if not form or not sel:
        raise ParseError("Bac A Bank: currency dropdown not found")
    data = {i["name"]: i.get("value", "") for i in form.find_all("input") if i.get("name") and i.get("type") in ("hidden", None)}
    data.update({"__EVENTTARGET": sel["name"], "__EVENTARGUMENT": "", sel["name"]: OPTION})
    r = session.post(urljoin(SOURCE_URL, form.get("action") or SOURCE_URL), data=data, timeout=30,
                     headers={"Referer": SOURCE_URL})
    r.raise_for_status()
    return r.text


def parse(raw: str):
    doc = soup(raw)
    sel = doc.find("select", id=lambda x: x and x.endswith("DDL_LS"))
    chosen = sel.find("option", selected=True) if sel else None
    if not chosen or chosen.get("value") != OPTION:
        raise ParseError("Bac A Bank: page is not showing the VND table")
    table = doc.find("table")
    rows = [[clean(c.get_text(" ")) for c in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]
    m = re.search(r"hiệu lực từ ngày (\d{1,2})/(\d{1,2})/(\d{4})", " ".join(rows[0]) if rows else "", re.I)
    as_of = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None
    rates = []
    for row in rows:
        if len(row) != 4 or "*" in row[0]:
            continue
        months = parse_term_months(row[0])
        value = parse_rate(row[3])                      # Lĩnh lãi cuối kỳ
        if months and value:
            rates.append(Rate(CODE, "counter", months, value))
    return rates, as_of
