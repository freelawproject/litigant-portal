from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .decorators import superuser_required
from .forms import ChatModelForm, SiteForm
from .models import ChatModel, Site

USERS_PAGE_SIZE = 25


@superuser_required
def index(request):
    site = Site.load()
    return render(
        request,
        "pages/admin/index.html",
        {
            "site": site,
            "chat_model_count": ChatModel.objects.count(),
        },
    )


@superuser_required
def site_edit(request):
    site = Site.load()
    if request.method == "POST":
        form = SiteForm(request.POST, instance=site)
        if form.is_valid():
            form.save()
            messages.success(request, _("Site settings saved."))
            return redirect("admin_site:index")
    else:
        form = SiteForm(instance=site)
    return render(
        request,
        "pages/admin/site_edit.html",
        {"form": form, "site": site},
    )


@superuser_required
def chat_model_list(request):
    site = Site.load()
    return render(
        request,
        "pages/admin/chat_model_list.html",
        {
            "chat_models": ChatModel.objects.order_by("name"),
            "active_model": site.chat_model,
        },
    )


@superuser_required
def chat_model_create(request):
    if request.method == "POST":
        form = ChatModelForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(
                request,
                _("Added chat model “%(name)s”.") % {"name": obj.name},
            )
            return redirect("admin_site:chat_model_list")
    else:
        form = ChatModelForm()
    return render(
        request,
        "pages/admin/chat_model_form.html",
        {"form": form},
    )


@superuser_required
def chat_model_activate(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    chat_model = get_object_or_404(ChatModel, pk=pk)
    site = Site.load()
    site.chat_model = chat_model
    site.save()
    messages.success(
        request,
        _("Activated “%(name)s” for chat.") % {"name": chat_model.name},
    )
    return redirect("admin_site:chat_model_list")


@superuser_required
def chat_model_deactivate(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    site = Site.load()
    site.chat_model = None
    site.save()
    messages.success(request, _("Chat disabled."))
    return redirect("admin_site:chat_model_list")


@superuser_required
def chat_model_delete(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    chat_model = get_object_or_404(ChatModel, pk=pk)
    name = chat_model.name
    chat_model.delete()
    messages.success(
        request, _("Removed chat model “%(name)s”.") % {"name": name}
    )
    return redirect("admin_site:chat_model_list")


@superuser_required
def users(request):
    return render(request, "pages/admin/users.html")


@superuser_required
def users_data(request):
    User = get_user_model()
    query = request.GET.get("q", "").strip()

    try:
        page_num = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page_num = 1

    qs = User.objects.all().order_by("-date_joined")
    if query:
        qs = qs.filter(email__icontains=query)

    paginator = Paginator(qs, USERS_PAGE_SIZE)
    page = paginator.get_page(page_num)

    return JsonResponse(
        {
            "users": [
                {
                    "id": u.id,
                    "email": u.email or u.get_username(),
                    "date_joined": u.date_joined.isoformat()
                    if u.date_joined
                    else None,
                    "last_login": u.last_login.isoformat()
                    if u.last_login
                    else None,
                    "is_staff": u.is_staff,
                    "is_superuser": u.is_superuser,
                    "is_active": u.is_active,
                }
                for u in page.object_list
            ],
            "page": page.number,
            "page_count": paginator.num_pages,
            "total": paginator.count,
            "has_next": page.has_next(),
            "has_prev": page.has_previous(),
            "page_size": USERS_PAGE_SIZE,
        }
    )
