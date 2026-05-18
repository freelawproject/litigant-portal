from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "name", "state", "county", "created_at"]
    search_fields = ["user__email", "name", "county"]
