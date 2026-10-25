"""Site QA: run after tools/build_site.py. Exit code 1 if anything is wrong.
Checks every built page for title/description length, canonical, exactly one H1, OG tags, valid JSON-LD,
3+ internal links, broken internal links, orphan pages, banned phrases, and lists [PLACEHOLDER]s.
Usage: python tools/qa.py [--placeholders]
"""
import html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = json.load(open(os.path.join(ROOT, "tools", "site.json"), encoding="utf-8"))["base"]
# brief section 5 + Swedish equivalents
BANNED = re.compile(r"\b(delve|unlock|elevate|seamless|robust|game[- ]changer|look no further|cutting[- ]edge|unleash|"
                     r"dive into|tapestry|landscape|embark|"
                     r"sömlös\w*|banbrytande|revolutionerande|lås upp|i dagens snabba|oavsett om du är|"
                     r"leta inte längre|det är viktigt att notera|sammanfattningsvis|dyk in|dyka ner i|"
                     r"spjutspets\w*|nästa nivå|skräddarsydd\w*|oöverträffad\w*)\b", re.I)

def pages():
    for dp, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "tools", "assets")]
        for f in files:
            if f.endswith(".html"):
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
                url = "/" + ("" if rel == "index.html" else rel[:-len("index.html")]) if rel.endswith("index.html") else "/" + rel
                yield url, open(p, encoding="utf-8").read()

def main():
    problems, linked, exists, ph = [], {}, set(), []
    all_pages = dict(pages())
    exists = set(all_pages)
    for url, doc in all_pages.items():
        def bad(msg): problems.append(f"{url}: {msg}")
        title = html.unescape(re.search(r"<title>(.*?)</title>", doc, re.S).group(1))
        desc = html.unescape(re.search(r'<meta name="description" content="([^"]*)"', doc).group(1))
        if url != "/404.html":
            if not 40 <= len(title) <= 62: bad(f"title {len(title)} chars: {title}")
            if not 120 <= len(desc) <= 160: bad(f"description {len(desc)} chars")
            if '<link rel="canonical"' not in doc: bad("no canonical")
        n_h1 = len(re.findall(r"<h1[\s>]", doc))
        if n_h1 != 1: bad(f"{n_h1} H1")
        for tag in ("og:title", "og:description", "og:image", "og:url"):
            if f'property="{tag}"' not in doc: bad(f"missing {tag}")
        og = re.search(r'property="og:image" content="([^"]+)"', doc).group(1)
        if not os.path.exists(os.path.join(ROOT, og[len(BASE) + 1:])): bad(f"og image missing {og}")
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
            try: json.loads(block)
            except ValueError as e: bad(f"JSON-LD invalid: {e}")
        main_part = doc[doc.find("<main"):doc.find("</main>")]
        text = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", " ", main_part, flags=re.S))
        for m in BANNED.finditer(text): bad(f"banned phrase: {m.group(0)}")
        ph += [(url, p) for p in re.findall(r"\[PLACEHOLDER:[^\]]*\]", doc)]
        internal = set()
        for href in re.findall(r'href="([^"#?]+)', doc):
            if href.startswith(BASE): href = href[len(BASE):] or "/"
            if not href.startswith("/") or href.startswith("//") or href.startswith("/assets") or "." in href.rsplit("/", 1)[-1]:
                continue
            if href not in exists: bad(f"broken link {href}")
            if href != url: internal.add(href)
        body_links = {h for h in re.findall(r'href="((?:%s)?/[^"#?]*)"' % re.escape(BASE), main_part)}
        if url != "/404.html" and len(body_links) < 3: bad(f"only {len(body_links)} internal links in content")
        for h in internal: linked.setdefault(h, set()).add(url)
    for url in exists:
        if url not in ("/", "/404.html") and not linked.get(url):
            problems.append(f"{url}: orphan (no page links to it)")
    print(f"{len(exists)} pages checked, {len(problems)} problems, {len(ph)} placeholders")
    for p in problems: print("  FAIL", p)
    if "--placeholders" in sys.argv:
        seen = {}
        for u, p in ph: seen.setdefault(p, set()).add(u)
        for p, us in seen.items(): print(f"  {p}  ->  {', '.join(sorted(us))}")
    sys.exit(1 if problems else 0)

if __name__ == "__main__":
    main()
