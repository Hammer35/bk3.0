import hashlib
import logging
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

logger = logging.getLogger(__name__)


def rate_limit(scope, limit_setting):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != "POST":
                return view(request, *args, **kwargs)

            client_ip = request.META.get("REMOTE_ADDR", "unknown")
            digest = hashlib.sha256(client_ip.encode()).hexdigest()
            cache_key = f"rate-limit:{scope}:{digest}"
            try:
                if cache.add(cache_key, 1, timeout=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS):
                    return view(request, *args, **kwargs)
                attempts = cache.incr(cache_key)
            except Exception:
                logger.exception("Authentication rate-limit cache is unavailable")
                return HttpResponse(status=503)

            if attempts > getattr(settings, limit_setting):
                return HttpResponse("Too many requests.", status=429)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
