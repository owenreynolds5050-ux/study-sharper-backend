"""
Database Configuration
Centralized Supabase client instance
"""

from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY

# Create global Supabase client instance
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
