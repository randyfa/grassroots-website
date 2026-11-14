#!/usr/bin/env python3
"""Build the topic pages for grassrootsconversations.com.

Reads   content/topics/*.md
Writes  public/topics/index.html        (topic menu)
        public/topics/<slug>.html       (one page per topic)
        public/downloads/<slug>.pdf     (printable copy, needs Chrome/Chromium)
        public/downloads/<slug>.txt     (plain-text copy)
and refreshes the topic list on public/resources.html between the
<!-- TOPICS:START --> and <!-- TOPICS:END --> markers.

Standard library only. Run from anywhere:  python3 tools/build.py
Cloudflare does not run this script; commit the generated files in public/.
"""
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "topics"
PUBLIC = ROOT / "public"
TOPICS_OUT = PUBLIC / "topics"
DOWNLOADS_OUT = PUBLIC / "downloads"

NAV = [
    ("index.html", "Home"),
    ("about.html", "About"),
    ("training.html", "Training"),
    ("topics/index.html", "Topics"),
    ("bridges.html", "Conversation Bridges"),
    ("partners.html", "Partners & Grassroots Network"),
    ("resources.html", "Resources"),
]

# Section heading -> (anchor id, one-line "what this is for" shown under the heading)
SECTIONS = {
    "short bridge": ("short-bridge",
        "Use this after you’ve listened and let them know you heard them. It’s one or two sentences that move "
        "the talk from the national noise to something local they care about, and it ends with a question so "
        "they keep talking. If they open up, keep listening. If not, thank them and move on."),
    "the issue and expanded bridge": ("expanded-bridge",
        "The facts behind the issue and a longer bridge, for when they want to keep talking."),
    "deeper background": ("background",
        "For your own preparation. You don’t need to recite this. It helps you understand why people feel "
        "this way and answer questions with confidence."),
    "2-minute two-person conversation": ("conversation",
        "A sample conversation from start to finish. Practice it with a partner until it sounds like you."),
}
ORDER = ["short-bridge", "expanded-bridge", "background", "conversation"]


# ---------------------------------------------------------------- parsing
def parse_topic(path):
    text = path.read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        text = text[m.end():]
    intro, sections, cur = [], [], None
    for line in text.splitlines():
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            cur = {"heading": h.group(1), "lines": []}
            sections.append(cur)
        elif cur is None:
            intro.append(line)
        else:
            cur["lines"].append(line)
    for s in sections:
        s["id"], s["label"] = SECTIONS.get(s["heading"].strip().lower(), (slugify(s["heading"]), ""))
    title = meta.get("title", path.stem)
    return {
        "slug": meta.get("slug", path.stem),
        "title": title,
        "plain_title": title.strip("“”\""),
        "order": int(meta.get("order", 999)),
        "source": meta.get("source", ""),
        "intro": "\n".join(intro).strip(),
        "sections": sections,
    }


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def md_to_html(text):
    """Tiny Markdown subset: paragraphs, **bold**, *italic*, '* ' lists,
    a line that is only **bold** becomes a sub-heading, and each line inside
    a paragraph stays on its own line (as in the source doc)."""
    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>\n".join(inline(x) for x in para) + "</p>")
            para.clear()
        if items:
            out.append("<ul>\n" + "\n".join(f"<li>{inline(x)}</li>" for x in items) + "\n</ul>")
            items.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if re.match(r"^[*-]\s+", line):
            if para:
                flush()
            items.append(re.sub(r"^[*-]\s+", "", line))
            continue
        if items:
            flush()
        if re.fullmatch(r"\*\*[^*]+\*\*", line):
            flush()
            out.append(f"<h4>{inline(line[2:-2])}</h4>")
            continue
        para.append(line)
    flush()
    return "\n".join(out)


def md_to_text(text):
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", t)
    t = re.sub(r"^[*-]\s+", "  - ", t, flags=re.M)
    return "\n".join(x.rstrip() for x in t.splitlines()).strip()


# ---------------------------------------------------------------- page shell
def page(title, body, prefix, current):
    cur_attr = ' aria-current="page"'
    nav = "\n".join(
        f'        <li><a href="{prefix}{href}"{cur_attr if href == current else ""}>{html.escape(label)}</a></li>'
        for href, label in NAV
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)} | Grassroots Conversations</title>
  <link rel="stylesheet" href="{prefix}styles.css">
</head>
<body>
  <header>
    <nav>
      <a class="logo" href="{prefix}index.html"><img src="{prefix}images/logo-icon.png" alt="" width="48" height="44"><span>Grassroots Conversations</span></a>
      <ul>
{nav}
      </ul>
    </nav>
  </header>

  <main>
{body}
  </main>

  <footer>
    <p>Grassroots Conversations</p>
    <p class="footer-legal">&copy; 2026 Randy Fahrbach. All rights reserved. Training materials may be shared for volunteer use with credit.</p>
    <p class="footer-legal">Written with help from AI tools.</p>
  </footer>
</body>
</html>
"""


def topic_body(t):
    have = {s["id"] for s in t["sections"]}
    jump = [f'<li><a href="#{s["id"]}">{html.escape(s["heading"])}</a></li>' for s in t["sections"]]
    parts = [
        '    <p class="crumbs"><a href="index.html">All topics</a></p>',
        '    <p class="eyebrow">If you hear this</p>',
        f'    <h1>{html.escape(t["title"])}</h1>',
    ]
    if t["intro"]:
        parts.append(f'    <div class="topic-intro">{md_to_html(t["intro"])}</div>')
    parts.append(
        '    <div class="topic-tools">\n'
        f'      <a class="btn" href="../downloads/{t["slug"]}.pdf" download>Download this topic (PDF)</a>\n'
        f'      <a class="btn btn-plain" href="../downloads/{t["slug"]}.txt" download>Plain text</a>\n'
        '    </div>'
    )
    parts.append('    <nav class="jump" aria-label="On this page"><ul>' + "".join(jump) + "</ul></nav>")
    for s in t["sections"]:
        cls = "level level-basic" if s["id"] == "short-bridge" else "level"
        note = f'<p class="level-note">{html.escape(s["label"])}</p>' if s["label"] else ""
        parts.append(
            f'    <section class="{cls}" id="{s["id"]}">\n'
            f'      <h2>{html.escape(s["heading"])}</h2>\n      {note}\n'
            f'      {md_to_html(chr(10).join(s["lines"]))}\n'
            '      <p class="to-top"><a href="#top">Back to top</a></p>\n    </section>'
        )
    missing = [n for n in ORDER[1:] if n not in have]
    if missing:
        parts.append(
            '    <section class="level level-pending">\n'
            '      <h2>More coming soon</h2>\n'
            '      <p>The expanded bridge, deeper background, and two-minute '
            'conversation for this topic are being added. Start with the short bridge above: listen first, '
            'talk from the heart, and connect to one practical next step.</p>\n    </section>'
        )
    parts.append('    <p class="closing">Neighbors talking to neighbors. We are the they.</p>')
    return "\n".join(parts)


def menu_body(topics):
    cards = []
    for t in topics:
        basic = next((s for s in t["sections"] if s["id"] == "short-bridge"), None)
        preview = md_to_html("\n".join(basic["lines"])) if basic else ""
        n_levels = len(t["sections"])
        status = "Short bridge, expanded bridge, background, and two-minute conversation" if n_levels >= 4 else "Short bridge (more coming)"
        cards.append(f"""      <li class="topic-card">
        <h2><a href="{t['slug']}.html">{html.escape(t['title'])}</a></h2>
        <div class="short">{preview}</div>
        <p class="topic-meta">{status}</p>
        <p class="topic-links"><a class="btn" href="{t['slug']}.html">Open topic</a> <a class="btn btn-plain" href="../downloads/{t['slug']}.pdf" download>Download PDF</a></p>
      </li>""")
    return f"""    <h1>Conversations by Topic</h1>
    <p>Return to the original social media — neighbors talking to neighbors. Pick the line you are hearing at the door. Start with the short bridge. The rest of each page is there for training, or when the setting allows you to go further. Listen first. Talk from the heart.</p>
    <ul class="topic-list">
{chr(10).join(cards)}
    </ul>
    <p class="closing">We are the they.</p>"""


def topic_text(t):
    out = ["GRASSROOTS CONVERSATIONS", "If you hear this: " + t["plain_title"], ""]
    if t["intro"]:
        out += [md_to_text(t["intro"]), ""]
    for s in t["sections"]:
        head = s["heading"]
        out += [head.upper(), "-" * len(head)] + ([s["label"], ""] if s["label"] else []) + [md_to_text("\n".join(s["lines"])), ""]
    out += ["Neighbors talking to neighbors. We are the they.", "grassrootsconversations.com", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- PDF
def find_chrome():
    # Set CHROME=/path/to/chrome to choose a browser. chrome-headless-shell
    # (npx @puppeteer/browsers install chrome-headless-shell@stable) is the
    # most reliable for printing PDFs.
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for name in ("chrome-headless-shell", "google-chrome", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if os.path.exists(mac) else None


def make_pdf(chrome, html_path, pdf_path):
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run(
            [chrome] + ([] if "headless-shell" in chrome else ["--headless=new"]) + ["--disable-gpu", "--no-sandbox", f"--user-data-dir={prof}",
             "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", html_path.as_uri()],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        )


# ---------------------------------------------------------------- resources.html list
def update_downloads_page(topics):
    p = PUBLIC / "resources.html"
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")
    if "<!-- TOPICS:START -->" not in s:
        return
    items = "\n".join(
        f'      <li><a href="downloads/{t["slug"]}.pdf" download>{html.escape(t["title"])}</a> (PDF) · '
        f'<a href="topics/{t["slug"]}.html">read online</a></li>' for t in topics
    )
    block = f'<!-- TOPICS:START -->\n    <ul class="download-list">\n{items}\n    </ul>\n    <!-- TOPICS:END -->'
    s = re.sub(r"<!-- TOPICS:START -->.*?<!-- TOPICS:END -->", block, s, flags=re.S)
    p.write_text(s, encoding="utf-8")


def main():
    topics = sorted((parse_topic(p) for p in CONTENT.glob("*.md")), key=lambda t: (t["order"], t["slug"]))
    if not topics:
        sys.exit("No topics found in content/topics/")
    TOPICS_OUT.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_OUT.mkdir(parents=True, exist_ok=True)
    keep = {f"{t['slug']}.html" for t in topics} | {"index.html"}
    for old in TOPICS_OUT.glob("*.html"):
        if old.name not in keep:
            old.unlink()

    (TOPICS_OUT / "index.html").write_text(
        page("Conversations by Topic", menu_body(topics), "../", "topics/index.html").replace('<main>', '<main id="top">'),
        encoding="utf-8")
    for t in topics:
        (TOPICS_OUT / f"{t['slug']}.html").write_text(
            page(t["plain_title"], topic_body(t), "../", "topics/index.html").replace('<main>', '<main id="top">'),
            encoding="utf-8")
        (DOWNLOADS_OUT / f"{t['slug']}.txt").write_text(topic_text(t), encoding="utf-8")
        print("built topic:", t["slug"])

    chrome = find_chrome()
    if chrome:
        for t in topics:
            make_pdf(chrome, TOPICS_OUT / f"{t['slug']}.html", DOWNLOADS_OUT / f"{t['slug']}.pdf")
            print("pdf:", t["slug"])
    else:
        print("WARNING: Chrome/Chromium not found; PDFs not rebuilt. Install Chrome and run again.")
    update_downloads_page(topics)
    print("done:", len(topics), "topics")


if __name__ == "__main__":
    main()
