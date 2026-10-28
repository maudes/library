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
# Other names for an author: used both to SEARCH (e.g. "落日 湊かなえ" finds
# the Japanese edition, "落日 湊佳苗" doesn't) and to accept matches. Needed
# when Notion has the Chinese name but editions list the English/Japanese one.
AUTHOR_ALIASES = {
    "伍綺詩": ["Celeste Ng"],
    "愛蓮娜．厄克特": ["Alaina Urquhart"],
    "譽田哲也": ["誉田哲也", "Tetsuya Honda"],
    "湊佳苗": ["湊かなえ", "Kanae Minato"],   # Japanese editions write her name in kana
}

# Hand-picked cover images, by Main Title exactly as in Notion. These win over
# automatic lookup (like a "Cover URL" column in Notion would). The image is
# downloaded once into static/covers/, so the link only needs to work once.
COVER_OVERRIDES = {
    "落日": "https://cdn.readmoo.com/cover/jg/nejjreo_460x580.jpg?v=1609989061",
    "小碎肉末": "https://cdn.readmoo.com/cover/fg/8fckmf9_460x580.jpg?v=1750319278",
    "噓噓、嗯嗯、屁屁": "https://cdn.readmoo.com/social/cover/bb/gi7ckgf_460x580.jpg",
    "成為怪物以前": "https://cdn.readmoo.com/cover/in/ckgfpko_460x580.jpg?v=1698216809",
    "最後的信仰；新聞倫理十二講": "https://m.media-amazon.com/images/S/compressed.photo.goodreads.com/books/1721398859i/216649178.jpg",
    "死亡祭儀": "https://cdn.readmoo.com/social/cover/pt/highuth_460x580.jpg",
    "鱷魚手記": "https://cdn.readmoo.com/cover/64/232bg19_460x580.jpg?v=1751015973",
    "我們沒有秘密": "https://m.media-amazon.com/images/S/compressed.photo.goodreads.com/books/1599446684i/55235942.jpg",
    "願你安息": "https://cdn.readmoo.com/cover/bg/d6lekcg_460x580.jpg",
    "運動博弈與彩券莊家不說的遊戲規則": "https://m.media-amazon.com/images/S/compressed.photo.goodreads.com/books/1525532987i/40041465.jpg",
    "巷仔口的社會學": "https://cdn.readmoo.com/cover/64/bbbcg41_460x580.jpg?v=0",
    "折傘的女人": "https://s2.eslite.com/unsafe/fit-in/x1200/filters:format(webp)/s.eslite.com/Upload/Product/201708/o/636390739856892500.jpg",
    "橫山家之味": "https://s2.eslite.com/unsafe/fit-in/x1200/filters:format(webp)/s.eslite.com/upload/product/o/2680409905007/ec301404.jpg",
}

# "Not found" results are cached; retry them after this many days.
RETRY_NOT_FOUND_DAYS = 30
HTTP_TIMEOUT_SECONDS = 10
USER_AGENT = "MaudesLibrary/1.0 (+https://github.com/maudes/library)"
