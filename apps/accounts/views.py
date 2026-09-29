from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.ratelimit import rate_limit

from .forms import SignupForm
from .models import FONT_SCALE_PERCENT_VALUES, InterfacePreference


@rate_limit("registration", "AUTH_REGISTRATION_RATE_LIMIT")
def register(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("workspaces:onboarding")

    return render(request, "accounts/register.html", {"form": form})


@login_required
@require_POST
def update_interface_preference(request):
    try:
        font_scale_percent = int(request.POST.get("font_scale_percent", ""))
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_font_scale_percent"}, status=400)

    if font_scale_percent not in FONT_SCALE_PERCENT_VALUES:
        return JsonResponse({"error": "invalid_font_scale_percent"}, status=400)

    preference, _ = InterfacePreference.objects.get_or_create(user=request.user)
    if preference.font_scale_percent != font_scale_percent:
        preference.font_scale_percent = font_scale_percent
        preference.save(update_fields=("font_scale_percent", "updated_at"))

    return JsonResponse({"font_scale_percent": preference.font_scale_percent})
