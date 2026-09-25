from django.contrib.auth import login
from django.shortcuts import redirect, render

from apps.core.ratelimit import rate_limit

from .forms import SignupForm


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
