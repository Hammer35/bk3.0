from django.contrib import admin

from .models import Business


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "status", "language", "created_at")
    list_filter = ("status", "language")
    search_fields = ("name", "slug", "website")
