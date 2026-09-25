from django.urls import path

from . import views

app_name = "workspaces"

urlpatterns = [
    path("", views.onboarding, name="onboarding"),
]
