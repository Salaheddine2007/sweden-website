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
# cache-busting: ?v=<content hash> on the stylesheet and script so a new build is never hidden by browser cache
import hashlib
for asset in ("site.css", "site.js"):
    v = hashlib.md5(open(os.path.join(ROOT, "assets", asset), "rb").read()).hexdigest()[:8]
    LAYOUT = LAYOUT.replace(f'/assets/{asset}"', f'/assets/{asset}?v={v}"')
MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november", "december"]
ORG = {"@context": "https://schema.org", "@type": "Organization", "@id": BASE + "/#org", "name": SITE["name"], "url": BASE + "/",
       "logo": BASE + "/assets/icons/icon-512.png", "areaServed": "SE", "publishingPrinciples": BASE + "/om-oss/#sa-skriver-vi",
       "description": "BästaIPTVHD säljer IPTV-abonnemang med svenska och nordiska kanaler i HD till hushåll i Sverige, med beställning och support via WhatsApp.",
       "knowsAbout": ["IPTV", "IPTV Sverige", "Nordic IPTV", "Smart TV", "Apple TV", "Android TV", "Fire TV Stick", "EPG"],
       "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "availableLanguage": ["sv", "en"], "url": BASE + "/kontakt/"}}
WEBSITE = {"@context": "https://schema.org", "@type": "WebSite", "@id": BASE + "/#site", "name": SITE["name"], "url": BASE + "/",
           "inLanguage": "sv-SE", "publisher": {"@id": BASE + "/#org"}}

# inline SVG icons (Lucide style, 24x24 stroke); use {{I:name}} in page sources
ICONS = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "tv": '<rect x="2" y="7" width="20" height="15" rx="2"/><path d="m17 2-5 5-5-5"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "phone": '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>',
    "box": '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20"/>',
    "spark": '<path d="M12 3l1.9 5.8L20 10l-6.1 1.2L12 17l-1.9-5.8L4 10l6.1-1.2z"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "film": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4M17 8h4M3 16h4M17 16h4"/>',
    "wifi": '<path d="M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M2 9a15 15 0 0 1 20 0"/><path d="M12 20h.01"/>',
    "chat": '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-4-1L3 20l1.2-4.4A8.4 8.4 0 1 1 21 11.5z"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    "laptop": '<path d="M4 16V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10M2 20h20"/>',
    "zap": '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
}

def icon(name):
    return f'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'

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

MONTH_NAMES = {"1": "1 månad", "3": "3 månader", "6": "6 månader", "12": "12 månader"}

def devices(body):
    """<!--DEVICES--> = 1/2/3-device picker (site.js swaps [data-pp] prices, [data-pm] per month, [data-pwa] links);
    <!--PRICETABLE--> = every price as a plain table, readable without JavaScript"""
    if "<!--DEVICES-->" in body:
        btns = "".join(f'<button type="button" role="radio" aria-checked="{str(d == "1").lower()}" tabindex="{0 if d == "1" else -1}" data-dev="{d}">'
                       f'<b>{d}</b> {"enhet" if d == "1" else "enheter"}</button>' for d in SITE["prices"])
        pick = (f'<div class="dev-pick"><p class="dev-q" id="dev-q">Hur många skärmar vill ni titta på samtidigt?</p>'
                f'<div class="seg" role="radiogroup" aria-labelledby="dev-q">{btns}</div></div>'
                f'<script type="application/json" id="prices">{json.dumps(SITE["prices"])}</script>')
        body = body.replace("<!--DEVICES-->", pick, 1)
    if "<!--PRICETABLE-->" in body:
        heads = "".join(f'<th scope="col">{d} {"enhet" if d == "1" else "enheter"}</th>' for d in SITE["prices"])
        rows = "".join(f'<tr><th scope="row">{name}</th>' + "".join(
                   f'<td>{SITE["prices"][d][m]} kr' + (f'<small>{round(SITE["prices"][d][m] / int(m))} kr/mån</small>' if m != "1" else "") + '</td>'
                   for d in SITE["prices"]) + '</tr>' for m, name in MONTH_NAMES.items())
        table = (f'<div class="table-wrap"><table class="dev-table"><caption>Alla priser för 1, 2 och 3 enheter</caption>'
                 f'<thead><tr><th scope="col">Paket</th>{heads}</tr></thead><tbody>{rows}</tbody></table></div>')
        body = body.replace("<!--PRICETABLE-->", table, 1)
    return body

def page(meta, body, url, trail, og_name, extra_schema=(), og_type="website"):
    crumb_html, crumb_schema = crumbs(trail)
    schema = [ORG, WEBSITE] + ([crumb_schema] if crumb_schema else []) + list(extra_schema)
    if meta.get("tldr") or meta.get("speakable"):
        schema.append({"@context": "https://schema.org", "@type": "WebPage", "@id": url + "#webpage", "url": url, "name": meta["title"],
                       "inLanguage": "sv-SE", "isPartOf": {"@id": BASE + "/#site"}, "dateModified": meta.get("updated", SITE["launched"]),
                       "speakable": {"@type": "SpeakableSpecification", "cssSelector": [".kort", ".facts", "h1"]}})
    head = "\n".join(f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>' for s in schema)
    body = devices(body)
    body = re.sub(r"\{\{WA:([^}]*)\}\}", lambda m: wa(m.group(1)), body)
    body = re.sub(r"\{\{I:([a-z]+)\}\}", lambda m: icon(m.group(1)), body)
    out = LAYOUT
    for k, v in {"TITLE": html.escape(meta["title"]), "DESC": html.escape(meta["desc"]), "URL": url, "OG_TYPE": og_type,
                 "ROBOTS": meta.get("robots", "index, follow, max-image-preview:large"), "HEAD": head,
                 "OG_IMAGE": f"{BASE}/assets/og/{og_name}.png", "CRUMBS": crumb_html,
                 "WA_DEFAULT": wa("Hej! Jag vill beställa BästaIPTVHD."), "WA_DISPLAY": SITE["whatsapp_display"],
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

def kort(meta):
    return (f'<aside class="kort" aria-label="Kort svar"><div class="kort-title">Kort svar</div>'
            f'<p>{html.escape(meta["tldr"])}</p></aside>')

def enrich(body, meta, og_name):
    """Rank Math helpers for pages with a focus keyword: ids on H2s, a table of contents ("Innehåll")
    and a featured image whose alt text carries the keyword. Placed at <!--TOC--> / <!--FIGURE-->
    markers when the source has them, otherwise right after the first paragraph."""
    tldr_done = False
    if meta.get("tldr") and "<!--TOC-->" in body:
        body = body.replace("<!--TOC-->", kort(meta) + "<!--TOC-->", 1); tldr_done = True
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
    for im in meta.get("images", []):  # extra in-content images: <!--IMG:name-->
        body = body.replace(f"<!--IMG:{im['name']}-->",
            f'<figure class="feature"><img src="/assets/og/{im["name"]}.webp" width="1200" height="630" loading="lazy" '
            f'decoding="async" alt="{html.escape(im["alt"])}"></figure>', 1)
    if "<!--FIGURE-->" in body:
        body = body.replace("<!--FIGURE-->", fig, 1)
    else:
        block = fig + block
    if "<!--TOC-->" in body:
        return body.replace("<!--TOC-->", block, 1)
    i = body.find("</p>")
    body = body[:i + 4] + block + body[i + 4:] if i >= 0 else block + body
    return (kort(meta) + body) if meta.get("tldr") and not tldr_done else body

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
    author = ('<aside class="author" aria-label="Om skribenten"><img class="author-pic" src="/assets/icons/mark.svg" width="56" height="56" alt=""><div>'
              f'<p><strong>{html.escape(SITE["author"]["name"])}</strong></p><p>{SITE["author"]["bio"]} '
              '<a href="/om-oss/#sa-skriver-vi">Så skriver vi guiderna</a>.</p></div></aside>')
    sources = ""
    if meta.get("sources"):
        items = "".join(f'<li><a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(n)}</a></li>' for n, u in meta["sources"])
        sources = f'<aside class="sources" aria-label="Källor"><p class="sources-h">Källor och officiella hjälpsidor</p><ul>{items}</ul></aside>'
    pn = ""
    if prev or nxt:
        pn = '<nav class="pn" aria-label="Fler guider">'
        if prev:
            pn += f'<a class="prev" href="{prev["url"]}" rel="prev"><small>Föregående guide</small>{html.escape(prev["h1"])}</a>'
        if nxt:
            pn += f'<a class="next" href="{nxt["url"]}" rel="next"><small>Nästa guide</small>{html.escape(nxt["h1"])}</a>'
        pn += "</nav>"
    return f'{head}<div class="wrap"><article class="prose">{body}{sources}{author}{pn}</article></div>'

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
                [{"@context": "https://schema.org", "@type": "Blog", "name": "Guider – BästaIPTVHD", "url": BASE + "/blogg/", "inLanguage": "sv-SE"},
                 {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
                     {"@type": "ListItem", "position": i + 1, "url": m["url"], "name": m["h1"]} for i, (m, _) in enumerate(posts)]}])

def llms_txt(posts):
    """/llms.txt: a plain summary of the site for AI assistants (llmstxt.org format)"""
    pages = []
    for fn in sorted(os.listdir(os.path.join(TOOLS, "pages"))):
        meta, _ = read_source(os.path.join(TOOLS, "pages", fn))
        if meta["slug"] in ("404",) or "noindex" in meta.get("robots", ""):
            continue
        pages.append((meta["title"], BASE + "/" + (meta["slug"] + "/" if meta["slug"] else ""), meta.get("tldr") or meta["desc"]))
    out = [f"# {SITE['name']}", "",
           "> BästaIPTVHD säljer IPTV-abonnemang med svenska och nordiska kanaler i HD till svenska hushåll. "
           "Beställning, betalning och hjälp med installationen sker via WhatsApp.", "",
           "## Fakta", ""]
    out += [f"- {k}: {v}" for k, v in SITE["facts"]]
    pages.sort(key=lambda x: (x[1] != BASE + "/", x[1]))  # homepage first
    out += ["", "## Sidor", ""] + [f"- [{t}]({u}): {d}" for t, u, d in pages]
    out += ["", "## Guider", ""] + [f"- [{m['h1']}]({m['url']}): {m.get('tldr') or m['desc']}" for m, _ in posts]
    out += ["", f"Senast uppdaterad: {max([SITE['launched']] + [m.get('updated', m['date']) for m, _ in posts])}", ""]
    return "\n".join(out)

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
        og += [(im["name"], im["title"]) for im in meta.get("images", [])]
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
    write("llms.txt", llms_txt(posts))
    made = make_og.build(os.path.join(ROOT, "assets", "og"), og)
    print(f"built {len(sitemap)} indexable urls ({len(posts)} articles), 404, sitemap, {made} new og images")

if __name__ == "__main__":
    main()
