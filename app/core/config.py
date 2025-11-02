import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# IMPORTANT: Use SERVICE_ROLE_KEY for backend operations
# This allows the backend to bypass RLS and perform admin operations
# The anon key won't work because RLS blocks operations without user context
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# CORS configuration
# In production, set ALLOWED_ORIGINS to your Vercel domain(s)
# Example: "https://your-app.vercel.app,https://your-app-production.vercel.app"
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://study-sharper-frontend-2.vercel.app")
ALLOWED_ORIGINS_LIST = [origin.strip() for origin in ALLOWED_ORIGINS.split(",") if origin.strip()]

# Log CORS configuration on startup
import logging
logger = logging.getLogger(__name__)
logger.info(f"CORS Configuration: ALLOWED_ORIGINS={ALLOWED_ORIGINS}")
logger.info(f"CORS Origins List: {ALLOWED_ORIGINS_LIST}")
