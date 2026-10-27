# The singleton Site row. Read through site_get, dropped on commit by the
# busts_cache on the site services.
SITE_CACHE_KEY = "site"

# Every Topic in display order. Read through topic_list, dropped on commit
# by the busts_cache on the topic services.
TOPIC_LIST_CACHE_KEY = "topic_list"

# Every enabled TopicFlow with its Topic, in display order. Read through
# topic_flow_list on every page render with tester tools and on every
# chat turn, dropped on commit by the busts_cache on corpus_sync and the
# topic services (a topic write reorders or removes its flows).
TOPIC_FLOW_LIST_CACHE_KEY = "topic_flow_list"

# The court's Contact and Resource rows in display order. Read through
# contact_list and resource_list, dropped on commit by the busts_cache on
# corpus_sync, the only writer.
CONTACT_LIST_CACHE_KEY = "contact_list"
RESOURCE_LIST_CACHE_KEY = "resource_list"

# Keys holding cached model rows.
DATA_MODEL_CACHE_KEYS = [
    SITE_CACHE_KEY,
    TOPIC_LIST_CACHE_KEY,
    TOPIC_FLOW_LIST_CACHE_KEY,
    CONTACT_LIST_CACHE_KEY,
    RESOURCE_LIST_CACHE_KEY,
]
