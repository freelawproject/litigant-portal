from django.contrib.auth.models import User
from django.db import models

from .base import BaseModel


class UserIdentity(BaseModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, blank=True, null=True
    )
    session_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        if self.user:
            return f"User {self.user.id} - {self.user.username}"
        return f"Anonymous {self.id}"
