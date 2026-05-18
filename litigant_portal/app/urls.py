from django.urls import path

from litigant_portal.app import views

urlpatterns = [
    path("", views.index, name="index"),
]
