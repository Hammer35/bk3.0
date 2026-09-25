from django.db import transaction
from django.utils.text import slugify

from apps.businesses.services import create_business

from .models import Membership, Workspace


def _next_workspace_slug(name):
    base_slug = slugify(name)[:220] or "workspace"
    candidate = base_slug
    suffix = 2
    while Workspace.objects.filter(slug=candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base_slug[:220 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


@transaction.atomic
def create_workspace_with_business(
    *,
    user,
    workspace_name,
    business_name,
    website="",
    niche="",
    subniche="",
    market="",
    audience="",
    goals="",
):
    workspace = Workspace.objects.create(
        name=workspace_name,
        slug=_next_workspace_slug(workspace_name),
        created_by=user,
    )
    Membership.objects.create(
        workspace=workspace,
        user=user,
        role=Membership.Role.OWNER,
    )
    business = create_business(
        workspace=workspace,
        name=business_name,
        website=website,
        niche=niche,
        subniche=subniche,
        market=market,
        audience=audience,
        goals=goals,
    )
    return workspace, business
