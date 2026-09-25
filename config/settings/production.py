import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

secret_key = os.getenv("DJANGO_SECRET_KEY", "")
allowed_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "")
csrf_trusted_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "")

if len(secret_key) < 50:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be a runtime secret of at least 50 characters."
    )

if SECRET_KEY == "development-only-not-for-production-change-me":  # noqa: F405
    raise ImproperlyConfigured("Development SECRET_KEY cannot be used in production.")

if not allowed_hosts or not csrf_trusted_origins:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS must be configured in production."
    )

ALLOWED_HOSTS = [host.strip() for host in allowed_hosts.split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_trusted_origins.split(",") if origin.strip()]

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
