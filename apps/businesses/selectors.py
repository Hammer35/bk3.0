from django.db.models import Prefetch

from apps.pinterest.models import PinterestAccount
from apps.workspaces.models import BUSINESS_MANAGEMENT_ROLES, Membership

from .models import Business


def get_businesses_for_user(user):
    businesses = list(
        Business.objects.filter(workspace__memberships__user=user)
        .select_related("workspace")
        .prefetch_related(
            Prefetch(
                "pinterest_accounts",
                queryset=PinterestAccount.objects.filter(deleted_at__isnull=True),
                to_attr="active_pinterest_accounts",
            )
        )
        .order_by("workspace__name", "name")
    )
    roles = dict(
        Membership.objects.filter(
            user=user,
            workspace_id__in={business.workspace_id for business in businesses},
        ).values_list("workspace_id", "role")
    )
    for business in businesses:
        business.can_manage_pinterest = roles.get(business.workspace_id) in BUSINESS_MANAGEMENT_ROLES
        business.can_connect_pinterest = (
            business.can_manage_pinterest and business.status == Business.Status.ACTIVE
        )
    return businesses
