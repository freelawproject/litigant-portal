from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("demo/", views.demo_page, name="demo"),
]
