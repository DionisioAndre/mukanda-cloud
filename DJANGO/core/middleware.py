"""
backend/core/middleware.py
Injects client IP and User-Agent into every request for audit logging.
"""

class AuditContextMiddleware:
    """Attaches IP + UA to request object. Views read from request.client_*"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.client_ip = self._get_ip(request)
        request.client_ua = request.META.get('HTTP_USER_AGENT', '')[:500]
        return self.get_response(request)

    @staticmethod
    def _get_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')
