from fastapi import Header, HTTPException
from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY
from typing import Optional

def get_supabase_client() -> Client:
    """Get Supabase client instance"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract and validate user ID from Supabase JWT token.
    Expects Authorization header in format: "Bearer <token>"
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "").strip()
    
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    
    try:
        supabase = get_supabase_client()
        # Verify the token and get user
        user_response = supabase.auth.get_user(token)
        
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        return user_response.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
