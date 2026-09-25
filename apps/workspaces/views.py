from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .forms import OnboardingForm
from .selectors import get_workspace_memberships_for_user
from .services import create_workspace_with_business


@login_required
def onboarding(request):
    if get_workspace_memberships_for_user(request.user).exists():
        return redirect("core:home")

    form = OnboardingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        create_workspace_with_business(user=request.user, **form.cleaned_data)
        messages.success(request, _("Рабочее пространство и первый бизнес созданы."))
        return redirect("core:home")

    return render(request, "workspaces/onboarding.html", {"form": form})
