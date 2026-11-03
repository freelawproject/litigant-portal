from enum import IntEnum

# FLP's own people: every admin tab, and every account below them.
FLP_STAFF_GROUP = "FLP Staff"
# A court's own account: the app users on its instance, from the Users tab.
COURT_ADMINS_GROUP = "Court Admins"

GROUP_PERMISSIONS = {
    FLP_STAFF_GROUP: ["manage_site", "manage_app_users"],
    COURT_ADMINS_GROUP: ["manage_app_users"],
}


class Tier(IntEnum):
    """Who may manage whom (#1135). Each tier manages the tiers below it,
    never its own tier, itself, or anything above. Every tier is also an
    app user."""

    APP_USER = 0
    COURT_ADMIN = 1
    FLP_STAFF = 2
    SUPERUSER = 3
