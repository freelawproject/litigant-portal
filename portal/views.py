"""Views for the portal app."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def index(request: HttpRequest) -> HttpResponse:
    """Home page view."""
    return render(request, "index.html")


def camera_demo(request: HttpRequest) -> HttpResponse:
    """Document camera demo page."""
    return render(request, "demo_camera.html")
