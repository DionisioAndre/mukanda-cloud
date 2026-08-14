"""backend/core/exceptions.py"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """Normalise all API errors to consistent JSON shape."""
    response = exception_handler(exc, context)
    if response is None:
        return Response(
            {'error': 'server_error', 'message': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    # Wrap flat string detail in consistent shape
    if isinstance(response.data, dict) and 'detail' in response.data:
        response.data = {
            'error':   getattr(exc, 'default_code', 'error'),
            'message': str(response.data['detail']),
        }
    return response
