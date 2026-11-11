# Maude's Library

A personal reading log. Books live in a Notion database; a Python script reads
them once a month, fills in missing covers and ISBNs, and publishes a static site to
GitHub Pages.

**Site:** https://maudes.github.io/library/

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
- **Ranking** (Top 3 / Top 10 and the "Rating" sort): rating high → low, then
  reading order (the `Date` column: read earlier ranks higher), then title.
- **Reading order** comes from Notion's `Date` column (created time), set as
  `DATE_PROPERTY` in `config.py`. Only the order is used; the date itself isn't
  shown, because for books entered later its year differs from `Year`.
- **Title order**: English titles A–Z first, then Chinese titles in
  ㄅㄆㄇㄈ (Zhuyin) order. Chinese readings come from the `pypinyin` library;
  a character with several pronunciations (破音字) is occasionally sorted by the
  wrong one.

---

## 1. Create a Notion internal connection

Use an **internal connection** (formerly called an "integration"), not a personal
access token: it can only see the pages you share with it, can be read-only, and
doesn't expire. A personal access token can read *and edit* your whole workspace
and expires within a year, which would silently stop the monthly build.

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

The site then rebuilds on the 1st of every month at 08:00 Taipei time, and on every
push to `main`. To publish Notion changes sooner: **Actions → Build and deploy → Run
workflow**, or `gh workflow run deploy.yml`.
When new covers or ISBNs are found, the workflow commits them back
(`data/cache/books.json` and `static/covers/`) so they're never looked up twice.

> GitHub pauses scheduled workflows in repositories with no activity for 60 days.
> A monthly run only commits when you've added books, so after ~2 quiet months the
> schedule may pause. GitHub emails you when that happens; re-enable it from the
> **Actions** tab (or just run the workflow manually once).

---

## Reading notes (blog)

Each post is one Markdown file in `posts/`, e.g. `posts/my-first-post.md`
(the file name becomes the URL: `/blog/my-first-post/`):

```
---
title: 書名 — 我的心得
date: 2025-03-01
book: 書名                       # optional
medium_url: https://medium.com/...   # optional: adds "Originally published on Medium"
summary: 列表頁顯示的一句話。          # optional; defaults to the first paragraph
draft: true                      # optional: hidden until you remove this line
---

文章內容，用 Markdown 寫。
```

Posts are listed newest first at `/blog/`. To move a Medium article over, paste its
text below the header and keep `medium_url` so readers can find the original.
Posts are public, like everything else here.

---

## Reading taste page (`/taste/`)

Three hand-edited files in `data/` feed it (edit them on github.com; the site
redeploys about a minute after you save):

| File | What | How to edit |
|---|---|---|
| `genres.yml` | Topic genre of each book (警探辦案, 心理驚悚, …), grouped by genre | Add the new book's title under a genre. A warning in the build log lists any book without one. |
| `tbr.yml` | Your to-be-read list | One entry per book: `title`, `author`, optional `note`, `isbn`, `cover_url` |
| `picks.yml` | Pool of acclaimed books that "接下來讀什麼" chooses from | Each entry has `genre` and `sources`. Refresh it once a year. |

- **Genre ratio:** the top 5 genres by number of books (Fast-food excluded); the
  rest are grouped as 其他. Genre names live in `TASTE_GENRES` in `config.py`.
- **Read next:** one book per genre, ranked by how much you read the genre ×
  how highly you rate it, plus a bonus per list the book is on. Books you've read
  or put in `tbr.yml` are skipped. The code is `recommend()` in `src/taste.py`.
- **Playlist:** set `PLAYLIST_ID` and `PLAYLIST_TITLE` in `config.py`. It only
  loads when a visitor presses play.
- Covers for `tbr.yml` and `picks.yml` books are looked up like the library's
  (and saved in `data/cache/books.json` and `static/covers/`).

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
| Genre | Multi-select | ✅ | One of `Fiction` / `Non-fiction` / `Tool books` / `Fast-food type` |
| Year | Text or Number | ✅ | Year you finished the book |
| Date | Created time | | Reading order (automatic in Notion) |
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
src/taste.py           genre ratio, to-read list, "read next" (reading taste page)
src/posts.py           reads posts/*.md (reading notes)
src/render.py          writes site/ with Jinja2
templates/             HTML templates
posts/                 reading-note Markdown files
static/                style.css, app.js, downloaded covers
data/cache/books.json  lookup cache (committed)
tests/                 pytest
```
