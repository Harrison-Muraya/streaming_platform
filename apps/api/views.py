"""
REST API Views for streaming platform
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils import timezone
from django.db.models import Sum, Avg, Count
import uuid

from apps.users.models import User, DeviceToken
from apps.streams.models import Stream, ViewSession
from .serializers import (
    UserSerializer, StreamSerializer, ViewSessionSerializer,
    PlaybackURLSerializer, DeviceTokenSerializer
)


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for user management
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Users can only see their own profile
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def register_device(self, request):
        """Register a device for push notifications"""
        serializer = DeviceTokenSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get user viewing statistics"""
        user = request.user
        
        # Calculate stats
        total_sessions = ViewSession.objects.filter(user=user).count()
        total_watch_time = user.total_watch_time
        total_data_used = user.monthly_data_used
        
        # Recent sessions
        recent_sessions = ViewSession.objects.filter(
            user=user
        ).order_by('-started_at')[:10]
        
        return Response({
            'total_sessions': total_sessions,
            'total_watch_time': total_watch_time,
            'total_watch_hours': round(total_watch_time / 3600, 2),
            'total_data_used': total_data_used,
            'total_data_gb': round(total_data_used / (1024**3), 2),
            'subscription_tier': user.subscription_tier,
            'max_quality': user.max_quality,
            'recent_sessions': ViewSessionSerializer(recent_sessions, many=True).data
        })


class StreamViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for stream information
    """
    queryset = Stream.objects.all()
    serializer_class = StreamSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Stream.objects.all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def get_playback_url(self, request, pk=None):
        """
        Generate signed HLS playback URL for authenticated user
        """
        stream = self.get_object()
        user = request.user
        
        # Check if stream is online
        if stream.status != Stream.Status.ONLINE:
            return Response(
                {'error': 'Stream is not currently online'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get requested quality
        quality = request.data.get('quality', 'auto')
        
        # Validate quality access based on subscription
        if quality != 'auto' and not user.can_watch_quality(quality):
            return Response(
                {
                    'error': f'Your subscription does not allow {quality} quality',
                    'max_quality': user.max_quality
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate signed URL
        signed_url = stream.generate_signed_url(
            user=user,
            quality=quality,
            expires_in=3600  # 1 hour
        )
        
        # Create view session
        session_id = str(uuid.uuid4())
        ViewSession.objects.create(
            user=user,
            stream=stream,
            session_id=session_id,
            device_type=request.data.get('device_type', 'unknown'),
            quality=quality,
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Update viewer count
        stream.update_viewer_count(1)
        
        return Response({
            'stream_url': signed_url,
            'session_id': session_id,
            'quality': quality,
            'available_qualities': stream.available_qualities,
            'expires_in': 3600
        })
    
    @action(detail=False, methods=['get'])
    def live(self, request):
        """Get all currently live streams"""
        live_streams = Stream.objects.filter(status=Stream.Status.ONLINE)
        serializer = self.get_serializer(live_streams, many=True)
        return Response(serializer.data)
    
    def get_client_ip(self, request):
        """Extract client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ViewSessionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing view sessions
    """
    queryset = ViewSession.objects.all()
    serializer_class = ViewSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Users can only see their own sessions
        if self.request.user.is_staff:
            return ViewSession.objects.all()
        return ViewSession.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def heartbeat(self, request, pk=None):
        """
        Update session heartbeat and stats
        """
        session = self.get_object()
        
        # Update heartbeat
        session.last_heartbeat = timezone.now()
        
        # Update stats if provided
        if 'buffer_count' in request.data:
            session.buffer_count = request.data['buffer_count']
        if 'quality_switches' in request.data:
            session.quality_switches = request.data['quality_switches']
        if 'data_consumed' in request.data:
            session.data_consumed = request.data['data_consumed']
        if 'average_bitrate' in request.data:
            session.average_bitrate = request.data['average_bitrate']
        
        session.save()
        
        return Response({'status': 'ok'})
    
    @action(detail=True, methods=['post'])
    def end(self, request, pk=None):
        """End a viewing session"""
        session = self.get_object()
        session.end_session()
        
        return Response({
            'status': 'ended',
            'watch_duration': session.watch_duration,
            'data_consumed': session.data_consumed
        })


class WebhookViewSet(viewsets.ViewSet):
    """
    Webhooks for stream events from Nginx RTMP
    """
    permission_classes = [permissions.AllowAny]  # Secured by IP whitelist
    
    @action(detail=False, methods=['post'])
    def stream_start(self, request):
        """Called when a stream starts"""
        stream_key = request.data.get('name')
        
        try:
            stream = Stream.objects.get(stream_key=stream_key)
            stream.status = Stream.Status.ONLINE
            stream.started_at = timezone.now()
            stream.current_viewers = 0
            stream.save()
            
            # Send notification to subscribers (implement as needed)
            # send_stream_notification(stream)
            
            return Response({'status': 'ok'})
        except Stream.DoesNotExist:
            return Response(
                {'error': 'Stream not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def stream_stop(self, request):
        """Called when a stream stops"""
        stream_key = request.data.get('name')
        
        try:
            stream = Stream.objects.get(stream_key=stream_key)
            stream.status = Stream.Status.OFFLINE
            stream.ended_at = timezone.now()
            stream.current_viewers = 0
            stream.save()
            
            # End all active sessions
            active_sessions = ViewSession.objects.filter(
                stream=stream,
                ended_at__isnull=True
            )
            for session in active_sessions:
                session.end_session()
            
            return Response({'status': 'ok'})
        except Stream.DoesNotExist:
            return Response(
                {'error': 'Stream not found'},
                status=status.HTTP_404_NOT_FOUND
            )