from .models import InterfacePreference


def interface_preferences(request):
    font_scale_percent = 100
    if request.user.is_authenticated:
        font_scale_percent = (
            InterfacePreference.objects.filter(user_id=request.user.pk)
            .values_list("font_scale_percent", flat=True)
            .first()
            or 100
        )
    return {"interface_font_scale_percent": font_scale_percent}
