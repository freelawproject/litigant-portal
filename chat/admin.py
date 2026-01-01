from django.contrib import admin

from .models import ChatSession, Document, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["id", "role", "content", "sources", "created_at"]
    can_delete = False

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
    list_display = ["id", "session", "role", "content_preview", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["content", "session__id"]
    readonly_fields = ["id", "created_at"]

    def content_preview(self, obj):
        return (
            obj.content[:100] + "..."
            if len(obj.content) > 100
            else obj.content
        )

    content_preview.short_description = "Content"


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "source_url", "created_at"]
    list_filter = ["category", "created_at"]
    search_fields = ["title", "content"]
    readonly_fields = ["id", "created_at", "updated_at"]
