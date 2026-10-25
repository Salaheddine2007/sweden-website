"""Publish one article: writes tools/posts/<slug>.html, rebuilds the site and runs QA.

Usage:
  python tools/publish_post.py --keyword "iptv sverige app" --slug iptv-sverige-app \
      --h1 "IPTV Sverige-app: ..." --title "<= 60 chars" --desc "120-155 chars" \
      --crumb "Kort namn" --article /tmp/article.html

The article file is the body only (no <html>, no <h1>; the H1 comes from --h1).
Refuses (exit 1, nothing written) when: slug already exists, < site.json min_words, no link to the
homepage trunk (href="/" or https://bastaiptvhd.se/), no link to /iptv-abonnemang/, no external link,
an <h1> inside the body, or QA fails after the build.
Prints "PUBLISHED <url> | words=N" on success.
"""
import argparse, json, os, re, subprocess, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SITE = json.load(open(os.path.join(TOOLS, "site.json"), encoding="utf-8"))

def fail(msg):
    print("ERROR:", msg)
    sys.exit(1)

def main():
    ap = argparse.ArgumentParser()
    for a in ("keyword", "slug", "h1", "title", "desc", "crumb", "tldr", "article"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--source", action="append", default=[], help='"Label|https://url", repeat 2-4 times')
    a = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", a.slug):
        fail(f"bad slug {a.slug!r}")
    src = os.path.join(TOOLS, "posts", a.slug + ".html")
    if os.path.exists(src) or os.path.exists(os.path.join(ROOT, a.slug)):
        fail(f"slug {a.slug} already exists")
    body = open(a.article, encoding="utf-8").read().strip()
    body = re.sub(r"(?is)^.*?<body[^>]*>|</body>.*$", "", body)
    if re.search(r"<h1[\s>]", body, re.I):
        fail("article body must not contain <h1> (pass it with --h1)")
    words = len(re.sub(r"<[^>]+>", " ", body).split())
    if words < SITE["min_words"]:
        fail(f"only {words} words, minimum is {SITE['min_words']}")
    if not re.search(r'href="(/|%s/?)"' % re.escape(SITE["base"]), body):
        fail('no link to the homepage trunk (href="/" with anchor text like "bästa IPTV")')
    if "/iptv-abonnemang/" not in body:
        fail("no link to /iptv-abonnemang/")
    if not re.search(r'href="https?://(?!(www\.)?bastaiptvhd\.se)', body):
        fail("no external link")
    heads = [re.sub(r"<[^>]+>", "", h).lower() for h in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", body, re.S)]
    kw_heads = sum(a.keyword.lower() in h for h in heads)
    if kw_heads > max(3, len(heads) // 4):
        fail(f"keyword in {kw_heads} of {len(heads)} headings - keep it in 2-3, write the rest naturally")
    claims = re.findall(r"(?i)kunder (?:använder|väljer|säger) (?:mest|oftast)|de flesta (?:av våra )?kunder|under \d+ minuter|inom \d+ minuter|tio minuter från|\d+ ?% av (?:våra|alla)", body)
    if claims:
        fail(f"unverifiable claim(s): {claims} - only use the confirmed facts")
    sources = []
    for s in a.source:
        label, _, url = s.partition("|")
        if not (label.strip() and re.match(r"https://", url.strip())):
            fail(f"bad --source {s!r}, use \"Label|https://url\"")
        sources.append([label.strip(), url.strip()])

    today = date.today().isoformat()
    meta = {"slug": a.slug, "tldr": a.tldr, "crumb": a.crumb, "keyword": a.keyword, "date": today, "updated": today,
            "h1": a.h1, "title": a.title, "desc": a.desc}
    if sources:
        meta["sources"] = sources
    os.makedirs(os.path.dirname(src), exist_ok=True)
    open(src, "w", encoding="utf-8", newline="\n").write("<!--" + json.dumps(meta, ensure_ascii=False) + "-->\n" + body + "\n")

    build = subprocess.run([sys.executable, os.path.join(TOOLS, "build_site.py")], capture_output=True, text=True)
    qa = subprocess.run([sys.executable, os.path.join(TOOLS, "qa.py")], capture_output=True, text=True)
    if build.returncode or qa.returncode:
        os.remove(src)
        subprocess.run([sys.executable, os.path.join(TOOLS, "build_site.py")], capture_output=True)
        fail("build/QA failed, post removed:\n" + build.stdout + build.stderr + qa.stdout + qa.stderr)
    print(f"PUBLISHED {SITE['base']}/blogg/{a.slug}/ | words={words}")

if __name__ == "__main__":
    main()
