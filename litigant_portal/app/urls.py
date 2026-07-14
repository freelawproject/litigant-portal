import re

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.i18n import JavaScriptCatalog
from django.views.static import serve

from litigant_portal.app.views import (
    assistant,
    endpoints,
    pages,
)

app_patterns = [
    # Main pages
    path("", pages.home, name="home"),
    path("about/", pages.about, name="about"),
    path("privacy/", pages.privacy, name="privacy"),
    path("accessibility/", pages.accessibility, name="accessibility"),
    path("topics/<slug:slug>/", pages.topic_detail, name="topic_detail"),
    path("t/<slug:court>/<slug:topic>/", pages.deep_link, name="deep_link"),
    path(
        "t/<slug:court>/<slug:topic>/<slug:role>/",
        pages.topic_flow,
        name="topic_flow",
    ),
    path(
        "t/<slug:court>/<slug:topic>/<slug:role>/download/<slug:output_id>/",
        pages.topic_flow_download,
        name="topic_flow_download",
    ),
    path("chat/", pages.chat_page, name="chat"),
    path("chat-v2/", pages.chat_v2_view, name="chat_v2"),
    path("chat/action-plan/", endpoints.action_plan, name="action_plan"),
    path("style-guide/", pages.style_guide, name="style_guide"),
    # Agent testing
    path("test/<str:agent_name>/", pages.test_agent, name="test_agent"),
    # Profile
    path("profile/", pages.ProfileDetailView.as_view(), name="profile"),
    path(
        "profile/edit/", pages.ProfileEditView.as_view(), name="profile_edit"
    ),
]

api_patterns = [
    # API endpoints (used by home page chat)
    path("stream/", endpoints.stream, name="stream"),
    path("search/", endpoints.search, name="search"),
    path("status/", endpoints.status, name="status"),
    path("upload/", endpoints.upload_document, name="upload"),
    path("summarize/", endpoints.summarize_conversation, name="summarize"),
    # Case info endpoints
    path("case/", endpoints.case_get, name="case_get"),
    path("case/save/", endpoints.case_save, name="case_save"),
    path(
        "case/timeline/", endpoints.case_timeline_add, name="case_timeline_add"
    ),
    path("case/clear/", endpoints.case_clear, name="case_clear"),
    path("case/resolve/", endpoints.case_resolve, name="case_resolve"),
    path(
        "case/action-item/<uuid:item_id>/toggle/",
        endpoints.action_item_toggle,
        name="action_item_toggle",
    ),
    path(
        "case/deadline/<uuid:deadline_id>/remind/",
        endpoints.deadline_reminder_toggle,
        name="deadline_reminder_toggle",
    ),
]

assistant_patterns = [
    path("stream/", assistant.stream, name="stream"),
    path("threads/", assistant.thread_list, name="thread_list"),
    path(
        "threads/<uuid:thread_id>/",
        assistant.message_list,
        name="message_list",
    ),
    path(
        "threads/<uuid:thread_id>/usage/",
        assistant.thread_usage,
        name="thread_usage",
    ),
    path(
        "threads/<uuid:thread_id>/delete/",
        assistant.thread_delete,
        name="thread_delete",
    ),
    path("uploads/", assistant.upload_list, name="upload_list"),
    path("uploads/create/", assistant.upload_create, name="upload_create"),
    path(
        "uploads/<uuid:upload_id>/delete/",
        assistant.upload_delete,
        name="upload_delete",
    ),
]

urlpatterns = [
    # App Routes
    *i18n_patterns(
        path(
            "",
            include((app_patterns, "litigant_portal.app"), namespace="pages"),
        ),
        prefix_default_language=False,
    ),
    # API Routes
    path("api/health/", endpoints.health, name="health"),
    path(
        "api/chat/",
        include((api_patterns, "litigant_portal.app"), namespace="endpoints"),
    ),
    path(
        "api/agents/assistant/",
        include(
            (assistant_patterns, "litigant_portal.app"),
            namespace="assistant",
        ),
    ),
    # Allauth Routes
    path("accounts/", include("allauth.urls")),
    # Django Admin
    path("django-admin/", admin.site.urls),
    # i18n Routes
    path("i18n/", include("django.conf.urls.i18n")),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
]

# Serve uploaded media when USE_S3 is false.
if not settings.USE_S3:
    urlpatterns += [
        re_path(
            rf"^{re.escape(settings.MEDIA_URL.lstrip('/'))}(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
