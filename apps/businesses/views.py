from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from apps.workspaces.permissions import can_manage_businesses
from apps.workspaces.models import Workspace

from .forms import BusinessForm
from .services import create_business


@login_required
def create(request, workspace_slug):
    workspace = get_object_or_404(Workspace, slug=workspace_slug)
    if not can_manage_businesses(user=request.user, workspace=workspace):
        raise Http404

    form = BusinessForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        create_business(workspace=workspace, **form.cleaned_data)
        messages.success(request, _("Бизнес добавлен."))
        return redirect("core:home")

    return render(request, "businesses/create.html", {"form": form, "workspace": workspace})


@login_required
def legacy_create_redirect(request, workspace_id):
    workspace = get_object_or_404(Workspace, public_id=workspace_id)
    if not can_manage_businesses(user=request.user, workspace=workspace):
        raise Http404

    return redirect(
        "businesses:create",
        workspace_slug=workspace.slug,
        permanent=True,
    )
