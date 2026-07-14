from django.db.models import QuerySet

from litigant_portal.app.models import UserIdentity, UserUpload


def user_upload_list(*, identity: UserIdentity) -> QuerySet[UserUpload]:
    """An identity's uploads, newest first."""
    return UserUpload.objects.filter(identity=identity).order_by("-created_at")
