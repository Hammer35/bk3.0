from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Business


class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ("name", "website", "niche", "subniche", "market", "audience", "goals")
        labels = {
            "name": _("Название бизнеса"),
            "website": _("Сайт"),
            "niche": _("Ниша"),
            "subniche": _("Подниша"),
            "market": _("Рынок"),
            "audience": _("Целевая аудитория"),
            "goals": _("Цели продвижения"),
        }
