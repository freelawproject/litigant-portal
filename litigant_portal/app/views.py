from django.shortcuts import render


def index(request):
    return render(request, "index.html")


def register(request):
    return render(request, "register.html")


def login(request):
    return render(request, "login.html")


def chat(request):
    return render(request, "chat.html")


def search(request):
    return render(request, "search.html")


def profile(request):
    return render(request, "profile.html")


def admin(request):
    return render(request, "admin.html")


def about(request):
    return render(request, "about.html")
