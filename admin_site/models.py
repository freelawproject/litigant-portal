from django.db import models


class ConfigKey(models.Model):
    key = models.CharField(max_length=255, unique=True)
    data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.key
