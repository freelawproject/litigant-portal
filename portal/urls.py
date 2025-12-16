# TODO: Replace distill_path with django.urls.path when switching to Docker
from django_distill import distill_path

from . import views

app_name = "portal"

urlpatterns = [
    distill_path("", views.home, name="home"),
    distill_path("components/", views.components, name="components"),
    distill_path("style-guide/", views.style_guide, name="style_guide"),
]
