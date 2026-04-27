from django.db import models


class ChatModel(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class Site(models.Model):
    court_name = models.CharField(max_length=255, blank=True)
    chat_model = models.ForeignKey(
        ChatModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Site"

    def __str__(self):
        return self.court_name or "Site"

    @property
    def chat_model_slug(self) -> str | None:
        if self.chat_model_id is None:
            return None
        return self.chat_model.slug

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
