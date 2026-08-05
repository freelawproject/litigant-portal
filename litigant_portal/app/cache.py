# The singleton Site row. Read through site_get, dropped on commit by the
# busts_cache on the site services, and cleared after migrate by ensure_site_row.
SITE_CACHE_KEY = "site"

# Every Topic in display order. Read through topic_list, dropped on commit
# by the busts_cache on the topic services.
TOPIC_LIST_CACHE_KEY = "topic_list"
