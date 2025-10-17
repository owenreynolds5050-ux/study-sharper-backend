"""
Standardized error responses for the API
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel


class ErrorCode:
    """Standard error codes"""
    # Authentication errors (1xxx)
    UNAUTHORIZED = "AUTH_001"
    INVALID_TOKEN = "AUTH_002"
    TOKEN_EXPIRED = "AUTH_003"
    
    # Resource errors (2xxx)
    NOT_FOUND = "RESOURCE_001"
    ALREADY_EXISTS = "RESOURCE_002"
    FORBIDDEN = "RESOURCE_003"
    
    # Validation errors (3xxx)
    INVALID_INPUT = "VALIDATION_001"
    MISSING_FIELD = "VALIDATION_002"
    INVALID_FORMAT = "VALIDATION_003"
    
    # Server errors (5xxx)
    INTERNAL_ERROR = "SERVER_001"
    DATABASE_ERROR = "SERVER_002"
    EXTERNAL_SERVICE_ERROR = "SERVER_003"


class ErrorResponse(BaseModel):
    """Standardized error response model"""
    error: str  # Human-readable error message
    code: str  # Machine-readable error code
    details: Optional[Dict[str, Any]] = None  # Additional context


def create_error_response(
    message: str,
    code: str = ErrorCode.INTERNAL_ERROR,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response
    
    Args:
        message: Human-readable error message
        code: Machine-readable error code
        details: Optional additional context
        
    Returns:
        Dictionary with error, code, and details
    """
    response = {
        "error": message,
        "code": code,
        "details": details or {}
    }
    return response
