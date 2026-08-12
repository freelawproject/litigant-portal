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
    health,
    pages,
)
from litigant_portal.app.views import (
    topic_flow as topic_flow_views,
)

app_patterns = [
    path("", pages.home, name="home"),
    path("chat/", pages.chat_view, name="chat"),
    path(
        "t/<slug:topic_slug>/",
        pages.topic_detail,
        name="topic",
    ),
    path(
        "t/<slug:topic_slug>/<slug:flow_slug>/",
        pages.topic_flow_detail,
        name="topic_flow",
    ),
    path("admin/", pages.admin, name="admin_dashboard"),
    path("profile/", pages.ProfileDetailView.as_view(), name="profile"),
    path(
        "profile/edit/", pages.ProfileEditView.as_view(), name="profile_edit"
    ),
    path("about/", pages.about, name="about"),
    path("privacy/", pages.privacy, name="privacy"),
    path("accessibility/", pages.accessibility, name="accessibility"),
    path("style-guide/", pages.style_guide, name="style_guide"),
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

topic_flow_api_patterns = [
    path(
        "<slug:topic_slug>/<slug:flow_slug>/interview/",
        topic_flow_views.topic_flow_interview_view,
        name="interview",
    ),
    path(
        "<slug:topic_slug>/<slug:flow_slug>/answers/",
        topic_flow_views.topic_flow_answers_view,
        name="answers",
    ),
    path(
        "<slug:topic_slug>/<slug:flow_slug>/packet/",
        topic_flow_views.topic_flow_packet_view,
        name="packet",
    ),
    path(
        "<slug:topic_slug>/<slug:flow_slug>/forms/<slug:form_slug>/",
        topic_flow_views.topic_flow_form_view,
        name="form",
    ),
    path(
        "<slug:topic_slug>/<slug:flow_slug>/calendar.ics",
        topic_flow_views.topic_flow_calendar_view,
        name="calendar",
    ),
    path(
        "<slug:topic_slug>/<slug:flow_slug>/contacts.vcf",
        topic_flow_views.topic_flow_contacts_view,
        name="contacts",
    ),
]

admin_api_patterns = [
    path("site/", admin_views.site_view, name="site"),
    path(
        "site/court-details/",
        admin_views.site_court_details_update_view,
        name="site_court_details_update",
    ),
    path(
        "site/models/",
        admin_views.site_models_update_view,
        name="site_models_update",
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
    path(
        "topics/<uuid:topic_id>/move/",
        admin_views.topic_move_view,
        name="topic_move",
    ),
    path(
        "topics/<uuid:topic_id>/flows/create/",
        admin_views.topic_flow_create_view,
        name="topic_flow_create",
    ),
    path(
        "flows/<uuid:flow_id>/content/",
        admin_views.topic_flow_content_update_view,
        name="topic_flow_content_update",
    ),
    path(
        "flows/<uuid:flow_id>/details/",
        admin_views.topic_flow_details_update_view,
        name="topic_flow_details_update",
    ),
    path(
        "flows/<uuid:flow_id>/delete/",
        admin_views.topic_flow_delete_view,
        name="topic_flow_delete",
    ),
    path(
        "flows/<uuid:flow_id>/enabled/",
        admin_views.topic_flow_enabled_update_view,
        name="topic_flow_enabled_update",
    ),
    path(
        "flows/<uuid:flow_id>/field-groups/create/",
        admin_views.topic_flow_field_group_create_view,
        name="topic_flow_field_group_create",
    ),
    path(
        "field-groups/<uuid:group_id>/update/",
        admin_views.topic_flow_field_group_update_view,
        name="topic_flow_field_group_update",
    ),
    path(
        "field-groups/<uuid:group_id>/move/",
        admin_views.topic_flow_field_group_move_view,
        name="topic_flow_field_group_move",
    ),
    path(
        "field-groups/<uuid:group_id>/delete/",
        admin_views.topic_flow_field_group_delete_view,
        name="topic_flow_field_group_delete",
    ),
    path(
        "field-groups/<uuid:group_id>/fields/create/",
        admin_views.topic_flow_field_create_view,
        name="topic_flow_field_create",
    ),
    path(
        "fields/<uuid:field_id>/update/",
        admin_views.topic_flow_field_update_view,
        name="topic_flow_field_update",
    ),
    path(
        "fields/<uuid:field_id>/move/",
        admin_views.topic_flow_field_move_view,
        name="topic_flow_field_move",
    ),
    path(
        "fields/<uuid:field_id>/delete/",
        admin_views.topic_flow_field_delete_view,
        name="topic_flow_field_delete",
    ),
    path(
        "flows/<uuid:flow_id>/deadlines/create/",
        admin_views.topic_flow_deadline_create_view,
        name="topic_flow_deadline_create",
    ),
    path(
        "deadlines/<uuid:deadline_id>/update/",
        admin_views.topic_flow_deadline_update_view,
        name="topic_flow_deadline_update",
    ),
    path(
        "deadlines/<uuid:deadline_id>/delete/",
        admin_views.topic_flow_deadline_delete_view,
        name="topic_flow_deadline_delete",
    ),
    path(
        "deadlines/<uuid:deadline_id>/move/",
        admin_views.topic_flow_deadline_move_view,
        name="topic_flow_deadline_move",
    ),
    path(
        "flows/<uuid:flow_id>/links/create/",
        admin_views.topic_flow_link_create_view,
        name="topic_flow_link_create",
    ),
    path(
        "links/<uuid:link_id>/update/",
        admin_views.topic_flow_link_update_view,
        name="topic_flow_link_update",
    ),
    path(
        "links/<uuid:link_id>/delete/",
        admin_views.topic_flow_link_delete_view,
        name="topic_flow_link_delete",
    ),
    path(
        "links/<uuid:link_id>/move/",
        admin_views.topic_flow_link_move_view,
        name="topic_flow_link_move",
    ),
    path(
        "flows/<uuid:flow_id>/forms/create/",
        admin_views.topic_flow_form_create_view,
        name="topic_flow_form_create",
    ),
    path(
        "forms/<uuid:form_id>/move/",
        admin_views.topic_flow_form_move_view,
        name="topic_flow_form_move",
    ),
    path(
        "forms/<uuid:form_id>/update/",
        admin_views.topic_flow_form_update_view,
        name="topic_flow_form_update",
    ),
    path(
        "forms/<uuid:form_id>/delete/",
        admin_views.topic_flow_form_delete_view,
        name="topic_flow_form_delete",
    ),
    path(
        "forms/<uuid:form_id>/preview/",
        admin_views.topic_flow_form_preview_view,
        name="topic_flow_form_preview",
    ),
    path("contacts/", admin_views.contact_list_view, name="contact_list"),
    path(
        "contacts/create/",
        admin_views.contact_create_view,
        name="contact_create",
    ),
    path(
        "contacts/<uuid:contact_id>/update/",
        admin_views.contact_update_view,
        name="contact_update",
    ),
    path(
        "contacts/<uuid:contact_id>/delete/",
        admin_views.contact_delete_view,
        name="contact_delete",
    ),
    path(
        "contacts/<uuid:contact_id>/move/",
        admin_views.contact_move_view,
        name="contact_move",
    ),
    path("resources/", admin_views.resource_list_view, name="resource_list"),
    path(
        "resources/create/",
        admin_views.resource_create_view,
        name="resource_create",
    ),
    path(
        "resources/<uuid:resource_id>/update/",
        admin_views.resource_update_view,
        name="resource_update",
    ),
    path(
        "resources/<uuid:resource_id>/delete/",
        admin_views.resource_delete_view,
        name="resource_delete",
    ),
    path(
        "resources/<uuid:resource_id>/move/",
        admin_views.resource_move_view,
        name="resource_move",
    ),
    path(
        "library/courts/",
        admin_views.library_court_list_view,
        name="library_court_list",
    ),
    path(
        "library/courts/<slug:slug>/apply/",
        admin_views.library_court_apply_view,
        name="library_court_apply",
    ),
    path(
        "library/topics/",
        admin_views.library_topic_list_view,
        name="library_topic_list",
    ),
    path(
        "library/topics/<slug:court_slug>/<slug:topic_slug>/apply/",
        admin_views.library_topic_apply_view,
        name="library_topic_apply",
    ),
    path(
        "library/topics/<slug:court_slug>/<slug:topic_slug>/flows/<slug:flow_slug>/apply/",
        admin_views.library_topic_flow_apply_view,
        name="library_topic_flow_apply",
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
    # Topic Flow API Endpoints
    path(
        "api/topic-flow/",
        include(
            (topic_flow_api_patterns, "litigant_portal.app"),
            namespace="topic_flow_api",
        ),
    ),
    # Assistant API Endpoints
    path(
        "api/agents/assistant/",
        include(
            (assistant_patterns, "litigant_portal.app"),
            namespace="assistant",
        ),
    ),
    # Admin API Endpoints
    path(
        "api/admin/",
        include(
            (admin_api_patterns, "litigant_portal.app"),
            namespace="admin_api",
        ),
    ),
    # Health check
    path("api/health/", health.health, name="health"),
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
