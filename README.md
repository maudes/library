# Maude's Library

A personal reading log. Books live in a Notion database; a Python script reads
them every day, fills in missing covers and ISBNs, and publishes a static site to
GitHub Pages.

**Site:** https://maudes.github.io/maudes-library/

> ⚠️ **Everything in the database is public.** The repository and the website are
> both public, so every title, rating and **Summary** you write in Notion will be
> visible to anyone. Don't put private notes in the Summary column.

---

## How it works

```
Notion ──► src/notion_source.py ──► src/enrich.py ──► src/stats.py ──► src/render.py ──► site/
           read + clean rows        covers & ISBNs     all numbers &     HTML via Jinja2
                                    (cached)           sort orders
```

- **All logic is Python.** `src/stats.py` computes every count, average, Top 3,
  genre share and sort order. The browser JavaScript (`static/app.js`) only
  shows/hides and re-orders what Python already prepared.
- **Fast-food** books appear in the reading list but are left out of every
  statistic (totals, averages, Top 3, genre chart).
- **Ranking** (Top 3 and the "Rating" sort): rating high → low, then finished date
  early → late (only if `DATE_PROPERTY` is set in `config.py`), then title.
- **Title order**: English titles A–Z first, then Chinese titles in
  ㄅㄆㄇㄈ (Zhuyin) order. Chinese readings come from the `pypinyin` library;
  a character with several pronunciations (破音字) is occasionally sorted by the
  wrong one.

---

## 1. Create a Notion internal connection

Use an **internal connection** (formerly called an "integration"), not a personal
access token: it can only see the pages you share with it, can be read-only, and
doesn't expire. A personal access token can read *and edit* your whole workspace
and expires within a year, which would silently stop the daily build.

1. Open the Notion Developer portal (<https://www.notion.so/developers>) and create
   a new **internal connection** in your workspace (e.g. "Maude's Library").
2. Under **Capabilities**, only **Read content** is needed.
3. Save, then copy its secret. This is your `NOTION_TOKEN`.
   Treat it like a password.

## 2. Connect the database to the internal connection

1. Open the reading-list database in Notion as a full page.
2. Click **•••** (top right) → **Connections** → find your connection → **Confirm**.
3. Copy the database id from the page URL:
   `https://www.notion.so/<workspace>/`**`1f33d1f4a99a80c2b396e2e1adc75cf0`**`?v=…`
   This is your `NOTION_DATABASE_ID`.

## 3. (Recommended) Get a Google Books API key

Without a key, Google Books often refuses requests and only Open Library is used,
which has few Chinese editions.

1. Open <https://console.cloud.google.com/>, create a project.
2. **APIs & Services → Library →** enable **Books API**.
3. **APIs & Services → Credentials → Create credentials → API key**.
4. Optionally restrict the key to the Books API.

The key is free for this level of use.

## 4. Run it on your computer

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then open .env and fill in the values
python build.py
python -m http.server 8765 --directory site
```

Open <http://localhost:8765>.

Other options:

```bash
python build.py --offline            # skip cover lookups, use only the cache
python build.py --csv export.csv     # use a Notion "Export → CSV" file instead of the API
pytest                               # run the tests
```

## 5. Publish on GitHub Pages

1. In the repository on GitHub: **Settings → Secrets and variables → Actions →
   New repository secret**, and add `NOTION_TOKEN`, `NOTION_DATABASE_ID`, and
   (optional) `GOOGLE_BOOKS_API_KEY`.
2. **Settings → Pages → Source:** choose **GitHub Actions**.
3. **Actions → Build and deploy → Run workflow** to publish right away.

The site then rebuilds every day at 04:00 Taipei time, and on every push to `main`.
When new covers or ISBNs are found, the workflow commits them back
(`data/cache/books.json` and `static/covers/`) so they're never looked up twice.

> GitHub pauses scheduled workflows in repositories with no activity for 60 days.
> The cache commits usually keep it active; if it ever pauses, GitHub emails you
> and you can re-enable it from the **Actions** tab.

---

## Notion columns

Column names are mapped in **`config.py`** — that's the only place to change if
you rename a column in Notion.

| Notion column | Type | Required | Notes |
|---|---|---|---|
| Main Title | Title | ✅ | |
| /2nd Title | Text | | Original or English title |
| 作者 \| Arthur | Text | ✅ | |
| Rating | Number (percent) | | Blank = not rated; not in Top 3 or averages |
| Genre | Select | ✅ | `Fiction` / `Non-fiction` / `Tool books` / `Fast-food type` |
| Year | Number | ✅ | Year you finished the book |
| Summary \| 朕．批閱 | Text | | **Public** |
| ISBN | Text | | Optional — overrides automatic lookup |
| Cover URL | URL | | Optional — overrides automatic lookup |

Rows missing a required value are skipped with a warning in the build log; the
build itself doesn't fail.

### Fixing a wrong cover or ISBN

A lookup only counts when **both** the title and the author match, so a book
whose author is written differently (e.g. 石黑一雄 in Notion, "Kazuo Ishiguro"
in the English edition) may not be found and shows the placeholder. Automatic
matches can also occasionally be a different edition. In either case, fill in
**ISBN** and/or **Cover URL** in Notion for that book; those always win.

### Adding a new column

1. Add the column in Notion.
2. Add a line to `PROPERTIES` in `config.py`, e.g. `"pages": "Pages"`.
3. Add the field to the `Book` class in `src/book.py` and pass it in `make_book`
   in `src/notion_source.py`.
4. Show it in `templates/index.html` (list row, card) and in the pop-up in
   `templates/_macros.html`.

### Adding a new genre

Add it to `GENRE_MAP` in `config.py` (Notion value → label on the site). Add it to
`STAT_GENRES` too if it should count in the statistics and the genre chart; then
add a slice colour in `static/style.css` (`.pie`).

---

## Project layout

```
build.py               entry point
config.py              Notion column names, genres, settings
src/notion_source.py   read Notion / CSV, clean and validate rows
src/enrich.py          cover + ISBN lookup (Google Books → Open Library), cache
src/stats.py           all statistics and sort orders
src/render.py          writes site/ with Jinja2
templates/             HTML templates
static/                style.css, app.js, downloaded covers
data/cache/books.json  lookup cache (committed)
tests/                 pytest
```
