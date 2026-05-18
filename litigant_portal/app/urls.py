from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog

from litigant_portal.app import views

localized_patterns = i18n_patterns(
    path("", views.index, name="index"),
    prefix_default_language=False,
)

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    *localized_patterns,
]
