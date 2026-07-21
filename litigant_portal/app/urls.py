import re

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.i18n import JavaScriptCatalog
from django.views.static import serve

from litigant_portal.app.views import (
    admin as admin_views,
)
from litigant_portal.app.views import (
    assistant,
    pages,
)
from litigant_portal.app.views import (
    health as health_views,
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
    path("admin/", pages.admin, name="admin_dashboard"),
    path("chat/", pages.chat_view, name="chat"),
    path("style-guide/", pages.style_guide, name="style_guide"),
    # Profile
    path("profile/", pages.ProfileDetailView.as_view(), name="profile"),
    path(
        "profile/edit/", pages.ProfileEditView.as_view(), name="profile_edit"
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

admin_api_patterns = [
    path("sites/", admin_views.site_list_view, name="site_list"),
    path(
        "sites/<uuid:site_id>/update/",
        admin_views.site_update_view,
        name="site_update",
    ),
    path(
        "sites/<uuid:site_id>/activate/",
        admin_views.site_activate_view,
        name="site_activate",
    ),
    path("topics/", admin_views.topic_list_view, name="topic_list"),
    path(
        "topics/create/",
        admin_views.topic_create_view,
        name="topic_create",
    ),
    path(
        "topics/<uuid:topic_id>/update/",
        admin_views.topic_update_view,
        name="topic_update",
    ),
    path(
        "topics/<uuid:topic_id>/delete/",
        admin_views.topic_delete_view,
        name="topic_delete",
    ),
    path("users/", admin_views.user_list_view, name="user_list"),
    path(
        "users/<int:user_id>/admin/toggle/",
        admin_views.user_admin_toggle_view,
        name="user_admin_toggle",
    ),
    path(
        "users/<int:user_id>/developer/toggle/",
        admin_views.user_developer_toggle_view,
        name="user_developer_toggle",
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
    # Health check
    path("api/health/", health_views.health, name="health"),
    path(
        "api/agents/assistant/",
        include(
            (assistant_patterns, "litigant_portal.app"),
            namespace="assistant",
        ),
    ),
    path(
        "api/admin/",
        include(
            (admin_api_patterns, "litigant_portal.app"),
            namespace="admin_api",
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
