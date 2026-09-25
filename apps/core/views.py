from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from redis import Redis

from apps.businesses.selectors import get_businesses_for_user
from apps.workspaces.selectors import get_workspace_memberships_for_user


def landing(request):
    return render(request, "core/landing.html")


@login_required
def home(request):
    memberships = get_workspace_memberships_for_user(request.user)
    if not memberships.exists():
        return redirect("workspaces:onboarding")

    return render(
        request,
        "core/home.html",
        {
            "memberships": memberships,
            "businesses": get_businesses_for_user(request.user),
        },
    )


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
