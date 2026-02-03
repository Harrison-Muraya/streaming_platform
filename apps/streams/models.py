"""
Stream models for managing live streams
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import hashlib
import time


class Stream(models.Model):
    """
    Live stream configuration
    """
    
    class Status(models.TextChoices):
        OFFLINE = 'OFFLINE', _('Offline')
        ONLINE = 'ONLINE', _('Online')
        STARTING = 'STARTING', _('Starting')
        ERROR = 'ERROR', _('Error')
    
    stream_key = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OFFLINE
    )
    
    # Stream URLs
    rtmp_url = models.CharField(max_length=500)
    hls_master_url = models.CharField(max_length=500, blank=True)
    
    # Quality settings
    available_qualities = models.JSONField(default=list)  # ['360p', '480p', '720p', '1080p']
    default_quality = models.CharField(max_length=10, default='auto')
    
    # Viewer stats
    current_viewers = models.IntegerField(default=0)
    total_views = models.BigIntegerField(default=0)
    peak_viewers = models.IntegerField(default=0)
    
    # Recording
    recording_enabled = models.BooleanField(default=False)
    recording_path = models.CharField(max_length=500, blank=True)
    
    # Metadata
    thumbnail_url = models.URLField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'streams'
        verbose_name = _('stream')
        verbose_name_plural = _('streams')
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['stream_key']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.status})"
    
    def generate_signed_url(self, user, quality='auto', expires_in=3600):
        """
        Generate signed HLS URL for secure playback
        """
        from django.utils import timezone
        
        expires = int((timezone.now().timestamp() + expires_in))
        
        # Construct base URL
        if quality == 'auto':
            hls_path = f"{self.stream_key}/master.m3u8"
        else:
            hls_path = f"{self.stream_key}/{quality}/playlist.m3u8"
        
        base_url = settings.STREAMING_CONFIG['HLS_BASE_URL']
        secret = settings.STREAMING_CONFIG['HLS_SECRET_KEY']
        
        # Generate signature
        message = f"{expires}{hls_path}{secret}"
        signature = hashlib.md5(message.encode()).hexdigest()
        
        # Build signed URL
        signed_url = f"{base_url}/{hls_path}?md5={signature}&expires={expires}"
        
        return signed_url
    
    def update_viewer_count(self, delta):
        """Update current viewer count"""
        self.current_viewers = max(0, self.current_viewers + delta)
        if self.current_viewers > self.peak_viewers:
            self.peak_viewers = self.current_viewers
        self.save(update_fields=['current_viewers', 'peak_viewers'])


class ViewSession(models.Model):
    """
    Track individual viewing sessions for analytics and billing
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='view_sessions'
    )
    stream = models.ForeignKey(Stream, on_delete=models.CASCADE, related_name='sessions')
    
    # Session details
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    device_type = models.CharField(max_length=20)  # mobile, tv, web
    quality = models.CharField(max_length=10)  # 360p, 480p, 720p, 1080p
    
    # Network info
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    isp_detected = models.CharField(max_length=100, blank=True)
    
    # Duration tracking
    started_at = models.DateTimeField(auto_now_add=True)
    last_heartbeat = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    watch_duration = models.IntegerField(default=0)  # seconds
    
    # Data usage
    data_consumed = models.BigIntegerField(default=0)  # bytes
    
    # Quality of Experience
    buffer_count = models.IntegerField(default=0)
    quality_switches = models.IntegerField(default=0)
    average_bitrate = models.IntegerField(default=0)  # kbps
    
    class Meta:
        db_table = 'view_sessions'
        verbose_name = _('view session')
        verbose_name_plural = _('view sessions')
        indexes = [
            models.Index(fields=['user', 'started_at']),
            models.Index(fields=['stream', 'started_at']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.stream.name}"
    
    def end_session(self):
        """End the viewing session"""
        from django.utils import timezone
        
        if not self.ended_at:
            self.ended_at = timezone.now()
            duration = (self.ended_at - self.started_at).total_seconds()
            self.watch_duration = int(duration)
            self.save()
            
            # Update stream viewer count
            self.stream.update_viewer_count(-1)
            
            # Update user stats
            self.user.total_watch_time += self.watch_duration
            self.user.monthly_data_used += self.data_consumed
            self.user.save(update_fields=['total_watch_time', 'monthly_data_used'])


class StreamAlert(models.Model):
    """
    Alerts and notifications for stream events
    """
    
    class AlertType(models.TextChoices):
        STREAM_STARTED = 'STREAM_STARTED', _('Stream Started')
        STREAM_ENDED = 'STREAM_ENDED', _('Stream Ended')
        HIGH_VIEWERS = 'HIGH_VIEWERS', _('High Viewer Count')
        TRANSCODER_ERROR = 'TRANSCODER_ERROR', _('Transcoder Error')
        BANDWIDTH_WARNING = 'BANDWIDTH_WARNING', _('Bandwidth Warning')
    
    stream = models.ForeignKey(Stream, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=AlertType.choices)
    message = models.TextField()
    metadata = models.JSONField(default=dict)
    
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stream_alerts'
        verbose_name = _('stream alert')
        verbose_name_plural = _('stream alerts')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.alert_type} - {self.stream.name}"