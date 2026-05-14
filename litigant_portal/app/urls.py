from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("register/", views.register, name="register"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("app/", views.app, name="app"),
    path("search/", views.search, name="search"),
    path("profile/", views.profile, name="profile"),
    path("admin/", views.admin, name="admin"),
    path("about/", views.about, name="about"),
    path("chat/<str:agent_name>/", views.chat, name="chat"),
    path(
        "chat/<str:agent_name>/threads/",
        views.chat_threads,
        name="chat-threads",
    ),
    path(
        "chat/<str:agent_name>/threads/<int:thread_id>/",
        views.chat_thread,
        name="chat-thread",
    ),
]
