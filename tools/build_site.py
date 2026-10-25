"""Build every page of bastaiptvhd.se from tools/pages/*.html (fixed pages) and tools/posts/*.html (articles).

Page source = JSON header in an HTML comment, then the body:
  <!--{"slug": "iptv-abonnemang", "title": "...", "desc": "...", "crumb": "Priser", "schema": [...]}-->
  Articles also carry "date", "updated", "keyword" and live under /blogg/<slug>/.
Body helpers: {{WA:message}} = WhatsApp order link with that pre-filled text;
[PLACEHOLDER: ...] is highlighted so missing real facts are impossible to miss.
Writes the pages, /blogg/ index, sitemap.xml and one OG image per page (tools/make_og.py).
Usage: python tools/build_site.py
"""
import html, json, os, re, sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
import make_og

SITE = json.load(open(os.path.join(TOOLS, "site.json"), encoding="utf-8"))
BASE = SITE["base"]
LAYOUT = open(os.path.join(TOOLS, "layout.html"), encoding="utf-8").read()
MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november", "december"]
ORG = {"@context": "https://schema.org", "@type": "Organization", "@id": BASE + "/#org", "name": SITE["name"], "url": BASE + "/",
       "logo": BASE + "/assets/icons/icon-512.png",
       "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "availableLanguage": ["sv", "en"], "url": BASE + "/kontakt/"}}
WEBSITE = {"@context": "https://schema.org", "@type": "WebSite", "@id": BASE + "/#site", "name": SITE["name"], "url": BASE + "/",
           "inLanguage": "sv-SE", "publisher": {"@id": BASE + "/#org"}}

def wa(msg):
    return f"https://api.whatsapp.com/send/?phone={SITE['whatsapp']}&amp;text={quote(msg)}"

def nice_date(iso):
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"

def read_source(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"\s*<!--(\{.*?\})-->\s*", raw, re.S)
    return json.loads(m.group(1)), raw[m.end():]

def crumbs(trail):
    """trail = [(name, url), ...] without Home; last item is the current page"""
    if not trail:
        return "", None
    full = [("Hem", BASE + "/")] + trail
    items = "".join(
        f'<li><a href="{u}">{html.escape(n)}</a></li>' if i < len(full) - 1 else f'<li aria-current="page">{html.escape(n)}</li>'
        for i, (n, u) in enumerate(full))
    schema = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(full)]}
    return f'<nav class="crumbs" aria-label="Brödsmulor"><ol class="wrap">{items}</ol></nav>', schema

def page(meta, body, url, trail, og_name, extra_schema=(), og_type="website"):
    crumb_html, crumb_schema = crumbs(trail)
    schema = [ORG, WEBSITE] + ([crumb_schema] if crumb_schema else []) + list(extra_schema)
    head = "\n".join(f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>' for s in schema)
    body = re.sub(r"\{\{WA:([^}]*)\}\}", lambda m: wa(m.group(1)), body)
    out = LAYOUT
    for k, v in {"TITLE": html.escape(meta["title"]), "DESC": html.escape(meta["desc"]), "URL": url, "OG_TYPE": og_type,
                 "ROBOTS": meta.get("robots", "index, follow, max-image-preview:large"), "HEAD": head,
                 "OG_IMAGE": f"{BASE}/assets/og/{og_name}.png", "CRUMBS": crumb_html,
                 "WA_DEFAULT": wa("Hej! Jag vill beställa Bästa IPTV HD."), "WA_DISPLAY": SITE["whatsapp_display"],
                 "BODY": body}.items():
        out = out.replace("{{%s}}" % k, v)
    # wide tables scroll sideways on phones: make that region reachable by keyboard
    n = iter(range(1, 99))
    out = re.sub(r'<div class="table-wrap">', lambda m: f'<div class="table-wrap" tabindex="0" role="region" aria-label="Tabell {next(n)}, kan rullas i sidled">', out)
    path = "/" + url[len(BASE):].lstrip("/")
    out = out.replace(f'<a href="{path}">', f'<a href="{path}" aria-current="page">', 1) if path != "/" else out
    return re.sub(r"\[PLACEHOLDER:[^\]]*\]", lambda m: f'<span class="ph">{m.group(0)}</span>', out)

def slug_id(text):
    import unicodedata
    t = unicodedata.normalize("NFKD", html.unescape(re.sub(r"<[^>]+>", "", text))).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60]

def enrich(body, meta, og_name):
    """Rank Math helpers for pages with a focus keyword: ids on H2s, a table of contents ("Innehåll")
    and a featured image whose alt text carries the keyword. Placed at <!--TOC--> / <!--FIGURE-->
    markers when the source has them, otherwise right after the first paragraph."""
    seen = set()
    def add_id(m):
        if "id=" in m.group(1):
            return m.group(0)
        i = slug_id(m.group(2)) or "avsnitt"
        while i in seen:
            i += "-2"
        seen.add(i)
        return f'<h2{m.group(1)} id="{i}">{m.group(2)}</h2>'
    body = re.sub(r"<h2([^>]*)>(.*?)</h2>", add_id, body, flags=re.S)
    if not meta.get("keyword"):
        return body
    heads = [(i, h) for i, h in re.findall(r'<h2[^>]*id="([^"]+)"[^>]*>(.*?)</h2>', body, re.S) if "Läs vidare" not in h]
    block = ""
    if meta.get("toc", True) and len(heads) >= 4:
        items = "".join(f'<li><a href="#{i}">{re.sub(r"<[^>]+>", "", t).strip()}</a></li>' for i, t in heads)
        block += f'<nav class="toc" aria-label="Innehåll"><p class="toc-title">Innehåll</p><ol>{items}</ol></nav>'
    fig = (f'<figure class="feature"><img src="/assets/og/{og_name}.webp" width="1200" height="630" loading="lazy" decoding="async" '
           f'alt="{html.escape(meta.get("img_alt") or meta["keyword"].capitalize() + ": " + meta.get("h1", meta["title"]))}"></figure>')
    if "<!--FIGURE-->" in body:
        body = body.replace("<!--FIGURE-->", fig, 1)
    else:
        block = fig + block
    if "<!--TOC-->" in body:
        return body.replace("<!--TOC-->", block, 1)
    i = body.find("</p>")
    return body[:i + 4] + block + body[i + 4:] if i >= 0 else block + body

def write(rel, text):
    path = os.path.join(ROOT, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="\n").write(text)

def load_posts():
    d = os.path.join(TOOLS, "posts")
    posts = []
    for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        meta, body = read_source(os.path.join(d, fn))
        meta["url"] = f"{BASE}/blogg/{meta['slug']}/"
        posts.append((meta, body))
    posts.sort(key=lambda p: (p[0]["date"], p[0]["slug"]))
    return posts

def article(meta, body, prev, nxt):
    """wrap an article body with head, author box, related links and prev/next"""
    updated = meta.get("updated", meta["date"])
    head = (f'<section class="page-head"><div class="wrap"><span class="eyebrow">Guide</span><h1>{html.escape(meta["h1"])}</h1>'
            f'<p class="post-meta">Publicerad <time datetime="{meta["date"]}">{nice_date(meta["date"])}</time>'
            f' · Uppdaterad <time datetime="{updated}">{nice_date(updated)}</time></p></div></section>')
    author = ('<aside class="author" aria-label="Om skribenten"><div class="author-pic" aria-hidden="true">B</div><div>'
              f'<p><strong>{html.escape(SITE["author"]["name"])}</strong></p><p>{SITE["author"]["bio"]}</p></div></aside>')
    pn = ""
    if prev or nxt:
        pn = '<nav class="pn" aria-label="Fler guider">'
        if prev:
            pn += f'<a class="prev" href="{prev["url"]}" rel="prev"><small>Föregående guide</small>{html.escape(prev["h1"])}</a>'
        if nxt:
            pn += f'<a class="next" href="{nxt["url"]}" rel="next"><small>Nästa guide</small>{html.escape(nxt["h1"])}</a>'
        pn += "</nav>"
    return f'{head}<div class="wrap"><article class="prose">{body}{author}{pn}</article></div>'

def article_schema(meta):
    return {"@context": "https://schema.org", "@type": "Article", "headline": meta["h1"], "description": meta["desc"],
            "inLanguage": "sv-SE", "datePublished": meta["date"], "dateModified": meta.get("updated", meta["date"]),
            "mainEntityOfPage": meta["url"], "image": f"{BASE}/assets/og/blogg-{meta['slug']}.png",
            "author": {"@type": SITE["author"]["type"], "name": SITE["author"]["name"], "url": BASE + "/om-oss/"},
            "publisher": {"@id": BASE + "/#org"}}

def blog_index(posts):
    items = "".join(
        f'<li><a href="{m["url"]}"><time datetime="{m["date"]}">{nice_date(m["date"])}</time>'
        f'<h2>{html.escape(m["h1"])}</h2><p>{html.escape(m["desc"])}</p></a></li>' for m, _ in reversed(posts))
    body = ('<section class="page-head"><div class="wrap"><span class="eyebrow">Guider</span><h1>Guider om IPTV i Sverige</h1>'
            '<p>Installation, appar, bildkvalitet och felsökning. Vi skriver om sådant kunder faktiskt frågar oss om. '
            'Vill du hellre läsa om priserna finns de på <a href="/iptv-abonnemang/" style="color:var(--signal-soft)">sidan om IPTV-abonnemang</a>.</p></div></section>'
            f'<div class="wrap"><ul class="posts">{items}</ul></div>')
    meta = {"title": "Guider om IPTV i Sverige: appar, installation och felsökning",
            "desc": "Guider om IPTV i Sverige: välj app, installera på Smart TV och Apple TV, få 4K att flyta och lös hackande bild. Skrivna av vår support."}
    return page(meta, body, BASE + "/blogg/", [("Guider", BASE + "/blogg/")], "blogg",
                [{"@context": "https://schema.org", "@type": "Blog", "name": "Guider – Bästa IPTV HD", "url": BASE + "/blogg/", "inLanguage": "sv-SE"}])

def main():
    sitemap, og = [], []
    src = os.path.join(TOOLS, "pages")
    for fn in sorted(os.listdir(src)):
        meta, body = read_source(os.path.join(src, fn))
        slug = meta["slug"]
        url = BASE + "/" + (slug + "/" if slug else "")
        trail = [(meta["crumb"], url)] if slug and slug != "404" else []
        name = slug or "home"
        doc = page(meta, enrich(body, meta, name), url, trail, name, meta.get("schema", []))
        og.append((name, meta.get("og", meta["title"])))
        if slug == "404":
            write("404.html", doc.replace(f'<link rel="canonical" href="{url}">\n', ""))
            continue
        write((slug + "/" if slug else "") + "index.html", doc)
        if "noindex" not in meta.get("robots", ""):
            sitemap.append((url, meta.get("updated", SITE["launched"])))
    posts = load_posts()
    for i, (meta, body) in enumerate(posts):
        prev = posts[i - 1][0] if i else None
        nxt = posts[i + 1][0] if i + 1 < len(posts) else None
        trail = [("Guider", BASE + "/blogg/"), (meta["crumb"], meta["url"])]
        schema = [article_schema(meta)] + meta.get("schema", [])
        body = enrich(body, meta, "blogg-" + meta["slug"])
        write(f"blogg/{meta['slug']}/index.html",
              page(meta, article(meta, body, prev, nxt), meta["url"], trail, "blogg-" + meta["slug"], schema, "article"))
        og.append(("blogg-" + meta["slug"], meta["h1"]))
        sitemap.append((meta["url"], meta.get("updated", meta["date"])))
    # moved pages: noindex stub with canonical + instant refresh (GitHub Pages has no server-side 301)
    for old, new in SITE.get("redirects", {}).items():
        u = BASE + new
        write(old.strip("/") + "/index.html",
              f'<!DOCTYPE html><html lang="sv"><head><meta charset="UTF-8"><title>Sidan har flyttat</title>'
              f'<link rel="canonical" href="{u}"><meta name="robots" content="noindex, follow">'
              f'<meta http-equiv="refresh" content="0; url={u}"><script>location.replace("{u}")</script></head>'
              f'<body><p>Sidan har flyttat till <a href="{u}">{u}</a>.</p></body></html>\n')
    write("blogg/index.html", blog_index(posts))
    og.append(("blogg", "Guider om IPTV i Sverige"))
    sitemap.append((BASE + "/blogg/", posts[-1][0]["date"] if posts else SITE["launched"]))
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u, lm in sitemap:
            f.write(f"  <url><loc>{u}</loc><lastmod>{lm}</lastmod></url>\n")
        f.write("</urlset>\n")
    made = make_og.build(os.path.join(ROOT, "assets", "og"), og)
    print(f"built {len(sitemap)} indexable urls ({len(posts)} articles), 404, sitemap, {made} new og images")

if __name__ == "__main__":
    main()
