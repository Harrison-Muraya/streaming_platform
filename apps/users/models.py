"""
User models for streaming platform
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Custom user model with subscription and ISP integration
    """
    
    class SubscriptionTier(models.TextChoices):
        FREE = 'FREE', _('Free')
        BASIC = 'BASIC', _('Basic - 480p')
        PREMIUM = 'PREMIUM', _('Premium - 720p')
        ULTRA = 'ULTRA', _('Ultra - 1080p')
    
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(_('phone number'), max_length=20, blank=True)
    
    # Subscription info
    subscription_tier = models.CharField(
        max_length=10,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.FREE
    )
    subscription_expires = models.DateTimeField(null=True, blank=True)
    
    # ISP integration
    isp_customer_id = models.CharField(max_length=100, blank=True, db_index=True)
    isp_account_number = models.CharField(max_length=100, blank=True)
    zero_rated = models.BooleanField(default=False)  # ISP zero-rating
    
    # Usage tracking
    monthly_data_used = models.BigIntegerField(default=0)  # in bytes
    total_watch_time = models.IntegerField(default=0)  # in seconds
    
    # Preferences
    preferred_quality = models.CharField(max_length=10, default='auto')
    auto_play = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')
        indexes = [
            models.Index(fields=['subscription_tier']),
            models.Index(fields=['isp_customer_id']),
        ]
    
    def __str__(self):
        return self.email
    
    @property
    def is_premium(self):
        """Check if user has premium access"""
        from django.utils import timezone
        
        if self.subscription_tier in [self.SubscriptionTier.PREMIUM, self.SubscriptionTier.ULTRA]:
            if self.subscription_expires and self.subscription_expires > timezone.now():
                return True
        return False
    
    @property
    def max_quality(self):
        """Get maximum quality based on subscription"""
        quality_map = {
            self.SubscriptionTier.FREE: '360p',
            self.SubscriptionTier.BASIC: '480p',
            self.SubscriptionTier.PREMIUM: '720p',
            self.SubscriptionTier.ULTRA: '1080p',
        }
        return quality_map.get(self.subscription_tier, '360p')
    
    def can_watch_quality(self, quality):
        """Check if user can watch specific quality"""
        quality_hierarchy = ['360p', '480p', '720p', '1080p']
        max_idx = quality_hierarchy.index(self.max_quality)
        try:
            req_idx = quality_hierarchy.index(quality)
            return req_idx <= max_idx
        except ValueError:
            return False


class DeviceToken(models.Model):
    """
    Store device tokens for push notifications and device management
    """
    
    class DeviceType(models.TextChoices):
        MOBILE = 'MOBILE', _('Mobile')
        TV = 'TV', _('Android TV')
        WEB = 'WEB', _('Web Browser')
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_type = models.CharField(max_length=10, choices=DeviceType.choices)
    device_id = models.CharField(max_length=255, unique=True)
    device_name = models.CharField(max_length=100)
    fcm_token = models.CharField(max_length=255, blank=True)  # Firebase token
    
    os_version = models.CharField(max_length=50, blank=True)
    app_version = models.CharField(max_length=50, blank=True)
    
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'device_tokens'
        verbose_name = _('device token')
        verbose_name_plural = _('device tokens')
        indexes = [
            models.Index(fields=['user', 'device_type']),
            models.Index(fields=['device_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.device_name}"