from django.urls import path

from . import views

app_name = "businesses"

urlpatterns = [
    path("workspace/<uuid:workspace_id>/create/", views.legacy_create_redirect, name="legacy-create"),
    path("workspace/<slug:workspace_slug>/create/", views.create, name="create"),
]
