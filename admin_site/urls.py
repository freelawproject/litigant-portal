from django.urls import path

from . import views

app_name = "admin_site"

urlpatterns = [
    path("", views.index, name="index"),
    path("site/", views.site_edit, name="site_edit"),
    path("chat-models/", views.chat_model_list, name="chat_model_list"),
    path(
        "chat-models/new/",
        views.chat_model_create,
        name="chat_model_create",
    ),
    path(
        "chat-models/<int:pk>/activate/",
        views.chat_model_activate,
        name="chat_model_activate",
    ),
    path(
        "chat-models/deactivate/",
        views.chat_model_deactivate,
        name="chat_model_deactivate",
    ),
    path(
        "chat-models/<int:pk>/delete/",
        views.chat_model_delete,
        name="chat_model_delete",
    ),
    path("users/", views.users, name="users"),
    path("users/data/", views.users_data, name="users_data"),
]
