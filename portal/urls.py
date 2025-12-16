from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("components/", views.components, name="components"),
    path("style-guide/", views.style_guide, name="style_guide"),
]
