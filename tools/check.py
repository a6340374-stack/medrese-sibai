"""Verify generated metadata, structured data, assets, links and indexing mode."""
import json
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import urlsplit, unquote
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1 = 0
        self.ids = set()
        self.refs = []
        self.meta = {}
        self.title = ""
        self.in_title = False
        self.schema = []
        self.in_schema = False
        self.canonical = ""
        self.lang = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.h1 += tag == "h1"
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "html":
            self.lang = attrs.get("lang", "")
        if tag == "title":
            self.in_title = True
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.in_schema = True
        if tag == "meta":
            self.meta[attrs.get("name", attrs.get("property", ""))] = attrs.get("content", "")
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href", "")
        for key in ("href", "src"):
            if key in attrs:
                self.refs.append(attrs[key])

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script":
            self.in_schema = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_schema:
            self.schema.append(json.loads(data))


def check(output):
    output = Path(output)
    info = json.loads((output / "build-info.json").read_text(encoding="utf-8"))
    base_path = info.get("base_path", "")
    parsed, errors = {}, []
    for file in sorted(output.rglob("*.html")):
        parser = Page()
        source = file.read_text(encoding="utf-8")
        parser.feed(source)
        relative = file.relative_to(output).as_posix()
        parsed[relative] = parser
        for condition, message in [
            (parser.h1 == 1, "должен быть один h1"),
            (bool(parser.title.strip()), "нет title"),
            (bool(parser.meta.get("description")), "нет description"),
            (parser.lang == "ru", "нет русского lang"),
            ("{{" not in source, "не заполнен шаблон"),
            ("viewport" in parser.meta, "нет viewport"),
        ]:
            if not condition:
                errors.append(f"{relative}: {message}")
        indexable = info["public"] and relative != "404.html"
        if indexable:
            path = "/" if relative == "index.html" else "/" + relative.removesuffix("index.html")
            if parser.canonical != info["origin"] + path:
                errors.append(f"{relative}: неверный canonical")
            if parser.meta.get("robots") != "index, follow" or not parser.schema:
                errors.append(f"{relative}: неверный robots/schema")
        elif "noindex" not in parser.meta.get("robots", ""):
            errors.append(f"{relative}: предпросмотр/404 должен иметь noindex")
    for field in ("title", "description"):
        values = [page.title if field == "title" else page.meta.get(field) for page in parsed.values()]
        if len(set(values)) != len(values):
            errors.append(f"Повторяющиеся {field}")
    for relative, page in parsed.items():
        for ref in page.refs:
            url = urlsplit(ref)
            if url.scheme or url.netloc:
                continue
            local_path = url.path
            if local_path.startswith("/") and base_path:
                if not local_path.startswith(base_path + "/"):
                    errors.append(f"{relative}: ссылка вне пути проекта: {ref}")
                    continue
                local_path = local_path[len(base_path):]
            target = output / unquote(local_path.lstrip("/")) if local_path.startswith("/") else output / Path(relative).parent / unquote(local_path)
            if not url.path:
                target = output / relative
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                errors.append(f"{relative}: не найдено {ref}")
            elif url.fragment and target.suffix == ".html":
                dest = target.relative_to(output).as_posix()
                if dest not in parsed or unquote(url.fragment) not in parsed[dest].ids:
                    errors.append(f"{relative}: не найден якорь {ref}")
    robots = (output / "robots.txt").read_text(encoding="utf-8")
    sitemap = output / "sitemap.xml"
    if info["public"]:
        urls = [item.text for item in ET.parse(sitemap).findall(".//{*}loc")]
        expected = {p.canonical for key, p in parsed.items() if key != "404.html"}
        if set(urls) != expected or len(urls) != len(expected):
            errors.append("Sitemap не совпадает с canonical")
        if f'Sitemap: {info["origin"]}/sitemap.xml' not in robots:
            errors.append("Нет sitemap в robots")
    elif "Disallow: /\n" not in robots or sitemap.exists():
        errors.append("Предпросмотр должен быть закрыт, без sitemap")
    if errors:
        raise ValueError("\n".join(errors))
    print(f"OK: {len(parsed)} HTML, уникальные метаданные, ссылки, ресурсы и режим индексации.")


if __name__ == "__main__":
    try:
        check(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist")
    except (ValueError, OSError, ET.ParseError) as error:
        raise SystemExit(f"Ошибка проверки: {error}")
