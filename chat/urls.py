from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.chat_home, name="home"),
    path("send/", views.send_message, name="send"),
    path("stream/<uuid:session_id>/", views.stream_response, name="stream"),
    path("search/", views.keyword_search, name="search"),
    path("status/", views.chat_status, name="status"),
]
