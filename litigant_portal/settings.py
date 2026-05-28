import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent

DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

SECRET_KEY = os.environ.get("SECRET_KEY") or get_random_secret_key()

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if h.strip()
] or (["localhost", "127.0.0.1", "0.0.0.0"] if DEBUG else [])


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "django_cotton",
    "heroicons",
    # Local apps
    "litigant_portal.app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "litigant_portal.app.middleware.AnonymousSessionKeyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "litigant_portal.app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "app" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # "portal.context_processors.toast_messages",
            ],
            "builtins": [
                "django_cotton.templatetags.cotton",
            ],
        },
    },
]

WSGI_APPLICATION = "litigant_portal.main.application"


# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "litigant_portal"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
LANGUAGE_CODE = "en-us"

LANGUAGES = [
    ("en", "English"),
    ("es", "Spanish"),
]

LOCALE_PATHS = [BASE_DIR / "app" / "locale"]

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = os.environ.get("STATIC_URL", "/static/")
STATIC_ROOT = BASE_DIR / "app" / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "app" / "static",
]

# Use ManifestStaticFilesStorage in production for cache busting
# In development (DEBUG=True), Django uses the default storage
if not DEBUG:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# Django Cotton configuration
# Default: components in templates/cotton/ (e.g., <c-button> → templates/cotton/button.html)
COTTON_DIR = "cotton"

# Django Allauth configuration
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

# Allauth account settings
ACCOUNT_LOGIN_METHODS = {"email"}  # Email-based login (not username)
ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "password1*",
    "password2*",
]  # Required fields
ACCOUNT_EMAIL_VERIFICATION = "none"  # Disable email verification for now
ACCOUNT_LOGOUT_ON_GET = False  # Require POST for CSRF protection
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Email backend (console for dev, configure SMTP for production)
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Content Security Policy (django-csp)
# https://django-csp.readthedocs.io/
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)  # Alpine.js served locally
CSP_STYLE_SRC = ("'self'",)
CSP_IMG_SRC = (
    "'self'",
    "data:",
    "blob:",
)  # data: for inline, blob: for camera
CSP_FONT_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = ("'self'",)
# Alpine.js CSP build — no unsafe-eval needed

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Production security settings
# https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
if not DEBUG:
    # HTTPS/SSL
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^health/$"]
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Secure cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Trust origins that match ALLOWED_HOSTS over HTTPS
    CSRF_TRUSTED_ORIGINS = [
        f"https://{host}" for host in ALLOWED_HOSTS if host != "*"
    ]

    # Additional security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"


# AI Chat configuration
CHAT_ENABLED = os.environ.get("CHAT_ENABLED", "true").lower() == "true"
DEFAULT_CHAT_AGENT = os.environ.get(
    "DEFAULT_CHAT_AGENT", "LitigantAssistantAgent"
)
CHAT_MODEL = os.environ.get("CHAT_MODEL", "openai/gpt-4o-mini")
