from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "development-only-not-for-production-change-me",
)

DEBUG = False

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.core",
    "apps.workspaces",
    "apps.businesses",
    "apps.pinterest",
    "apps.knowledge",
    "apps.strategist",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context_processors.interface_preferences",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "boostklient"),
        "USER": os.getenv("POSTGRES_USER", "boostklient"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "boostklient_dev_only"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
LANGUAGES = [
    ("ru", "Русский"),
    ("en", "English"),
]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "var" / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:landing"

VALKEY_URL = os.getenv("VALKEY_URL", "redis://valkey:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": VALKEY_URL,
    }
}
CELERY_BROKER_URL = VALKEY_URL
CELERY_RESULT_BACKEND = VALKEY_URL
CELERY_TASK_DEFAULT_QUEUE = "low_priority"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_SOFT_TIME_LIMIT = 270
CELERY_TASK_TIME_LIMIT = 300
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "refresh-pinterest-oauth-tokens-daily": {
        "task": "apps.pinterest.tasks.refresh_pinterest_tokens",
        "schedule": 86400.0,
    },
}

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
AUTH_LOGIN_RATE_LIMIT = int(os.getenv("AUTH_LOGIN_RATE_LIMIT", "5"))
AUTH_REGISTRATION_RATE_LIMIT = int(os.getenv("AUTH_REGISTRATION_RATE_LIMIT", "3"))
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300"))

GIGACHAT_API_TOKEN = os.getenv("GIGACHAT_API_TOKEN", "")
STRATEGIST_PRODUCT_VISION_ENABLED = os.getenv("STRATEGIST_PRODUCT_VISION_ENABLED", "false").lower() == "true"
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat-2-Pro")
GIGACHAT_MODEL_PRIORITY = tuple(
    dict.fromkeys(
        model.strip()
        for model in (
            GIGACHAT_MODEL,
            *os.getenv(
                "GIGACHAT_MODEL_PRIORITY",
                "GigaChat-2-Pro,GigaChat-2,GigaChat-3-Lightning,GigaChat-3-Pro,"
                "GigaChat-2-Max,GigaChat-3-Ultra",
            ).split(","),
        )
        if model.strip()
    )
)
GIGACHAT_AVAILABLE_MODELS_CACHE_SECONDS = int(
    os.getenv("GIGACHAT_AVAILABLE_MODELS_CACHE_SECONDS", "300")
)
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_BASE_URL = os.getenv("GIGACHAT_BASE_URL", "https://api.giga.chat/v1")
GIGACHAT_EMBEDDING_MODEL = os.getenv("GIGACHAT_EMBEDDING_MODEL", "EmbeddingsGigaR")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_PROXY_URL = os.getenv("OPENROUTER_PROXY_URL", "")
KNOWLEDGE_EMBEDDING_PROVIDER = os.getenv("KNOWLEDGE_EMBEDDING_PROVIDER", "gigachat")
KNOWLEDGE_EMBEDDING_MODEL = os.getenv(
    "KNOWLEDGE_EMBEDDING_MODEL",
    "",
) or (
    "nvidia/nemotron-3-embed-1b:free"
    if KNOWLEDGE_EMBEDDING_PROVIDER == "openrouter" else GIGACHAT_EMBEDDING_MODEL
)
KNOWLEDGE_MIN_SIMILARITY_SCORE = float(os.getenv(
    "KNOWLEDGE_MIN_SIMILARITY_SCORE",
    "0.25" if KNOWLEDGE_EMBEDDING_PROVIDER == "openrouter" else "0.55",
))
KNOWLEDGE_FALLBACK_EMBEDDING_MODEL = os.getenv("KNOWLEDGE_FALLBACK_EMBEDDING_MODEL", "")
KNOWLEDGE_FALLBACK_MIN_SIMILARITY_SCORE = float(os.getenv("KNOWLEDGE_FALLBACK_MIN_SIMILARITY_SCORE", "0.25"))
GIGACHAT_TIMEOUT_SECONDS = float(os.getenv("GIGACHAT_TIMEOUT_SECONDS", "45"))
GIGACHAT_CA_BUNDLE_FILE = os.getenv(
    "GIGACHAT_CA_BUNDLE_FILE",
    str(BASE_DIR / "infra" / "certs" / "russian_trusted_root_ca_pem.crt"),
)

PINTEREST_CLIENT_ID = os.getenv("PINTEREST_CLIENT_ID", "")
PINTEREST_CLIENT_SECRET = os.getenv("PINTEREST_CLIENT_SECRET", "")
PINTEREST_REDIRECT_URI = os.getenv("PINTEREST_REDIRECT_URI", "")
PINTEREST_SCOPES = tuple(
    scope.strip()
    for scope in os.getenv(
        "PINTEREST_SCOPES", "user_accounts:read,boards:read,boards:write,pins:read,pins:write,ads:read"
    ).replace(" ", ",").split(",")
    if scope.strip()
)
PINTEREST_APP_CREATED_BEFORE_CONTINUOUS_REFRESH = (
    os.getenv("PINTEREST_APP_CREATED_BEFORE_2025_09_25", "false").lower()
    in {"1", "true", "yes"}
)
PINTEREST_TOKEN_ENCRYPTION_KEY = os.getenv("PINTEREST_TOKEN_ENCRYPTION_KEY", "")
# Policy switches. Competitor research stays off until Pinterest authorizes it in writing.
# Transient use of Pinterest API data as LLM context was confirmed by Pinterest in writing
# (owner statement, 2026-10-06); the switch lets it be turned off without a deploy of code.
PINTEREST_COMPETITOR_RESEARCH_ENABLED = os.getenv("PINTEREST_COMPETITOR_RESEARCH_ENABLED", "false").lower() in {"1", "true", "yes"}
PINTEREST_AI_DATA_TRANSFER_ENABLED = os.getenv("PINTEREST_AI_DATA_TRANSFER_ENABLED", "true").lower() in {"1", "true", "yes"}
RESEARCH_SNAPSHOT_RETENTION_DAYS = int(os.getenv("RESEARCH_SNAPSHOT_RETENTION_DAYS", "30"))
