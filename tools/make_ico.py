"""Ghép favicon.ico (16, 32, 48 px) từ favicon-256.tmp.png do tools/make_icons.js tạo, rồi xoá tệp tạm."""
from pathlib import Path
from PIL import Image

S = Path(__file__).resolve().parents[1] / "site" / "static"
src = S / "favicon-256.tmp.png"
Image.open(src).save(S / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
src.unlink()
print("wrote favicon.ico")
