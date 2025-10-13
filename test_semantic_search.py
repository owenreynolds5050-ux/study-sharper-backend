#!/usr/bin/env python3
"""Quick test for semantic search after fixing duplicate function"""

import json
from supabase import create_client
from app.core.config import SUPABASE_URL, SUPABASE_KEY
from app.services.embeddings import get_embedding_for_text

print("🧪 Testing Semantic Search...")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Get test user
users = supabase.table('profiles').select('id').limit(1).execute()
test_user_id = users.data[0]['id']

# Generate query embedding
search_query = "What is chlorophyll and what does it do?"
print(f"Query: '{search_query}'")

query_result = get_embedding_for_text(search_query)
query_embedding = query_result["embedding"]

# Search
try:
    search_results = supabase.rpc(
        'search_similar_notes',
        {
            'query_embedding': query_embedding,  # Pass as list, not JSON string
            'user_id_param': test_user_id,
            'match_threshold': 0.5,
            'match_count': 5
        }
    ).execute()
    
    if search_results.data:
        print(f"✅ Found {len(search_results.data)} matching note(s):")
        for i, result in enumerate(search_results.data, 1):
            print(f"   {i}. {result['title']} (similarity: {result['similarity']:.3f})")
            print(f"      Preview: {result['content'][:100]}...")
    else:
        print("⚠️  No matching notes found")
        
    print("\n✅ Semantic search is working!")
    
except Exception as e:
    print(f"❌ Semantic search failed: {str(e)}")
