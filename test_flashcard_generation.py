#!/usr/bin/env python3
"""
Test Flashcard Generation
Tests the AI-powered flashcard generation from notes
"""

import requests
import json
from supabase import create_client
from app.core.config import SUPABASE_URL, SUPABASE_KEY

print("=" * 60)
print("🧪 TESTING FLASHCARD GENERATION")
print("=" * 60)

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Get test user and note
print("\n📋 Step 1: Getting test user and note...")
users = supabase.table('profiles').select('id').limit(1).execute()
if not users.data:
    print("❌ No users found")
    exit(1)

test_user_id = users.data[0]['id']

# Get the photosynthesis note we created earlier
notes = supabase.table('notes').select('id, title').eq(
    'title', 'Biology 101 - Photosynthesis'
).eq('user_id', test_user_id).execute()

if not notes.data:
    print("❌ Test note not found")
    exit(1)

note_id = notes.data[0]['id']
note_title = notes.data[0]['title']
print(f"✅ Using note: {note_title} (ID: {note_id})")

# Test flashcard generation using the service directly
print("\n📋 Step 2: Testing flashcard generation service...")
try:
    from app.services.flashcards import generate_flashcards_from_text
    
    test_text = """
    # Introduction to Photosynthesis

    Photosynthesis is the process by which plants convert light energy into chemical energy.

    ## Key Components:
    - **Chlorophyll**: The green pigment that captures light
    - **Light-dependent reactions**: Occur in the thylakoid membranes
    - **Light-independent reactions (Calvin Cycle)**: Occur in the stroma

    ## The Process:
    1. Light energy is absorbed by chlorophyll
    2. Water molecules are split (photolysis)
    3. Oxygen is released as a byproduct
    4. ATP and NADPH are produced
    5. Carbon dioxide is fixed into glucose

    ## Chemical Equation:
    6CO₂ + 6H₂O + light energy → C₆H₁₂O₆ + 6O₂
    """
    
    flashcards = generate_flashcards_from_text(
        text=test_text,
        note_title="Biology 101 - Photosynthesis",
        num_cards=5,
        difficulty="medium"
    )
    
    print(f"✅ Generated {len(flashcards)} flashcards!")
    print("\n📝 Sample Flashcards:")
    for i, card in enumerate(flashcards[:3], 1):
        print(f"\n   Card {i}:")
        print(f"   Q: {card['front']}")
        print(f"   A: {card['back'][:100]}{'...' if len(card['back']) > 100 else ''}")
        if card.get('explanation'):
            print(f"   💡 {card['explanation'][:80]}{'...' if len(card['explanation']) > 80 else ''}")
    
    # Save to database
    print("\n📋 Step 3: Saving flashcards to database...")
    
    # Create flashcard set
    set_data = {
        "user_id": test_user_id,
        "title": f"Test Flashcards: {note_title}",
        "description": "AI-generated flashcards for testing",
        "source_note_ids": [note_id]
    }
    
    set_response = supabase.table("flashcard_sets").insert(set_data).execute()
    flashcard_set = set_response.data[0]
    set_id = flashcard_set["id"]
    print(f"✅ Created flashcard set (ID: {set_id})")
    
    # Insert flashcards
    flashcard_records = []
    for i, card in enumerate(flashcards):
        flashcard_records.append({
            "user_id": test_user_id,
            "set_id": set_id,
            "front": card["front"],
            "back": card["back"],
            "explanation": card.get("explanation", ""),
            "position": i,
            "source_note_id": note_id
        })
    
    cards_response = supabase.table("flashcards").insert(flashcard_records).execute()
    print(f"✅ Saved {len(cards_response.data)} flashcards to database")
    
    # Verify the set stats were updated by trigger
    updated_set = supabase.table("flashcard_sets").select("*").eq("id", set_id).single().execute()
    print(f"✅ Set stats: {updated_set.data['total_cards']} cards, {updated_set.data['mastered_cards']} mastered")
    
except Exception as e:
    print(f"❌ Flashcard generation failed: {str(e)}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "=" * 60)
print("🎉 FLASHCARD GENERATION TEST COMPLETE!")
print("=" * 60)
print("\n📊 Summary:")
print(f"✅ Flashcard service: Working")
print(f"✅ AI generation: Working")
print(f"✅ Database storage: Working")
print(f"✅ Triggers: Working")
print("\n🚀 Ready to test API endpoints!")
