from .models import Business


def get_businesses_for_user(user):
    return (
        Business.objects.filter(workspace__memberships__user=user)
        .select_related("workspace")
        .order_by("workspace__name", "name")
    )
