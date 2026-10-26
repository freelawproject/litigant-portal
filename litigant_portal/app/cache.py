# The singleton Site row. Read through site_get, dropped on commit by the
# busts_cache on the site services.
SITE_CACHE_KEY = "site"

# Every Topic in display order. Read through topic_list, dropped on commit
# by the busts_cache on the topic services.
TOPIC_LIST_CACHE_KEY = "topic_list"

# The court's Contact and Resource rows in display order. Read through
# contact_list and resource_list, dropped on commit by the busts_cache on
# corpus_sync, the only writer.
CONTACT_LIST_CACHE_KEY = "contact_list"
RESOURCE_LIST_CACHE_KEY = "resource_list"

# Keys holding cached model rows.
DATA_MODEL_CACHE_KEYS = [
    SITE_CACHE_KEY,
    TOPIC_LIST_CACHE_KEY,
    CONTACT_LIST_CACHE_KEY,
    RESOURCE_LIST_CACHE_KEY,
]
