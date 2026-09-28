from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

admin.site.site_header = "Администрирование BOOSTKLIENT®"
admin.site.site_title = "BOOSTKLIENT® — административная панель"
admin.site.index_title = "Управление BOOSTKLIENT®"
from django.views.generic import RedirectView

from apps.accounts.urls import LoginView

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/images/favicon.svg", permanent=True)),
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(), name="login"),
    path("auth/", include("apps.accounts.urls")),
    path("accounts/login/", RedirectView.as_view(pattern_name="login", permanent=False)),
    path("accounts/register/", RedirectView.as_view(pattern_name="accounts:register", permanent=False)),
    path("onboarding/", include("apps.workspaces.urls")),
    path("businesses/", include("apps.businesses.urls")),
    path("pinterest/", include("apps.pinterest.urls")),
    path("strategist/", include("apps.strategist.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
