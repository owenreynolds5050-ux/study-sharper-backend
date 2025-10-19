# app/services/quota_service.py
from fastapi import HTTPException
from app.core.database import supabase
from datetime import date

# Quota limits
FREE_USER_LIMITS = {
    "daily_uploads": 50,  # 50 files per day
    "storage_bytes": 1024 * 1024 * 1024,  # 1GB total storage
    "max_file_size": 10 * 1024 * 1024,  # 10MB per file
    "max_audio_size": 25 * 1024 * 1024,  # 25MB per audio file
}

PREMIUM_USER_LIMITS = {
    "daily_uploads": 200,  # 200 files per day
    "storage_bytes": 10 * 1024 * 1024 * 1024,  # 10GB total storage
    "max_file_size": 50 * 1024 * 1024,  # 50MB per file
    "max_audio_size": 100 * 1024 * 1024,  # 100MB per audio file
}

async def get_or_create_quota(user_id: str) -> dict:
    """Get user quota record, create if doesn't exist"""
    # Try to get existing quota
    result = supabase.table("user_quotas").select("*").eq("user_id", user_id).execute()
    
    if result.data:
        quota = result.data[0]
        
        # Reset daily counter if it's a new day
        if quota["last_upload_reset_date"] != str(date.today()):
            quota = supabase.table("user_quotas").update({
                "files_uploaded_today": 0,
                "last_upload_reset_date": str(date.today())
            }).eq("user_id", user_id).execute().data[0]
        
        return quota
    
    # Create new quota record
    new_quota = supabase.table("user_quotas").insert({
        "user_id": user_id,
        "is_premium": False,
        "files_uploaded_today": 0,
        "last_upload_reset_date": str(date.today()),
        "total_storage_used": 0,
        "total_files": 0
    }).execute()
    
    return new_quota.data[0]

async def check_upload_quota(user_id: str, file_size: int = 0) -> dict:
    """
    Check if user can upload a file.
    Raises HTTPException if quota exceeded.
    Returns quota info if allowed.
    """
    quota = await get_or_create_quota(user_id)
    limits = PREMIUM_USER_LIMITS if quota["is_premium"] else FREE_USER_LIMITS
    
    # Check daily upload limit
    if quota["files_uploaded_today"] >= limits["daily_uploads"]:
        raise HTTPException(
            status_code=429,
            detail=f"Daily upload limit reached ({limits['daily_uploads']} files). Resets tomorrow."
        )
    
    # Check storage limit
    storage_limit = quota.get("storage_limit") or limits["storage_bytes"]
    if quota["total_storage_used"] + file_size > storage_limit:
        used_mb = quota["total_storage_used"] / (1024 * 1024)
        limit_mb = storage_limit / (1024 * 1024)
        raise HTTPException(
            status_code=507,
            detail=f"Storage limit exceeded. Used: {used_mb:.1f}MB / {limit_mb:.1f}MB"
        )
    
    return {
        "allowed": True,
        "is_premium": quota["is_premium"],
        "daily_uploads_remaining": limits["daily_uploads"] - quota["files_uploaded_today"],
        "storage_remaining": storage_limit - quota["total_storage_used"]
    }

async def increment_upload_count(user_id: str, file_size: int = 0):
    """Increment user's upload count and storage used"""
    quota = await get_or_create_quota(user_id)
    
    supabase.table("user_quotas").update({
        "files_uploaded_today": quota["files_uploaded_today"] + 1,
        "total_storage_used": quota["total_storage_used"] + file_size,
        "total_files": quota["total_files"] + 1
    }).eq("user_id", user_id).execute()

async def decrement_file_count(user_id: str, file_size: int = 0):
    """Decrement when file is deleted"""
    quota = await get_or_create_quota(user_id)
    
    new_storage = max(0, quota["total_storage_used"] - file_size)
    new_count = max(0, quota["total_files"] - 1)
    
    supabase.table("user_quotas").update({
        "total_storage_used": new_storage,
        "total_files": new_count
    }).eq("user_id", user_id).execute()

async def get_quota_info(user_id: str) -> dict:
    """Get user's current quota status"""
    quota = await get_or_create_quota(user_id)
    limits = PREMIUM_USER_LIMITS if quota["is_premium"] else FREE_USER_LIMITS
    storage_limit = quota.get("storage_limit") or limits["storage_bytes"]
    
    return {
        "is_premium": quota["is_premium"],
        "daily_uploads": {
            "used": quota["files_uploaded_today"],
            "limit": limits["daily_uploads"],
            "remaining": limits["daily_uploads"] - quota["files_uploaded_today"]
        },
        "storage": {
            "used_bytes": quota["total_storage_used"],
            "limit_bytes": storage_limit,
            "remaining_bytes": storage_limit - quota["total_storage_used"],
            "used_mb": round(quota["total_storage_used"] / (1024 * 1024), 2),
            "limit_mb": round(storage_limit / (1024 * 1024), 2)
        },
        "total_files": quota["total_files"],
        "max_file_size_bytes": limits["max_file_size"],
        "max_audio_size_bytes": limits["max_audio_size"]
    }

def get_file_size_limit(is_premium: bool, file_type: str) -> int:
    """Get max file size for user and file type"""
    limits = PREMIUM_USER_LIMITS if is_premium else FREE_USER_LIMITS
    
    if file_type == "audio":
        return limits["max_audio_size"]
    return limits["max_file_size"]
