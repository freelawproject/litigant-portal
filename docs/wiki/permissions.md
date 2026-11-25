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

"Manages" means add an account, send it a password link (or, on an
instance without email, set its password), disable or re-enable it, and
delete it, and give it a role below one's own: FLP Staff make Court
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
current one. On an instance with email, anyone who has forgotten theirs
uses "Forgot your password?" on the login page. Without email, a Court
Admin asks FLP Staff, and FLP Staff ask a superuser.

## Two-factor sign-in

Staff accounts sign in with a password and then a code from an
authenticator app (TOTP), or a recovery code. This is allauth's `mfa` app.
The pages live under `/accounts/2fa/`.

- **Who must have it:** a superuser, any `is_staff` account, and anyone
  holding `app.manage_site` or `app.manage_app_users`
  (`needs_two_factor` in `views/utils.py`). So every tier above
  app user.
- **The rule:** with `STAFF_TWO_FACTOR_REQUIRED` on,
  `StaffTwoFactorMiddleware` sends a staff account with no two-factor to
  the setup page from every page, and answers a JSON 403 on `/api/`. Only
  setup, confirm access, sign out, health and static files stay open. The
  rule is on by default when `DEBUG` is off and off by default in `DEBUG`;
  `true` or `false` wins in both. With the rule off outside `DEBUG`, the
  `two_factor.W001` system check warns at startup.
- **Unconfirmed addresses:** setup does not wait for every email address
  to be confirmed (`MFA_ALLOW_UNVERIFIED_EMAIL`). Sign-in already needs a
  confirmed address where real mail goes out, and an unconfirmed second
  address would lock a staff account out of setup.
- **Confirm access:** setup, turning it off, and recovery codes ask for
  the password again first (or a code, once two-factor is on). That lasts
  5 minutes. A new sign-in does not count.
- **App users:** a signed-in account that is not staff gets a 404 on
  `/accounts/2fa/`, whether the rule is on or off. Making an account an
  app user (`user_role_set`) removes its two-factor. An account that
  lost staff access another way (Django admin, a shell) keeps its
  two-factor, and can open the pages until it turns it off.
- **Django admin:** `/django-admin/login/` goes through the normal sign-in
  page (`secure_admin_login`), so the code step covers Django admin too.
  A signed-in account without `is_staff` is sent to the home page.
- **Reset:** on the Users tab, **Reset two-factor** removes an account's
  authenticator and recovery codes (`user_two_factor_reset`). FLP Staff
  reset Court Admins, and a superuser resets FLP Staff. Each reset is
  logged with the two account ids.
- **A superuser who is locked out** has nobody above them. Infra resets
  them from a shell in the app container:

  ```sh
  python litigant_portal/manage.py shell -c "
  from django.contrib.auth.models import User
  from litigant_portal.app.services.user import user_two_factor_reset
  user_two_factor_reset(user=User.objects.get(email='admin@yourdomain.com'))
  "
  ```

- **Secrets are encrypted** in the database with a key made from
  `TWO_FACTOR_KEY` (`MFAAdapter` in `adapters.py`). Set it once per
  instance. Without it the key is made from `SECRET_KEY`, and a change to
  `SECRET_KEY` then breaks two-factor; with `DEBUG` off the instance
  warns at startup (`two_factor.W002`). To change `TWO_FACTOR_KEY`, put
  the old key in `TWO_FACTOR_KEY_FALLBACKS` (comma separated). To start
  using `TWO_FACTOR_KEY` on an instance that ran without it, put the
  `SECRET_KEY` value in `TWO_FACTOR_KEY_FALLBACKS`.
- **After a lost key,** no code or recovery code matches, and the
  recovery codes page shows codes that do not work. Reset two-factor for
  every staff account (Users tab, or the shell command above).

## Users tab behavior

- **Each viewer lists their own tier and below.** A Court Admin sees app
  users and Court Admins; FLP Staff see everyone but superusers.
- **Gated by the `user_admin` feature,** on for dev, QA, and pilots
  (`app/features.py`). Where it's off (plain prod), the account actions
  answer 404 and the Court Admins group grants nothing. The Role picker
  and **Reset two-factor** are not gated: plain prod still needs its FLP
  Staff, so a superuser can make them there and help one who lost their
  phone.
- **Email on: invites.** With `EMAIL_HOST` set (`settings.EMAIL_ENABLED`),
  adding an account creates it with no usable password and emails an
  invite to set one. The row shows **Invited** until the tester does.
  **Send password link** emails the invite again, or a reset link once the
  account has a password; it refuses a disabled account. Both are
  allauth's reset email (`ResetPasswordForm`), with the invite text chosen
  by `AccountAdapter.send_password_reset_mail`. Links last 7 days
  (`PASSWORD_RESET_TIMEOUT`). The admin never sees a password.
- **Email on: confirmed addresses.** With `EMAIL_HOST` set and `DEBUG`
  off, `ACCOUNT_EMAIL_VERIFICATION` is `mandatory`: a person who signs up
  gets a confirm link and can't sign in until they use it. A sign-in
  before that sends the link again, at most once every 3 minutes. The
  link lasts 7 days (`ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`). Accounts
  added on the Users tab or by `bootstrap_superuser` are recorded as
  confirmed and skip this. An account with no confirmed address (an older
  signup, `createsuperuser`, Django admin) gets the link at its next
  sign-in.
- **Email off: passwords.** Without `EMAIL_HOST`, whoever adds or resets an
  account sets the password, entered twice, and shares it directly. This
  flow goes away once every instance can send email.
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
`manage_site_required` (including the role change and the two-factor
reset), and
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
