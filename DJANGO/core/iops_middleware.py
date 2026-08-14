"""
IOPS Management Middleware for Azure Files
Provides rate limiting and throttling for storage operations
"""
import time
import logging
from collections import defaultdict
from django.core.cache import cache
from django.conf import settings
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class IOPSThrottleMiddleware:
    """
    Middleware to throttle IOPS (Input/Output Operations Per Second) 
    for Azure Files storage operations.
    
    Uses Django cache for distributed tracking across multiple workers.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Configuration
        self.iops_limit = getattr(settings, 'AZURE_STORAGE_IOPS_LIMIT', 1000)
        self.window_seconds = getattr(settings, 'AZURE_STORAGE_IOPS_WINDOW', 1.0)
        self.burst_limit = getattr(settings, 'AZURE_STORAGE_BURST_LIMIT', 100)
        self.cache_prefix = 'azure_iops:'
        
        # Track per-user and per-company limits
        self.per_user_limit = getattr(settings, 'AZURE_STORAGE_USER_IOPS_LIMIT', 100)
        self.per_company_limit = getattr(settings, 'AZURE_STORAGE_COMPANY_IOPS_LIMIT', 500)
    
    def __call__(self, request):
        # Skip throttling for non-file operations
        if not self._is_file_operation(request):
            return self.get_response(request)
        
        # Get identifiers for rate limiting
        user_id = getattr(request.user, 'id', None)
        company_id = getattr(request.user, 'company_id', None)
        ip_address = self._get_client_ip(request)
        
        # Check global IOPS limit
        if not self._check_rate_limit('global', self.iops_limit):
            logger.warning(f"Global IOPS limit exceeded: {self.iops_limit}")
            return self._rate_limit_response("Global storage rate limit exceeded")
        
        # Check per-user limit
        if user_id and not self._check_rate_limit(f'user:{user_id}', self.per_user_limit):
            logger.warning(f"User {user_id} IOPS limit exceeded: {self.per_user_limit}")
            return self._rate_limit_response("User storage rate limit exceeded")
        
        # Check per-company limit
        if company_id and not self._check_rate_limit(f'company:{company_id}', self.per_company_limit):
            logger.warning(f"Company {company_id} IOPS limit exceeded: {self.per_company_limit}")
            return self._rate_limit_response("Company storage rate limit exceeded")
        
        # Check per-IP limit (additional protection)
        if not self._check_rate_limit(f'ip:{ip_address}', self.burst_limit):
            logger.warning(f"IP {ip_address} burst limit exceeded: {self.burst_limit}")
            return self._rate_limit_response("IP rate limit exceeded")
        
        # Process request
        response = self.get_response(request)
        
        # Add rate limit headers
        self._add_rate_limit_headers(response, user_id, company_id)
        
        return response
    
    def _is_file_operation(self, request):
        """Check if request is a file storage operation."""
        file_paths = ['/api/files/', '/api/upload/', '/api/download/']
        return any(request.path.startswith(path) for path in file_paths)
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _check_rate_limit(self, key, limit):
        """
        Check if rate limit is exceeded using sliding window counter.
        
        Args:
            key: Identifier for the rate limit (e.g., 'global', 'user:123')
            limit: Maximum operations allowed in the time window
            
        Returns:
            bool: True if under limit, False if limit exceeded
        """
        cache_key = f'{self.cache_prefix}{key}'
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        # Get current counter data
        counter_data = cache.get(cache_key, {'count': 0, 'window_start': current_time})
        
        # Reset if window has expired
        if counter_data['window_start'] < window_start:
            counter_data = {'count': 0, 'window_start': current_time}
        
        # Check if limit exceeded
        if counter_data['count'] >= limit:
            return False
        
        # Increment counter
        counter_data['count'] += 1
        cache.set(cache_key, counter_data, timeout=int(self.window_seconds * 2))
        
        return True
    
    def _add_rate_limit_headers(self, response, user_id=None, company_id=None):
        """Add rate limit information to response headers."""
        remaining = self._get_remaining_requests('global', self.iops_limit)
        response['X-RateLimit-Limit'] = str(self.iops_limit)
        response['X-RateLimit-Remaining'] = str(remaining)
        response['X-RateLimit-Reset'] = str(int(time.time() + self.window_seconds))
        
        if user_id:
            user_remaining = self._get_remaining_requests(f'user:{user_id}', self.per_user_limit)
            response['X-RateLimit-User-Limit'] = str(self.per_user_limit)
            response['X-RateLimit-User-Remaining'] = str(user_remaining)
        
        if company_id:
            company_remaining = self._get_remaining_requests(f'company:{company_id}', self.per_company_limit)
            response['X-RateLimit-Company-Limit'] = str(self.per_company_limit)
            response['X-RateLimit-Company-Remaining'] = str(company_remaining)
    
    def _get_remaining_requests(self, key, limit):
        """Get remaining requests for a rate limit key."""
        cache_key = f'{self.cache_prefix}{key}'
        counter_data = cache.get(cache_key, {'count': 0, 'window_start': time.time()})
        return max(0, limit - counter_data['count'])
    
    def _rate_limit_response(self, message):
        """Return HTTP response when rate limit is exceeded."""
        return HttpResponse(
            {'error': message, 'retry_after': int(self.window_seconds)},
            status=429,
            content_type='application/json'
        )


class IOPSCounter:
    """
    Utility class to track IOPS operations for monitoring and analytics.
    Can be used in views to track specific operations.
    """
    
    @staticmethod
    def track_operation(operation_type, user_id=None, company_id=None, file_size=None):
        """
        Track a storage operation for analytics.
        
        Args:
            operation_type: Type of operation (upload, download, delete, etc.)
            user_id: User performing the operation
            company_id: Company the operation belongs to
            file_size: Size of file in bytes (optional)
        """
        timestamp = time.time()
        cache_key = f'iops_analytics:{operation_type}'
        
        # Get current stats
        stats = cache.get(cache_key, {
            'total_operations': 0,
            'total_bytes': 0,
            'operations_per_minute': []
        })
        
        # Update stats
        stats['total_operations'] += 1
        if file_size:
            stats['total_bytes'] += file_size
        
        # Track operations per minute (sliding window of 60 minutes)
        stats['operations_per_minute'].append(timestamp)
        # Remove entries older than 60 minutes
        stats['operations_per_minute'] = [
            t for t in stats['operations_per_minute'] 
            if t > timestamp - 3600
        ]
        
        # Store with 1 hour expiry
        cache.set(cache_key, stats, timeout=3600)
        
        logger.info(
            f"IOPS Operation: {operation_type}, User: {user_id}, "
            f"Company: {company_id}, Size: {file_size}"
        )
    
    @staticmethod
    def get_stats(operation_type):
        """Get statistics for a specific operation type."""
        cache_key = f'iops_analytics:{operation_type}'
        return cache.get(cache_key, {
            'total_operations': 0,
            'total_bytes': 0,
            'operations_per_minute': []
        })
