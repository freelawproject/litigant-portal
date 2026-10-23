ADMINS_GROUP = "Admins"
DEVELOPERS_GROUP = "Developers"
# Manages the app users on its own instance from the admin Users tab
# (#1043). The same role on QA (an FLP test account) and on a court's pilot
# (the court's own account); the instance decides whose accounts it covers.
USER_ADMINS_GROUP = "User admins"

# Accounts in these groups are staff. The user admin role never reaches
# them, so only the people who run the portal can change each other.
STAFF_GROUPS = (ADMINS_GROUP, DEVELOPERS_GROUP)

GROUP_PERMISSIONS = {
    ADMINS_GROUP: ["manage_site", "manage_app_users"],
    DEVELOPERS_GROUP: [
        "manage_site",
        "manage_developers",
        "manage_app_users",
    ],
    USER_ADMINS_GROUP: ["manage_app_users"],
}
