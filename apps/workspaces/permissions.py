from .models import BUSINESS_MANAGEMENT_ROLES, Membership


def can_manage_businesses(*, user, workspace):
    return user.is_authenticated and Membership.objects.filter(
        workspace=workspace,
        user=user,
        role__in=BUSINESS_MANAGEMENT_ROLES,
    ).exists()
