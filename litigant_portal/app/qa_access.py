"""
Temporary developer access for the QA PoC's pre-created demo account.
"""

from django.conf import settings
from django.contrib.auth.backends import BaseBackend


class QADeveloperBackend(BaseBackend):
    """
    Grant runtime permissions without storing elevated access in QA's database.
    """

    def get_user_permissions(self, user_obj, obj=None):
        """
        Keep normal authentication and limit the grant to this one QA account.
        """
        if (
            settings.DEPLOYMENT_ENV == "qa"
            and obj is None
            and user_obj.is_authenticated
            and user_obj.is_active
            and user_obj.email.casefold()
            == "qa-agent-86004-0241280d@example.invalid"
        ):
            return {"app.manage_site", "app.manage_developers"}
        return set()
