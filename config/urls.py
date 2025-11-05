"""URL configuration for config project."""

from django.contrib import admin
from django.urls import path

from portal import views

urlpatterns = [
    path("", views.index, name="index"),
    path("camera/", views.camera_demo, name="camera_demo"),
    path("admin/", admin.site.urls),
]
