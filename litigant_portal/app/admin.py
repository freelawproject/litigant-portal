from django.contrib import admin

from .models import (
    UserIdentity,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "name", "state", "county", "created_at"]
    search_fields = ["user__email", "name", "county"]


@admin.register(UserIdentity)
class UserIdentityAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "session_key", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__email", "session_key"]
    readonly_fields = ["id", "created_at"]
