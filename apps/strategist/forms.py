from django import forms
from django.utils.translation import gettext_lazy as _


class StrategistMessageForm(forms.Form):
    message = forms.CharField(
        label=_("Сообщение"),
        max_length=4000,
        widget=forms.Textarea(
            attrs={
                "rows": 1,
                "placeholder": _("Например: составь план первых 10 пинов для моего бизнеса."),
            }
        ),
    )
