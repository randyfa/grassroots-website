# Grassroots Conversations website

Static site for grassrootsconversations.com. Files in `public/` deploy automatically to the Cloudflare Worker `lively-violet-4d2b` on every push to `main`. Cloudflare does not run any build step, so everything the site needs must be committed inside `public/`.

## Layout

- `public/` – the live website (HTML, `styles.css`, `images/`).
- `public/topics/` – **generated** topic menu (`index.html`) and one page per topic.
- `public/downloads/` – **generated** printable PDF and plain-text copy of each topic.
- `content/topics/` – the source text for each topic (edit these, not the generated pages).
- `content/integration-notes.md` – working notes from the source doc; not published.
- `tools/build.py` – generator (Python 3, standard library only).

## Add or update a topic

1. Create or edit a file in `content/topics/`, e.g. `content/topics/not-my-problem.md`. The file name becomes the page address (`/topics/not-my-problem.html`).
2. Use this format (copy text verbatim from the bridges document):

   ```
   ---
   title: “The line you hear at the door.”
   order: 3
   source: Name of the source document
   ---
   Optional note shown under the title.

   ## Level 1 — Short Conversational Bridge
   *“The short bridge, word for word.”*

   ## Level 2 — One-Pager
   **The issue**
   Paragraph text…

   ## Level 3 — White Paper
   * bullet points start with "* "

   ## Level 4 — 2-Minute Two-Person Conversation
   **Neighbor:** …
   **You:** …
   ```

   Level 1 is shown as the **Basic Bridge**; Levels 2–4 are shown as **Expanded Bridge** sections. Leave out levels that are not written yet and the page shows "Expanded levels coming soon".
   Supported formatting: `**bold**`, `*italic*`, `* ` bullet lists, a line that is only `**bold**` becomes a sub-heading.
3. Run `python3 tools/build.py`. It rebuilds `public/topics/`, `public/downloads/<topic>.pdf` and `.txt`, and the topic list on `resources.html`.
   PDFs need Chrome or Chromium. The most reliable is chrome-headless-shell:
   `npx @puppeteer/browsers install chrome-headless-shell@stable`, then `CHROME=/path/to/chrome-headless-shell python3 tools/build.py`.
4. Preview locally (open `public/topics/index.html` in a browser), then commit everything (content and generated files) and push. Pushing to `main` publishes the site.
