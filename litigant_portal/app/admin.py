import uuid

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (
    ChatThread,
    UserIdentity,
    UserProfile,
)
from .selectors.chat_engine import (
    chat_thread_export_data,
    chat_thread_export_markdown,
    chat_thread_owner_label,
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


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    """Read-only audit surface for AI conversation transcripts."""

    list_display = [
        "id",
        "owner",
        "thread_type",
        "description",
        "message_count",
        "created_at",
    ]
    list_filter = ["thread_type", "created_at"]
    search_fields = [
        "identity__session_key",
        "identity__user__email",
        "description",
    ]
    ordering = ["-created_at"]
    fields = [
        "id",
        "owner",
        "thread_type",
        "description",
        "created_at",
        "updated_at",
        "downloads",
        "transcript",
    ]
    readonly_fields = fields

    class Media:
        css = {"all": ["css/audit_admin.css"]}

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("identity__user")
            .annotate(message_total=Count("messages"))
        )

    def get_search_results(self, request, queryset, search_term):
        # UUIDField doesn't support icontains, so match thread ids here.
        try:
            return queryset.filter(pk=uuid.UUID(search_term.strip())), False
        except ValueError:
            return super().get_search_results(request, queryset, search_term)

    @admin.display(description="Owner")
    def owner(self, obj):
        return chat_thread_owner_label(thread=obj)

    @admin.display(description="Messages", ordering="message_total")
    def message_count(self, obj):
        return obj.message_total

    @admin.display(description="Downloads")
    def downloads(self, obj):
        return format_html(
            '<a href="{}">Markdown</a> | <a href="{}">JSON</a>',
            reverse("admin:app_chatthread_transcript_md", args=[obj.pk]),
            reverse("admin:app_chatthread_transcript_json", args=[obj.pk]),
        )

    @admin.display(description="Transcript")
    def transcript(self, obj):
        return format_html(
            '<pre class="audit-transcript">{}</pre>',
            chat_thread_export_markdown(thread=obj),
        )

    def get_urls(self):
        custom = [
            path(
                "<uuid:pk>/transcript.md",
                self.admin_site.admin_view(self.transcript_markdown_view),
                name="app_chatthread_transcript_md",
            ),
            path(
                "<uuid:pk>/transcript.json",
                self.admin_site.admin_view(self.transcript_json_view),
                name="app_chatthread_transcript_json",
            ),
        ]
        return custom + super().get_urls()

    def _get_thread_or_403(self, request, pk):
        thread = get_object_or_404(
            ChatThread.objects.select_related("identity__user"), pk=pk
        )
        if not self.has_view_permission(request, thread):
            raise PermissionDenied
        return thread

    def transcript_markdown_view(self, request, pk):
        thread = self._get_thread_or_403(request, pk)
        response = HttpResponse(
            chat_thread_export_markdown(thread=thread),
            content_type="text/markdown; charset=utf-8",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="transcript-{pk}.md"'
        )
        return response

    def transcript_json_view(self, request, pk):
        thread = self._get_thread_or_403(request, pk)
        response = JsonResponse(
            chat_thread_export_data(thread=thread),
            json_dumps_params={"indent": 2, "ensure_ascii": False},
        )
        response["Content-Disposition"] = (
            f'attachment; filename="transcript-{pk}.json"'
        )
        return response

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # Transcript review is open to all staff, no per-model perms needed.
    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_staff
