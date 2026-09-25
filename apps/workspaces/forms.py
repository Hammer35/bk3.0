from django import forms
from django.utils.translation import gettext_lazy as _


class OnboardingForm(forms.Form):
    workspace_name = forms.CharField(
        label=_("Название рабочего пространства"),
        help_text=_("Общее имя для ваших проектов. Например: «Мой магазин» или «Studio North»."),
        max_length=200,
    )
    business_name = forms.CharField(
        label=_("Название бизнеса"),
        help_text=_("Название бренда, магазина или отдельного направления, для которого будете создавать контент."),
        max_length=200,
    )
    website = forms.URLField(
        label=_("Сайт"),
        help_text=_("Ссылка на сайт или карточку магазина. Например: https://example.com. Можно заполнить позже."),
        required=False,
    )
    niche = forms.CharField(
        label=_("Ниша"),
        help_text=_("Широкая категория товаров или услуг. Например: «женская одежда», «декор для дома»."),
        max_length=200,
        required=False,
    )
    subniche = forms.CharField(
        label=_("Подниша"),
        help_text=_("Более точное направление внутри ниши. Например: «льняные платья», «аромасвечи ручной работы»."),
        max_length=200,
        required=False,
    )
    market = forms.CharField(
        label=_("Рынок"),
        help_text=_("Страна или регион, где вы продаёте. Например: «Россия», «Казахстан», «Европа»."),
        max_length=80,
        required=False,
    )
    audience = forms.CharField(
        label=_("Целевая аудитория"),
        help_text=_("Кому вы продаёте: возраст, интересы, задача или ситуация покупки. Например: «женщины 25–40, ищут базовую одежду для офиса»."),
        required=False,
        widget=forms.Textarea,
    )
    goals = forms.CharField(
        label=_("Цели продвижения"),
        help_text=_("Что хотите получить от Pinterest. Например: «больше переходов на сайт», «продажи новой коллекции», «узнаваемость бренда»."),
        required=False,
        widget=forms.Textarea,
    )
