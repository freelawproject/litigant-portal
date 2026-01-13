from django.http import HttpResponse
from django.shortcuts import render


def health(request):
    """Lightweight health check for Fly.io."""
    return HttpResponse("ok")


def home(request):
    """Home page - main app landing page"""
    return render(request, "pages/home.html")


def style_guide(request):
    """Design tokens and component library"""
    return render(request, "pages/style_guide.html")
