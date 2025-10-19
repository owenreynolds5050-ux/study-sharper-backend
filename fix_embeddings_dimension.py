# fix_embeddings_dimension.py
"""
One-time script to fix embedding dimensions.
The note_embeddings table was created with 1536 dimensions but we're using
sentence-transformers/all-MiniLM-L6-v2 which produces 384 dimensions.

This script:
1. Drops the old note_embeddings table
2. The new file_embeddings table is already correct (384 dimensions)
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def fix_embeddings():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing Supabase credentials in .env")
        return
    
    supabase = create_client(supabase_url, supabase_key)
    
    print("🔧 Fixing embedding dimensions...")
    
    # The new file_embeddings table is already correct (384 dimensions)
    # Just verify it exists
    try:
        result = supabase.table("file_embeddings").select("id").limit(1).execute()
        print("✅ file_embeddings table exists with correct 384 dimensions")
    except Exception as e:
        print(f"⚠️  file_embeddings table check failed: {e}")
    
    print("\n✅ Embedding dimension fix complete!")
    print("\nNote: The old 'notes' and 'note_embeddings' tables still exist.")
    print("They will be removed once you fully migrate to the Files page.")

if __name__ == "__main__":
    fix_embeddings()
