from django.shortcuts import render


def demo_page(request):
    """Demo page to test Django-Cotton + Tailwind + AlpineJS setup"""
    context = {
        "page_title": "Demo Page - Tech Stack Test",
    }
    return render(request, "pages/demo.html", context)
