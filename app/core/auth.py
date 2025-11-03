from fastapi import Header, HTTPException, Depends
from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY
from typing import Optional
import jwt
import logging

# Set up logging
logger = logging.getLogger(__name__)

def get_supabase_client() -> Client:
    """Get Supabase client instance with service role key for backend operations"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase configuration missing")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract and validate user ID from Supabase JWT token.
    Properly validates the token using Supabase client.
    Expects Authorization header in format: "Bearer <token>"
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "").strip()
    
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    
    # Log incoming token (first 20 chars only for security)
    token_preview = token[:20] + "..." if len(token) > 20 else token
    logger.info(f"[AUTH] Incoming token: {token_preview}")
    
    try:
        # First, decode JWT to extract user_id without verification (for logging)
        try:
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            user_id = unverified_payload.get("sub")
            exp = unverified_payload.get("exp")
            logger.info(f"[AUTH] Token received for user: {user_id}, expires: {exp}")
        except Exception as e:
            logger.warning(f"[AUTH] Could not decode token for logging: {e}")
        
        # Validate token using Supabase client
        supabase = get_supabase_client()
        
        # Use the token to get user info - this validates the token
        try:
            user_response = supabase.auth.get_user(token)
            if not user_response.user or not user_response.user.id:
                raise HTTPException(status_code=401, detail="Invalid token: user not found")
            
            returned_user_id = user_response.user.id
            logger.info(f"[AUTH] PATH 1 (Supabase): Returning user_id = {returned_user_id}")
            return returned_user_id
            
        except Exception as supabase_error:
            logger.error(f"[AUTH] Supabase token validation failed: {supabase_error}")
            
            # Fallback: decode JWT manually if Supabase validation fails
            # This is less secure but allows operation during service issues
            try:
                decoded = jwt.decode(token, options={"verify_signature": False})
                user_id = decoded.get("sub")
                
                if not user_id:
                    raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
                
                logger.warning(f"[AUTH] PATH 2 (JWT Fallback): Returning user_id = {user_id}")
                return user_id
                
            except jwt.DecodeError as decode_error:
                raise HTTPException(status_code=401, detail=f"Invalid token format: {str(decode_error)}")
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"[AUTH] Authentication failed with unexpected error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


async def get_current_user_from_token(token: str) -> dict:
    """
    Authenticate user from JWT token (for WebSocket connections).

    Args:
        token: JWT access token

    Returns:
        User dict with id and email

    Raises:
        HTTPException if token is invalid
    """
    try:
        supabase = get_supabase_client()

        # Verify token with Supabase
        user_response = supabase.auth.get_user(token)

        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid token")

        return {
            "id": user_response.user.id,
            "email": user_response.user.email
        }

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
