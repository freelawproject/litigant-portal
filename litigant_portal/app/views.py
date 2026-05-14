import json

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
)
from django.contrib.auth import (
    login as auth_login,
)
from django.contrib.auth import (
    logout as auth_logout,
)
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)

from litigant_portal.agents import agent_registry
from litigant_portal.app.models import ChatThread
from litigant_portal.app.utils import get_user_identity


def index(request):
    return render(request, "index.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("app")

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm_password") or ""
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()

        if not email or not password:
            messages.error(request, "Email and password are required.")
        elif password != confirm_password:
            messages.error(request, "Passwords do not match.")
        elif User.objects.filter(username=email).exists():
            messages.error(
                request, "An account with this email already exists."
            )
        else:
            try:
                validate_password(password)
            except ValidationError as e:
                for msg in e.messages:
                    messages.error(request, msg)
            else:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                auth_login(request, user)
                return redirect("app")
    return render(request, "auth/register.html")


def login(request):
    if request.user.is_authenticated:
        return redirect("app")

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=email, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect("app")
        messages.error(request, "Invalid email or password.")
    return render(request, "auth/login.html")


def logout(request):
    if request.method == "POST":
        auth_logout(request)
    return redirect("index")


@ensure_csrf_cookie
def app(request):
    return render(
        request,
        "app.html",
        {"agent_name": "weather-agent"},
    )


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------


@require_POST
def chat(request, agent_name: str):
    """Run one turn of the agent and stream its raw events back as NDJSON.

    Body (JSON):
        message: str (required)
        thread_id: int | null — null/missing creates a new thread

    Response:
        Content-Type: application/x-ndjson
        X-Thread-Id: <id of the thread this message landed in>
        Body: one JSON event per line, exactly as yielded by Agent.stream_run.
    """
    agent_class = agent_registry.get(agent_name)
    if agent_class is None:
        raise Http404(f"Unknown agent: {agent_name}")

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    message_text = (body.get("message") or "").strip()
    if not message_text:
        return JsonResponse({"error": "Message is required."}, status=400)

    uid = get_user_identity(request)

    thread_id = body.get("thread_id")
    if thread_id:
        thread = get_object_or_404(
            ChatThread, id=thread_id, uid=uid, agent_name=agent_name
        )
    else:
        thread = ChatThread.objects.create(uid=uid, agent_name=agent_name)

    agent = agent_class(thread=thread)

    def stream():
        for event in agent.stream_run(message_text):
            yield json.dumps(event) + "\n"

    response = StreamingHttpResponse(
        stream(), content_type="application/x-ndjson"
    )
    response["X-Thread-Id"] = str(thread.id)
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@require_GET
def chat_threads(request, agent_name: str):
    """List the current identity's chat threads for a given agent."""
    if agent_name not in agent_registry:
        raise Http404(f"Unknown agent: {agent_name}")
    uid = get_user_identity(request)
    threads = ChatThread.objects.filter(uid=uid, agent_name=agent_name)
    return JsonResponse(
        {
            "threads": [
                {"id": t.id, "updated_at": t.updated_at.isoformat()}
                for t in threads
            ],
        }
    )


@require_http_methods(["GET", "DELETE"])
def chat_thread(request, agent_name: str, thread_id: int):
    """Return a thread's raw stored message history, or delete it."""
    if agent_name not in agent_registry:
        raise Http404(f"Unknown agent: {agent_name}")
    uid = get_user_identity(request)
    thread = get_object_or_404(
        ChatThread, id=thread_id, uid=uid, agent_name=agent_name
    )
    if request.method == "DELETE":
        thread.delete()
        return JsonResponse({"deleted": True, "id": thread_id})
    return JsonResponse({"id": thread.id, "messages": thread.history})


def search(request):
    return render(request, "search.html")


def profile(request):
    return render(request, "profile.html")


def admin(request):
    if not request.user.is_staff:
        return redirect("index")
    return render(request, "admin.html")


def about(request):
    return render(request, "about.html")
