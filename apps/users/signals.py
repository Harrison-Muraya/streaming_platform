"""
User-related signals
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for user creation
    """
    if created:
        # Send welcome email
        # send_welcome_email(instance)
        
        # Log user creation
        print(f"New user created: {instance.email}")
        
        # Create default preferences
        # UserPreference.objects.create(user=instance)
        
        pass