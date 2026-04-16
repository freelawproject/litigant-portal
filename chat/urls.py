from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    # API endpoints (used by home page chat)
    path("stream/", views.stream, name="stream"),
    path("search/", views.search, name="search"),
    path("status/", views.status, name="status"),
    path("upload/", views.upload_document, name="upload"),
    path("summarize/", views.summarize_conversation, name="summarize"),
    # Case info endpoints
    path("case/", views.case_get, name="case_get"),
    path("case/save/", views.case_save, name="case_save"),
    path("case/timeline/", views.case_timeline_add, name="case_timeline_add"),
    path("case/clear/", views.case_clear, name="case_clear"),
    path("case/resolve/", views.case_resolve, name="case_resolve"),
    path(
        "case/action-item/<uuid:item_id>/toggle/",
        views.action_item_toggle,
        name="action_item_toggle",
    ),
    path(
        "case/deadline/<uuid:deadline_id>/remind/",
        views.deadline_reminder_toggle,
        name="deadline_reminder_toggle",
    ),
]
