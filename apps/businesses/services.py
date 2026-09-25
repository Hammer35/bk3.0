from django.utils.text import slugify

from .models import Business


def _next_business_slug(*, workspace, name):
    base_slug = slugify(name)[:220] or "business"
    candidate = base_slug
    suffix = 2
    while Business.objects.filter(workspace=workspace, slug=candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base_slug[:220 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


def create_business(
    *,
    workspace,
    name,
    website="",
    niche="",
    subniche="",
    market="",
    audience="",
    goals="",
):
    return Business.objects.create(
        workspace=workspace,
        name=name,
        slug=_next_business_slug(workspace=workspace, name=name),
        website=website,
        niche=niche,
        subniche=subniche,
        market=market,
        audience=audience,
        goals=goals,
    )
