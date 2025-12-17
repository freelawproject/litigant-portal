from django.shortcuts import render


def home(request):
    """Home page - main app landing page"""
    return render(request, "pages/home.html")


def style_guide(request):
    """Design tokens and component library"""
    return render(request, "pages/style_guide.html")
