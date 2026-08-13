# Permissions

How access to the in-app admin panel is granted and checked.

The portal uses Django's own permission framework. There is no custom
permission layer, no bespoke predicate helpers, and nothing to import before
you can ask whether a user may do something — `user.has_perm(...)` is the
whole API.

Declared in: [`models/site.py`](../../litigant_portal/app/models/site.py)
(`Site.Meta.permissions`) ·
mapped to groups in
[`permissions.py`](../../litigant_portal/app/permissions.py) ·
provisioned by [`signals.py`](../../litigant_portal/app/signals.py)
(`ensure_permission_groups`) ·
granted through the admin panel's Users tab.

## The two permissions

| Permission              | Who it's for                                       | Grants                                                    |
| ----------------------- | -------------------------------------------------- | --------------------------------------------------------- |
| `app.manage_site`       | Court partners and administrators running the site | Access to the admin panel and everything configured there |
| `app.manage_developers` | Free Law Project developers working on the portal  | Ability to grant and revoke developer access              |

The split is about **who the person is to the project**, not how much they
are trusted. A court partner configuring their own jurisdiction's content is
the intended holder of `manage_site` — it is the normal, expected permission
for the people the portal is built for. `manage_developers` is narrower in a
different direction: it is for FLP staff building and operating the portal,
and its only power is deciding who else counts as a developer.

Both are declared on `Site.Meta.permissions`, which is why they carry the
`app.` prefix. That prefix is the app label, not the model — a permission
lives on some model by necessity, but these gate the application, not the
`Site` row.

These are separate from the `add_*` / `change_*` / `delete_*` / `view_*`
permissions Django generates for every model. Those gate Django admin at
`/django-admin/`. A user can hold `manage_site` and have no Django-admin
access at all, and that is the normal case.

## The two groups

Permissions are granted through groups, never assigned to users directly.

| Group        | Who belongs to it                                 | Holds                              |
| ------------ | ------------------------------------------------- | ---------------------------------- |
| `Admins`     | Court partners and site administrators            | `manage_site`                      |
| `Developers` | Free Law Project developers working on the portal | `manage_site`, `manage_developers` |

`Developers` is a superset: a developer can do anything an admin can, plus
promote other developers. FLP developers need the admin panel to build and
support it, so they hold `manage_site` in their own right rather than by
also being added to `Admins`. A consequence worth knowing: removing someone
from `Admins` does not remove their admin access if they are also a
developer.

Both groups are created and stocked by a `post_migrate` receiver, so every
environment converges on the same definition after `migrate` — a fresh
database, a restored dump, and a long-running deployment all end up
identical. The receiver is additive: permissions granted to a group by hand
are left alone.

**Superusers implicitly hold every permission.** `has_perm` returns `True`
for them without any group membership, so a superuser never needs to be
added to `Admins` or `Developers`.

## Checking a permission

### In views — use a decorator

This is the expected pattern. Guard at the boundary: the view or endpoint is
where a permission is enforced, never a selector or service.

**Page views** use Django's built-in decorator:

```python
from django.contrib.auth.decorators import login_required, permission_required


@login_required
@permission_required("app.manage_site", raise_exception=True)
def admin(request):
    ...
```

`raise_exception=True` produces a 403 for a signed-in user who lacks the
permission. Without it, Django redirects them to the login page, which is
misleading — they are already logged in.

Keep `login_required` **outermost**. It sends an anonymous visitor to log in,
while `permission_required` 403s an authenticated user who lacks the
permission. Reversing them turns the anonymous case into a bare 403.

**JSON endpoints** use the app's own decorators from
[`views/utils.py`](../../litigant_portal/app/views/utils.py), which are
available to any surface:

```python
from litigant_portal.app.views.utils import (
    manage_site_required,
    manage_developers_required,
)


@require_GET
@manage_site_required
def user_list_view(request):
    ...
```

They exist rather than reusing `permission_required` because the built-in
raises `PermissionDenied`, which renders an **HTML** 403 page. These
endpoints must answer with `{"error": "Forbidden"}` and a 403 status,
because the frontend parses the response body.

### In templates — use `perms`

Django's auth context processor puts a `perms` object in every template
context. Nothing needs to be passed from the view:

```django
{% if perms.app.manage_site %}
  <a href="{% url 'pages:admin_dashboard' %}">{% trans "Admin" %}</a>
{% endif %}
```

```django
{% if perms.app.manage_developers %}
  <th>{% trans "Developer" %}</th>
{% endif %}
```

The lookup is `perms.<app_label>.<codename>`. It is safe for anonymous
visitors — `perms` resolves to `False` for them rather than erroring.

Template guards hide UI. They are not access control on their own: anything
they hide must also be guarded at the view or endpoint that serves it.

### Anywhere else — `has_perm`

When a check does not fit a decorator — a branch inside a view, a management
command, a queryset built differently for different callers — ask the user
directly:

```python
if request.user.has_perm("app.manage_developers"):
    ...
```

```python
can_promote = user.has_perm("app.manage_site")
```

Prefer a decorator when the whole view is gated. Reach for `has_perm` when
only part of the behavior changes.

**Do not wrap `has_perm` in a helper.** A selector like
`user_can_manage_site(user=...)` adds a layer over a one-line call, and
hides which permission is actually being checked at the call site.

## Granting and revoking

Group membership is changed through the admin panel's Users tab, which calls
the services in
[`services/user.py`](../../litigant_portal/app/services/user.py):

```python
from litigant_portal.app.services.user import (
    user_admin_toggle,
    user_developer_toggle,
)

user_admin_toggle(user=target)       # -> new state, True if now in Admins
user_developer_toggle(user=target)   # -> new state, True if now a Developer
```

Both are idempotent toggles that return the resulting state.

Two self-revocation guards are enforced server-side, so nobody locks
themselves out:

- An admin cannot toggle their own admin access. A developer can, because
  they keep `manage_site` through the `Developers` group regardless.
- Nobody can revoke their own developer status.

The Users tab pills reflect **group membership**, not effective access — a
developer shows `Admin: Off` while still holding `manage_site`. That is
deliberate: the toggles grant groups, so showing group state is what makes
them round-trip honestly.

## Gotcha: permissions are cached per instance

`has_perm` caches its result on the user object the first time it is called.
Changing a user's groups does not invalidate that cache, so a stale instance
keeps answering with the old value:

```python
user_admin_toggle(user=user)
user.has_perm("app.manage_site")   # may still be the pre-toggle answer
```

Re-fetch the user after changing group membership:

```python
user = User.objects.get(pk=user.pk)
user.has_perm("app.manage_site")   # correct
```

This matters mostly in tests and management commands. A normal request loads
the user fresh, so a permission change takes effect on the user's next
request.
