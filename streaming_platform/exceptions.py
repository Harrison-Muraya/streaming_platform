from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses
    
    This handler wraps the default DRF exception handler to provide
    a standardized error format across the API.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Customize the response data
        custom_response_data = {
            'error': True,
            'status_code': response.status_code,
            'message': str(exc),
            'details': response.data
        }
        response.data = custom_response_data
    else:
        # Handle unexpected errors
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        custom_response_data = {
            'error': True,
            'status_code': 500,
            'message': 'An unexpected error occurred',
            'details': str(exc) if hasattr(exc, '__str__') else 'Internal server error'
        }
        response = Response(custom_response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response
