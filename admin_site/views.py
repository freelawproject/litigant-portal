from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .decorators import superuser_required
from .forms import ChatModelForm, SiteForm
from .models import ChatModel, Site


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
