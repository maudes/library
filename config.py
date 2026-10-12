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

# Optional date column used to break rating ties (earlier date ranks higher).
# Your database has no such column, so ties go straight to title order.
# If you add one later, put its column name here, e.g. "Finished Date".
DATE_PROPERTY = None

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

# The reading list's "80%+" filter shows books rated at least this much.
HIGH_RATING = 80

# --- Cover / ISBN lookup -----------------------------------------------------
# "Not found" results are cached; retry them after this many days.
RETRY_NOT_FOUND_DAYS = 30
HTTP_TIMEOUT_SECONDS = 10
USER_AGENT = "MaudesLibrary/1.0 (+https://github.com/maudes/maudes-library)"
