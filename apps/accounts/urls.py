from django.contrib.auth import views as auth_views
from django.utils.decorators import method_decorator
from django.urls import path

from . import views


@method_decorator(views.rate_limit("login", "AUTH_LOGIN_RATE_LIMIT"), name="dispatch")
class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("preferences/interface-scale/", views.update_interface_preference, name="interface-scale"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
