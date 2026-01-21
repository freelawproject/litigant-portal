from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("stream/", views.stream, name="stream"),
    path("search/", views.search, name="search"),
    path("status/", views.status, name="status"),
]
