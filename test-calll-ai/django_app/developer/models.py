import secrets
from django.db import models
from django.contrib.auth.models import User

class UserApiKey(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    key = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=100, default='Default App Key')
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'developer_userapikey'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.key[:12]}...)"

    @classmethod
    def generate_for_user(cls, user, name='Default App Key'):
        key_str = f"sk_live_usr_{secrets.token_hex(20)}"
        return cls.objects.create(user=user, key=key_str, name=name)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "key": self.key,
            "masked_key": f"{self.key[:12]}...{self.key[-4:]}",
            "is_active": self.is_active,
            "last_used_at": self.last_used_at.strftime("%Y-%m-%d %H:%M:%S") if self.last_used_at else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class UserWebhookEndpoint(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='webhook_endpoint')
    url = models.URLField(max_length=500, blank=True, default='')
    secret = models.CharField(max_length=64, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'developer_userwebhookendpoint'

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = secrets.token_hex(24)
        super().save(*args, **kwargs)

    def to_dict(self):
        return {
            "url": self.url,
            "has_secret": bool(self.secret),
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

