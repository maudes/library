"""All settings that depend on your Notion database live here.

If you rename a column in Notion, change it here — nowhere else.
"""

# --- Notion column names -----------------------------------------------------
# Left: the name the code uses.  Right: the column name in your Notion database.
# Set a value to None if that column doesn't exist; the site will show "—".
PROPERTIES = {
    "title": "Main Title",
    "second_title": "/2nd Title",
    "author": "作者 | Arthur",
    "rating": "Rating",
    "genre": "Genre",
    "year": "Year",                      # the year you FINISHED the book
    "summary": "Summary | 朕．批閱",
    "isbn": "ISBN",                      # optional; overrides automatic lookup
    "cover_url": "Cover URL",            # optional; overrides automatic lookup
}

# Column giving the order you read the books in (a Date or "Created time"
# column). Used to break rating ties (read earlier ranks higher) and for the
# list's "Reading order" sorts. It is NOT shown on the site: for books entered
# later, its year can differ from the Year column. Set to None to turn off.
DATE_PROPERTY = "Date"

# Fields a row must have. Rows missing any of these are skipped with a warning.
REQUIRED = ["title", "author", "genre", "year"]

# --- Genres ------------------------------------------------------------------
# Notion select value  ->  label shown on the site.
GENRE_MAP = {
    "Fiction": "Fiction",
    "Non-fiction": "Non-fiction",
    "Tool books": "Tool",
    "Fast-food type": "Fast-food",
}
FAST_FOOD = "Fast-food"
# Genres that count in statistics, in the order they appear in the pie chart.
STAT_GENRES = ["Fiction", "Non-fiction", "Tool"]
# All genres, in the order they appear in the list filter.
ALL_GENRES = STAT_GENRES + [FAST_FOOD]

# Google Analytics (same property as the blog on this domain). Tracking only
# runs on SITE_HOSTNAME, so local previews (localhost) never count as visits.
# Set GA_MEASUREMENT_ID = None to turn analytics off.
GA_MEASUREMENT_ID = "G-BHN5D0SF9L"
SITE_HOSTNAME = "maudes.github.io"

# Colour palettes visitors can shuffle between (the header button).
# "current" is the default; each other name needs a matching
# :root[data-palette="..."] block in static/style.css.
PALETTES = ["current", "lemons", "idea", "autumn"]

# The reading list's "80%+" filter shows books rated at least this much.
HIGH_RATING = 80

# --- Cover / ISBN lookup -----------------------------------------------------
# Other names for an author, used when matching books. Needed when Notion has
# the Chinese name but the found editions only list the English one (or the
# reverse). Most are learned automatically; add the rest here.
AUTHOR_ALIASES = {
    "伍綺詩": "Celeste Ng",
}

# "Not found" results are cached; retry them after this many days.
RETRY_NOT_FOUND_DAYS = 30
HTTP_TIMEOUT_SECONDS = 10
USER_AGENT = "MaudesLibrary/1.0 (+https://github.com/maudes/maudes-library)"
