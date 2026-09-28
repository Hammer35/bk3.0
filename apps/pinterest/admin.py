from django.contrib import admin

from .models import PinterestAccount


@admin.register(PinterestAccount)
class PinterestAccountAdmin(admin.ModelAdmin):
    list_display = ("username", "business", "status", "access_token_expires_at")
    list_filter = ("status",)
    search_fields = ("username", "pinterest_user_id", "business__name")
    readonly_fields = ("pinterest_user_id",)
