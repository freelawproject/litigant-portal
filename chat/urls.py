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
]
