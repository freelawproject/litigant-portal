from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .decorators import admin_required
from .forms import ChatModelForm, SiteForm
from .models import ChatModel, Site

USERS_PAGE_SIZE = 25


@admin_required
def index(request):
    site = Site.load()
    if request.method == "POST":
        form = SiteForm(request.POST, instance=site)
        if form.is_valid():
            form.save()
            messages.success(request, _("Settings saved."))
            return redirect("admin_site:index")
    else:
        form = SiteForm(instance=site)
    return render(
        request,
        "pages/admin/index.html",
        {
            "site": site,
            "form": form,
            "chat_models": ChatModel.objects.order_by("name"),
            "active_model": site.chat_model,
        },
    )


@admin_required
def chat_model_create(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    form = ChatModelForm(request.POST)
    if form.is_valid():
        obj = form.save()
        messages.success(
            request,
            _("Added chat model “%(name)s”.") % {"name": obj.name},
        )
    else:
        messages.error(request, _("Could not add model — check the fields."))
    return redirect("admin_site:index")


@admin_required
def chat_model_delete(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    chat_model = get_object_or_404(ChatModel, pk=pk)
    name = chat_model.name
    chat_model.delete()
    messages.success(
        request, _("Removed chat model “%(name)s”.") % {"name": name}
    )
    return redirect("admin_site:index")


@admin_required
def users(request):
    User = get_user_model()
    return render(
        request,
        "pages/admin/users.html",
        {"total_users": User.objects.count()},
    )


@admin_required
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
