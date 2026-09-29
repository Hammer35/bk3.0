from django.urls import path

from . import views

app_name = "pinterest"

urlpatterns = [
    path("business/<uuid:business_id>/connect/", views.connect, name="connect"),
    path("account/<uuid:account_id>/reconnect/", views.reconnect, name="reconnect"),
    path("account/<uuid:account_id>/disconnect/", views.disconnect, name="disconnect"),
    path("account/<uuid:account_id>/sync/", views.sync_account, name="sync-account"),
    path("callback/", views.callback, name="callback"),
]
