"""
Serializers for REST API
"""

from rest_framework import serializers
from apps.users.models import User, DeviceToken
from apps.streams.models import Stream, ViewSession


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone_number', 'subscription_tier', 'subscription_expires',
            'isp_customer_id', 'zero_rated', 'max_quality',
            'total_watch_time', 'monthly_data_used',
            'preferred_quality', 'auto_play', 'created_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'total_watch_time',
            'monthly_data_used', 'max_quality'
        ]
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user


class DeviceTokenSerializer(serializers.ModelSerializer):
    """Serializer for DeviceToken model"""
    
    class Meta:
        model = DeviceToken
        fields = [
            'id', 'device_type', 'device_id', 'device_name',
            'fcm_token', 'os_version', 'app_version',
            'is_active', 'last_seen', 'created_at'
        ]
        read_only_fields = ['id', 'last_seen', 'created_at']


class StreamSerializer(serializers.ModelSerializer):
    """Serializer for Stream model"""
    
    uptime = serializers.SerializerMethodField()
    
    class Meta:
        model = Stream
        fields = [
            'id', 'stream_key', 'name', 'description', 'status',
            'available_qualities', 'default_quality', 'current_viewers',
            'total_views', 'peak_viewers', 'thumbnail_url',
            'started_at', 'uptime', 'recording_enabled'
        ]
        read_only_fields = [
            'id', 'current_viewers', 'total_views', 'peak_viewers',
            'started_at', 'uptime'
        ]
    
    def get_uptime(self, obj):
        """Calculate stream uptime in seconds"""
        if obj.status == Stream.Status.ONLINE and obj.started_at:
            from django.utils import timezone
            delta = timezone.now() - obj.started_at
            return int(delta.total_seconds())
        return 0


class ViewSessionSerializer(serializers.ModelSerializer):
    """Serializer for ViewSession model"""
    
    stream_name = serializers.CharField(source='stream.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = ViewSession
        fields = [
            'id', 'session_id', 'user_email', 'stream_name',
            'device_type', 'quality', 'ip_address',
            'started_at', 'last_heartbeat', 'ended_at',
            'watch_duration', 'data_consumed', 'buffer_count',
            'quality_switches', 'average_bitrate'
        ]
        read_only_fields = [
            'id', 'session_id', 'started_at', 'user_email', 'stream_name'
        ]


class PlaybackURLSerializer(serializers.Serializer):
    """Serializer for playback URL request"""
    
    quality = serializers.ChoiceField(
        choices=['auto', '360p', '480p', '720p', '1080p'],
        default='auto'
    )
    device_type = serializers.ChoiceField(
        choices=['mobile', 'tv', 'web'],
        default='mobile'
    )


class SessionHeartbeatSerializer(serializers.Serializer):
    """Serializer for session heartbeat updates"""
    
    buffer_count = serializers.IntegerField(required=False)
    quality_switches = serializers.IntegerField(required=False)
    data_consumed = serializers.IntegerField(required=False)
    average_bitrate = serializers.IntegerField(required=False)