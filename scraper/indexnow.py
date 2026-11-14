"""IndexNow: báo cho Bing (và các công cụ tìm kiếm dùng IndexNow) những trang vừa thay đổi.

  python3 indexnow.py prepare <dist> <site_url>   so nội dung từng trang trong sitemap với lần đăng trước
                                                   (tệp <site_url>/indexnow-state.json), ghi trạng thái mới vào
                                                   <dist>/indexnow-state.json và in danh sách URL đã đổi (JSON)
  python3 indexnow.py submit <site_url> '<json>' [<thư mục chứa tệp khoá>]
                                                   gửi danh sách URL tới api.indexnow.org (chạy sau khi đã đăng trang)

Khoá IndexNow nằm trong tệp /<KEY>.txt của trang (công khai theo thiết kế của IndexNow).
Chỉ so tiêu đề, mô tả và phần nội dung chính, để đổi chân trang hay thanh bên không làm mọi trang bị coi là "đã đổi".
Lỗi mạng không làm hỏng việc đăng trang: in cảnh báo và thoát bình thường.
"""
import hashlib, json, pathlib, re, sys, time, urllib.parse, urllib.request

KEY_FILE = re.compile(r"^[0-9a-f]{32}\.txt$")


def key_of(dist: pathlib.Path) -> str:
    keys = [p.stem for p in dist.iterdir() if KEY_FILE.match(p.name) and p.read_text().strip() == p.stem]
    if len(keys) != 1:
        raise SystemExit(f"need exactly one IndexNow key file in {dist}, found {keys}")
    return keys[0]


def page_hash(html: str) -> str:
    pick = lambda pat: (re.search(pat, html, re.S) or [None, ""])[1]
    body = pick(r"<main[^>]*>(.*?)</main>") or pick(r"</header>(.*?)<footer") or html
    body = re.sub(r"\?v=[0-9a-f]+", "", body)                       # đổi mã phiên bản tệp js/css không phải đổi nội dung
    parts = [pick(r"<title>(.*?)</title>"), pick(r'<meta name="description" content="([^"]*)"'), body]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:16]


def sitemap_urls(dist: pathlib.Path) -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", (dist / "sitemap.xml").read_text(encoding="utf-8"))


def file_for(dist: pathlib.Path, url: str) -> pathlib.Path:
    path = urllib.parse.urlparse(url).path.strip("/")
    return dist / path / "index.html" if path else dist / "index.html"


def fetch_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(f"{url}?t={int(time.time())}", timeout=20) as r:
            return json.load(r)
    except Exception as e:  # lần đầu chưa có tệp, hoặc mạng lỗi: coi như mọi trang đều mới
        print(f"indexnow: no previous state ({e.__class__.__name__}); all pages count as changed", file=sys.stderr)
        return {}


def prepare(dist: pathlib.Path, site: str, old: dict | None = None) -> list[str]:
    key_of(dist)
    old = fetch_json(site.rstrip("/") + "/indexnow-state.json") if old is None else old
    new, changed = {}, []
    for url in sitemap_urls(dist):
        f = file_for(dist, url)
        if not f.exists():
            continue
        new[url] = page_hash(f.read_text(encoding="utf-8"))
        if old.get(url) != new[url]:
            changed.append(url)
    (dist / "indexnow-state.json").write_text(json.dumps(new, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return changed


def submit(site: str, urls: list[str], key: str) -> None:
    if not urls:
        print("indexnow: nothing changed"); return
    host = urllib.parse.urlparse(site).netloc
    for i in range(0, len(urls), 10000):
        body = json.dumps({"host": host, "key": key, "keyLocation": f"{site.rstrip('/')}/{key}.txt",
                           "urlList": urls[i:i + 10000]}).encode()
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f"indexnow: sent {len(urls[i:i + 10000])} URLs, HTTP {r.status}")
        except Exception as e:
            print(f"indexnow: submit failed ({e}); pages are still published", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "prepare":
        print(json.dumps(prepare(pathlib.Path(sys.argv[2]), sys.argv[3])))
    elif cmd == "submit":
        submit(sys.argv[2], json.loads(sys.argv[3] or "[]"), key_of(pathlib.Path(sys.argv[4] if len(sys.argv) > 4 else "dist")))
    else:
        raise SystemExit(__doc__)
