"""Build the public site using only the Python standard library."""
import argparse
import datetime as dt
import html
import json
from pathlib import Path
import re
import shutil
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def validate_origin(value):
    parsed = urllib.parse.urlsplit(value)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or not host or "." not in host
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/") or parsed.port
            or host in {"localhost", "example.com", "example.org", "example.net"}
            or host.endswith((".test", ".invalid", ".localhost", ".example"))
            or re.fullmatch(r"[0-9.]+", host)):
        raise ValueError("Укажите реальный HTTPS-домен без пути, порта и параметров.")
    return f"https://{host.encode('idna').decode('ascii')}"


def render(template, values):
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    if re.search(r"\{\{\w+\}\}", template):
        raise ValueError("В шаблоне остались незаполненные поля")
    return template


def page_path(slug):
    return f"/{slug}/" if slug else "/"


def build(public=False, origin="", output=None):
    site = json.loads((ROOT / "content/site.json").read_text(encoding="utf-8"))
    pages = json.loads((ROOT / "content/pages.json").read_text(encoding="utf-8"))
    origin = validate_origin(origin or site["site_url"]) if public else ""
    output = Path(output) if output else ROOT / "dist"
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / ".build-manifest.json"
    previous = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    generated = {"robots.txt", "build-info.json"}
    generated.update("assets/" + p.relative_to(ROOT / "src/assets").as_posix() for p in (ROOT / "src/assets").rglob("*") if p.is_file())
    shutil.copytree(ROOT / "src/assets", output / "assets", dirs_exist_ok=True)
    template = (ROOT / "src/partials/layout.html").read_text(encoding="utf-8")
    escape = lambda value: html.escape(str(value), quote=True)
    contact = []
    if site.get("address"):
        contact.append(f'<p>{escape(site["address"])}</p>')
    if site.get("phone"):
        phone = re.sub(r"[^+0-9]", "", site["phone"])
        contact.append(f'<p><a href="tel:{escape(phone)}">{escape(site["phone"])}</a></p>')
    if site.get("email"):
        email = escape(site["email"])
        contact.append(f'<p><a href="mailto:{email}">{email}</a></p>')
    error = {"slug": "404", "label": "Страница не найдена", "title": "Страница не найдена — Медресе в Сибае",
             "description": "Страница не найдена. Перейдите на главную страницу медресе в Сибае.", "source": "404.html"}
    for page in pages + [error]:
        is_error = page["slug"] == "404"
        path = page_path(page["slug"])
        navigation = []
        for item in pages:
            if item["slug"] in ("about", "construction", "education", "contacts"):
                current = ' aria-current="page"' if page["slug"] == item["slug"] else ""
                navigation.append(f'<a href="{page_path(item["slug"])}"{current}>{escape(item["label"])}</a>')
        url_meta, schema = "", ""
        if public and not is_error:
            url_meta = f'<link rel="canonical" href="{escape(origin + path)}">\n<meta property="og:url" content="{escape(origin + path)}">'
            nodes = [
                {"@type": "WebSite", "@id": origin + "/#website", "url": origin + "/", "name": site["name"], "inLanguage": "ru"},
                {"@type": "WebPage", "@id": origin + path + "#webpage", "url": origin + path,
                 "name": page["title"], "description": page["description"], "inLanguage": "ru",
                 "isPartOf": {"@id": origin + "/#website"}}
            ]
            if page["slug"]:
                nodes.append({"@type": "BreadcrumbList", "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Главная", "item": origin + "/"},
                    {"@type": "ListItem", "position": 2, "name": page["label"], "item": origin + path}
                ]})
            payload = json.dumps({"@context": "https://schema.org", "@graph": nodes}, ensure_ascii=False).replace("<", "\\u003c")
            schema = f'<script type="application/ld+json">{payload}</script>'
        body = (ROOT / "src/pages" / page["source"]).read_text(encoding="utf-8")
        body = body.replace("{{contact_details}}", "\n".join(contact))
        values = {"title": escape(page["title"]), "description": escape(page["description"]),
                  "robots": "index, follow" if public and not is_error else "noindex, nofollow",
                  "url_meta": url_meta, "schema": schema, "body": body,
                  "navigation": "".join(navigation), "year": dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).year}
        target = output / "404.html" if is_error else output / page["slug"] / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(template, values), encoding="utf-8")
        generated.add(target.relative_to(output).as_posix())
    robots = "User-agent: *\nDisallow: /\n"
    sitemap_path = output / "sitemap.xml"
    if public:
        robots = ("User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /admin/\nDisallow: /account/\n"
                  "\nUser-agent: Yandex\nAllow: /\nDisallow: /api/\nDisallow: /admin/\nDisallow: /account/\n"
                  "Clean-param: utm_source&utm_medium&utm_campaign&utm_content&utm_term&yclid&gclid /\n"
                  f"\nSitemap: {origin}/sitemap.xml\n")
        namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
        ET.register_namespace("", namespace)
        urlset = ET.Element(f"{{{namespace}}}urlset")
        for page in pages:
            url = ET.SubElement(urlset, f"{{{namespace}}}url")
            ET.SubElement(url, f"{{{namespace}}}loc").text = origin + page_path(page["slug"])
        ET.ElementTree(urlset).write(sitemap_path, encoding="utf-8", xml_declaration=True)
        generated.add("sitemap.xml")
    elif sitemap_path.exists():
        sitemap_path.unlink()
    (output / "robots.txt").write_text(robots, encoding="utf-8")
    (output / "build-info.json").write_text(json.dumps({"public": public, "origin": origin, "pages": len(pages)}, ensure_ascii=False), encoding="utf-8")
    for old in set(previous) - generated:
        stale = (output / old).resolve()
        if output.resolve() not in stale.parents:
            raise ValueError("Unsafe stale build path")
        if stale.is_file():
            stale.unlink()
    manifest.write_text(json.dumps(sorted(generated)), encoding="utf-8")
    print(f"Собрано {len(pages)} страниц + 404: {output}. Режим: {'публичный' if public else 'закрытый предпросмотр'}.")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", action="store_true", help="Разрешить индексацию после согласования материалов")
    parser.add_argument("--site-url", default="", help="Настоящий HTTPS-домен для публичной сборки")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        build(args.public, args.site_url, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Ошибка сборки: {error}\n")
