from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required(login_url="/accounts/login/")
def index(request):
    """Branded admin landing page."""
    return render(request, "pages/admin/index.html")
