from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("dashboard-demo/", views.dashboard_demo, name="dashboard_demo"),
    path("style-guide/", views.style_guide, name="style_guide"),
    # Agent testing
    path("test/<str:agent_name>/", views.test_agent, name="test_agent"),
    # Profile
    path("profile/", views.ProfileDetailView.as_view(), name="profile"),
    path(
        "profile/edit/", views.ProfileEditView.as_view(), name="profile_edit"
    ),
]
