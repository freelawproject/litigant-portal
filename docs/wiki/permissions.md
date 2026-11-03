# Permissions

Who can reach the in-app admin panel, and who can manage whose account.

The portal uses Django's own permission framework: `user.has_perm(...)` is
the whole API for access. Who may manage whom is one more rule on top, the
tier comparison below.

Declared in: [`models/site.py`](../../litigant_portal/app/models/site.py)
(`Site.Meta.permissions`) ·
groups and tiers in
[`permissions.py`](../../litigant_portal/app/permissions.py) ·
provisioned by [`signals.py`](../../litigant_portal/app/signals.py)
(`ensure_permission_groups`) ·
tier rule in [`selectors/user.py`](../../litigant_portal/app/selectors/user.py)
(`user_tier`, `user_is_manageable`).

## The tiers

Superuser → FLP Staff → Court Admin → App user (#1135). **Each tier manages
the tiers below it, never its own tier, itself, or anything above.** Every
tier is also an app user, so any admin account can be used for testing.

|                                | Superuser                          | FLP Staff                      | Court Admin           | App user            |
| ------------------------------ | ---------------------------------- | ------------------------------ | --------------------- | ------------------- |
| Who it's for                   | Mitch, infra                       | FLP's own people               | A court's own account | Everyone else       |
| Manages                        | FLP Staff, Court Admins, app users | Court Admins, app users        | App users             | —                   |
| Managed by                     | Infra (`bootstrap_superuser`)      | A superuser                    | FLP Staff and up      | Court Admins and up |
| /admin tabs                    | All                                | All (env features still apply) | Users only            | —                   |
| Django admin: read transcripts | ✓                                  | ✓ (with `is_staff`, view only) | —                     | —                   |
| Chat token and agent state     | ✓                                  | ✓                              | —                     | —                   |
| Stored as                      | `is_superuser`                     | `FLP Staff` group              | `Court Admins` group  | No group            |

"Manages" means add an account, set its password, disable or re-enable it,
and delete it, and give it a role below one's own: FLP Staff make Court
Admins, and only a superuser makes FLP Staff (`user_role_set`, which also
sets `is_staff` for FLP Staff and clears it for every other role).

`user_tier` reads the tier from the account itself: `is_superuser` first,
then `is_staff` or the FLP Staff group, then the Court Admins group. It
never uses `has_perm`, which answers False for a disabled account and would
drop a disabled FLP Staff account into a Court Admin's reach. An account in
two groups takes the higher tier.

`is_staff` on its own ranks as FLP Staff, because it opens Django admin,
where every transcript is readable. Only a superuser can manage it.

## The permissions

| Permission             | Held by                 | Grants                                                       |
| ---------------------- | ----------------------- | ------------------------------------------------------------ |
| `app.manage_site`      | FLP Staff, superusers   | Every admin tab, and the chat token and agent state readouts |
| `app.manage_app_users` | FLP Staff, Court Admins | The Users tab's account actions                              |

Both are declared on `Site.Meta.permissions`, which is why they carry the
`app.` prefix. They gate the application, not the `Site` row.

They're separate from the `add_*` / `change_*` / `delete_*` / `view_*`
permissions Django generates for every model, which gate Django admin at
`/django-admin/`. The transcript admin (`ChatThreadAdmin`) is open to any
`is_staff` account and read-only for everyone.

**Superusers implicitly hold every permission.** `has_perm` returns `True`
for them without any group membership.

Every group is created and stocked by a `post_migrate` receiver, so every
environment converges on the same definition after `migrate`. The receiver
is additive: permissions granted to a group by hand are left alone.

## Setting up accounts

All from the Users tab: **Add account**, then pick the role, or change it
later with the row's Role picker. Each viewer is offered only the roles
below their own.

- **FLP Staff:** a superuser picks FLP Staff. That also grants Django admin
  staff access, so they can read transcripts.
- **Court Admin:** FLP Staff (or a superuser) picks Court Admin.
- **App users:** sign up themselves, or anyone with the Users tab adds
  them. A Court Admin adds app users only, so they see no picker.

No one manages anyone else at their own tier, or their own account, from
the Users tab. Anyone signed in changes their own password at
`/accounts/password/change/` (linked from the Users tab), which needs the
current one. A Court Admin who has forgotten theirs asks FLP Staff; FLP
Staff ask a superuser.

## Users tab behavior

- **Each viewer lists their own tier and below.** A Court Admin sees app
  users and Court Admins; FLP Staff see everyone but superusers.
- **Gated by the `user_admin` feature,** on for dev, QA, and pilots
  (`app/features.py`). Where it's off (plain prod), the account actions
  answer 404 and the Court Admins group grants nothing. The Role picker is
  not gated: plain prod still needs its FLP Staff, so a superuser can make
  them there.
- **No email.** The pilots send none, so whoever adds or resets an account
  sets the password, entered twice, and shares it directly.
- **Disable** sets `is_active=False`: the account can't log in, keeps its
  history, and stays listed so it can be enabled again. **Delete** is
  permanent and removes the account's chats, uploads, and answers.

## Checking a permission

### In views — use a decorator

Guard at the boundary: the view or endpoint is where a permission is
enforced, never a selector or service.

**Page views** use Django's built-in decorator:

```python
from django.contrib.auth.decorators import login_required, permission_required


@login_required
@permission_required("app.manage_site", raise_exception=True)
def some_page(request): ...
```

The admin dashboard is the exception: it checks `admin_tabs(request.user)`,
because FLP Staff get every tab and a Court Admin gets Users alone.

`raise_exception=True` produces a 403 for a signed-in user who lacks the
permission. Keep `login_required` **outermost**, so an anonymous visitor is
sent to log in rather than shown a bare 403.

**JSON endpoints** use the app's decorators from
[`views/utils.py`](../../litigant_portal/app/views/utils.py):
`manage_site_required` (including the role change), and
`app_user_admin_required` for the account actions (404 where the feature
is off, 403 without `manage_app_users`).
They exist because the built-in renders an **HTML** 403, and these
endpoints must answer with `{"error": "Forbidden"}`.

The account actions then check the target with `user_is_manageable`, which
is the tier comparison.

### In templates — use `perms`

```django
{% if perms.app.manage_site %}
  <a href="{% url 'pages:admin_dashboard' %}">{% trans "Admin" %}</a>
{% endif %}
```

Template guards hide UI. They aren't access control on their own: anything
they hide must also be guarded at the view or endpoint that serves it.

### Anywhere else — `has_perm`

```python
if request.user.has_perm("app.manage_site"):
    ...
```

**Don't wrap `has_perm` in a helper.** It hides which permission is being
checked. The one exception is `can_manage_app_users` in `views/utils.py`,
because it also checks the `user_admin` feature.

## Gotcha: permissions are cached per instance

`has_perm` caches its result on the user object the first time it's called.
Changing a user's groups doesn't invalidate that cache, so re-fetch the user
after changing group membership:

```python
user = User.objects.get(pk=user.pk)
user.has_perm("app.manage_app_users")  # correct
```

This matters mostly in tests and management commands. A normal request
loads the user fresh.
