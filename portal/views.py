"""Views for the portal app."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def index(request: HttpRequest) -> HttpResponse:
    """Home page view."""
    return render(request, "index.html")
