from django.shortcuts import render


def home(request):
    """Home page placeholder - will be the main app landing page"""
    return render(request, "pages/home.html")


def components(request):
    """Atomic design component library"""
    return render(request, "pages/components.html")


def style_guide(request):
    """Tailwind CSS theme and design token documentation"""
    return render(request, "pages/style_guide.html")
