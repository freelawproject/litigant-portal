from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("register/", views.register, name="register"),
    path("login/", views.login, name="login"),
    path("chat/", views.chat, name="chat"),
    path("search/", views.search, name="search"),
    path("profile/", views.profile, name="profile"),
    path("admin/", views.admin, name="admin"),
    path("about/", views.about, name="about"),
]
