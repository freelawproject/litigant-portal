# A full-length session key (32 chars, like request.session.session_key) and
# the 8-char prefix that audit surfaces are allowed to show. SHORT_KEY is a
# deliberate literal: deriving it from SESSION_KEY_DISPLAY_CHARS would make
# the truncation tests circular.
SESSION_KEY = "k3f9ab21c7de40118a5b6c9d2e7f0a1b"
SHORT_KEY = "k3f9ab21"
