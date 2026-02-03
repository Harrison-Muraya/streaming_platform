from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, DeviceToken


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'subscription_tier', 'is_active', 'is_staff', 'created_at']
    list_filter = ['subscription_tier', 'is_active', 'is_staff', 'zero_rated', 'created_at']
    search_fields = ['email', 'username', 'isp_customer_id', 'phone_number']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Subscription', {'fields': ('subscription_tier', 'subscription_expires', 'preferred_quality')}),
        ('ISP Integration', {'fields': ('isp_customer_id', 'isp_account_number', 'zero_rated')}),
        ('Statistics', {'fields': ('total_watch_time', 'monthly_data_used')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['total_watch_time', 'monthly_data_used', 'date_joined', 'last_login']


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_name', 'device_type', 'is_active', 'last_seen', 'created_at']
    list_filter = ['device_type', 'is_active', 'created_at']
    search_fields = ['user__email', 'device_name', 'device_id']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'last_seen']
    
    actions = ['deactivate_devices', 'activate_devices']
    
    def deactivate_devices(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} devices deactivated.')
    deactivate_devices.short_description = 'Deactivate selected devices'
    
    def activate_devices(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} devices activated.')
    activate_devices.short_description = 'Activate selected devices'