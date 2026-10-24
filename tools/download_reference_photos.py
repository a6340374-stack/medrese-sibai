"""Download photographs used by the public site."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1] / "src/assets/images"
PHOTOS = {
    "college-photo-1.jpg": "https://cdn.mechet.ru/uploads/2026/04/27/30462c08be9d4f639c3e56be00484db9.jpg",
    "college-photo-3.jpg": "https://cdn.mechet.ru/uploads/2026/04/27/d50a8b1e80b54a2ea776eada5bbc425b.jpg",
    "college-2013.jpg": "https://upload.wikimedia.org/wikipedia/commons/d/d1/%D0%9C%D0%B5%D0%B4%D1%80%D0%B5%D1%81%D0%B5_%D0%B3._%D0%A1%D0%B8%D0%B1%D0%B0%D0%B9.jpg",
}


def download(item):
    name, url = item
    target = ROOT / name
    if target.exists() and target.read_bytes()[:2] == b"\xff\xd8":
        return f"{name}: already downloaded"
    if "cdn.mechet.ru" in url:
        url = "https://islamic-college.ru/_next/image?url=" + quote(url, safe="") + "&w=828&q=75"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=45) as response:
        data = response.read()
        if not response.headers.get_content_type().startswith("image/") or data[:2] != b"\xff\xd8":
            raise ValueError(f"Not a JPEG: {name}")
    target.write_bytes(data)
    return f"{name}: {len(data)} bytes"


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(download, PHOTOS.items()):
            print(result, flush=True)
