from django.contrib import admin

from .models import (
    ActionItemModel,
    CaseInfo,
    ChatSession,
    Deadline,
    Document,
    Message,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "name", "state", "county", "created_at"]
    search_fields = ["user__email", "name", "county"]


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = [
        "id",
        "role_display",
        "content_preview",
        "created_at",
    ]
    can_delete = False

    def role_display(self, obj):
        return obj.role

    role_display.short_description = "Role"

    def content_preview(self, obj):
        content = obj.content
        return content[:100] + "..." if len(content) > 100 else content

    content_preview.short_description = "Content"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "session_key", "created_at", "updated_at"]
    list_filter = ["created_at"]
    search_fields = ["id", "user__email", "session_key"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "session",
        "role_display",
        "content_preview",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = ["data", "session__id"]
    readonly_fields = ["id", "created_at"]

    def role_display(self, obj):
        return obj.role

    role_display.short_description = "Role"

    def content_preview(self, obj):
        content = obj.content
        return content[:100] + "..." if len(content) > 100 else content

    content_preview.short_description = "Content"


class DeadlineInline(admin.TabularInline):
    model = Deadline
    extra = 0
    readonly_fields = ["id", "label", "date", "is_deadline", "created_at"]


class ActionItemInline(admin.TabularInline):
    model = ActionItemModel
    extra = 0
    readonly_fields = [
        "id",
        "title",
        "priority",
        "deadline",
        "completed",
        "created_at",
    ]


@admin.register(CaseInfo)
class CaseInfoAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "session_key", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["id", "user__email", "session_key"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [DeadlineInline, ActionItemInline]


@admin.register(Deadline)
class DeadlineAdmin(admin.ModelAdmin):
    list_display = ["label", "date", "is_deadline", "case", "created_at"]
    list_filter = ["is_deadline", "created_at"]
    search_fields = ["label", "date"]
    readonly_fields = ["id", "created_at"]


@admin.register(ActionItemModel)
class ActionItemModelAdmin(admin.ModelAdmin):
    list_display = ["title", "priority", "completed", "case", "created_at"]
    list_filter = ["priority", "completed", "created_at"]
    search_fields = ["title"]
    readonly_fields = ["id", "created_at"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "source_url", "created_at"]
    list_filter = ["category", "created_at"]
    search_fields = ["title", "content"]
    readonly_fields = ["id", "created_at", "updated_at"]
