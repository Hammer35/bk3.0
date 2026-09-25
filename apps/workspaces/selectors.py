from .models import Membership


def get_workspace_memberships_for_user(user):
    return Membership.objects.filter(user=user).select_related("workspace").order_by("workspace__name")
