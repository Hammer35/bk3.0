from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from redis import Redis


def home(request):
    return render(request, "core/home.html")


def health_live(request):
    return JsonResponse({"status": "ok"})


def health_ready(request):
    checks = {"database": False, "valkey": False}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = True
    except Exception:
        pass

    try:
        Redis.from_url(
            settings.VALKEY_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
        ).ping()
        checks["valkey"] = True
    except Exception:
        pass

    ready = all(checks.values())
    return JsonResponse(
        {"status": "ok" if ready else "not_ready", "checks": checks},
        status=200 if ready else 503,
    )
