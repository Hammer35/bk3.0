"""The pin generation form: scalar settings as a Django form, plan items and boards parsed by hand."""
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.pinterest.models import PinterestAccount

from . import pin_settings as ps

_SHORT = {"maxlength": 60}


class PinGenerationForm(forms.Form):
    account = forms.ModelChoiceField(queryset=PinterestAccount.objects.none(), required=False, empty_label=_("— не выбран —"),
                                     label=_("Аккаунт Pinterest"), help_text=_("Для какого аккаунта готовятся пины и откуда берутся доски."))
    tone = forms.ChoiceField(choices=[("neutral", _("Нейтральный")), ("friendly", _("Дружелюбный")), ("expert", _("Экспертный")), ("premium", _("Премиальный"))],
                             label=_("Тон текста"))
    cta = forms.ChoiceField(choices=[("none", _("Без призыва")), ("soft", _("Мягкий призыв")), ("direct", _("Прямой призыв"))], label=_("Призыв к действию"))
    length = forms.ChoiceField(choices=[("short", _("Короткое описание")), ("standard", _("Стандартное")), ("detailed", _("Подробное"))], label=_("Длина описания"))
    keyword_mode = forms.ChoiceField(choices=[("both", _("Русский или английский")), ("ru", _("Только русский")), ("en", _("Английская фраза"))],
                                     label=_("Ключевая фраза"), help_text=_("Как использовать ключ из исследования ниши."))
    forbidden_words = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label=_("Слова, которых не должно быть"),
                                      help_text=_("Через запятую или с новой строки. Проверка заблокирует пин, если слово встретится."))
    instruction = forms.CharField(required=False, max_length=ps.MAX_INSTRUCTION, widget=forms.Textarea(attrs={"rows": 3}),
                                  label=_("Свободное пожелание"),
                                  help_text=_("До 500 символов. Это пожелание, а не правило: оно не отменяет проверки."))
    destination_url = forms.URLField(required=False, max_length=500, label=_("Ссылка назначения"),
                                     help_text=_("Куда ведёт пин. По умолчанию сайт из профиля бизнеса."))
    utm_source = forms.RegexField(regex=r"^[A-Za-z0-9._\-]{1,60}$", required=False, max_length=60, label=_("Метка utm_source"),
                                  error_messages={"invalid": _("Только латинские буквы, цифры, точка, дефис и подчёркивание.")})
    utm_medium = forms.RegexField(regex=r"^[A-Za-z0-9._\-]{1,60}$", required=False, max_length=60, label=_("Метка utm_medium"),
                                  error_messages={"invalid": _("Только латинские буквы, цифры, точка, дефис и подчёркивание.")})
    utm_campaign = forms.RegexField(regex=r"^[A-Za-z0-9._\-]{1,60}$", required=False, max_length=60, label=_("Метка utm_campaign"),
                                    error_messages={"invalid": _("Только латинские буквы, цифры, точка, дефис и подчёркивание.")})
    product_url = forms.CharField(required=False, max_length=500, label=_("Ссылка на карточку товара Wildberries"),
                                  help_text=_("Необязательно. По карточке проверяются числа и обещания в тексте."))
    rewrite = forms.BooleanField(required=False, label=_("Переписать один раз, если проверка заблокирует текст"))
    remember = forms.BooleanField(required=False, label=_("Запомнить эти настройки для бизнеса"))

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = PinterestAccount.objects.filter(
            business=business, deleted_at__isnull=True, status=PinterestAccount.Status.CONNECTED).order_by("created_at")
        self.fields["account"].label_from_instance = lambda a: f"@{a.username or a.pinterest_user_id}"

    def options(self, boards: dict) -> dict:
        data = self.cleaned_data
        return ps.normalize({
            "tone": data["tone"], "cta": data["cta"], "length": data["length"], "keyword_mode": data["keyword_mode"],
            "forbidden_words": data["forbidden_words"], "instruction": data["instruction"],
            "destination_url": data["destination_url"], "product_url": data["product_url"],
            "utm": {"source": data["utm_source"], "medium": data["utm_medium"], "campaign": data["utm_campaign"]},
            "rewrite": data["rewrite"], "remember": data["remember"],
            "account_id": data["account"].pk if data["account"] else None, "boards": boards})


def initial_values(options: dict) -> dict:
    """Form initial data from a normalized settings dict."""
    return {"account": options["account_id"], "tone": options["tone"], "cta": options["cta"], "length": options["length"],
            "keyword_mode": options["keyword_mode"], "forbidden_words": ", ".join(options["forbidden_words"]),
            "instruction": options["instruction"], "destination_url": options["destination_url"],
            "utm_source": options["utm"]["source"], "utm_medium": options["utm"]["medium"], "utm_campaign": options["utm"]["campaign"],
            "product_url": options["product_url"], "rewrite": options["rewrite"], "remember": options["remember"]}
