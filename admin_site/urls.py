from django.urls import path

from . import views

app_name = "admin_site"

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "chat-models/new/",
        views.chat_model_create,
        name="chat_model_create",
    ),
    path(
        "chat-models/<int:pk>/delete/",
        views.chat_model_delete,
        name="chat_model_delete",
    ),
    path("users/", views.users, name="users"),
    path("users/data/", views.users_data, name="users_data"),
]
