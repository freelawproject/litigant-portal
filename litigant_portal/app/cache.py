# The singleton Site row. Read through site_get, dropped on commit by
# busts_site_cache, and cleared after migrate by ensure_site_row.
SITE_CACHE_KEY = "site"

# Every Topic in display order. Read through topic_list, dropped on commit
# by busts_topic_list_cache.
TOPIC_LIST_CACHE_KEY = "topic_list"
