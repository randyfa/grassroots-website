#!/usr/bin/env python3
"""Build the printable volunteer materials for the Resources page.

Reads   content/materials/*.html          (hand-written page bodies)
        content/materials/*.md + next-three/*.md, content/topics/*.md (topic format)
Writes  public/downloads/<slug>.pdf

Needs chrome-headless-shell (set CHROME=/path). Run: python3 tools/build_materials.py
Cloudflare does not run this script; commit the generated PDFs.
"""
import html
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402  (reuse topic parser and Markdown subset)

ROOT = build.ROOT
SRC = ROOT / "content" / "materials"
OUT = ROOT / "public" / "downloads"
LOGO = ROOT / "public" / "images" / "logo-icon.png"

CSS = """
@page { size: letter; margin: 0.5in 0.6in 0.35in; }
@page landscape { size: letter landscape; margin: 0.45in 0.5in 0.3in; }
* { box-sizing: border-box; }
body { font-family: Arial, Helvetica, sans-serif; color: #2d3748; font-size: 10.5pt; line-height: 1.4; margin: 0; }
.mast { display: flex; align-items: center; gap: 10px; border-bottom: 3px solid #c53030; padding-bottom: 6px; margin-bottom: 10px; }
.mast img { width: 40px; height: auto; }
.mast .brand { color: #1a365d; font-weight: bold; font-size: 13pt; }
.mast .site { margin-left: auto; color: #1a365d; font-size: 9pt; }
h1 { color: #1a365d; font-size: 19pt; margin: 4px 0 2px; }
.subtitle { color: #c53030; font-style: italic; margin: 0 0 10px; }
h2 { color: #1a365d; font-size: 14pt; border-bottom: 1px solid #cbd5e0; padding-bottom: 2px; margin: 16px 0 6px; break-after: avoid; }
h3, h4 { color: #c53030; font-size: 11pt; margin: 10px 0 3px; break-after: avoid; }
p { margin: 0 0 6px; }
ul, ol { margin: 0 0 6px; padding-left: 20px; }
li { margin-bottom: 3px; }
.quote { border-left: 4px solid #c53030; background: #f7fafc; padding: 6px 10px; font-style: italic; }
.section-note { break-after: avoid; color: #4a5568; font-size: 9.5pt; font-style: italic; }
.topic { break-before: page; }
.topic:first-of-type { break-before: auto; }
.eyebrow { color: #c53030; text-transform: uppercase; letter-spacing: 1px; font-size: 8.5pt; font-weight: bold; margin: 0; }
.closing { color: #c53030; font-weight: bold; text-align: center; font-size: 12pt; margin-top: 12px; }
.center { text-align: center; } .small { font-size: 9pt; }
table.log { width: 100%; border-collapse: collapse; margin: 6px 0 10px; }
table.log th { background: #1a365d; color: #fff; font-size: 8.5pt; text-align: left; padding: 4px; border: 1px solid #1a365d; }
table.log td { border: 1px solid #a0aec0; height: 26px; }
table.tracker td { height: 30px; }
.page-break { break-before: page; }
.two-col { display: flex; gap: 18px; } .two-col > div { flex: 1; }
.card-side { border: 2px solid #1a365d; border-radius: 8px; padding: 8px 14px; }
.card-side h2 { margin-top: 2px; }
.side-label { color: #c53030; font-size: 8pt; text-transform: uppercase; letter-spacing: 1px; font-weight: bold; margin: 0; }
.cut { text-align: center; color: #718096; font-size: 9pt; margin: 8px 0; }
.foot { position: fixed; bottom: 0; background: #fff; left: 0; right: 0; text-align: center; font-size: 8pt; color: #4a5568; border-top: 1px solid #cbd5e0; padding-top: 3px; }
.foot .ai { font-size: 7pt; }
.foot .site { color: #1a365d; font-weight: bold; }
.landscape-doc { page: landscape; }
.wrap { width: 100%; border-collapse: collapse; } .wrap > tbody > tr > td, .wrap > tfoot > tr > td { padding: 0; }
.foot-space { height: 0.45in; }
"""

FOOT = ('<div class="foot"><span class="site">grassrootsconversations.com</span> · '
        '&copy; 2026 Randy Fahrbach. All rights reserved. Training materials may be shared for volunteer use with credit.'
        '<br><span class="ai">Written with help from AI tools.</span></div>')


def shell(title, subtitle, body, landscape=False):
    sub = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""
    cls = ' class="landscape-doc"' if landscape else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>{title} | Grassroots Conversations</title><style>{CSS}</style></head>
<body{cls}>{FOOT}
<div class="mast"><img src="{LOGO.as_uri()}" alt=""><span class="brand">Grassroots Conversations</span>
<span class="site">grassrootsconversations.com</span></div>
<h1>{title}</h1>{sub}
<table class="wrap"><tbody><tr><td>
{body}
</td></tr></tbody><tfoot><tr><td><div class="foot-space"></div></td></tr></tfoot></table>
</body></html>"""


def topic_html(t, show_eyebrow=True):
    parts = ['<section class="topic">']
    if show_eyebrow:
        parts.append('<p class="eyebrow">If you hear this</p>')
        parts.append(f'<h2 style="font-size:16pt;border:0">{html.escape(t["title"])}</h2>')
    if t["intro"]:
        parts.append(build.md_to_html(t["intro"]))
    for s in t["sections"]:
        parts.append(f'<h2>{html.escape(s["heading"])}</h2>')
        if s["label"]:
            parts.append(f'<p class="section-note">{html.escape(s["label"])}</p>')
        parts.append(build.md_to_html("\n".join(s["lines"])))
    parts.append('</section>')
    return "\n".join(parts)


def topics_from(paths):
    return sorted((build.parse_topic(p) for p in paths), key=lambda t: (t["order"], t["slug"]))


CLOSE = '<p class="closing">Neighbors talking to neighbors. We are the they.</p>'

SIX = ('<p class="small"><strong>The six steps:</strong> Friendly opener · Ask an open question · '
       'Listen and acknowledge · <strong>Bridge</strong> · Soft close · Thank them. '
       'Use the short bridge in step 4, after you’ve listened and acknowledged.</p>')


def bridges_doc(title, subtitle, topics):
    return shell(title, subtitle, SIX + "\n".join(topic_html(t) for t in topics) + CLOSE)


def fragment(name):
    text = (SRC / name).read_text(encoding="utf-8")
    title = re.search(r"<!-- title: (.*?) -->", text).group(1)
    sub = re.search(r"<!-- subtitle: (.*?) -->", text)
    land = "<!-- landscape -->" in text
    def rows(m):
        cols, n = int(m.group(1)), int(m.group(2))
        return ("<tr>" + "<td></td>" * cols + "</tr>") * n
    text = re.sub(r"ROWS(\d+)x(\d+)", rows, text)
    return shell(title, sub.group(1) if sub else "", text, land)


def main():
    chrome = build.find_chrome()
    if not chrome:
        sys.exit("Chrome not found; set CHROME=/path/to/chrome-headless-shell")
    frame = topics_from([SRC / "positive-conservative-frame.md"])[0]
    docs = {
        "conversation-card": fragment("conversation-card.html"),
        "training-packet": fragment("training-packet.html"),
        "bridges-top-two": bridges_doc("Expanded Bridges — Top Two",
            "If you hear this · Independent / PND / Other, and sitting it out",
            topics_from((ROOT / "content" / "topics").glob("*.md"))),
        "bridges-next-three": bridges_doc("Expanded Bridges — Next Three",
            "If you hear this · Distrust, “all corrupt,” and “I don’t like Trump / the GOP”",
            topics_from((SRC / "next-three").glob("*.md"))),
        "positive-conservative-frame": shell(frame["title"], "Optional companion document",
            topic_html(frame, show_eyebrow=False) + CLOSE),
        "ground-network-tracker": fragment("ground-network-tracker.html"),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for slug, doc in docs.items():
            hp = Path(tmp) / f"{slug}.html"
            hp.write_text(doc, encoding="utf-8")
            build.make_pdf(chrome, hp, OUT / f"{slug}.pdf")
            if "--keep-html" in sys.argv:
                shutil.copy(hp, Path("/tmp") / f"{slug}.html")
            print("pdf:", slug)


if __name__ == "__main__":
    main()
