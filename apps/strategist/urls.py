from django.urls import path

from . import views

app_name = "strategist"

urlpatterns = [
    path("business/<slug:workspace_slug>/<slug:business_slug>/", views.chat, name="chat"),
    path("business/<slug:workspace_slug>/<slug:business_slug>/sessions/new/", views.new_session, name="new-session"),
    path("business/<slug:workspace_slug>/<slug:business_slug>/sessions/<slug:session_slug>/", views.chat, name="session"),
    path("business/<slug:workspace_slug>/<slug:business_slug>/sessions/<slug:session_slug>/delete/", views.delete_session, name="delete-session"),
    path("business/<slug:workspace_slug>/<slug:business_slug>/strategy/", views.strategy_page, name="strategy"),
    path("business/<slug:workspace_slug>/<slug:business_slug>/strategy/versions/<int:number>/confirm/", views.strategy_confirm, name="strategy-confirm"),
    path("business/<slug:workspace_slug>/<slug:business_slug>/strategy/plan/confirm/", views.plan_confirm, name="plan-confirm"),
    path("business/<uuid:business_id>/", views.legacy_chat_redirect, name="legacy-chat"),
]
